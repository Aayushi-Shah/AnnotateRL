# External Dependencies Reference


## OpenRouter API
- Base URL: https://openrouter.ai/api/v1 (OpenAI-compatible)
- Project uses FREE models: nvidia/nemotron-nano-9b-v2:free (primary)
- Free models are heavily rate-limited -- the fallback chain in _chat()
  exists because a single model frequently returns 429s
- Some free models are "thinking" models that put output in a `reasoning`
  attribute instead of `content`. The code handles this:
  `msg.content or getattr(msg, "reasoning", None) or ""`
- Stub-finetuned models (IDs starting with "stub-") are detected and
  replaced with the base model for API calls, but version_id is still
  tracked for lineage
- Get API key at: https://openrouter.ai/keys

## MinIO (S3-compatible local storage)
- Console at :9001 (minioadmin/minioadmin in dev)
- API at :9000
- `createbuckets` Docker service auto-creates `annotaterl-exports`
- Presigned URLs contain "localhost:9000" -- only work from host machine,
  not from other containers
- S3 key patterns:
  - exports/{dataset_id}/{export_id}.jsonl
  - finetune/{job_id}/training_data.jsonl

## asyncpg + SQLAlchemy async
- expire_on_commit=False on session factory -- critical for background tasks
  that read objects after commit
- SELECT FOR UPDATE SKIP LOCKED is Postgres-specific; won't work with SQLite
- Pool: pool_size=10, max_overflow=20

## python-jose (JWT)
- HS256 algorithm (symmetric key from SECRET_KEY)
- Token payload: sub (user_id), role, exp, type ("access")
- The "type" field prevents using a refresh token as an access token
- python-jose is in maintenance mode; consider PyJWT if security concerns arise

## passlib + bcrypt
- bcrypt==3.2.2 is pinned: passlib 1.7.4 is incompatible with bcrypt 4.x
- Do NOT upgrade bcrypt without also upgrading passlib

## TanStack Query (React Query v5)
- Default stale time: 30 seconds
- Query keys: "tasks", "queue", "my-tasks", "finetune-jobs", "finetune-models"
- Conditional refetchInterval pattern: only poll every 3s if active jobs exist,
  otherwise stop. Good pattern for status-watching pages.

## Zustand (v5)
- Auth state persisted to localStorage under key "annotaterl-auth"
- Uses `partialize` to only persist tokens + user (not hydration state)
- `_hasHydrated` flag prevents flash-of-unauthenticated-content on SSR
