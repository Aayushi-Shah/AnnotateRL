from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import cast, func, select
from sqlalchemy.types import Date

from app.core.deps import DbDep, ResearcherDep
from app.models.annotation import Annotation, RewardSignal
from app.models.task import Task, TaskAssignment, AssignmentStatus, TaskStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview")
async def overview(db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    task_counts = await db.execute(
        select(Task.status, func.count(Task.id)).group_by(Task.status)
    )
    annotation_count = await db.scalar(select(func.count(Annotation.id)))
    active_annotators = await db.scalar(
        select(func.count(func.distinct(TaskAssignment.annotator_id))).where(
            TaskAssignment.status == AssignmentStatus.in_progress
        )
    )
    total_annotators = await db.scalar(
        select(func.count(User.id)).where(User.role == UserRole.annotator, User.is_active == True)
    )

    return {
        "tasks": {row[0]: row[1] for row in task_counts},
        "total_annotations": annotation_count,
        "active_annotators": active_annotators,
        "total_annotators": total_annotators,
    }


@router.get("/throughput")
async def throughput(
    db: DbDep,
    researcher: ResearcherDep,
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            cast(Annotation.created_at, Date).label("date"),
            func.count(Annotation.id).label("count"),
        )
        .where(Annotation.created_at >= since)
        .group_by("date")
        .order_by("date")
    )
    return {"days": days, "data": [{"date": str(row.date), "count": row.count} for row in result]}


@router.get("/reward-distribution")
async def reward_distribution(db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    result = await db.execute(
        select(RewardSignal.signal_type, RewardSignal.value)
    )
    rows = result.all()

    distribution: dict[str, dict] = {}
    for signal_type, value in rows:
        if signal_type not in distribution:
            distribution[signal_type] = {}
        if signal_type == "rating":
            score = str(value.get("score", "?"))
            distribution[signal_type][score] = distribution[signal_type].get(score, 0) + 1
        elif signal_type == "binary":
            key = "accept" if value.get("accept") else "reject"
            distribution[signal_type][key] = distribution[signal_type].get(key, 0) + 1
        elif signal_type == "comparison":
            key = value.get("chosen", "?")
            distribution[signal_type][key] = distribution[signal_type].get(key, 0) + 1

    return {"distribution": distribution}


@router.get("/annotators")
async def annotator_stats(db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    result = await db.execute(
        select(
            User.id,
            User.name,
            func.count(Annotation.id).label("annotation_count"),
            func.count(TaskAssignment.id).filter(
                TaskAssignment.status == AssignmentStatus.in_progress
            ).label("active_assignments"),
        )
        .join(Annotation, Annotation.annotator_id == User.id, isouter=True)
        .join(TaskAssignment, TaskAssignment.annotator_id == User.id, isouter=True)
        .where(User.role == UserRole.annotator)
        .group_by(User.id, User.name)
    )
    return {
        "annotators": [
            {
                "id": str(row.id),
                "name": row.name,
                "annotation_count": row.annotation_count,
                "active_assignments": row.active_assignments,
            }
            for row in result
        ]
    }
