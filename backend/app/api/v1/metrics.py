import uuid
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from fastapi import APIRouter, HTTPException, Query
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
        elif signal_type == "correction":
            distribution[signal_type]["count"] = distribution[signal_type].get("count", 0) + 1

    return {"distribution": distribution}


def _compute_iaa(signal_type: str, values: list[dict]) -> dict:
    """Compute inter-annotator agreement for a list of signal values (pure Python, no deps)."""
    n = len(values)
    if n < 2:
        return {}
    if signal_type == "rating":
        scores = [float(v.get("score", 0)) for v in values]
        mean = sum(scores) / n
        std = (sum((s - mean) ** 2 for s in scores) / n) ** 0.5
        pairs = [(scores[i], scores[j]) for i in range(n) for j in range(i + 1, n)]
        within_1 = sum(1 for a, b in pairs if abs(a - b) <= 1) / len(pairs)
        return {"mean": round(mean, 2), "std": round(std, 2), "within_1_rate": round(within_1, 3)}
    if signal_type in ("binary", "comparison"):
        labels = (
            ["accept" if v.get("accept") else "reject" for v in values]
            if signal_type == "binary"
            else [v.get("chosen", "?") for v in values]
        )
        pairs = [(labels[i], labels[j]) for i in range(n) for j in range(i + 1, n)]
        Po = sum(1 for a, b in pairs if a == b) / len(pairs)
        Pe = sum((labels.count(c) / n) ** 2 for c in set(labels))
        kappa = (Po - Pe) / (1 - Pe) if Pe < 1 else 1.0
        interp = (
            "poor" if kappa < 0.2 else
            "fair" if kappa < 0.4 else
            "moderate" if kappa < 0.6 else
            "substantial" if kappa < 0.8 else
            "almost perfect"
        )
        return {"percent_agreement": round(Po, 3), "kappa": round(kappa, 3), "interpretation": interp}
    return {}


@router.get("/tasks/{task_id}/iaa")
async def task_iaa(task_id: uuid.UUID, db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    """Per-task inter-annotator agreement metrics (current round only)."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only show signals from the current annotation round
    offset = (task.metadata_ or {}).get("round_completed_offset", 0)
    round_asgmt_result = await db.execute(
        select(TaskAssignment.id)
        .where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.status == AssignmentStatus.completed,
        )
        .order_by(TaskAssignment.completed_at)
        .offset(offset)
    )
    current_round_ids = [row[0] for row in round_asgmt_result.all()]

    if current_round_ids:
        result = await db.execute(
            select(RewardSignal)
            .join(Annotation, Annotation.id == RewardSignal.annotation_id)
            .where(Annotation.assignment_id.in_(current_round_ids))
        )
        signals = result.scalars().all()
    else:
        signals = []

    signal_type = signals[0].signal_type if signals else None
    return {
        "task_id": str(task_id),
        "annotation_count": len(signals),
        "annotations_required": task.annotations_required,
        "signal_type": signal_type,
        "agreement": _compute_iaa(signal_type, [s.value for s in signals]) if signal_type else None,
    }


@router.get("/iaa-summary")
async def iaa_summary(db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    """Aggregate IAA stats across all completed tasks with multiple annotations."""
    result = await db.execute(
        select(Annotation.task_id, RewardSignal.signal_type, RewardSignal.value)
        .join(RewardSignal, RewardSignal.annotation_id == Annotation.id)
        .join(Task, Task.id == Annotation.task_id)
        .where(Task.status == TaskStatus.completed)
        .order_by(Annotation.task_id)
    )
    rows = result.all()

    by_task: dict[str, list] = {}
    for task_id, signal_type, value in rows:
        by_task.setdefault(str(task_id), []).append((signal_type, value))

    tasks_evaluated = 0
    kappas = []
    for entries in by_task.values():
        if len(entries) < 2:
            continue
        tasks_evaluated += 1
        stype = entries[0][0]
        if stype in ("binary", "comparison"):
            iaa = _compute_iaa(stype, [v for _, v in entries])
            if "kappa" in iaa:
                kappas.append(iaa["kappa"])

    return {
        "tasks_evaluated": tasks_evaluated,
        "avg_kappa": round(sum(kappas) / len(kappas), 3) if kappas else None,
        "high_agreement_count": sum(1 for k in kappas if k >= 0.6),
    }


@router.get("/annotators")
async def annotator_stats(db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    # Use scalar subqueries to avoid JOIN multiplication when both tables have
    # multiple rows per user (e.g. 2 annotations × 2 assignments = 4 counted).
    annotation_count_sq = (
        select(func.count(Annotation.id))
        .where(Annotation.annotator_id == User.id)
        .scalar_subquery()
    )
    active_assignments_sq = (
        select(func.count(TaskAssignment.id))
        .where(
            TaskAssignment.annotator_id == User.id,
            TaskAssignment.status == AssignmentStatus.in_progress,
        )
        .scalar_subquery()
    )
    result = await db.execute(
        select(
            User.id,
            User.name,
            annotation_count_sq.label("annotation_count"),
            active_assignments_sq.label("active_assignments"),
        )
        .where(User.role == UserRole.annotator)
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


@router.get("/annotators-calibration")
async def annotators_calibration(db: DbDep, researcher: ResearcherDep) -> dict[str, Any]:
    """
    Batch calibration metrics for all annotators.
    - agreement_rate: % of annotations agreeing with majority (binary/comparison) or within 1 of
      task mean (rating). Only meaningful for tasks with >= 2 annotators.
    - score_bias: avg delta vs task mean for rating tasks (+ = lenient, - = harsh).
    - median_completion_minutes: median time from claim to completion.
    - comparable_tasks: how many multi-annotator tasks contributed to agreement_rate.
    """
    # 1. Speed: all completed assignment timings
    timing_result = await db.execute(
        select(
            TaskAssignment.annotator_id,
            TaskAssignment.claimed_at,
            TaskAssignment.completed_at,
        ).where(
            TaskAssignment.status == AssignmentStatus.completed,
            TaskAssignment.completed_at.is_not(None),
            TaskAssignment.claimed_at.is_not(None),
        )
    )
    annotator_times: dict[str, list[float]] = {}
    for annotator_id, claimed_at, completed_at in timing_result:
        minutes = (completed_at - claimed_at).total_seconds() / 60
        annotator_times.setdefault(str(annotator_id), []).append(minutes)

    # 2. All completed annotations with signals (for agreement + bias)
    ann_result = await db.execute(
        select(
            Annotation.annotator_id,
            Annotation.task_id,
            RewardSignal.signal_type,
            RewardSignal.value,
        )
        .join(RewardSignal, RewardSignal.annotation_id == Annotation.id)
        .join(TaskAssignment, TaskAssignment.id == Annotation.assignment_id)
        .where(TaskAssignment.status == AssignmentStatus.completed)
    )

    # Group by task
    by_task: dict[str, list] = {}
    for annotator_id, task_id, signal_type, value in ann_result:
        by_task.setdefault(str(task_id), []).append((str(annotator_id), signal_type, value))

    annotator_agreement: dict[str, list[int]] = {}
    annotator_rating_delta: dict[str, list[float]] = {}

    for entries in by_task.values():
        if len(entries) < 2:
            continue
        signal_type = entries[0][1]

        if signal_type == "rating":
            scores = [(ann_id, float(v.get("score", 0))) for ann_id, _, v in entries]
            task_mean = sum(s for _, s in scores) / len(scores)
            for ann_id, score in scores:
                annotator_rating_delta.setdefault(ann_id, []).append(score - task_mean)
                annotator_agreement.setdefault(ann_id, []).append(
                    1 if abs(score - task_mean) <= 1 else 0
                )
        elif signal_type in ("binary", "comparison"):
            labels = [
                (ann_id, "accept" if v.get("accept") else "reject")
                if signal_type == "binary"
                else (ann_id, v.get("chosen", "?"))
                for ann_id, _, v in entries
            ]
            label_counts: dict[str, int] = {}
            for _, lbl in labels:
                label_counts[lbl] = label_counts.get(lbl, 0) + 1
            majority = max(label_counts, key=lambda k: label_counts[k])
            for ann_id, lbl in labels:
                annotator_agreement.setdefault(ann_id, []).append(1 if lbl == majority else 0)

    all_ids = set(annotator_times) | set(annotator_agreement) | set(annotator_rating_delta)
    calibration: dict[str, dict] = {}
    for ann_id in all_ids:
        agreements = annotator_agreement.get(ann_id, [])
        deltas = annotator_rating_delta.get(ann_id, [])
        times = annotator_times.get(ann_id, [])
        calibration[ann_id] = {
            "agreement_rate": round(sum(agreements) / len(agreements), 3) if agreements else None,
            "score_bias": round(sum(deltas) / len(deltas), 2) if deltas else None,
            "median_completion_minutes": round(median(times), 1) if times else None,
            "comparable_tasks": len(agreements),
        }

    return {"calibration": calibration}
