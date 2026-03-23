# Environment Variables

> Auto-generated on 2026-03-23 23:05 UTC. Do not edit manually.

## From `.env.example`

| Variable | Example Value | Notes |
|----------|---------------|-------|
| `DB_USER` | `annotaterl` |  |
| `DB_PASSWORD` | `***` |  |
| `DB_NAME` | `annotaterl` |  |
| `DB_PORT` | `5433        # use a port != 5432 if local postgres is already running` |  |
| `REDIS_URL` | `redis://localhost:6379/0` |  |
| `SECRET_KEY` | `change-me-in-production` |  |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` |  |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` |  |
| `OPENROUTER_API_KEY` | `***` |  |
| `S3_BUCKET` | `annotaterl-exports` |  |
| `S3_ENDPOINT_URL` | `http://localhost:9000` |  |
| `AWS_ACCESS_KEY_ID` | `***` |  |
| `AWS_SECRET_ACCESS_KEY` | `***` |  |
| `S3_REGION` | `us-east-1` |  |
| `FINETUNE_ENABLED` | `true` |  |
| `FINETUNE_PROVIDER` | `stub          # "stub" simulates training for dev/learning` |  |
| `FINETUNE_MIN_ROWS` | `1             # minimum training examples to start a job` |  |
| `CORS_ORIGINS` | `["http://localhost:3000"]` |  |

## From `config.py` Settings class

| Setting | Type | Default |
|---------|------|---------|
| `DB_USER` | `str` | `'annotaterl'` |
| `DB_PASSWORD` | `str` | `'annotaterl'` |
| `DB_NAME` | `str` | `'annotaterl'` |
| `DB_HOST` | `str` | `'localhost'` |
| `DB_PORT` | `int` | `5433` |
| `DATABASE_URL` | `str` | `''` |
| `REDIS_URL` | `str` | `required` |
| `SECRET_KEY` | `str` | `required` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `30` |
| `ANTHROPIC_API_KEY` | `str | None` | `None` |
| `OPENROUTER_API_KEY` | `str | None` | `None` |
| `S3_BUCKET` | `str` | `required` |
| `S3_ENDPOINT_URL` | `str | None` | `None` |
| `AWS_ACCESS_KEY_ID` | `str` | `required` |
| `AWS_SECRET_ACCESS_KEY` | `str` | `required` |
| `S3_REGION` | `str` | `'us-east-1'` |
| `FINETUNE_ENABLED` | `bool` | `True` |
| `FINETUNE_PROVIDER` | `str` | `'stub'` |
| `FINETUNE_MIN_ROWS` | `int` | `1` |
| `CORS_ORIGINS` | `list[str]` | `['http://localhost:3000']` |
