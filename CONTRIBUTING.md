# Contributing

ModelAudit is maintained as a focused evaluation research prototype by **Arabome Obadiah Ayodeji**.

## Local checks

```bash
cd backend
python -m pytest -q
alembic upgrade head
```

In a separate terminal:

```bash
cd frontend
npm install
npm run build
```

Before proposing a change, include a reproducible test for scoring or adapter behavior. Never let a model under evaluation write or modify reference labels. Preserve denominators and report missing judgments as missing; do not impute support.

For substantive changes, explain the methodological impact in the pull request. Use synthetic or public examples only. See `SECURITY.md` before adding integrations or using external providers.
