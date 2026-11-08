# Safe, self-contained HTML report generation and stable content fingerprinting.
import hashlib
import html
import json
from collections import Counter

def canonical_sha256(payload):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def failure_analysis(examples, predictions):
    rows=[]
    counts=Counter()
    for ex in examples:
        pred=predictions.get(ex.id)
        label=pred.predicted_label if pred and pred.status=='SUCCESS' else None
        if pred is None: category='PENDING'
        elif pred.status!='SUCCESS' or label is None: category='EXECUTION_ERROR'
        elif label!=ex.gold_label: category='MISCLASSIFIED'
        else: category='CORRECT'
        counts[category]+=1
        if category!='CORRECT':
            rows.append({'example_id':ex.external_id,'claim':ex.claim,'gold_label':ex.gold_label,
                         'predicted_label':label,'category':category,'error':pred.error if pred else None})
    return {'counts':dict(counts),'total':len(examples),'failures':rows}

def html_report(report):
    h=lambda value: html.escape(str(value),quote=True)
    met=report['metrics']; ds=report['dataset']; exp=report['experiment']
    percentage=lambda x: 'N/A' if x is None else f'{x*100:.1f}%'
    rows=[]
    for r in report['results']:
        rows.append('<tr>'+''.join(f'<td>{h(r.get(k) or "")}</td>' for k in ('example_id','gold_label','predicted_label','status','error'))+'</tr>')
    matrix=''.join('<tr><th>'+h(label)+'</th>'+''.join('<td>'+h(n)+'</td>' for n in row)+'</tr>' for label,row in zip(met['labels'],met['confusion_matrix']))
    head=''.join('<th>'+h(x)+'</th>' for x in met['labels'])
    provenance=h(json.dumps(report['provenance'],indent=2,sort_keys=True))
    support=report['evidence_support']
    citation=report.get('citation_metrics', {})
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ModelAudit report — {h(exp['name'])}</title>
<style>body{{font:15px/1.55 system-ui,Arial,sans-serif;color:#1c283b;max-width:980px;margin:48px auto;padding:0 20px}}h1,h2{{line-height:1.25}}h1{{font-size:32px}}h2{{margin-top:36px;border-bottom:1px solid #dce3ed;padding-bottom:8px}}.muted{{color:#68778b}}.metrics{{display:flex;flex-wrap:wrap;gap:12px}}.metric{{background:#f1f5fb;border-radius:9px;padding:14px;min-width:150px}}.metric strong{{display:block;font-size:25px}}table{{border-collapse:collapse;width:100%;margin:16px 0}}td,th{{border:1px solid #dae2ec;text-align:left;padding:8px;vertical-align:top;overflow-wrap:anywhere}}th{{background:#f1f5fb}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:16px;border-radius:8px}}.notice{{background:#fff8e4;border-left:4px solid #ae7922;padding:12px}}@media print{{body{{margin:12mm}}}}</style></head><body>
<p class="muted">MODELAUDIT · EVALUATION REPORT · ARABOME OBADIAH AYODEJI · SCHEMA {h(report['schema_version'])}</p><h1>{h(exp['name'])}</h1>
<p>Dataset: <b>{h(ds['name'])}</b> · Version {h(ds['version'])} · Model: {h(exp['model_identifier'])} · Status: {h(exp['status'])}</p>
<div class="metrics"><div class="metric">Accuracy<strong>{percentage(met['accuracy'])}</strong></div><div class="metric">Macro F1<strong>{h(round(met['macro_f1'],3) if met['macro_f1'] is not None else 'N/A')}</strong></div><div class="metric">Coverage<strong>{percentage(met['coverage'])}</strong></div></div>
<p class="notice">Classification metrics exclude invalid responses; coverage is reported separately. Explanation support is manually annotated, so incomplete review can introduce selection bias. This report does not establish general model reliability.</p>
<h2>Methodology</h2><p>Three-class claim verification against independent reference labels. Valid predictions: {h(met['valid_predictions'])} / {h(met['total_expected'])}. Unscored: {h(met['unscored'])}.</p>
<h2>Confusion matrix</h2><table><thead><tr><th>Reference / Predicted</th>{head}</tr></thead><tbody>{matrix}</tbody></table>
<h2>Citation completeness</h2><p>Eligible evidence-annotated examples: {h(citation.get("annotated_examples", 0))}. Evaluated: {h(citation.get("evaluated_examples", 0))}. Complete citation rate: {percentage(citation.get("citation_completeness_rate"))}. This measures evidence-set citation, not whether explanations are true.</p>
<h2>Human-reviewed evidence support</h2><p>Assessed claims: {h(support['assessed_claims'])} / {h(support['total_extracted_claims'])}. Unsupported claim rate: {percentage(support['unsupported_claim_rate'])}.</p>
<h2>Case-level results</h2><table><thead><tr><th>ID</th><th>Gold</th><th>Prediction</th><th>Status</th><th>Error</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Experiment provenance</h2><pre>{provenance}</pre>
<p class="muted">Report payload fingerprint: {h(report['content_sha256'])}. Fingerprint covers the captured configuration, classification metrics and prediction labels/statuses; it does not cover manual judgments, raw model responses or timing.</p></body></html>'''
