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
