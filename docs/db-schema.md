# Database Schema

> Auto-generated on 2026-03-23 22:47 UTC. Do not edit manually.

## `Annotation` (table: `annotations`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `task_id` | `Mapped[uuid.UUID]` | indexed, FK(tasks.id) |
| `assignment_id` | `Mapped[uuid.UUID]` | unique, FK(task_assignments.id) |
| `annotator_id` | `Mapped[uuid.UUID]` | indexed, FK(users.id) |
| `response` | `Mapped[str]` | - |
| `created_at` | `Mapped[datetime]` | has default |
| `updated_at` | `Mapped[datetime | None]` | nullable |
| `metadata_` | `Mapped[dict]` | has default |
| `task` | `Mapped['Task']` | - |
| `assignment` | `Mapped['TaskAssignment']` | - |
| `annotator` | `Mapped['User']` | - |
| `reward_signal` | `Mapped['RewardSignal | None']` | nullable |

**Relationships:** `task` -> `Mapped['Task']` | `assignment` -> `Mapped['TaskAssignment']` | `annotator` -> `Mapped['User']` | `reward_signal` -> `Mapped['RewardSignal | None']`

## `RewardSignal` (table: `reward_signals`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `annotation_id` | `Mapped[uuid.UUID]` | unique, FK(annotations.id) |
| `signal_type` | `Mapped[str]` | - |
| `value` | `Mapped[dict]` | - |
| `created_at` | `Mapped[datetime]` | has default |
| `annotation` | `Mapped['Annotation']` | - |

**Relationships:** `annotation` -> `Mapped['Annotation']`

## `Dataset` (table: `datasets`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `name` | `Mapped[str]` | - |
| `description` | `Mapped[str | None]` | nullable |
| `filter_config` | `Mapped[dict]` | has default |
| `created_by` | `Mapped[uuid.UUID]` | FK(users.id) |
| `created_at` | `Mapped[datetime]` | has default |
| `creator` | `Mapped['User']` | - |
| `exports` | `Mapped[list['DatasetExport']]` | - |

**Relationships:** `creator` -> `Mapped['User']` | `exports` -> `Mapped[list['DatasetExport']]`

## `DatasetExport` (table: `dataset_exports`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `dataset_id` | `Mapped[uuid.UUID]` | indexed, FK(datasets.id) |
| `format` | `Mapped[str]` | has default |
| `status` | `Mapped[str]` | has default |
| `s3_key` | `Mapped[str | None]` | nullable |
| `row_count` | `Mapped[int | None]` | nullable |
| `error_message` | `Mapped[str | None]` | nullable |
| `created_at` | `Mapped[datetime]` | has default |
| `completed_at` | `Mapped[datetime | None]` | nullable |
| `dataset` | `Mapped['Dataset']` | - |

**Relationships:** `dataset` -> `Mapped['Dataset']`

## `ModelVersion` (table: `model_versions`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `version_tag` | `Mapped[str]` | unique |
| `base_model` | `Mapped[str]` | has default |
| `finetuned_model_id` | `Mapped[str | None]` | nullable |
| `is_active` | `Mapped[bool]` | has default |
| `training_job_id` | `Mapped[uuid.UUID | None]` | nullable, FK(fine_tuning_jobs.id) |
| `created_at` | `Mapped[datetime]` | has default |
| `training_job` | `Mapped['FineTuningJob | None']` | nullable |

**Relationships:** `training_job` -> `Mapped['FineTuningJob | None']`

## `FineTuningJob` (table: `fine_tuning_jobs`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `status` | `Mapped[str]` | has default |
| `trigger_task_id` | `Mapped[uuid.UUID | None]` | nullable, FK(tasks.id) |
| `training_data_s3_key` | `Mapped[str | None]` | nullable |
| `training_data_rows` | `Mapped[int | None]` | nullable |
| `external_job_id` | `Mapped[str | None]` | nullable |
| `config` | `Mapped[dict]` | has default |
| `error_message` | `Mapped[str | None]` | nullable |
| `created_at` | `Mapped[datetime]` | has default |
| `started_at` | `Mapped[datetime | None]` | nullable |
| `completed_at` | `Mapped[datetime | None]` | nullable |
| `trigger_task` | `Mapped['Task | None']` | nullable |
| `model_version` | `Mapped['ModelVersion | None']` | nullable |

**Relationships:** `trigger_task` -> `Mapped['Task | None']` | `model_version` -> `Mapped['ModelVersion | None']`

## `Task` (table: `tasks`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `title` | `Mapped[str]` | - |
| `prompt` | `Mapped[str]` | - |
| `context` | `Mapped[str | None]` | nullable |
| `task_type` | `Mapped[str]` | - |
| `status` | `Mapped[str]` | indexed, has default |
| `priority` | `Mapped[int]` | has default |
| `annotations_required` | `Mapped[int]` | has default |
| `created_by` | `Mapped[uuid.UUID]` | FK(users.id) |
| `created_at` | `Mapped[datetime]` | has default |
| `updated_at` | `Mapped[datetime | None]` | nullable |
| `metadata_` | `Mapped[dict]` | has default |
| `model_version_id` | `Mapped[uuid.UUID | None]` | nullable |
| `creator` | `Mapped['User']` | - |
| `assignments` | `Mapped[list['TaskAssignment']]` | - |
| `annotations` | `Mapped[list['Annotation']]` | - |

**Relationships:** `creator` -> `Mapped['User']` | `assignments` -> `Mapped[list['TaskAssignment']]` | `annotations` -> `Mapped[list['Annotation']]`

## `TaskAssignment` (table: `task_assignments`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `task_id` | `Mapped[uuid.UUID]` | indexed, FK(tasks.id) |
| `annotator_id` | `Mapped[uuid.UUID]` | indexed, FK(users.id) |
| `status` | `Mapped[str]` | has default |
| `claimed_at` | `Mapped[datetime]` | has default |
| `completed_at` | `Mapped[datetime | None]` | nullable |
| `expires_at` | `Mapped[datetime]` | - |
| `task` | `Mapped['Task']` | - |
| `annotator` | `Mapped['User']` | - |
| `annotation` | `Mapped['Annotation | None']` | nullable |

**Relationships:** `task` -> `Mapped['Task']` | `annotator` -> `Mapped['User']` | `annotation` -> `Mapped['Annotation | None']`

## `User` (table: `users`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `email` | `Mapped[str]` | unique, indexed |
| `name` | `Mapped[str]` | - |
| `role` | `Mapped[str]` | - |
| `hashed_password` | `Mapped[str]` | - |
| `is_active` | `Mapped[bool]` | has default |
| `created_at` | `Mapped[datetime]` | has default |
| `refresh_tokens` | `Mapped[list['RefreshToken']]` | - |
| `tasks` | `Mapped[list['Task']]` | - |
| `assignments` | `Mapped[list['TaskAssignment']]` | - |
| `annotations` | `Mapped[list['Annotation']]` | - |

**Relationships:** `refresh_tokens` -> `Mapped[list['RefreshToken']]` | `tasks` -> `Mapped[list['Task']]` | `assignments` -> `Mapped[list['TaskAssignment']]` | `annotations` -> `Mapped[list['Annotation']]`

## `RefreshToken` (table: `refresh_tokens`)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Mapped[uuid.UUID]` | PK, has default |
| `user_id` | `Mapped[uuid.UUID]` | indexed, FK(users.id) |
| `token_hash` | `Mapped[str]` | unique |
| `expires_at` | `Mapped[datetime]` | - |
| `revoked_at` | `Mapped[datetime | None]` | nullable |
| `created_at` | `Mapped[datetime]` | has default |
| `user` | `Mapped['User']` | - |

**Relationships:** `user` -> `Mapped['User']`
