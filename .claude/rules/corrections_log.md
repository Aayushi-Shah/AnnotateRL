# Corrections Log (Memory Loop)

Append new entries at the TOP. Each entry follows this format:
- **Date**: YYYY-MM-DD
- **Category**: lint | build | logic | api | docker | style | scope
- **What went wrong**: concise description
- **Correct approach**: what to do instead
- **Severity**: low | medium | high (high = caused user frustration or wasted time)

Cap at ~15 entries. Archive or remove entries that are no longer relevant.

---

## 2026-03-23 logic: completed_count + 1 in annotation submission
**Wrong:** Checking `if completed_count >= task.annotations_required` without accounting for the uncommitted current assignment
**Right:** The code correctly does `(completed_count + 1) >= task.annotations_required` because the current assignment status change hasn't been committed yet. Always account for uncommitted state when checking thresholds in the same transaction.
**Why:** The count query returns pre-commit state. Missing this leads to tasks never completing.
**Severity:** high

## 2026-03-23 docker: frontend API URL is browser-relative
**Wrong:** Setting NEXT_PUBLIC_API_URL to http://backend:8000 (container name)
**Right:** Must be http://localhost:8000 because API calls originate from the user's BROWSER, not from the frontend container. This is client-side fetch, not SSR.
**Why:** Next.js App Router pages render client-side; fetch calls run in the browser, which can't resolve Docker container names.
**Severity:** high

## 2026-03-23 build: npm lint on host corrupts Docker dev server
**Wrong:** Running `npm run lint` or `npm run build` on the host while `docker compose up` is running
**Right:** This overwrites `.next` on the host (via volume mount), which breaks the Docker dev server. Either stop the container first OR run inside: `docker compose exec frontend npm run lint`
**Why:** The volume mount shares ./frontend between host and container. Writing .next on host overwrites the container's compiled cache.
**Severity:** medium

## 2026-03-23 logic: SQLAlchemy JSONB mutation detection
**Wrong:** Mutating task.metadata_ dict in-place and expecting SQLAlchemy to detect the change
**Right:** Must use `flag_modified(task, "metadata_")` after in-place mutation, OR reassign: `task.metadata_ = dict(metadata)`. The codebase uses both patterns.
**Why:** SQLAlchemy tracks identity of mutable objects, not their contents. In-place dict mutation doesn't change identity.
**How to apply:** Any time you modify a JSONB column in-place, add `from sqlalchemy.orm import flag_modified` and call it.
**Severity:** medium

## 2026-03-23 api: lazy imports in annotations.py for circular dependency avoidance
**Wrong:** Adding top-level imports from finetune, redis, or queue in annotations.py
**Right:** The finetune, redis, and queue imports in annotations.py are done INSIDE the endpoint function body to avoid circular import chains.
**Why:** Import chain: annotations -> finetune -> models -> annotations would fail at module load time.
**How to apply:** When adding cross-service imports in API routes, do them inside the function body, not at module level.
**Severity:** medium

## 2026-03-23 lint: SQLAlchemy boolean == True triggers E712
**Wrong:** Writing `ModelVersion.is_active == True` and getting linter complaints
**Right:** SQLAlchemy requires `== True` for boolean column filtering (you cannot use `is True` with column objects). Suppress with `# noqa: E712` if your linter flags it.
**Why:** Python `is` operator checks identity, not value. SQLAlchemy columns override `__eq__` to produce SQL expressions, so `==` is correct.
**Severity:** low

## 2026-03-23 docker: DB_PORT mismatch between host and container
**Wrong:** Using DB_PORT=5433 inside the Docker backend container
**Right:** docker-compose.yml overrides DB_HOST=postgres and DB_PORT=5432 for the backend container. The host-side port 5433 is only for direct host access. New services inside Docker should use postgres:5432.
**Why:** Docker port mapping (5433:5432) only applies to host access. Container-to-container uses the internal port.
**Severity:** medium
