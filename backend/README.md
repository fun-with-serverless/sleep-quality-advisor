# Sleep Quality Advisor - Backend

Serverless backend using AWS SAM: API Gateway (REST) → SQS → Lambda → DynamoDB, with a Lambda authorizer.

## Dev setup (uv)

- Install uv via Homebrew:
  
  ```bash
  brew install uv
  ```

- Install & pin Python:
  
  ```bash
  uv python install 3.12
  uv python pin 3.12
  ```

- Sync deps:
  
  ```bash
  cd backend
  uv sync --all-extras
  ```

## Quality checks

- Quick checks:
  ```bash
  uv run task check
  ```
  Runs lint, format (check), mypy, tests, and `sam validate`.

- Auto-fix and re-verify:
  ```bash
  uv run task check-fix
  ```
  Applies lint/format fixes, then runs mypy, tests, and `sam validate`.

## Build

Generate a runtime-only `src/requirements.txt` from the locked env and run SAM build:

```bash
uv run task build
```

## Deploy

Deploy the stack (region/profile are picked from `samconfig.toml` unless overridden):

```bash
uv run task deploy
```

## Post-deployment

Fill in the following secrets/parameters in AWS:

- SSM Parameter (String): `/fitbit/client/id` — Fitbit client ID
- Secrets Manager: `fitbit/client/secret` — Fitbit client secret
- Secrets Manager: `ingest/shared/secret` — shared header secret for `X-Secret`

Notes:
- If your org enforces encryption for `/fitbit/*`, store as SecureString and provide a KMS key.
- The stack bootstraps placeholder secrets/parameter, but you must set real values after deploy.

## Structure
- `template.yaml`: SAM resources
- `src/`: Lambda handlers and shared code
- `src/common/`: shared helpers (config, models, ddb)
- `src/env_ingest_authorizer/handler.py`: validates `X-Secret`
- `src/env_ingest_consumer/handler.py`: SQS → DynamoDB writer
- `src/fitbit_callback/handler.py`: OAuth callback (bootstrap placeholder)
- `src/fitbit_fetch/handler.py`: scheduled fetch (placeholder)

## Notes
- Do not run `sam build` / `sam deploy` yet.
- Default region in `samconfig.toml` is `us-east-1`.
