# Data Flow Diagrams

These diagrams capture flows that cross multiple files and async boundaries.
They show the non-obvious "what calls what and when" that is hard to see
from reading individual files.


## 1. Closed-Loop RLHF Cycle

The full loop from task creation to model improvement. Key non-obvious aspect:
the fine-tuning trigger is a BackgroundTask fired from the annotation submission
endpoint, NOT from the queue service.

    Researcher                  Backend                         External
    ---------                  -------                         --------
    POST /tasks
     |
    POST /tasks/{id}/publish
     |----> task.status = available
     |----> Redis ZADD (priority queue)
     |----> BackgroundTask: ai_agent.generate_for_task ------> OpenRouter API
     |          |                                               (free models)
     |          +--> _get_active_model(db)
     |          |     checks ModelVersion.is_active
     |          |     falls back to DEFAULT_MODEL
     |          +--> writes to task.metadata_
     |               (model_response / response_a,b / context)
     |
    Annotator
    ---------
    GET /queue  (reads from DB, not Redis directly)
     |
    POST /queue/{id}/claim
     |----> SELECT FOR UPDATE SKIP LOCKED
     |----> creates TaskAssignment (4h TTL)
     |
    POST /annotations
     |----> creates Annotation + RewardSignal
     |----> assignment.status = completed
     |----> if completed_count >= annotations_required:
     |        task.status = completed
     |        remove from Redis queue
     |        BackgroundTask: maybe_trigger_finetune  <--- TRIGGER POINT
     |            |
     |            +--> gating: FINETUNE_ENABLED?
     |            +--> gating: no active job already running?
     |            +--> creates FineTuningJob
     |            +--> run_finetuning_job:
     |                  Phase 1: _build_training_rows (all completed annotations)
     |                  Phase 2: upload JSONL to S3 (finetune/{job_id}/...)
     |                  Phase 3: provider.start_training
     |                  Phase 4: create ModelVersion (deactivate others)
     |
     +----> Next task publish uses the NEW model version
            (ai_agent reads ModelVersion.is_active)


## 2. Annotation Submission -- Detailed Internal Flow

The most complex single endpoint. Non-obvious: the completed_count check
uses the count BEFORE commit, so code checks (completed_count + 1).
Also: finetune import is done inline (lazy) to avoid circular imports.

    POST /annotations (annotations.py:submit_annotation)
     |
     +-- Validate: assignment exists, belongs to annotator
     +-- Validate: assignment.status == in_progress
     +-- Validate: not expired (else mark expired + return 400)
     +-- Validate: no duplicate annotation for this assignment (409)
     |
     +-- CREATE Annotation (flush for ID)
     +-- CREATE RewardSignal (linked to annotation)
     +-- assignment.status = completed
     |
     +-- SELECT COUNT completed assignments for this task
     |   NOTE: count is BEFORE this commit, so code does:
     |         if (completed_count + 1) >= task.annotations_required
     |
     +-- if threshold reached:
     |     task.status = completed
     |     LAZY IMPORT: from app.core.redis import get_redis
     |     LAZY IMPORT: from app.services.queue import remove_task_from_queue
     |     LAZY IMPORT: from app.services.finetune import maybe_trigger_finetune
     |     ZREM from Redis queue
     |     background_tasks.add_task(maybe_trigger_finetune, task.id)
     |
     +-- COMMIT all changes atomically
     +-- RETURN annotation response


## 3. Background Task Pattern (shared by 3 services)

All three background services open their own AsyncSessionLocal because
FastAPI's request-scoped session is closed by the time the background
task runs. This is a critical design constraint.

    Request handler returns response to client
     |
     +-- FastAPI fires BackgroundTask AFTER response sent
     |
     +-- Background task function runs:
     |     async with AsyncSessionLocal() as db:
     |       (creates independent DB session)
     |       (request session is ALREADY CLOSED)
     |       ... do work ...
     |       await db.commit()
     |
     +-- Services using this pattern:
     |     ai_agent.generate_for_task   -- generates AI responses
     |     export.run_export            -- builds JSONL, uploads to S3
     |     finetune.run_finetuning_job  -- prepares data, runs training
     |
     +-- All write status transitions for observability:
           pending -> running/preparing_data -> done/completed | failed


## 4. Auth Token Flow

Non-obvious: refresh tokens stored as SHA-256 hashes (not raw).
Frontend auto-retries exactly ONCE on 401 before redirecting to /login.
Zustand store persisted to localStorage with partialize.

    LOGIN:
      Browser --> POST /auth/login {email, password}
       --> Backend: verify_password(plain, hashed)
       --> create_access_token(user_id, role)  [15min expiry, HS256]
       --> create_refresh_token()  [returns (raw, sha256_hash)]
       --> Store sha256_hash in refresh_tokens table
       --> Response: {access_token, refresh_token: RAW}
       --> Browser: Zustand.setAuth() --> localStorage["annotaterl-auth"]

    API CALL:
      apiFetch(url, opts)
       --> Injects: Authorization: Bearer {access_token}
       --> On 401:
            POST /auth/refresh {refresh_token: RAW}
             --> Backend: hash(raw) --> lookup in DB --> check not revoked
             --> New access_token
             --> Retry original request ONCE
           If refresh fails --> store.logout() --> redirect /login

    CRITICAL: refresh token in API = RAW. Backend hashes to look up.


## 5. Docker Network Topology

Non-obvious: NEXT_PUBLIC_API_URL must be localhost:8000 because API calls
come from the BROWSER (not the frontend container). DB_HOST inside Docker
is "postgres" (container name), not "localhost".

    Host machine (localhost)
     |
     +-- :3000 --> frontend container (Next.js dev)
     |              NEXT_PUBLIC_API_URL=http://localhost:8000
     |              API calls go: BROWSER --> host:8000
     |              NOT: container --> container
     |              Volume: ./frontend:/app (hot reload)
     |              Excluded: /app/node_modules (named volume)
     |
     +-- :8000 --> backend container (FastAPI + uvicorn)
     |              DB_HOST=postgres  (Docker internal network)
     |              DB_PORT=5432      (internal, NOT 5433)
     |              REDIS_URL=redis://redis:6379
     |              S3_ENDPOINT_URL=http://minio:9000
     |              Volume: ./backend:/app (hot reload)
     |
     +-- :5433 --> postgres container (internal :5432)
     |              Data: named volume pgdata
     |
     +-- :6379 --> redis container
     |              Data: named volume redisdata
     |
     +-- :9000 --> minio API
     +-- :9001 --> minio console (minioadmin/minioadmin)
     |
     +-- createbuckets (one-shot, fire-and-forget)
          mc mb myminio/annotaterl-exports
          Depends on: minio healthy
          WARNING: fails silently if minio not ready
