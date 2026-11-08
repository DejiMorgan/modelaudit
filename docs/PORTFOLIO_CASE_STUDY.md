# ModelAudit — Evaluating AI answers against evidence
**Arabome Obadiah Ayodeji** | Python, FastAPI, React, SQLite, pytest

## Problem

Most model comparisons start and end with a correct-answer percentage. That misses a second failure mode: the answer may be correct, but the model's explanation may not be justified by the evidence it was given.

## What I built

ModelAudit is a local-first evaluation workbench. It imports labelled claim-verification datasets, runs the same cases through pluggable model adapters, saves predictions, computes three-class classification metrics and supports manual review of explanation claims. Each experiment keeps a record of its configuration so that results can be investigated and reproduced where the model provider permits.

## Engineering approach

The backend uses FastAPI and SQLAlchemy with SQLite persistence and Alembic migrations. I implemented a deterministic offline adapter so a test can cover the evaluation pipeline without making external model calls. React provides the experiment and evidence-review interface. Tests cover backend metrics, data integrity and API workflows.

## What I learned / current limitations

The measurement policy matters as much as the interface: missing predictions must be visible, and unreviewed claims cannot be silently counted as supported. ModelAudit is still a local research prototype. It does not yet have a durable distributed job queue or a validated automatic evidence judge.

## Demonstration

The included 60-example benchmark is synthetic. Its role is to demonstrate and test the evaluation workflow—not establish a scientific model ranking. No real-world model benchmark results are claimed in this document.
