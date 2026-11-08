"""Release tests for citation scoring and paired evaluation behavior."""
import json
from pathlib import Path
from types import SimpleNamespace
from app.citation_metrics import citation_metrics
from app.core import parse_dataset
from test_api import wait_done


def example(eid, sets):
    return SimpleNamespace(id=eid, evidence_json=json.dumps([{'evidence_id': 'E1', 'text': 'A'}, {'evidence_id': 'E2', 'text': 'B'}]),
                           gold_evidence_sets_json=json.dumps(sets))


def prediction(citations, status='SUCCESS'):
    return SimpleNamespace(status=status, cited_evidence_json=json.dumps(citations))


def test_complete_evidence_set_and_missing_annotations():
    cases = [example('1', [['E1','E2'], ['E2']]), example('2', [['E1','E2']]), example('3', [])]
    predictions = {'1': prediction(['E2']), '2': prediction(['E1']), '3': prediction(['E1'])}
    result = citation_metrics(cases, predictions)
    assert result['annotated_examples'] == 2
    assert result['evaluated_examples'] == 2
    assert result['complete_citations'] == 1
    assert result['citation_completeness_rate'] == .5
    assert result['citation_validity_rate'] == 1


def test_no_valid_prediction_or_annotated_evidence_does_not_invent_zero_rate():
    no_annotation = citation_metrics([example('1', [])], {'1': prediction([])})
    assert no_annotation['citation_completeness_rate'] is None
    assert no_annotation['citation_validity_rate'] is None
    failed = citation_metrics([example('2', [['E1']])], {'2': prediction(['E1'], 'ERROR')})
    assert failed['annotated_examples'] == 1
    assert failed['evaluated_examples'] == 0
    assert failed['citation_completeness_rate'] is None


def test_synthetic_benchmark_has_balance_and_explicit_evidence_policy():
    path = Path(__file__).resolve().parents[2] / 'benchmarks' / 'modelaudit_synthetic_60.json'
    result = parse_dataset(path.read_bytes(), 'bench.json')
    assert result['errors'] == []
    assert result['total'] == 60
    assert result['distribution'] == {'SUPPORTED':20,'REFUTED':20,'NOT_ENOUGH_INFO':20}
    assert sum(bool(r['gold_evidence_sets']) for r in result['valid']) == 40


def test_citation_api_report_and_paired_mock_reproducibility(client):
    path = Path(__file__).resolve().parents[2] / 'benchmarks' / 'modelaudit_synthetic_60.json'
    uploaded = client.post('/api/v1/datasets/import', files={'file': ('synthetic.json', path.read_bytes(), 'application/json')}, data={'name':'Synthetic'})
    assert uploaded.status_code == 201,uploaded.text
    ds = uploaded.json()['id']
    runs=[]
    for i in (1,2):
        created = client.post('/api/v1/experiments',json={'name':f'Repeat {i}','dataset_id':ds,'seed':17})
        assert created.status_code==201,created.text
        eid=created.json()['id']
        assert client.post(f'/api/v1/experiments/{eid}/run').status_code==202
        wait_done(client,eid)
        runs.append(eid)
    metrics=client.get(f'/api/v1/experiments/{runs[0]}/citation-metrics')
    assert metrics.status_code==200
    m=metrics.json()
    assert m['annotated_examples']==40
    assert m['evaluated_examples']==40
    report=client.get(f'/api/v1/experiments/{runs[0]}/report').json()
    assert report['citation_metrics']['annotated_examples']==40
    assert report['schema_version']=='0.5'
    assert report['authorship']['prepared_by']=='Arabome Obadiah Ayodeji'
    comparison=client.post('/api/v1/comparisons',json={'experiment_ids':runs}).json()
    assert comparison['compatible']
    assert comparison['paired_disagreements_first_two']==[]
    assert comparison['runs'][0]['metrics']==comparison['runs'][1]['metrics']
    html=client.get(f'/api/v1/experiments/{runs[0]}/report.html').text
    assert 'Citation completeness' in html
    assert 'ARABOME OBADIAH AYODEJI' in html
