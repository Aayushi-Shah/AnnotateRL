# AnnotateRL — Claude Working Memory

## What This Is
Internal RLHF/RLAIF data collection platform. Three surfaces: task management, annotation workspace, training observability.
Portfolio project targeting Anthropic RL org — mirrors their internal stack.

## Phase Status
- [x] Phase 1: Core backend (FastAPI + SQLAlchemy + Redis + JWT + all APIs)
- [x] Phase 2: Annotation UI (Next.js — researcher + annotator views)
- [ ] Phase 3: Observability dashboard (metrics API + Recharts + Grafana)
- [ ] Phase 4: Export + deploy (HuggingFace JSONL, Docker, GCP/AWS, Loom)

## Running Locally
```bash
cp backend/.env.example backend/.env   # fill in secrets
docker compose up                       # starts postgres, redis, minio, backend
# backend auto-runs: alembic upgrade head then uvicorn
```

API docs: http://localhost:8000/docs
MinIO console: http://localhost:9001 (minioadmin/minioadmin)

## Project Layout
```
annotate-rl/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # route handlers (auth, tasks, queue, annotations, metrics, datasets)
│   │   ├── core/            # config, db, redis, auth, deps
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # business logic (queue, export)
│   ├── alembic/             # migrations
│   └── main.py
├── frontend/                # Next.js (Phase 2)
└── docker-compose.yml
```

## Key Architectural Decisions
- **UUID PKs everywhere** — never int, painful to migrate after data exists
- **JSONB for reward_signals.value** — polymorphic: rating={score:4}, comparison={chosen:"A"}, correction={edited:"..."}, binary={accept:true}
- **Redis sorted set for queue** — `annotaterl:task_queue`, score = priority. Annotators ZPOPMAX, then verify+write in Postgres
- **SELECT FOR UPDATE SKIP LOCKED** — prevents double-claiming under concurrent load
- **Refresh tokens stored hashed in DB** — SHA-256 hash, so they can be revoked without rotating JWT secret
- **Access token: 15 min, Refresh token: 30 days**
- **annotations_required on Task** — default 1, but tasks can require N annotations for IAA
- **BackgroundTasks for exports (MVP)** — replace with Celery in Phase 4
- **S3 key structure: exports/{dataset_id}/{export_id}.jsonl** — don't change once files exist
- **All config via pydantic-settings** — never hardcode secrets

## Stack
- Backend: FastAPI (async) + SQLAlchemy 2.0 + asyncpg + Alembic
- Queue: Redis (redis.asyncio)
- Storage: S3-compatible (boto3) — MinIO locally
- Auth: JWT (python-jose) + bcrypt (passlib)
- Frontend: Next.js 14 + TypeScript + Tailwind + shadcn/ui + TanStack Query

## Roles
- `researcher` — create/publish tasks, view all annotations, export datasets
- `annotator` — claim tasks from queue, submit annotations
- `admin` — all permissions
