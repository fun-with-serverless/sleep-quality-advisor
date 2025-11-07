# Streamlit Dashboard (Local)

This is a local-only Streamlit dashboard for visualizing temperature and humidity from the `EnvReadingsTable` in DynamoDB.

## Setup

1. Ensure your local AWS credentials can read DynamoDB (profile/region from your local config).
2. Create a `.env` file (you can copy from `.env.example`):

```
TABLE_NAME=<your-deployed-DynamoDB-table-name>
```

To find the physical table name quickly:

```
aws dynamodb list-tables --output table
# or, if you know the stack name:
aws cloudformation describe-stack-resources \
  --stack-name <your-backend-stack-name> \
  --logical-resource-id EnvReadingsTable \
  --query 'StackResources[0].PhysicalResourceId' --output text
```

## Install & Run (uv)

Inside this `streamlit/` directory:

```
uv sync
uv run task app
```

Alternatively:

```
uv run streamlit run app.py
```

## Features
- Date picker (defaults to today UTC)
- Bucket size: 5 minutes or 1 hour
- Percentiles: P50, P90, P99, Max (Average always shown)
- Summary for timeframe: min, max, std (temperature and humidity)

## Notes
- Table schema expected:
  - Partition key `day` (string, `YYYY-MM-DD` UTC)
  - Sort key `ts_min` (number, epoch minutes)
  - Attributes: `temp_c` (number), `humidity_pct` (number)

