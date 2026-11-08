# Publishing ModelAudit v0.5.1 on GitHub

**Author:** Arabome Obadiah Ayodeji  
**Release candidate:** v0.5.1  
**Scope:** Repository readiness, CI, safety defaults and documentation; evaluation algorithms unchanged.

## Before pushing

1. Keep `.env`, local database files, test reports with private data, and API keys out of Git.
2. Review the MIT licence. It allows reuse, modification and distribution with attribution. Change or remove it **before publication** if that does not match the intended licensing policy.
3. Run backend tests and migration locally.
4. Run `npm install && npm run build` in `frontend` when registry access is available. The frontend build was not independently verified while assembling this package.
5. Inspect the sample benchmark; all 60 examples are synthetic.

## Create the public repository

In GitHub, create an empty repository named `modelaudit` (do not initialize it with a README or .gitignore). Then, from the extracted **modelaudit** directory:

```bash
git init
git branch -M main
git add .
git status --short
git commit -m "Release ModelAudit v0.5.1 research prototype"
git remote add origin https://github.com/YOUR_USERNAME/modelaudit.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username. GitHub may require authentication through an SSH key or a credential manager.

## After pushing

1. Open the **Actions** tab and ensure the backend and frontend checks run. Do not claim a green frontend build until this has passed.
2. Add a short repository description and topics: `ai-evaluation`, `fastapi`, `react`, `evidence-grounding`, `research`, `pytest`.
3. Use a screenshot of the real application after starting and testing the frontend; do not use a fabricated UI screenshot.
4. Create release tag `v0.5.1` after CI is green, with the release notes below.
5. Share the repository link in your portfolio. Describe it as a local-first **research prototype**, not as a proven production AI-safety benchmark.

## Suggested release notes

**ModelAudit v0.5.1 — GitHub-ready research prototype**

ModelAudit evaluates three-class AI claim verification, evidence citation completeness and human-reviewed explanation support. This release packages the v0.5 workbench with CI configuration, Git hygiene, a sample environment template, security guidance and clearer engineering documentation. The bundled 60-case dataset is synthetic and serves as a repeatable functional fixture, not a published scientific benchmark.

**Known limitations:** single-process execution, cooperative cancellation, manual explanation annotation, and provider integrations tested with mocked HTTP responses. Real provider runs and the frontend production build must be verified separately.
