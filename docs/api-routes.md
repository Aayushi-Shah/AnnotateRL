# API Routes

> Auto-generated on 2026-03-23 22:47 UTC. Do not edit manually.

## annotations (`/annotations`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `POST` | `/annotations` | `submit_annotation` | AnnotatorDep | 201 |
| `GET` | `/annotations` | `list_annotations` | CurrentUser | 200 |
| `GET` | `/annotations/{annotation_id}` | `get_annotation` | CurrentUser | 200 |

## auth (`/auth`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `POST` | `/auth/login` | `login` | public | 200 |
| `POST` | `/auth/refresh` | `refresh` | public | 200 |
| `POST` | `/auth/logout` | `logout` | public | 200 |
| `GET` | `/auth/me` | `me` | CurrentUser | 200 |
| `POST` | `/auth/register` | `register` | public | 200 |

## datasets (`/datasets`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `GET` | `/datasets` | `list_datasets` | ResearcherDep | 200 |
| `POST` | `/datasets` | `create_dataset` | ResearcherDep | 201 |
| `GET` | `/datasets/{dataset_id}` | `get_dataset` | ResearcherDep | 200 |
| `POST` | `/datasets/{dataset_id}/export` | `trigger_export` | ResearcherDep | 202 |
| `GET` | `/datasets/{dataset_id}/exports` | `list_exports` | ResearcherDep | 200 |

## finetune (`/finetune`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `GET` | `/finetune/jobs` | `list_jobs` | ResearcherDep | 200 |
| `GET` | `/finetune/jobs/{job_id}` | `get_job` | ResearcherDep | 200 |
| `POST` | `/finetune/jobs` | `trigger_finetune` | ResearcherDep | 202 |
| `GET` | `/finetune/models` | `list_model_versions` | ResearcherDep | 200 |
| `POST` | `/finetune/models/{version_id}/activate` | `activate_model_version` | ResearcherDep | 200 |

## metrics (`/metrics`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `GET` | `/metrics/overview` | `overview` | ResearcherDep | 200 |
| `GET` | `/metrics/throughput` | `throughput` | ResearcherDep | 200 |
| `GET` | `/metrics/reward-distribution` | `reward_distribution` | ResearcherDep | 200 |
| `GET` | `/metrics/annotators` | `annotator_stats` | ResearcherDep | 200 |

## queue (`/queue`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `GET` | `/queue` | `list_available` | AnnotatorDep | 200 |
| `POST` | `/queue/{task_id}/claim` | `claim_task` | AnnotatorDep | 201 |
| `GET` | `/queue/mine` | `my_assignments` | AnnotatorDep | 200 |
| `POST` | `/queue/{assignment_id}/abandon` | `abandon` | AnnotatorDep | 200 |

## tasks (`/tasks`)

| Method | Path | Function | Auth | Status |
|--------|------|----------|------|--------|
| `GET` | `/tasks` | `list_tasks` | CurrentUser | 200 |
| `POST` | `/tasks` | `create_task` | ResearcherDep | 201 |
| `GET` | `/tasks/{task_id}` | `get_task` | CurrentUser | 200 |
| `PATCH` | `/tasks/{task_id}` | `update_task` | ResearcherDep | 200 |
| `DELETE` | `/tasks/{task_id}` | `delete_task` | ResearcherDep | 204 |
| `POST` | `/tasks/{task_id}/publish` | `publish_task_endpoint` | ResearcherDep | 200 |
