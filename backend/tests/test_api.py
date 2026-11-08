import time
import json
from app.core import scores, parse_dataset

DATA=[
 {'example_id':'1','claim':'The city has 5 bridges.','evidence':[{'evidence_id':'E1','text':'The report lists five bridges.'}], 'gold_label':'SUPPORTED','gold_evidence_sets':[['E1']]},
 {'example_id':'2','claim':'The earth has two moons.','evidence':[{'evidence_id':'E1','text':'Earth has one natural moon.'}], 'gold_label':'REFUTED'},
 {'example_id':'3','claim':'A meeting happened Tuesday.','evidence':[{'evidence_id':'E1','text':'A meeting was discussed.'}], 'gold_label':'NOT_ENOUGH_INFO'}]

def test_scores_and_confusion():
    res=scores(['SUPPORTED','REFUTED','NOT_ENOUGH_INFO'],['SUPPORTED','SUPPORTED',None])
    assert res['coverage']==2/3
    assert res['accuracy']==0.5
    assert res['confusion_matrix']==[[1,0,0],[1,0,0],[0,0,0]]
    assert res['unscored']==1

def test_validation_rejects_bad_label():
    bad=[{'example_id':'one','claim':'yes','gold_label':'MAYBE','evidence':[]}]
    result=parse_dataset(json.dumps(bad).encode(),'bad.json')
    assert result['errors'] and result['valid']==[]

def test_full_lifecycle(client):
    f={'file':('sample.json',json.dumps(DATA),'application/json')}
    preview=client.post('/api/v1/datasets/import/preview', files=f)
    assert preview.status_code==200
    assert preview.json()['valid_count']==3
    imported=client.post('/api/v1/datasets/import',files=f,data={'name':'Sample benchmark'})
    assert imported.status_code==201, imported.text
    ds=imported.json()['id']
    duplicate=client.post('/api/v1/datasets/import',files=f,data={'name':'Duplicate'})
    assert duplicate.status_code==409
    created=client.post('/api/v1/experiments',json={'name':'mock baseline','dataset_id':ds})
    assert created.status_code==201
    eid=created.json()['id']
    run=client.post(f'/api/v1/experiments/{eid}/run')
    assert run.status_code==202,run.text
    wait_done(client,eid)
    assert client.post(f'/api/v1/experiments/{eid}/run').status_code==409
    metrics=client.get(f'/api/v1/experiments/{eid}/metrics').json()
    assert metrics['total_expected']==3
    assert metrics['valid_predictions']==3
    result=client.get(f'/api/v1/experiments/{eid}/report')
    assert result.status_code==200
    assert result.json()['methodology']['claim_support']=='HUMAN_ANNOTATED_ONLY'

def test_external_provider_validation_and_run_failure(client,monkeypatch):
    monkeypatch.delenv('MODELAUDIT_OPENAI_API_KEY',raising=False)
    files={'file':('data.json',json.dumps(DATA),'application/json')}
    ds=client.post('/api/v1/datasets/import',files=files,data={'name':'Demo'}).json()['id']
    wrong=client.post('/api/v1/experiments',json={'name':'Bad parameters','dataset_id':ds,'parameters':{'max_output_tokens':-1}})
    assert wrong.status_code==422
    created=client.post('/api/v1/experiments',json={'name':'Provider attempt','dataset_id':ds,'adapter':'openai_compatible','model_identifier':'example-model'})
    assert created.status_code==201
    eid=created.json()['id']
    refused=client.post(f'/api/v1/experiments/{eid}/run')
    assert refused.status_code==422
    assert client.get(f'/api/v1/experiments/{eid}').json()['status']=='QUEUED'


def test_mock_checkpoint_details(client):
    files={'file':('data.json',json.dumps(DATA),'application/json')}
    ds=client.post('/api/v1/datasets/import',files=files,data={'name':'Demo'}).json()['id']
    eid=client.post('/api/v1/experiments',json={'name':'Offline','dataset_id':ds,'parameters':{'temperature':0}}).json()['id']
    run=client.post(f'/api/v1/experiments/{eid}/run')
    assert run.status_code==202
    wait_done(client,eid)
    assert client.get(f'/api/v1/experiments/{eid}/progress').json()['processed']==3
    assert client.get(f'/api/v1/experiments/{eid}').json()['completed_at']
    report=client.get(f'/api/v1/experiments/{eid}/report').json()
    assert report['methodology']['adapter']=='mock'
    assert report['methodology']['model_identifier']=='deterministic-baseline-v1'


def wait_done(client,eid,timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        response=client.get(f'/api/v1/experiments/{eid}/progress')
        if response.json()['status'] in ('COMPLETED','FAILED','CANCELLED'):
            assert response.json()['status']=='COMPLETED', response.json()
            return response.json()
        time.sleep(.02)
    raise AssertionError('Experiment did not reach completion')

def test_manual_claim_review_and_comparison(client):
    data={'file':('d.json',json.dumps(DATA),'application/json')}
    ds=client.post('/api/v1/datasets/import',files=data,data={'name':'Review'}).json()['id']
    runs=[]
    for name in ('run-1','run-2'):
        eid=client.post('/api/v1/experiments',json={'name':name,'dataset_id':ds}).json()['id']
        assert client.post(f'/api/v1/experiments/{eid}/run').status_code==202
        wait_done(client,eid)
        runs.append(eid)
    result=client.get(f'/api/v1/experiments/{runs[0]}/results').json()['rows'][0]
    prediction_id=result['prediction_id']
    claim=client.post(f'/api/v1/predictions/{prediction_id}/claims',json={'claim_text':'The record establishes five bridges.'})
    assert claim.status_code==201,claim.text
    cid=claim.json()['id']
    bad=client.post(f'/api/v1/claims/{cid}/judgments',json={'judgment':'SUPPORTED','evidence_ids':['nonexistent']})
    assert bad.status_code==422
    judge=client.post(f'/api/v1/claims/{cid}/judgments',json={'judgment':'INSUFFICIENT_EVIDENCE','evidence_ids':['E1'],'rationale':'Insufficient justification.'})
    assert judge.status_code==201,judge.text
    m=client.get(f'/api/v1/experiments/{runs[0]}/support-metrics').json()
    assert m['assessed_claims']==1 and m['unsupported_claim_rate']==1
    compare=client.post('/api/v1/comparisons',json={'experiment_ids':runs})
    assert compare.status_code==200 and compare.json()['compatible']
    assert len(compare.json()['runs'])==2

def test_cancellation_and_progress(client,monkeypatch):
    from app import jobs
    original=jobs.make_adapter
    class SlowAdapter:
        def predict(self,*args,**kwargs):
            time.sleep(.06)
            return original('mock','deterministic-baseline-v1').predict(*args,**kwargs)
    monkeypatch.setattr(jobs,'make_adapter',lambda *args:SlowAdapter())
    ds=client.post('/api/v1/datasets/import',files={'file':('d.json',json.dumps(DATA),'application/json')},data={'name':'cancel'}).json()['id']
    eid=client.post('/api/v1/experiments',json={'name':'cancel','dataset_id':ds}).json()['id']
    assert client.post(f'/api/v1/experiments/{eid}/run').status_code==202
    assert client.post(f'/api/v1/experiments/{eid}/cancel').status_code==202
    for _ in range(200):
        state=client.get(f'/api/v1/experiments/{eid}/progress').json()
        if state['status']=='CANCELLED':break
        time.sleep(.01)
    assert state['status']=='CANCELLED',state
    assert state['processed']<3

def test_v04_provenance_failure_analysis_and_html(client):
    data=[{'example_id':'unsafe','claim':'<script>alert(1)</script>',
           'evidence':[{'evidence_id':'E1','text':'No text is trusted.'}],
           'gold_label':'SUPPORTED'}]
    ds=client.post('/api/v1/datasets/import',files={'file':('unsafe.json',json.dumps(data),'application/json')},data={'name':'Safety test'}).json()['id']
    eid=client.post('/api/v1/experiments',json={'name':'<script>Bad title</script>','dataset_id':ds}).json()['id']
    prov=client.get(f'/api/v1/experiments/{eid}/provenance')
    assert prov.status_code==200
    assert prov.json()['dataset_rows']==1
    assert len(prov.json()['configuration_sha256'])==64
    before=client.get(f'/api/v1/experiments/{eid}/failures').json()
    assert before['counts']['PENDING']==1
    assert client.post(f'/api/v1/experiments/{eid}/run').status_code==202
    wait_done(client,eid)
    after=client.get(f'/api/v1/experiments/{eid}/failures').json()
    assert sum(after['counts'].values())==1
    json_report=client.get(f'/api/v1/experiments/{eid}/report').json()
    assert json_report['provenance']['dataset_sha256']
    assert len(json_report['content_sha256'])==64
    html=client.get(f'/api/v1/experiments/{eid}/report.html')
    assert html.status_code==200 and 'text/html' in html.headers['content-type']
    assert '<script>Bad title</script>' not in html.text
    assert '&lt;script&gt;Bad title&lt;/script&gt;' in html.text


def test_v04_fingerprint_stability_and_html_safety():
    from app.reporting import canonical_sha256,html_report
    assert canonical_sha256({'a':1,'b':2})==canonical_sha256({'b':2,'a':1})
