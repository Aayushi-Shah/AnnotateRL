import uuid
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskAssignment, AssignmentStatus, TaskStatus

QUEUE_KEY = "annotaterl:task_queue"
CLAIM_HOURS = 4
CANDIDATES_BATCH = 10  # how many to inspect per claim attempt


async def publish_task(redis: Redis, task_id: uuid.UUID, priority: int) -> None:
    """Add task to the Redis priority queue. Score = priority (higher = served first)."""
    await redis.zadd(QUEUE_KEY, {str(task_id): priority})


async def remove_task_from_queue(redis: Redis, task_id: uuid.UUID) -> None:
    await redis.zrem(QUEUE_KEY, str(task_id))


async def claim_next(
    db: AsyncSession, redis: Redis, annotator_id: uuid.UUID
) -> TaskAssignment | None:
    """
    Atomically claim the highest-priority available task for an annotator.
    Uses Redis for fast priority ordering + SELECT FOR UPDATE SKIP LOCKED in
    Postgres to prevent double-claiming under concurrent load.
    """
    candidates = await redis.zrevrange(QUEUE_KEY, 0, CANDIDATES_BATCH - 1)

    for raw in candidates:
        task_id = uuid.UUID(raw)

        # Lock the row; skip if another transaction already holds it
        result = await db.execute(
            select(Task)
            .where(Task.id == task_id, Task.status == TaskStatus.available)
            .with_for_update(skip_locked=True)
        )
        task = result.scalar_one_or_none()
        if task is None:
            continue

        # Skip if this annotator already has an active (in_progress) assignment
        existing = await db.scalar(
            select(func.count(TaskAssignment.id)).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.annotator_id == annotator_id,
                TaskAssignment.status == AssignmentStatus.in_progress,
            )
        )
        if existing:
            continue

        # Check if task still needs more annotations this round
        completed = await db.scalar(
            select(func.count(TaskAssignment.id)).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.status == AssignmentStatus.completed,
            )
        )
        offset = (task.metadata_ or {}).get("round_completed_offset", 0)
        if (completed - offset) >= task.annotations_required:
            # Fully annotated — clean up
            task.status = TaskStatus.completed
            await remove_task_from_queue(redis, task_id)
            await db.commit()
            continue

        expires_at = datetime.now(timezone.utc) + timedelta(hours=CLAIM_HOURS)
        assignment = TaskAssignment(
            task_id=task_id,
            annotator_id=annotator_id,
            status=AssignmentStatus.in_progress,
            expires_at=expires_at,
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)
        return assignment

    return None


async def claim_specific(
    db: AsyncSession, redis: Redis, annotator_id: uuid.UUID, task_id: uuid.UUID
) -> TaskAssignment | None:
    """
    Atomically claim a specific task by ID.
    Same locking guarantees as claim_next — used when annotator selects a task explicitly.
    """
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id, Task.status == TaskStatus.available)
        .with_for_update(skip_locked=True)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None

    existing = await db.scalar(
        select(func.count(TaskAssignment.id)).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.annotator_id == annotator_id,
            TaskAssignment.status == AssignmentStatus.in_progress,
        )
    )
    if existing:
        return None

    completed = await db.scalar(
        select(func.count(TaskAssignment.id)).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.status == AssignmentStatus.completed,
        )
    )
    offset = (task.metadata_ or {}).get("round_completed_offset", 0)
    if (completed - offset) >= task.annotations_required:
        task.status = TaskStatus.completed
        await remove_task_from_queue(redis, task_id)
        await db.commit()
        return None

    expires_at = datetime.now(timezone.utc) + timedelta(hours=CLAIM_HOURS)
    assignment = TaskAssignment(
        task_id=task_id,
        annotator_id=annotator_id,
        status=AssignmentStatus.in_progress,
        expires_at=expires_at,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def expire_stale_claims(db: AsyncSession) -> int:
    """Mark in_progress assignments past their deadline as expired. Called on startup + periodically."""
    from sqlalchemy import update

    result = await db.execute(
        update(TaskAssignment)
        .where(
            TaskAssignment.status == AssignmentStatus.in_progress,
            TaskAssignment.expires_at < datetime.now(timezone.utc),
        )
        .values(status=AssignmentStatus.expired)
        .returning(TaskAssignment.id)
    )
    await db.commit()
    return len(result.fetchall())
