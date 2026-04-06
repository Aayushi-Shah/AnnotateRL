"""
AI response generation service.
Called as a BackgroundTask when a task is published without pre-filled responses.
Uses OpenRouter (OpenAI-compatible API) to generate the model_response annotators will evaluate.
"""
import logging
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.task import Task

logger = logging.getLogger(__name__)

# System prompts tuned per task type
_SYSTEM: dict[str, str] = {
    "reasoning": (
        "You are a knowledgeable AI assistant. "
        "Answer the user's question clearly and thoroughly. "
        "Be direct and accurate — your response will be evaluated by human annotators."
    ),
    "coding": (
        "You are an expert software engineer. "
        "Write clean, working code for the given task. "
        "Include brief inline comments where helpful. "
        "Your response will be evaluated by human annotators."
    ),
    # Two distinct response styles for A/B comparison tasks
    "comparison_a": (
        "You are a helpful AI assistant. "
        "Answer the following question with a concise, direct approach. "
        "Keep your response focused and efficient."
    ),
    "comparison_b": (
        "You are a helpful AI assistant. "
        "Answer the following question with a comprehensive, detailed approach. "
        "Explore multiple angles and provide thorough coverage."
    ),
}

DEFAULT_MODEL = "nvidia/nemotron-nano-9b-v2:free"

# Fallback models if the primary is rate-limited
_FALLBACK_MODELS = [
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-mini:free",
    "google/gemma-3-12b-it:free",
]


def _get_api_key() -> str | None:
    """Return the configured API key, preferring OpenRouter over Anthropic."""
    return settings.OPENROUTER_API_KEY or settings.ANTHROPIC_API_KEY


async def _get_active_model(db) -> tuple[str, str | None]:
    """Return (model_id, version_id) from the active ModelVersion, or fall back to default.
    Stub-finetuned models (starting with 'stub-') fall back to the default model
    since they aren't real, but we still return the version_id for tracking.
    """
    from app.models.finetune import ModelVersion

    result = await db.execute(
        select(ModelVersion).where(ModelVersion.is_active == True)  # noqa: E712
    )
    version = result.scalar_one_or_none()
    if version:
        model_id = version.finetuned_model_id
        # Stub models aren't real — fall back to the base model for actual API calls
        if not model_id or model_id.startswith("stub-"):
            model_id = version.base_model or DEFAULT_MODEL
        return model_id, str(version.id)
    return DEFAULT_MODEL, None


async def _chat(client: AsyncOpenAI, model: str, system: str, user_msg: str, max_tokens: int = 2048) -> str:
    """Send a chat completion request with fallback models on rate-limit."""
    models_to_try = [model] + [m for m in _FALLBACK_MODELS if m != model]
    last_err = None
    for m in models_to_try:
        try:
            resp = await client.chat.completions.create(
                model=m,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
            )
            if not resp.choices:
                raise ValueError(f"Model {m} returned empty choices")
            if m != model:
                logger.info("Used fallback model %s (primary %s was rate-limited)", m, model)
            msg = resp.choices[0].message
            # Some free models are "thinking" models that put output in reasoning
            return msg.content or getattr(msg, "reasoning", None) or ""
        except Exception as e:
            logger.warning("Model %s failed: %s", m, e)
            last_err = e
    raise last_err  # all models failed


async def regenerate_rejected_tasks(model_version_id: uuid.UUID) -> None:
    """
    Called after a model version is activated.
    Finds all tasks with quality_status='rejected', saves the old response to
    round_history, re-generates a new response using the now-active model,
    and pushes each task back to the annotation queue.
    """
    from app.models.task import TaskStatus, TaskAssignment, AssignmentStatus
    from app.services.queue import publish_task
    from app.core.redis import get_redis
    from sqlalchemy import func

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.metadata_["quality_status"].astext == "rejected",
                Task.status == TaskStatus.completed,
            )
        )
        tasks = result.scalars().all()

        task_ids = []
        for task in tasks:
            # Count completed assignments so far — new-round claims use this as an offset
            completed_so_far = await db.scalar(
                select(func.count(TaskAssignment.id)).where(
                    TaskAssignment.task_id == task.id,
                    TaskAssignment.status == AssignmentStatus.completed,
                )
            )

            metadata = dict(task.metadata_ or {})
            current_round = metadata.get("generation_round", 1)
            metadata.setdefault("round_history", []).append({
                "round": current_round,
                "model_version_id": str(model_version_id),
                "old_response": metadata.get("model_response", ""),
            })
            metadata["generation_round"] = current_round + 1
            metadata["quality_status"] = "pending"
            metadata["ai_generation_status"] = "pending"
            # Offset so claim/completion checks only count NEW-round annotations
            metadata["round_completed_offset"] = completed_so_far
            # Clear old AI responses so generate_for_task produces fresh output
            metadata.pop("model_response", None)
            metadata.pop("response_a", None)
            metadata.pop("response_b", None)
            task.metadata_ = dict(metadata)
            flag_modified(task, "metadata_")
            task.status = TaskStatus.available
            task_ids.append((task.id, task.priority))

        await db.commit()
        logger.info("Queued %d rejected tasks for re-generation using model %s", len(task_ids), model_version_id)

    redis = get_redis()
    for tid, priority in task_ids:
        await publish_task(redis, tid, priority)
        await generate_for_task(tid)


async def generate_for_task(task_id: uuid.UUID) -> None:
    """
    Generate AI response(s) for a published task and store them in task.metadata_.
    Runs as a FastAPI BackgroundTask — opens its own DB session.
    """
    api_key = _get_api_key()
    if not api_key:
        return

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            return

        metadata: dict = dict(task.metadata_ or {})
        metadata["ai_generation_status"] = "pending"
        task.metadata_ = metadata
        await db.commit()

        try:
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            model_id, version_id = await _get_active_model(db)

            # Track which model version generated this task's response
            if version_id:
                metadata["model_version_id"] = version_id

            user_msg = task.prompt
            if task.context:
                user_msg += f"\n\nContext: {task.context}"

            if task.task_type in ("reasoning", "coding"):
                if not metadata.get("model_response"):
                    metadata["model_response"] = await _chat(
                        client, model_id, _SYSTEM[task.task_type], user_msg
                    )

            elif task.task_type == "comparison":
                if not metadata.get("response_a"):
                    metadata["response_a"] = await _chat(
                        client, model_id, _SYSTEM["comparison_a"], user_msg, max_tokens=1024
                    )
                if not metadata.get("response_b"):
                    metadata["response_b"] = await _chat(
                        client, model_id, _SYSTEM["comparison_b"], user_msg, max_tokens=1024
                    )

            elif task.task_type == "correction":
                _NEUTRAL = (
                    "You are a knowledgeable AI assistant. "
                    "Answer the user's question accurately and concisely. "
                    "Aim for 3–4 focused paragraphs — no need for elaborate headers or bullet lists."
                )
                _CRITIQUE_PROMPT = (
                    "Review the following response. "
                    "Does it contain any factual errors, logical flaws, or misleading statements? "
                    "If yes, list each issue in 2–4 bullet points, being specific. "
                    "If you find no errors, reply with exactly: 'No errors found.'"
                )
                if not task.context:
                    # Generate a natural response, then evaluate it for flaws.
                    # Retry up to 3 times if the model reports no errors.
                    candidate = ""
                    critique = ""
                    for _attempt in range(3):
                        candidate = await _chat(
                            client, model_id, _NEUTRAL, task.prompt, max_tokens=2048
                        )
                        critique = await _chat(
                            client,
                            model_id,
                            _SYSTEM["reasoning"],
                            f"Response:\n{candidate}\n\n{_CRITIQUE_PROMPT}",
                            max_tokens=1024,
                        )
                        if "no errors found" not in critique.lower():
                            break  # found a flawed response
                    task.context = candidate
                    metadata["critique"] = critique
                    revised = await _chat(
                        client,
                        model_id,
                        _SYSTEM["reasoning"],
                        (
                            f"Original response:\n{candidate}\n\n"
                            f"Critique:\n{critique}\n\n"
                            "Write a corrected version that addresses all issues identified."
                        ),
                        max_tokens=2048,
                    )
                    metadata["revised_response"] = revised
                elif not metadata.get("critique"):
                    # Researcher-provided context: only generate the critique
                    critique = await _chat(
                        client,
                        model_id,
                        _SYSTEM["reasoning"],
                        f"Response:\n{task.context}\n\n{_CRITIQUE_PROMPT}",
                        max_tokens=1024,
                    )
                    metadata["critique"] = critique

            metadata["ai_generation_status"] = "done"
            logger.info("AI generation done for task %s", task_id)

        except Exception:
            logger.exception("AI generation failed for task %s", task_id)
            metadata["ai_generation_status"] = "failed"

        task.metadata_ = dict(metadata)
        flag_modified(task, "metadata_")
        await db.commit()

    # Trigger AI annotation after generation succeeds (RLAIF / hybrid modes).
    # Runs outside the session so ai_annotate_task opens its own session cleanly.
    annotation_mode = metadata.get("annotation_mode")
    if (
        annotation_mode in ("rlaif", "hybrid")
        and metadata.get("ai_generation_status") == "done"
        and settings.RLAIF_ENABLED
    ):
        from app.services.ai_annotator import ai_annotate_task
        await ai_annotate_task(task_id)
