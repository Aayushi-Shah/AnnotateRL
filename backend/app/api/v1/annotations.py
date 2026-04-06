import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import AnnotatorDep, CurrentUser, DbDep, ResearcherDep
from app.models.annotation import Annotation, RewardSignal
from app.models.task import TaskAssignment, AssignmentStatus, Task, TaskStatus
from app.schemas.annotation import AnnotationCreate, AnnotationResponse
from app.schemas.common import PaginatedResponse
from sqlalchemy import func

router = APIRouter(prefix="/annotations", tags=["annotations"])

# Quality thresholds for accepting/rejecting task annotation rounds
_RATING_ACCEPT_MIN = 4.0
_RATING_REJECT_MAX = 3.0


def _evaluate_task_quality(signals: list) -> str:
    """
    Given all RewardSignal objects for a completed task, return quality status.
    Returns "accepted", "rejected", or "pending" (ambiguous / no scalar signal).
    """
    if not signals:
        return "pending"

    signal_type = signals[0].signal_type

    if signal_type == "rating":
        scores = [float(s.value.get("score", 0)) for s in signals]
        avg = sum(scores) / len(scores)
        if avg >= _RATING_ACCEPT_MIN:
            return "accepted"
        if avg <= _RATING_REJECT_MAX:
            return "rejected"
        return "pending"

    if signal_type == "binary":
        accept_count = sum(1 for s in signals if s.value.get("accept"))
        return "accepted" if accept_count > len(signals) / 2 else "rejected"

    if signal_type == "comparison":
        a_count = sum(1 for s in signals if s.value.get("chosen") == "A")
        b_count = sum(1 for s in signals if s.value.get("chosen") == "B")
        if a_count == b_count:
            return "rejected"  # tie = no clear preference
        return "accepted"

    if signal_type == "correction":
        accepted_count = sum(1 for s in signals if s.value.get("critique_accepted"))
        return "accepted" if accepted_count > len(signals) / 2 else "rejected"

    return "pending"


def _to_response(annotation: Annotation) -> AnnotationResponse:
    signal = annotation.reward_signal
    source = (annotation.metadata_ or {}).get("source", "human")
    return AnnotationResponse(
        id=str(annotation.id),
        task_id=str(annotation.task_id),
        assignment_id=str(annotation.assignment_id),
        annotator_id=str(annotation.annotator_id),
        response=annotation.response,
        signal_type=signal.signal_type if signal else "",
        signal_value=signal.value if signal else {},
        source=source,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


@router.post("", response_model=AnnotationResponse, status_code=201)
async def submit_annotation(
    payload: AnnotationCreate, background_tasks: BackgroundTasks, db: DbDep, annotator: AnnotatorDep,
):
    """Submit response + reward signal atomically. Marks assignment as completed."""
    assignment_id = uuid.UUID(payload.assignment_id)
    assignment = await db.get(TaskAssignment, assignment_id)

    if not assignment or assignment.annotator_id != annotator.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status != AssignmentStatus.in_progress:
        raise HTTPException(status_code=400, detail="Assignment is not in progress")
    if assignment.expires_at < datetime.now(timezone.utc):
        assignment.status = AssignmentStatus.expired
        await db.commit()
        raise HTTPException(status_code=400, detail="Assignment has expired")

    # Check for duplicate submission
    existing = await db.scalar(
        select(func.count(Annotation.id)).where(Annotation.assignment_id == assignment_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Annotation already submitted for this assignment")

    annotation = Annotation(
        task_id=assignment.task_id,
        assignment_id=assignment_id,
        annotator_id=annotator.id,
        response=payload.response,
        metadata_={},
    )
    db.add(annotation)
    await db.flush()  # get annotation.id

    # Build signal but do NOT add to session yet — added after quality eval so
    # autoflush doesn't double-count it in the signal query below.
    signal = RewardSignal(
        annotation_id=annotation.id,
        signal_type=payload.signal_type,
        value=payload.signal_value,
    )

    # Correction rejection: record the annotation but don't count toward completion.
    # Clear AI-generated content and re-trigger generation for the next annotator.
    if payload.signal_type == "correction" and payload.signal_value.get("critique_accepted") is False:
        assignment.status = AssignmentStatus.completed
        assignment.completed_at = datetime.now(timezone.utc)
        task = await db.get(Task, assignment.task_id)
        task.context = None
        metadata = dict(task.metadata_ or {})
        metadata.pop("critique", None)
        metadata.pop("revised_response", None)
        metadata["ai_generation_status"] = "pending"
        task.metadata_ = metadata
        flag_modified(task, "metadata_")
        db.add(signal)
        await db.commit()
        await db.refresh(annotation)
        await db.refresh(signal)
        annotation.reward_signal = signal
        from app.services.ai_agent import generate_for_task
        background_tasks.add_task(generate_for_task, task.id)
        return _to_response(annotation)

    # Count BEFORE changing assignment status so autoflush doesn't include
    # the current assignment in the count. +1 accounts for this one.
    completed_count = await db.scalar(
        select(func.count(TaskAssignment.id)).where(
            TaskAssignment.task_id == assignment.task_id,
            TaskAssignment.status == AssignmentStatus.completed,
        )
    )
    task = await db.get(Task, assignment.task_id)

    assignment.status = AssignmentStatus.completed
    assignment.completed_at = datetime.now(timezone.utc)

    offset = (task.metadata_ or {}).get("round_completed_offset", 0)
    if (completed_count - offset + 1) >= task.annotations_required:
        task.status = TaskStatus.completed
        from app.core.redis import get_redis
        from app.services.queue import remove_task_from_queue
        await remove_task_from_queue(get_redis(), task.id)

        # Only evaluate signals from the current round: skip the first `offset`
        # oldest completed assignments (those belong to prior rounds).
        # Signal is not in session yet so the query won't double-count it.
        round_asgmt_result = await db.execute(
            select(TaskAssignment.id)
            .where(
                TaskAssignment.task_id == assignment.task_id,
                TaskAssignment.status == AssignmentStatus.completed,
            )
            .order_by(TaskAssignment.completed_at)
            .offset(offset)
        )
        current_round_ids = [row[0] for row in round_asgmt_result.all()]

        existing_result = await db.execute(
            select(RewardSignal)
            .join(Annotation, Annotation.id == RewardSignal.annotation_id)
            .where(Annotation.assignment_id.in_(current_round_ids))
        )
        existing_signals = list(existing_result.scalars().all())
        all_signals = existing_signals + [signal]  # current signal not yet in DB
        quality_status = _evaluate_task_quality(all_signals)

        metadata = dict(task.metadata_ or {})
        metadata["quality_status"] = quality_status
        if "generation_round" not in metadata:
            metadata["generation_round"] = 1
        task.metadata_ = metadata
        flag_modified(task, "metadata_")

        # Trigger fine-tune for all completed tasks — accepted examples become SFT
        # positives, rejected become DPO negatives; both are used in training.
        from app.services.finetune import maybe_trigger_finetune
        background_tasks.add_task(maybe_trigger_finetune, task.id)

    db.add(signal)  # add after quality eval so it wasn't in session during the query
    await db.commit()
    await db.refresh(annotation)
    await db.refresh(signal)
    annotation.reward_signal = signal

    return _to_response(annotation)


@router.get("", response_model=PaginatedResponse[AnnotationResponse])
async def list_annotations(
    db: DbDep,
    current_user: CurrentUser,
    task_id: str | None = Query(default=None),
    annotator_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    query = select(Annotation).options(selectinload(Annotation.reward_signal))

    if task_id:
        query = query.where(Annotation.task_id == uuid.UUID(task_id))
    if annotator_id:
        query = query.where(Annotation.annotator_id == uuid.UUID(annotator_id))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(Annotation.created_at.desc())
    )
    annotations = result.scalars().all()

    return PaginatedResponse(
        items=[_to_response(a) for a in annotations],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(annotation_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    result = await db.execute(
        select(Annotation)
        .options(selectinload(Annotation.reward_signal))
        .where(Annotation.id == annotation_id)
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return _to_response(annotation)
