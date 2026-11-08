"""Single-process local job worker. Not suitable for multiworker or production queues."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from sqlalchemy import select, func
from .db import SessionLocal
from .models import Example, Experiment, Prediction
from .adapters import make_adapter

EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='modelaudit-eval')
LOCK = Lock()
ACTIVE = set()

def utcnow(): return datetime.now(timezone.utc)

def submit(experiment_id):
    with LOCK:
        if experiment_id in ACTIVE:
            return False
        ACTIVE.add(experiment_id)
    try:
        EXECUTOR.submit(run_job, experiment_id)
    except Exception:
        with LOCK: ACTIVE.discard(experiment_id)
        raise
    return True

def run_job(experiment_id):
    try:
        with SessionLocal() as db:
            exp=db.get(Experiment,experiment_id)
            if exp is None or exp.status!='QUEUED': return
            if exp.cancel_requested:
                exp.status='CANCELLED';exp.completed_at=utcnow();db.commit();return
            exp.status='RUNNING'
            if exp.started_at is None: exp.started_at=utcnow()
            db.commit()
            adapter=make_adapter(exp.adapter,exp.model_identifier)
            examples=db.scalars(select(Example).where(Example.dataset_id==exp.dataset_id).order_by(Example.external_id)).all()
            existing=set(db.scalars(select(Prediction.example_id).where(Prediction.experiment_id==exp.id)).all())
            for ex in examples:
                db.refresh(exp)
                if exp.cancel_requested:
                    exp.status='CANCELLED';exp.completed_at=utcnow();db.commit();return
                if ex.id in existing: continue
                begin=time.perf_counter()
                try:
                    result=adapter.predict(ex.claim,json.loads(ex.evidence_json),exp.seed,exp.prompt_template,json.loads(exp.parameters_json))
                    pred=Prediction(experiment_id=exp.id,example_id=ex.id,predicted_label=result.predicted_label,
                        explanation=result.explanation,cited_evidence_json=json.dumps(result.cited_evidence_ids),
                        raw_response_json=json.dumps(result.raw_output),input_tokens=result.input_tokens,output_tokens=result.output_tokens,
                        latency_ms=(time.perf_counter()-begin)*1000,status='SUCCESS')
                except Exception as err:
                    pred=Prediction(experiment_id=exp.id,example_id=ex.id,predicted_label=None,
                        error=type(err).__name__,status='FAILED',latency_ms=(time.perf_counter()-begin)*1000)
                db.add(pred)
                db.commit()
            exp.status='COMPLETED';exp.completed_at=utcnow();db.commit()
    except Exception as err:
        with SessionLocal() as db:
            exp=db.get(Experiment,experiment_id)
            if exp:
                exp.status='FAILED';exp.error=type(err).__name__;exp.completed_at=utcnow();db.commit()
    finally:
        with LOCK: ACTIVE.discard(experiment_id)

def progress(db,exp):
    processed=db.scalar(select(func.count()).select_from(Prediction).where(Prediction.experiment_id==exp.id)) or 0
    total=db.scalar(select(func.count()).select_from(Example).where(Example.dataset_id==exp.dataset_id)) or 0
    failed=db.scalar(select(func.count()).select_from(Prediction).where(Prediction.experiment_id==exp.id,Prediction.status=='FAILED')) or 0
    return {'total':total,'processed':processed,'successful':processed-failed,'failed':failed,
            'pending':max(0,total-processed),'progress_percent':round(100*processed/total,2) if total else 0}
