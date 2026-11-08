# Security and data handling

ModelAudit is a **local research prototype**. It has no authentication layer and must not be exposed directly to the public internet.

- Bind the backend to `127.0.0.1` as shown in the README. Do not use `--host 0.0.0.0` for an unprotected deployment.
- Store provider API keys in the shell environment, not in code, datasets, screenshots, or source control.
- `.env.example` documents variable names only. The application does **not** automatically load `.env` files.
- External model adapters send claim and evidence text to their configured provider. Use public or approved data.
- Imported datasets and model responses are untrusted input. Never enter secrets in benchmark examples.
- Generated local SQLite databases and report files are excluded from Git by `.gitignore`.
- Provider integrations have mocked HTTP tests; live credentials have not been used for a verified end-to-end benchmark.

For a vulnerability report, use the repository's private security-reporting mechanism if enabled, rather than publishing secrets or exploit details in a public issue.
