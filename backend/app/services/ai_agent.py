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
    # Correction tasks: generate a flawed response for annotators to fix
    "correction": (
        "You are an AI assistant. Answer the question, but intentionally include "
        "1–2 subtle errors or imprecisions (wrong facts, flawed logic, or a misleading statement) "
        "that a knowledgeable human could identify and correct. "
        "Do not announce the errors — weave them in naturally."
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
            if m != model:
                logger.info("Used fallback model %s (primary %s was rate-limited)", m, model)
            msg = resp.choices[0].message
            # Some free models are "thinking" models that put output in reasoning
            return msg.content or getattr(msg, "reasoning", None) or ""
        except Exception as e:
            logger.warning("Model %s failed: %s", m, e)
            last_err = e
    raise last_err  # all models failed


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
                # Only generate if researcher didn't supply the context text
                if not task.context:
                    task.context = await _chat(
                        client, model_id, _SYSTEM["correction"], task.prompt, max_tokens=1024
                    )

            metadata["ai_generation_status"] = "done"
            logger.info("AI generation done for task %s", task_id)

        except Exception:
            logger.exception("AI generation failed for task %s", task_id)
            metadata["ai_generation_status"] = "failed"

        task.metadata_ = dict(metadata)
        flag_modified(task, "metadata_")
        await db.commit()
