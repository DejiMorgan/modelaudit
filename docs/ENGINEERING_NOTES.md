# Engineering notes
**Arabome Obadiah Ayodeji** · ModelAudit v0.5 · November 2026

## What the project is for

I wanted an evaluation tool that separates a model getting an answer right from a model being able to justify that answer. They are not the same measurement. An explanation can sound plausible and still fail to cite enough evidence. ModelAudit lets me inspect both outcomes without treating the model's self-assessment as a reference answer.

## Decisions I made for the first release

I kept the execution engine local and the database in SQLite. This is enough to test the end-to-end evaluation workflow without introducing a job broker or distributed deployment. The tradeoff is that queued work is tied to a single API process; I would not expose this as a public multi-user service in its current form.

I also kept manual claim review separate from citation checks. Citing an existing evidence ID is not the same as making a sound argument. A complete evidence set is useful to measure, but it cannot replace human judgment about whether the explanation actually follows from the cited material.

## What I can verify

The repository contains automated checks for data validation, classification scores, provider response handling, job workflow, claim annotations and reporting. Version 0.5 adds tests for evidence-set completeness, missing annotations and deterministic mock experiments. The 60-case fixture is synthetic and is not presented as field research.

## Work still to do

The frontend build needs to be exercised on a configured Node environment. Live provider calls need credentialed integration tests. A stronger research release needs an independent human-labelled benchmark, annotation protocol, inter-rater agreement and a clearly controlled model comparison.

## Methodological limitation

Accuracy is computed on valid predictions and reported alongside coverage; unsupported-claim rate is calculated only for manually extracted and assessed claims. In a dataset where only obvious claims receive review, this may severely understate the true error rate. Results should always show counts and denominators.
