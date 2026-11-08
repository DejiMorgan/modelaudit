import hashlib
import os
import sys
from pathlib import Path
import json
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db
from .models import Dataset, Example, Experiment, Prediction, ExplanationClaim, ClaimJudgment
from .core import parse_dataset, scores, MAX_IMPORT_BYTES
from .adapters import ADAPTERS, make_adapter, AdapterError
from .jobs import submit, progress, ACTIVE, LOCK
from .reporting import canonical_sha256, html_report, failure_analysis
from .citation_metrics import citation_metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Previous in-process jobs do not survive restart; preserve checkpoints and mark them interrupted.
    with SessionLocal() as db:
        running=db.scalars(select(Experiment).where(Experiment.status=='RUNNING')).all()
        for exp in running:
            exp.status='FAILED';exp.error='INTERRUPTED_AFTER_RESTART'
        db.commit()
    yield

app = FastAPI(title='ModelAudit API', version='0.5.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],
                   allow_methods=['*'], allow_headers=['*'])

def session():
    with SessionLocal() as db:
        yield db

def get_or_404(db, model, obj_id):
    obj = db.get(model, obj_id)
    if obj is None: raise HTTPException(404, f'{model.__name__} not found')
    return obj

def dataset_view(d):
    return {'id':d.id,'name':d.name,'version':d.version,'sha256':d.sha256,'row_count':d.row_count,'source':d.source}

def experiment_view(e):
    return {'id':e.id,'name':e.name,'dataset_id':e.dataset_id,'adapter':e.adapter,
            'status':e.status,'cancel_requested':e.cancel_requested,'seed':e.seed,'prompt_hash':e.prompt_hash,'error':e.error,
            'created_at':e.created_at.isoformat() if e.created_at else None,
            'model_identifier':e.model_identifier,'parameters':json.loads(e.parameters_json),'provenance':json.loads(e.provenance_json),
            'started_at':e.started_at.isoformat() if e.started_at else None,
            'completed_at':e.completed_at.isoformat() if e.completed_at else None}

@app.get('/api/v1/health')
def health(): return {'status':'ok','version':'0.5.0'}

async def load_upload(file: UploadFile):
    # Bounded read to avoid unbounded upload memory usage.
    content = await file.read(MAX_IMPORT_BYTES+1)
    return parse_dataset(content, file.filename or '')

@app.post('/api/v1/datasets/import/preview')
async def import_preview(file: UploadFile = File(...)):
    r = await load_upload(file)
    return {'total':r['total'],'valid_count':len(r['valid']),'errors':r['errors'],
            'distribution':r['distribution'],'sha256':r['hash'],'preview':r['valid'][:20]}

@app.post('/api/v1/datasets/import', status_code=201)
async def import_dataset(file: UploadFile = File(...), name: str = Form(...), version: str = Form('1.0'),
                         source: str = Form('user-upload'), db:Session=Depends(session)):
    r = await load_upload(file)
    if r['errors']: raise HTTPException(422, {'message':'Import rejected; correct invalid rows first','errors':r['errors']})
    existing = db.scalar(select(Dataset).where(Dataset.sha256 == r['hash']))
    if existing: raise HTTPException(409, {'message':'Dataset content already imported','dataset_id':existing.id})
    d = Dataset(name=name.strip(), version=version, source=source, sha256=r['hash'],row_count=len(r['valid']))
    for item in r['valid']:
        d.examples.append(Example(external_id=item['example_id'],claim=item['claim'],gold_label=item['gold_label'],
                  evidence_json=json.dumps(item['evidence']),gold_evidence_sets_json=json.dumps(item['gold_evidence_sets']),
                  domain=item['domain']))
    db.add(d); db.commit(); db.refresh(d)
    return dataset_view(d)

@app.get('/api/v1/datasets')
def datasets(db:Session=Depends(session)):
    return [dataset_view(d) for d in db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()]

@app.get('/api/v1/datasets/{dataset_id}')
def dataset_detail(dataset_id:str, db:Session=Depends(session)):
    d = get_or_404(db,Dataset,dataset_id)
    return {**dataset_view(d),'examples':len(d.examples)}

@app.get('/api/v1/datasets/{dataset_id}/examples')
def dataset_examples(dataset_id:str, limit:int=50, offset:int=0, db:Session=Depends(session)):
    get_or_404(db,Dataset,dataset_id)
    if not 1<=limit<=200 or offset<0: raise HTTPException(422,'Invalid pagination')
    examples = db.scalars(select(Example).where(Example.dataset_id==dataset_id).order_by(Example.external_id).limit(limit).offset(offset)).all()
    return [{'id':e.id,'example_id':e.external_id,'claim':e.claim,'gold_label':e.gold_label,
             'evidence':json.loads(e.evidence_json),'gold_evidence_sets':json.loads(e.gold_evidence_sets_json)} for e in examples]

@app.get('/api/v1/models')
def models_list():
    return [{'id':'mock','name':'Deterministic mock baseline','offline':True},
            {'id':'openai_compatible','name':'OpenAI-compatible chat endpoint','offline':False,'configured':bool(__import__('os').getenv('MODELAUDIT_OPENAI_API_KEY'))},
            {'id':'anthropic','name':'Anthropic Messages API','offline':False,'configured':bool(__import__('os').getenv('MODELAUDIT_ANTHROPIC_API_KEY'))}]

class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1,max_length=255)
    dataset_id: str
    adapter: str = 'mock'
    prompt_template: str = 'Classify the claim using only the supplied evidence.'
    seed: int = 42
    model_identifier: str = Field(default='mock',max_length=200)
    parameters: dict = Field(default_factory=dict)

@app.post('/api/v1/experiments',status_code=201)
def create_experiment(payload:ExperimentCreate,db:Session=Depends(session)):
    get_or_404(db,Dataset,payload.dataset_id)
    if payload.adapter not in ADAPTERS: raise HTTPException(422,'Unsupported adapter')
    if any(k not in {'temperature','max_output_tokens'} for k in payload.parameters):
        raise HTTPException(422,'Unsupported generation parameter')
    temp=payload.parameters.get('temperature',0)
    max_tokens=payload.parameters.get('max_output_tokens',512)
    if not isinstance(temp,(int,float)) or not 0<=temp<=1 or not isinstance(max_tokens,int) or not 1<=max_tokens<=4096:
        raise HTTPException(422,'Invalid model generation parameters')
    dataset=db.get(Dataset,payload.dataset_id)
    config={'temperature':temp,'max_output_tokens':max_tokens}
    provenance={'schema_version':'0.5','dataset_sha256':dataset.sha256,
                'dataset_version':dataset.version,'dataset_rows':dataset.row_count,
                'adapter':payload.adapter,
                'model_identifier':payload.model_identifier if payload.adapter!='mock' else 'deterministic-baseline-v1',
                'prompt_sha256':hashlib.sha256(payload.prompt_template.encode()).hexdigest(),
                'prompt_template':payload.prompt_template,'seed':payload.seed,
                'generation_parameters':config,'python_version':sys.version.split()[0],
                'app_version':'0.5.0','adapter_implementation':'modelaudit-adapters-v0.4'}
    provenance['configuration_sha256']=canonical_sha256(provenance)
    e = Experiment(name=payload.name,dataset_id=payload.dataset_id,adapter=payload.adapter,
                   model_identifier=payload.model_identifier if payload.adapter!='mock' else 'deterministic-baseline-v1',
                   parameters_json=json.dumps(config),provenance_json=json.dumps(provenance,sort_keys=True),
                   prompt_template=payload.prompt_template,seed=payload.seed,
                   prompt_hash=hashlib.sha256(payload.prompt_template.encode()).hexdigest())
    db.add(e); db.commit(); db.refresh(e)
    return experiment_view(e)

@app.get('/api/v1/experiments')
def experiments(db:Session=Depends(session)):
    return [experiment_view(e) for e in db.scalars(select(Experiment).order_by(Experiment.created_at.desc())).all()]

@app.get('/api/v1/experiments/{experiment_id}')
def experiment_detail(experiment_id:str,db:Session=Depends(session)):
    return experiment_view(get_or_404(db,Experiment,experiment_id))

@app.post('/api/v1/experiments/{experiment_id}/run',status_code=202)
def run_experiment(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    if e.status not in ('QUEUED','FAILED'):
        raise HTTPException(409,'Experiment cannot start in its current state')
    try:
        make_adapter(e.adapter,e.model_identifier)
    except AdapterError as exc:
        raise HTTPException(422,str(exc))
    # In-process executor is deliberately limited to one API process.
    if e.status=='FAILED':
        # Failed individual predictions remain terminal. Resume checkpoints only missing examples.
        e.status='QUEUED'
    e.cancel_requested=False;e.error=None;e.completed_at=None
    db.commit()
    if not submit(e.id):raise HTTPException(409,'Already submitted')
    return {'experiment_id':e.id,'status':'QUEUED','message':'Execution accepted; poll /progress'}

@app.get('/api/v1/experiments/{experiment_id}/progress')
def experiment_progress(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    return {'experiment_id':e.id,'status':e.status,'cancel_requested':e.cancel_requested,**progress(db,e)}

@app.post('/api/v1/experiments/{experiment_id}/cancel',status_code=202)
def cancel_experiment(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    if e.status not in ('QUEUED','RUNNING'):
        raise HTTPException(409,'Only queued/running experiments can be cancelled')
    e.cancel_requested=True;db.commit()
    return {'experiment_id':e.id,'status':e.status,'cancel_requested':True}

@app.post('/api/v1/experiments/{experiment_id}/recover')
def recover_interrupted(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    if e.status!='RUNNING':raise HTTPException(409,'Only interrupted RUNNING experiments are recoverable')
    with LOCK:
        if e.id in ACTIVE:raise HTTPException(409,'Worker is still active')
    e.status='FAILED';e.error='MANUALLY_RECOVERED';db.commit()
    return experiment_view(e)

def results_for(db,e):
    exs=db.scalars(select(Example).where(Example.dataset_id==e.dataset_id).order_by(Example.external_id)).all()
    preds=db.scalars(select(Prediction).where(Prediction.experiment_id==e.id)).all()
    predmap={p.example_id:p for p in preds}
    return exs,predmap

@app.get('/api/v1/experiments/{experiment_id}/results')
def experiment_results(experiment_id:str,limit:int=50,offset:int=0,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    if not 1<=limit<=200 or offset<0: raise HTTPException(422,'Invalid pagination')
    exs, predmap=results_for(db,e)
    return {'total':len(exs),'rows':[{'example_id':ex.external_id,'prediction_id':predmap[ex.id].id if ex.id in predmap else None,'claim':ex.claim,'gold_label':ex.gold_label,
              'predicted_label':predmap[ex.id].predicted_label if ex.id in predmap else None,
              'explanation':predmap[ex.id].explanation if ex.id in predmap else None,
              'status':predmap[ex.id].status if ex.id in predmap else 'PENDING',
              'evidence':json.loads(ex.evidence_json)} for ex in exs[offset:offset+limit]]}

@app.get('/api/v1/experiments/{experiment_id}/metrics')
def experiment_metrics(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    exs,pm=results_for(db,e)
    return {'experiment_id':e.id,'status':e.status,
            **scores([x.gold_label for x in exs],[pm[x.id].predicted_label if x.id in pm else None for x in exs])}

@app.get('/api/v1/experiments/{experiment_id}/report')
def experiment_report(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    if e.status!='COMPLETED': raise HTTPException(409,'Report requires completed experiment')
    d=get_or_404(db,Dataset,e.dataset_id)
    exs,pm=results_for(db,e)
    metrics=scores([x.gold_label for x in exs],[pm[x.id].predicted_label if x.id in pm else None for x in exs])
    report={'schema_version':'0.5','authorship':{'prepared_by':'Arabome Obadiah Ayodeji','project':'ModelAudit'},'experiment':experiment_view(e),'dataset':dataset_view(d),
            'methodology':{'task':'three-class claim verification','adapter':e.adapter,'model_identifier':e.model_identifier,'parameters':json.loads(e.parameters_json),'provenance':json.loads(e.provenance_json),
                           'claim_support':'HUMAN_ANNOTATED_ONLY','metric_policy':'invalid predictions excluded from accuracy and counted as unscored'},
            'metrics':metrics,'citation_metrics':citation_metrics(exs,pm),'evidence_support':support_metrics(db,e.id),'results':[{'example_id':x.external_id,'gold_label':x.gold_label,
                'predicted_label':pm[x.id].predicted_label if x.id in pm else None,
                'status':pm[x.id].status if x.id in pm else 'PENDING',
                'explanation_claims':claims_view(db,pm[x.id].id) if x.id in pm else [],
                'error':pm[x.id].error if x.id in pm else None} for x in exs]}
    report['provenance']=json.loads(e.provenance_json)
    report['content_sha256']=canonical_sha256({'provenance':report['provenance'],'metrics':metrics,
         'predictions':[(x.external_id,pm[x.id].predicted_label if x.id in pm else None,
                         pm[x.id].status if x.id in pm else 'PENDING') for x in exs]})
    return report

@app.get('/api/v1/experiments/{experiment_id}/report.html',response_class=HTMLResponse)
def experiment_html_report(experiment_id:str,db:Session=Depends(session)):
    return HTMLResponse(html_report(experiment_report(experiment_id,db)))

@app.get('/api/v1/experiments/{experiment_id}/failures')
def experiment_failures(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    exs,pm=results_for(db,e)
    return {'experiment_id':e.id,'status':e.status,**failure_analysis(exs,pm)}

@app.get('/api/v1/experiments/{experiment_id}/provenance')
def experiment_provenance(experiment_id:str,db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    return json.loads(e.provenance_json)

# ---------------- Evidence claim review (manual, never automatic model self-scoring) ---------
class ClaimCreate(BaseModel):
    claim_text: str = Field(min_length=2,max_length=4000)

class JudgmentCreate(BaseModel):
    judgment: str
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(default='',max_length=4000)

def claims_view(db,prediction_id):
    claims=db.scalars(select(ExplanationClaim).where(ExplanationClaim.prediction_id==prediction_id).order_by(ExplanationClaim.claim_index)).all()
    output=[]
    for claim in claims:
        judgment=db.scalars(select(ClaimJudgment).where(ClaimJudgment.claim_id==claim.id).order_by(ClaimJudgment.created_at.desc(),ClaimJudgment.id.desc())).first()
        output.append({'id':claim.id,'claim_index':claim.claim_index,'claim_text':claim.claim_text,
          'judgment':{'judgment':judgment.judgment,'evidence_ids':json.loads(judgment.evidence_ids_json),'rationale':judgment.rationale} if judgment else None})
    return output

@app.get('/api/v1/predictions/{prediction_id}/claims')
def list_claims(prediction_id:str,db:Session=Depends(session)):
    get_or_404(db,Prediction,prediction_id)
    return claims_view(db,prediction_id)

@app.post('/api/v1/predictions/{prediction_id}/claims',status_code=201)
def add_claim(prediction_id:str,payload:ClaimCreate,db:Session=Depends(session)):
    prediction=get_or_404(db,Prediction,prediction_id)
    if prediction.status!='SUCCESS':raise HTTPException(409,'Only successful predictions support claim review')
    idx=db.scalar(select(func.count()).select_from(ExplanationClaim).where(ExplanationClaim.prediction_id==prediction_id)) or 0
    claim=ExplanationClaim(prediction_id=prediction_id,claim_index=idx,claim_text=payload.claim_text.strip())
    db.add(claim);db.commit();db.refresh(claim)
    return {'id':claim.id,'claim_index':idx,'claim_text':claim.claim_text,'judgment':None}

@app.post('/api/v1/claims/{claim_id}/judgments',status_code=201)
def add_judgment(claim_id:str,payload:JudgmentCreate,db:Session=Depends(session)):
    claim=get_or_404(db,ExplanationClaim,claim_id)
    allowed={'SUPPORTED','CONTRADICTED','INSUFFICIENT_EVIDENCE','NOT_ASSESSED'}
    if payload.judgment not in allowed:raise HTTPException(422,'Invalid claim judgment')
    prediction=get_or_404(db,Prediction,claim.prediction_id)
    example=get_or_404(db,Example,prediction.example_id)
    valid_ids={e['evidence_id'] for e in json.loads(example.evidence_json)}
    if len(payload.evidence_ids)!=len(set(payload.evidence_ids)) or not set(payload.evidence_ids).issubset(valid_ids):
        raise HTTPException(422,'Unknown or duplicate cited evidence ID')
    row=ClaimJudgment(claim_id=claim_id,judgment=payload.judgment,
        evidence_ids_json=json.dumps(payload.evidence_ids),rationale=payload.rationale,annotation_source='human')
    db.add(row);db.commit()
    return {'id':row.id,'claim_id':claim_id,'judgment':row.judgment,'evidence_ids':payload.evidence_ids}

def support_metrics(db,experiment_id):
    rows=db.execute(select(ExplanationClaim.id,ClaimJudgment.judgment,ClaimJudgment.created_at,ClaimJudgment.id)
      .join(Prediction,Prediction.id==ExplanationClaim.prediction_id)
      .outerjoin(ClaimJudgment,ClaimJudgment.claim_id==ExplanationClaim.id)
      .where(Prediction.experiment_id==experiment_id)).all()
    latest={}
    for claim_id,judgment,created,jid in rows:
        if claim_id not in latest or (created is not None and (latest[claim_id][1] is None or (created,jid)>(latest[claim_id][1],latest[claim_id][2]))):
            latest[claim_id]=(judgment,created,jid)
    labels=[v[0] for v in latest.values()]
    assessed=[x for x in labels if x in ('SUPPORTED','CONTRADICTED','INSUFFICIENT_EVIDENCE')]
    bad=sum(x in ('CONTRADICTED','INSUFFICIENT_EVIDENCE') for x in assessed)
    return {'total_extracted_claims':len(latest),'assessed_claims':len(assessed),
        'unassessed_claims':len(labels)-len(assessed),'unsupported_claims':bad,
        'contradicted_claims':assessed.count('CONTRADICTED'),
        'insufficient_evidence_claims':assessed.count('INSUFFICIENT_EVIDENCE'),
        'unsupported_claim_rate':bad/len(assessed) if assessed else None,
        'method':'human_manual_annotation','warning':'Selection bias possible: only manually extracted and assessed claims are scored.'}

@app.get('/api/v1/experiments/{experiment_id}/support-metrics')
def experiment_support_metrics(experiment_id:str,db:Session=Depends(session)):
    get_or_404(db,Experiment,experiment_id)
    return support_metrics(db,experiment_id)

class ComparisonCreate(BaseModel):
    experiment_ids: list[str] = Field(min_length=2,max_length=6)

@app.post('/api/v1/comparisons')
def compare_experiments(payload:ComparisonCreate,db:Session=Depends(session)):
    if len(set(payload.experiment_ids))!=len(payload.experiment_ids):raise HTTPException(422,'Experiments must be distinct')
    exps=[get_or_404(db,Experiment,eid) for eid in payload.experiment_ids]
    if any(e.status!='COMPLETED' for e in exps):raise HTTPException(409,'Only completed experiments can be compared')
    # Comparing like with like: identical dataset, prompt and evaluation population.
    compatible=len({e.dataset_id for e in exps})==1 and len({e.prompt_hash for e in exps})==1
    output=[]
    for e in exps:
        exs,pm=results_for(db,e)
        output.append({'experiment':experiment_view(e),
           'metrics':scores([x.gold_label for x in exs],[pm[x.id].predicted_label if x.id in pm else None for x in exs]),
           'support_metrics':support_metrics(db,e.id)})
    paired = []
    if compatible:
        left, right = exps[0], exps[1]
        examples_a, predictions_a = results_for(db, left)
        _, predictions_b = results_for(db, right)
        for example in examples_a:
            a = predictions_a.get(example.id)
            b = predictions_b.get(example.id)
            label_a = a.predicted_label if a and a.status == 'SUCCESS' else None
            label_b = b.predicted_label if b and b.status == 'SUCCESS' else None
            if label_a != label_b:
                paired.append({'example_id': example.external_id, 'gold_label': example.gold_label,
                    'first_prediction': label_a, 'second_prediction': label_b})
    return {'compatible':compatible,'warning':None if compatible else 'Different dataset or prompt. Not a controlled comparison.',
      'paired_disagreements_first_two':paired,'runs':output}

@app.get('/api/v1/experiments/{experiment_id}/citation-metrics')
def experiment_citation_metrics(experiment_id:str, db:Session=Depends(session)):
    e=get_or_404(db,Experiment,experiment_id)
    exs,pm=results_for(db,e)
    return {'experiment_id':e.id, **citation_metrics(exs,pm)}
