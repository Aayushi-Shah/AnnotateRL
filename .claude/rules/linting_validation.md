# Linting and Validation Gotchas

The basic commands are in CLAUDE.md. This file explains WHY things fail
and the non-obvious fixes.


## Frontend (Next.js + TypeScript + ESLint)

### ESLint config
- Uses `next/core-web-vitals` (strict ruleset)
- Config file: `.eslintrc.json` (extends core-web-vitals only, no custom rules)
- Failures come from Next.js defaults, not custom overrides

### Known fragile patterns
1. **Unused imports**: ESLint flags any unused import. When removing a feature,
   also remove imports from api.ts, types.ts, and referencing pages.

2. **JSONB types**: Frontend uses `Record<string, unknown>` for JSONB fields
   (metadata, signal_value, filter_config). Do NOT change to `any` -- ESLint
   will complain. The pattern is deliberate.

3. **React hooks exhaustive deps**: AnnotationWorkspace has a tick counter
   (setInterval) with empty dependency array. Do not add dependencies -- it's
   a timer, not a reactive effect.

### Build vs Lint ordering
Run lint FIRST, then build. Lint catches import errors that cause cryptic
build failures. Build catches type errors that lint ignores.

### The Docker .next problem (CRITICAL)
Running `npm run build` or `npm run lint` on HOST while Docker dev server
is running writes into `./frontend/.next/` which is volume-mounted.
This corrupts the dev server.
**Fix:** Stop Docker first, OR `docker compose exec frontend npm run lint`.


## Backend (Python)

### py_compile limitations
`python -m py_compile` only checks SYNTAX. It does NOT catch:
- Import errors (circular imports, missing modules)
- Type errors
- Runtime configuration issues (missing env vars)

### Known fragile patterns
1. **Circular imports**: Key lazy-import locations:
   - `annotations.py` lazily imports finetune, redis, queue
   - `ai_agent.py` lazily imports finetune.ModelVersion
   Adding cross-service imports at module level WILL cause circular failures
   at startup. Always import inside the function body.

2. **Alembic autogenerate**: After changing models:
   `alembic revision --autogenerate -m "description"` then `alembic upgrade head`
   Make sure new models are imported in `models/__init__.py` or autogenerate
   won't see them.

3. **pydantic-settings fails at import time**: The Settings class crashes if
   required env vars are missing. py_compile passes but uvicorn fails.
   Required vars: REDIS_URL, SECRET_KEY, S3_BUCKET, AWS_ACCESS_KEY_ID,
   AWS_SECRET_ACCESS_KEY. For local dev without Docker, you need `.env`.

4. **Enum values stored as strings**: task_type, status, role are plain strings
   in Postgres (not Postgres ENUMs). DB won't enforce valid values -- validation
   happens in Pydantic schemas. If adding a new task_type, update BOTH the
   Python enum AND the schema.


## Docker Validation

### Smoke test pitfalls
- `/health` only tests FastAPI is up, NOT database connectivity. Use `/ready`
  to verify DB + Redis.
- Frontend takes ~10-15s in dev mode (Next.js compilation). The `sleep 5` in
  CLAUDE.md may not be enough on slow machines.
- `createbuckets` is fire-and-forget. If MinIO isn't healthy when it runs,
  the bucket won't exist and S3 uploads fail with a generic boto3 ClientError
  that doesn't mention the missing bucket clearly.
