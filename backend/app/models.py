from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Integer, ForeignKey, Float, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc)

class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(80), default='1.0')
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    row_count: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text, default='user-upload')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    examples: Mapped[list['Example']] = relationship(back_populates='dataset', cascade='all, delete-orphan')

class Example(Base):
    __tablename__ = 'examples'
    __table_args__ = (UniqueConstraint('dataset_id','external_id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    claim: Mapped[str] = mapped_column(Text)
    gold_label: Mapped[str] = mapped_column(String(40))
    evidence_json: Mapped[str] = mapped_column(Text)
    gold_evidence_sets_json: Mapped[str] = mapped_column(Text, default='[]')
    domain: Mapped[str] = mapped_column(String(100), default='general')
    dataset: Mapped['Dataset'] = relationship(back_populates='examples')

class Experiment(Base):
    __tablename__ = 'experiments'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(255))
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    adapter: Mapped[str] = mapped_column(String(64), default='mock')
    prompt_template: Mapped[str] = mapped_column(Text, default='Classify the claim using only the supplied evidence.')
    prompt_hash: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer, default=42)
    status: Mapped[str] = mapped_column(String(32), default='QUEUED')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_identifier: Mapped[str] = mapped_column(String(200), default='mock')
    parameters_json: Mapped[str] = mapped_column(Text, default='{}')
    provenance_json: Mapped[str] = mapped_column(Text, default='{}')
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    predictions: Mapped[list['Prediction']] = relationship(back_populates='experiment', cascade='all, delete-orphan')

class Prediction(Base):
    __tablename__ = 'predictions'
    __table_args__ = (UniqueConstraint('experiment_id','example_id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    experiment_id: Mapped[str] = mapped_column(ForeignKey('experiments.id'), index=True)
    example_id: Mapped[str] = mapped_column(ForeignKey('examples.id'))
    predicted_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_evidence_json: Mapped[str] = mapped_column(Text, default='[]')
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='SUCCESS')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experiment: Mapped['Experiment'] = relationship(back_populates='predictions')

class ExplanationClaim(Base):
    __tablename__ = 'explanation_claims'
    __table_args__ = (UniqueConstraint('prediction_id','claim_index'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    prediction_id: Mapped[str] = mapped_column(ForeignKey('predictions.id'), index=True)
    claim_index: Mapped[int] = mapped_column(Integer)
    claim_text: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(32), default='human')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ClaimJudgment(Base):
    __tablename__ = 'claim_judgments'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    claim_id: Mapped[str] = mapped_column(ForeignKey('explanation_claims.id'), index=True)
    judgment: Mapped[str] = mapped_column(String(40))
    evidence_ids_json: Mapped[str] = mapped_column(Text, default='[]')
    rationale: Mapped[str] = mapped_column(Text, default='')
    annotation_source: Mapped[str] = mapped_column(String(32), default='human')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
