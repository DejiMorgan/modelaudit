# ModelAudit
**AI Evaluation Workbench**  
**Author:** Arabome Obadiah Ayodeji  
**Repository release:** 0.5.1 · November 2026  
**Application API version:** 0.5.0 (evaluation behavior unchanged)

I built ModelAudit to study a gap between an AI model's answer and the evidence it uses to defend that answer. A model can predict the right label for a claim while giving a weak explanation. I wanted to measure both outcomes without relying on the model to grade itself.

ModelAudit is a local-first prototype built with Python, FastAPI, React, SQLite and pytest. It runs three-class claim verification experiments, tracks failures, and lets a reviewer annotate the factual claims in model-generated explanations.

## In this version

- Import JSON, JSONL or CSV datasets with explicit reference labels and evidence.
- Run a deterministic offline adapter, or configure an OpenAI-compatible or Anthropic endpoint.
- Review classification accuracy, macro-F1, confusion matrix, coverage and failures.
- Review explanations manually: supported, contradicted, insufficient evidence, not assessed.
- Measure complete cited evidence sets when a benchmark includes reference evidence annotations.
- Compare two runs and inspect paired disagreements on compatible datasets.
- Export experiment results as JSON or HTML with configuration provenance.
- Use a 60-example **synthetic** fixture to test the workflow (not a scientific benchmark).

## Project status

This repository is a functional **local research prototype**, not a production hosted service. The included 60-case dataset is synthetic; do not treat its results as independently validated research findings. CI is configured for Python tests, migrations and a frontend build, but workflow status is not known until the repository is pushed.

## Run locally

Requires Python 3.11+, Node.js 20+ and npm.

**Backend** (from project root):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend** (new terminal, from project root):

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 or inspect the API at http://127.0.0.1:8000/docs. Import `benchmarks/modelaudit_synthetic_60.json` and create a mock experiment.

**Backend tests:** from `backend`, run `python -m pytest -q`. A fresh copy previously passed 18 backend tests.

**Frontend verification:** from `frontend`, run `npm run build` after installing dependencies. The build was not verified in the release-building environment because the npm registry was unreachable.

**Database:** local SQLite files are Git-ignored. Back up the database before upgrades; the repository does not ship a user database.

## API addition in v0.5

`GET /api/v1/experiments/{id}/citation-metrics` reports citation coverage, validity and completeness for examples with annotated complete evidence sets. The comparison API also returns paired disagreements for its first two runs when their datasets and prompts match.

## Provider setup

See `.env.example` for supported variable names. Copying the file alone has no effect: **the app does not auto-load `.env` files**. Export variables in the shell before starting the server. For example:

```bash
export MODELAUDIT_OPENAI_API_KEY="your-api-key"
export MODELAUDIT_OPENAI_MODEL="your-model-id"
```

Never commit credentials. The mock adapter needs no provider key.


Model API credentials stay in backend environment variables. The available configuration variables are `MODELAUDIT_OPENAI_API_KEY`, `MODELAUDIT_OPENAI_MODEL`, `MODELAUDIT_OPENAI_BASE_URL`, `MODELAUDIT_ANTHROPIC_API_KEY` and `MODELAUDIT_ANTHROPIC_MODEL`. Live calls may cost money. Do not expose this single-process local service to the internet.

## Upgrade from v0.4

Stop the server and back up your existing SQLite database. Replace the source while retaining your database and environment, install dependencies, and run `alembic upgrade head`. **v0.5 makes no database schema changes**. Older experiments have no newly backfilled evidence annotations; their citation completeness is unavailable unless their datasets already contained complete evidence sets.

## Limits of the current build

The worker is an in-process thread, not a durable queue. Cancellation is cooperative. Claims are extracted and judged manually. The provider adapters have mocked-response tests, not confirmed live-provider integrations. Citation completeness is not a substitute for factual grounding, and missing gold evidence annotations are not treated as failures. The synthetic fixture cannot establish real-world model performance. Frontend production bundling must be verified separately wherever npm dependencies are installed.

More detail: `docs/ENGINEERING_NOTES.md`, `docs/PORTFOLIO_CASE_STUDY.md`, and `benchmarks/README.md`.

## Repository files

- `backend/` — FastAPI endpoints, adapters, scoring, Alembic migrations and tests.
- `frontend/` — React research workbench.
- `benchmarks/` — public-safe synthetic demonstration fixtures.
- `docs/ENGINEERING_NOTES.md` — scope, methodological decisions and limitations.
- `docs/PORTFOLIO_CASE_STUDY.md` — concise project case study.
- `docs/GITHUB_RELEASE.md` — publication steps and release notes.
- `.github/workflows/ci.yml` — migration, test and frontend-build checks.

## Attribution and licence

**Arabome Obadiah Ayodeji** is the named project author and maintainer. This repository includes an MIT licence; review its reuse permissions before publishing. Technical claims here reflect the implemented code and locally checked tests, not unperformed independent research.
