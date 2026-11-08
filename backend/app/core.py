import hashlib
import io
import csv
import json
from typing import Any
from collections import Counter
from fastapi import HTTPException

LABELS = ('SUPPORTED', 'REFUTED', 'NOT_ENOUGH_INFO')
MAX_IMPORT_BYTES = 5 * 1024 * 1024

def validate_example(item: dict, row: int):
    errors = []
    ext = str(item.get('example_id') or '').strip()
    claim = str(item.get('claim') or '').strip()
    label = str(item.get('gold_label') or '').strip().upper()
    if not ext: errors.append('example_id is required')
    if not claim: errors.append('claim is required')
    if label not in LABELS: errors.append(f'gold_label must be one of {list(LABELS)}')
    evidence = item.get('evidence', [])
    if isinstance(evidence, str):
        try: evidence = json.loads(evidence)
        except json.JSONDecodeError: errors.append('evidence must contain valid JSON')
    if not isinstance(evidence, list):
        errors.append('evidence must be an array')
        evidence = []
    ev_ids = set()
    for i, ev in enumerate(evidence):
        if not isinstance(ev, dict) or not str(ev.get('evidence_id','')).strip() or not str(ev.get('text','')).strip():
            errors.append(f'evidence item {i + 1} requires evidence_id and text')
        else:
            if ev['evidence_id'] in ev_ids: errors.append(f'duplicate evidence id {ev["evidence_id"]}')
            ev_ids.add(ev['evidence_id'])
    gold_sets = item.get('gold_evidence_sets', [])
    if isinstance(gold_sets, str):
        try: gold_sets = json.loads(gold_sets)
        except json.JSONDecodeError: errors.append('gold_evidence_sets must contain valid JSON')
    if not isinstance(gold_sets, list) or any(not isinstance(s, list) for s in gold_sets):
        errors.append('gold_evidence_sets must be a list of lists')
        gold_sets = []
    elif any(eid not in ev_ids for s in gold_sets for eid in s):
        errors.append('gold_evidence_sets reference nonexistent evidence IDs')
    if errors: return None, {'row': row, 'example_id': ext, 'errors': errors}
    return {'example_id': ext, 'claim': claim, 'gold_label': label,
            'evidence': evidence, 'gold_evidence_sets': gold_sets,
            'domain': str(item.get('domain') or 'general')}, None

def parse_dataset(contents: bytes, filename: str):
    if len(contents) > MAX_IMPORT_BYTES: raise HTTPException(413, 'Maximum file size is 5 MB')
    try: raw = contents.decode('utf-8-sig')
    except UnicodeDecodeError: raise HTTPException(422, 'The file must use UTF-8 encoding')
    try:
        if filename.lower().endswith('.csv'):
            rows = list(csv.DictReader(io.StringIO(raw)))
        elif filename.lower().endswith('.jsonl'):
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        elif filename.lower().endswith('.json'):
            rows = json.loads(raw)
            if not isinstance(rows, list): raise ValueError('JSON dataset must be an array')
        else: raise HTTPException(415, 'Accepted files: CSV, JSON and JSONL')
    except (ValueError, json.JSONDecodeError, csv.Error) as ex:
        raise HTTPException(422, f'Unable to parse dataset: {ex}')
    if not rows: raise HTTPException(422, 'Dataset is empty')
    valid, errors, seen = [], [], set()
    for idx, item in enumerate(rows, 1):
        if not isinstance(item, dict):
            errors.append({'row':idx,'errors':['Row must be an object']}); continue
        norm, err = validate_example(item, idx)
        if err: errors.append(err); continue
        if norm['example_id'] in seen:
            errors.append({'row':idx,'example_id':norm['example_id'],'errors':['Duplicate example_id']})
        else:
            seen.add(norm['example_id']); valid.append(norm)
    digest = hashlib.sha256(json.dumps(valid, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    return {'valid':valid, 'errors':errors, 'hash':digest, 'total':len(rows),
            'distribution': dict(Counter(v['gold_label'] for v in valid))}

def scores(golds: list[str], predictions: list[str | None]):
    if len(golds) != len(predictions): raise ValueError('Labels and predictions must match')
    valid = [(g,p) for g,p in zip(golds,predictions) if p in LABELS]
    n = len(valid)
    per_class = {}
    matrix = [[0]*3 for _ in range(3)]
    for g,p in valid:
        matrix[LABELS.index(g)][LABELS.index(p)] += 1
    for c in LABELS:
        tp = sum(g==c and p==c for g,p in valid)
        fp = sum(g!=c and p==c for g,p in valid)
        fn = sum(g==c and p!=c for g,p in valid)
        precision = tp/(tp+fp) if tp+fp else 0
        recall = tp/(tp+fn) if tp+fn else 0
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0
        per_class[c] = {'precision':precision,'recall':recall,'f1':f1,'support':sum(g==c for g,p in valid)}
    return {'total_expected':len(golds), 'valid_predictions':n, 'coverage': n/len(golds) if golds else 0,
            'accuracy': sum(g==p for g,p in valid)/n if n else None,
            'macro_f1': sum(v['f1'] for v in per_class.values())/3 if n else None,
            'per_class':per_class, 'labels':list(LABELS), 'confusion_matrix':matrix,
            'unscored':len(golds)-n}
