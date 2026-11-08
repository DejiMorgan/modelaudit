"""Evidence-set scoring, independent of model classification scoring.

Only examples with at least one annotated complete evidence set are eligible.
The score is citation completeness, not explanation truthfulness.
"""
import json


def citation_metrics(examples, predmap):
    annotated = 0
    evaluated = 0
    complete = 0
    citation_total = 0
    valid_total = 0
    cited_on_annotated = 0
    for example in examples:
        evidence = json.loads(example.evidence_json)
        allowed = {item['evidence_id'] for item in evidence}
        pred = predmap.get(example.id)
        if pred is not None and pred.status == 'SUCCESS':
            citations = json.loads(pred.cited_evidence_json or '[]')
            if isinstance(citations, list):
                citation_total += len(citations)
                valid_total += sum(c in allowed for c in citations)
        else:
            citations = []
        gold_sets = json.loads(example.gold_evidence_sets_json or '[]')
        # A dataset without complete evidence sets cannot be used to evaluate completeness.
        gold_sets = [set(s) for s in gold_sets if isinstance(s, list) and s]
        if not gold_sets:
            continue
        annotated += 1
        if pred is None or pred.status != 'SUCCESS':
            continue
        evaluated += 1
        cited = set(citations)
        if cited:
            cited_on_annotated += 1
        if any(required <= cited for required in gold_sets):
            complete += 1
    return {
        'annotated_examples': annotated,
        'evaluated_examples': evaluated,
        'complete_citations': complete,
        'citation_completeness_rate': complete / evaluated if evaluated else None,
        'citation_coverage': cited_on_annotated / evaluated if evaluated else None,
        'citation_validity_rate': valid_total / citation_total if citation_total else None,
        'total_citations': citation_total,
        'warning': 'Measures cited evidence-set coverage only; does not establish explanation support. Only examples with annotated nonempty complete sets qualify.'
    }
