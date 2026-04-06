"""
RLAIF (Reinforcement Learning from AI Feedback) annotation service.

annotation_mode values (stored in task.metadata_["annotation_mode"]):
  "rlhf"   — human annotators only (default, AI never called)
  "hybrid" — AI submits 1 annotation slot, humans fill the rest
  "rlaif"  — AI fills all annotations_required slots; task hidden from human queue

Triggered from ai_agent.generate_for_task after AI response generation completes.
"""
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.annotation import Annotation, RewardSignal
from app.models.task import Task, TaskAssignment, AssignmentStatus, TaskStatus
from app.models.user import User, UserRole
from app.services.ai_agent import _chat, _get_api_key, _get_active_model, _SYSTEM  # noqa: PLC2701

logger = logging.getLogger(__name__)


# ── AI annotator user ─────────────────────────────────────────────────────────


async def _get_or_create_ai_user(db) -> User:
    """Return the AI annotator system user, creating it on first use."""
    result = await db.execute(
        select(User).where(User.email == settings.RLAIF_ANNOTATOR_EMAIL)
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        email=settings.RLAIF_ANNOTATOR_EMAIL,
        name="AI Annotator",
        role=UserRole.annotator,
        hashed_password="!rlaif-system-no-login",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Created AI annotator system user: %s", user.id)
    return user


# ── Signal generation ─────────────────────────────────────────────────────────


async def _generate_signal(
    task: Task, metadata: dict, client: AsyncOpenAI, model_id: str
) -> tuple[str | None, dict, str]:
    """
    Generate a reward signal for a task using the active model.
    Returns (signal_type, signal_value, response_text) or (None, {}, "") if unsupported.
    """
    if task.task_type in ("reasoning", "coding"):
        model_response = metadata.get("model_response", "")
        if not model_response:
            return None, {}, ""
        prompt = (
            f"Question: {task.prompt}\n\n"
            f"Response: {model_response}\n\n"
            "Rate the quality, accuracy, and helpfulness of this response on a scale of 1 to 5.\n"
            "5 = excellent, 4 = good, 3 = adequate, 2 = poor, 1 = very poor.\n"
            "Reply with ONLY a single digit (1, 2, 3, or 4, or 5)."
        )
        raw = await _chat(client, model_id, _SYSTEM["reasoning"], prompt, max_tokens=10)
        m = re.search(r"[1-5]", raw)
        score = int(m.group()) if m else 3
        return "rating", {"score": score}, model_response

    if task.task_type == "comparison":
        response_a = metadata.get("response_a", "")
        response_b = metadata.get("response_b", "")
        if not response_a or not response_b:
            return None, {}, ""
        prompt = (
            f"Question: {task.prompt}\n\n"
            f"Response A:\n{response_a}\n\n"
            f"Response B:\n{response_b}\n\n"
            "Which response is better overall? Consider accuracy, completeness, and clarity.\n"
            "Reply with ONLY the letter 'A' or 'B'."
        )
        raw = await _chat(client, model_id, _SYSTEM["reasoning"], prompt, max_tokens=10)
        m = re.search(r"\b[AB]\b", raw.upper())
        chosen = m.group() if m else "A"
        return "comparison", {"chosen": chosen}, response_a if chosen == "A" else response_b

    # Correction tasks are human-only — AI critique/accept judgment is the human's role
    return None, {}, ""


# ── Core service ──────────────────────────────────────────────────────────────


async def ai_annotate_task(task_id: uuid.UUID) -> None:
    """
    Submit AI annotation(s) for a task.
    - hybrid: fills 1 annotation slot
    - rlaif:  fills all annotations_required slots

    Opens its own DB session (called from generate_for_task after its session closes).
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("RLAIF: no API key configured, skipping task %s", task_id)
        return

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task or task.status != TaskStatus.available:
            return

        metadata = dict(task.metadata_ or {})
        annotation_mode = metadata.get("annotation_mode", "rlhf")

        if annotation_mode == "rlaif":
            ai_slots = task.annotations_required
        elif annotation_mode == "hybrid":
            ai_slots = 1
        else:
            return  # rlhf — no AI annotation

        try:
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            model_id, _ = await _get_active_model(db)
            signal_type, signal_value, response_text = await _generate_signal(
                task, metadata, client, model_id
            )
            if signal_type is None:
                logger.info("RLAIF: no signal for task %s (type=%s)", task_id, task.task_type)
                return
        except Exception:
            logger.exception("RLAIF: signal generation failed for task %s", task_id)
            return

        ai_user = await _get_or_create_ai_user(db)

        # How many AI slots are already filled?
        existing_count = await db.scalar(
            select(func.count(TaskAssignment.id)).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.annotator_id == ai_user.id,
            )
        )
        remaining = ai_slots - existing_count
        if remaining <= 0:
            logger.info("RLAIF: AI already filled all slots for task %s", task_id)
            return

        should_trigger = False

        for _ in range(remaining):
            # Re-read task status — a prior iteration may have completed the task
            await db.refresh(task)
            if task.status != TaskStatus.available:
                break

            # Count BEFORE marking completed (same autoflush pattern as annotations.py)
            completed_count = await db.scalar(
                select(func.count(TaskAssignment.id)).where(
                    TaskAssignment.task_id == task_id,
                    TaskAssignment.status == AssignmentStatus.completed,
                )
            )

            ai_assignment = TaskAssignment(
                task_id=task_id,
                annotator_id=ai_user.id,
                status=AssignmentStatus.in_progress,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(ai_assignment)
            await db.flush()

            annotation = Annotation(
                task_id=task_id,
                assignment_id=ai_assignment.id,
                annotator_id=ai_user.id,
                response=response_text,
                metadata_={"source": "ai"},
            )
            db.add(annotation)
            await db.flush()

            signal = RewardSignal(
                annotation_id=annotation.id,
                signal_type=signal_type,
                value=signal_value,
            )

            ai_assignment.status = AssignmentStatus.completed
            ai_assignment.completed_at = datetime.now(timezone.utc)

            offset = (task.metadata_ or {}).get("round_completed_offset", 0)
            if (completed_count - offset + 1) >= task.annotations_required:
                task.status = TaskStatus.completed
                from app.core.redis import get_redis
                from app.services.queue import remove_task_from_queue
                await remove_task_from_queue(get_redis(), task.id)

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
                existing_result = await db.execute(
                    select(RewardSignal)
                    .join(Annotation, Annotation.id == RewardSignal.annotation_id)
                    .where(Annotation.assignment_id.in_(current_round_ids))
                )
                existing_signals = list(existing_result.scalars().all())
                all_signals = existing_signals + [signal]

                from app.api.v1.annotations import _evaluate_task_quality
                quality_status = _evaluate_task_quality(all_signals)

                md = dict(task.metadata_ or {})
                md["quality_status"] = quality_status
                if "generation_round" not in md:
                    md["generation_round"] = 1
                task.metadata_ = md
                flag_modified(task, "metadata_")
                should_trigger = True

            db.add(signal)
            await db.commit()

            logger.info(
                "RLAIF: annotated task %s [%s] — %s %s (slot %d/%d)",
                task_id, annotation_mode, signal_type, signal_value,
                existing_count + 1, ai_slots,
            )

            if should_trigger:
                break

    if should_trigger:
        from app.services.finetune import maybe_trigger_finetune
        await maybe_trigger_finetune(task_id)
