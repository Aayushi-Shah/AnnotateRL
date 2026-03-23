# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AnnotateRL is an RLHF/RLAIF data collection platform. Researchers create tasks; annotators claim and complete them; the platform exports labeled data as JSONL for fine-tuning pipelines.

**Goal: closed-loop RLHF.** Once annotators rate a task, that signal should automatically trigger a fine-tuning run so the model improves from each round of human feedback — no manual export/train step required.

## Commands
### Full stack (recommended)
```bash
# From project root — starts postgres, redis, minio, backend, frontend
docker compose up
```

### Backend (local)
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload        # dev server on :8000
alembic upgrade head                  # run migrations
python seed.py                        # seed demo users and tasks
```

### Frontend (local)
```bash
cd frontend
npm run dev      # dev server on :3000
npm run lint
npm run build
```

### Environment
Copy `.env.example` to `.env` at the project root. `DATABASE_URL` is auto-assembled from `DB_*` vars if not set explicitly. `OPENROUTER_API_KEY` is optional — when set, AI auto-generates model responses on task publish using free models via OpenRouter.

## Build & Validation

Run these checks after making any changes and fix all errors before considering the task done. Repeat each failing command until it exits 0.

### Frontend
**Important:** If Docker dev server is running, run these inside the container to avoid overwriting `.next` on the host (which breaks the dev server). Stop the container first, or use `docker compose exec frontend npm run lint`.
```bash
cd frontend
npm run lint     # fix all ESLint errors
npm run build    # fix all TypeScript / Next.js build errors
```

Both must exit 0. When a command fails:
1. Read the full error output.
2. Fix every reported error.
3. Re-run until it passes.

### Backend
```bash
cd backend
source .venv/bin/activate
python -m py_compile $(find app -name "*.py")    # syntax-check all modules
```

Fix any syntax errors before moving on. Do not suppress errors with `# type: ignore` unless the source is an untyped third-party library.

### Docker smoke test (run when Dockerfile or docker-compose.yml changes)
```bash
docker compose build
docker compose up -d && sleep 5
curl -sf http://localhost:8000/health
curl -sf http://localhost:3000
docker compose down
```

All four commands must succeed.

## Architecture

### Backend (`backend/`)
FastAPI + SQLAlchemy (async/asyncpg) + PostgreSQL + Redis + S3/MinIO.

**Layer structure:**
- `app/core/` — infrastructure singletons: `config.py` (pydantic-settings), `db.py` (async engine + session), `redis.py`, `auth.py` (JWT + bcrypt), `s3.py`, `deps.py` (FastAPI dependency injection)
- `app/models/` — SQLAlchemy ORM models (source of truth for schema)
- `app/schemas/` — Pydantic request/response models
- `app/api/v1/` — FastAPI routers, one file per resource
- `app/services/` — business logic: `queue.py`, `export.py`, `ai_agent.py`
- `alembic/versions/` — migration files

**Key dependency aliases** (use these in route signatures):
- `DbDep` — async DB session
- `CurrentUser` — authenticated user (any role)
- `ResearcherDep` — requires `researcher` or `admin` role
- `AnnotatorDep` — requires `annotator` or `admin` role

### Frontend (`frontend/`)
Next.js 14 App Router + TypeScript + TanStack Query + Zustand + Tailwind + Radix UI.

**Key files:**
- `src/lib/api.ts` — all API calls via a central `apiFetch` that auto-refreshes tokens on 401
- `src/lib/types.ts` — TypeScript interfaces mirroring backend schemas
- `src/app/login/` — unauthenticated entry point
- `src/app/researcher/` — researcher UI (task creation, datasets, metrics)
- `src/app/annotator/` — annotator UI (queue, workspace, my-tasks)
- `src/components/annotations/` — signal-type-specific annotation UI components

### Data model
```
User (researcher | annotator | admin)
  └── Task (draft → available → completed)
        └── TaskAssignment (in_progress → completed | expired | abandoned)
              └── Annotation
                    └── RewardSignal (rating | comparison | correction | binary)

Dataset (filter config) → DatasetExport (JSONL → S3)
```

### Task queue
Redis sorted set (`annotaterl:task_queue`) holds `task_id → priority` scores. On claim, the backend reads the top candidates from Redis then uses `SELECT FOR UPDATE SKIP LOCKED` in Postgres to prevent double-claiming under concurrent load. Assignments expire after 4 hours; stale claims are cleaned on startup via `expire_stale_claims`.

### Task lifecycle & AI generation
1. Researcher creates a task (status: `draft`)
2. Researcher publishes → status becomes `available`, task is pushed to Redis queue
3. If `OPENROUTER_API_KEY` is set, a `BackgroundTask` calls `ai_agent.generate_for_task`, which uses OpenRouter (free models) to populate `task.metadata_`:
   - `reasoning`/`coding`: `metadata.model_response`
   - `comparison`: `metadata.response_a` and `metadata.response_b` (contrasting styles)
   - `correction`: generates a subtly flawed response stored in `task.context`
4. Annotator claims task → `TaskAssignment` created; annotator sees AI response and submits feedback
5. When `annotations_required` completions are reached, task status → `completed`

### Reward signals
Each annotation produces one `RewardSignal` with a JSONB `value`. Signal types and their value shapes:
- `rating` → `{ score: int }` (normalized to float for export)
- `binary` → `{ accept: bool, justification?: str }` (1.0 / 0.0)
- `comparison` → `{ chosen: "A" | "B", rationale?: str }` (1.0 if A else 0.0)
- `correction` → `{ edited: str }` (no scalar reward)

### Dataset export
Datasets are defined by a `filter_config` (task_type, date range, annotator IDs, min_rating). Triggering an export spawns a background task that queries annotations + reward signals, builds JSONL in HuggingFace datasets format, and uploads to `S3_BUCKET` via boto3 (pointed at MinIO locally).

### Closed-loop fine-tuning
Fully automated RLHF loop — annotation → fine-tune → new model, no manual steps:

1. Annotator submits signal → `RewardSignal` written to DB
2. When `annotations_required` completions are reached → task status → `completed`
3. `annotations.py` fires `BackgroundTask: maybe_trigger_finetune` (gated by `FINETUNE_ENABLED` and no overlapping job)
4. `app/services/finetune.py` builds training JSONL, uploads to S3, calls `TrainingProvider.start_training`
5. New `ModelVersion` created (is_active=True); `ai_agent.generate_for_task` uses it for subsequent tasks

**Key files:** `app/api/v1/annotations.py` (trigger), `app/services/finetune.py` (job runner), `app/models/finetune.py` (FineTuningJob + ModelVersion), `app/api/v1/finetune.py` (manual trigger + activation endpoints)

### Auth
Short-lived JWT access tokens (15 min, HS256). Refresh tokens stored as SHA-256 hashes in `refresh_tokens` table. Frontend auto-retries on 401 using the stored refresh token before redirecting to `/login`.

## Working with this codebase

- Always plan before implementing — use plan mode for non-trivial changes
- Zero tolerance for broken builds: lint and build must both exit 0
- Prefer automation over manual steps; if something is done twice, automate it
- Shared team knowledge lives in `.claude/rules/` (auto-loaded); auto-generated reference docs in `docs/` (updated by CI on push to main)
- When a mistake is made or corrected, append an entry to `.claude/rules/corrections_log.md`
- Typed Python (Pydantic schemas) and strict TypeScript throughout — do not introduce `any` or untyped patterns
