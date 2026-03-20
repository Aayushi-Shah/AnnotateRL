"""
AI response generation service.
Called as a BackgroundTask when a task is published without pre-filled responses.
Uses Claude to generate the model_response annotators will evaluate.
"""
import logging
import uuid

from anthropic import AsyncAnthropic

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


def _text(message) -> str:
    """Extract the first text block from a Claude response."""
    return next((b.text for b in message.content if b.type == "text"), "")


async def generate_for_task(task_id: uuid.UUID) -> None:
    """
    Generate AI response(s) for a published task and store them in task.metadata_.
    Runs as a FastAPI BackgroundTask — opens its own DB session.
    """
    if not settings.ANTHROPIC_API_KEY:
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
            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            user_msg = task.prompt
            if task.context:
                user_msg += f"\n\nContext: {task.context}"

            if task.task_type in ("reasoning", "coding"):
                if not metadata.get("model_response"):
                    resp = await client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=2048,
                        system=_SYSTEM[task.task_type],
                        messages=[{"role": "user", "content": user_msg}],
                    )
                    metadata["model_response"] = _text(resp)

            elif task.task_type == "comparison":
                if not metadata.get("response_a"):
                    resp_a = await client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=1024,
                        system=_SYSTEM["comparison_a"],
                        messages=[{"role": "user", "content": user_msg}],
                    )
                    metadata["response_a"] = _text(resp_a)

                if not metadata.get("response_b"):
                    resp_b = await client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=1024,
                        system=_SYSTEM["comparison_b"],
                        messages=[{"role": "user", "content": user_msg}],
                    )
                    metadata["response_b"] = _text(resp_b)

            elif task.task_type == "correction":
                # Only generate if researcher didn't supply the context text
                if not task.context:
                    resp = await client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=1024,
                        system=_SYSTEM["correction"],
                        messages=[{"role": "user", "content": task.prompt}],
                    )
                    task.context = _text(resp)

            metadata["ai_generation_status"] = "done"
            logger.info("AI generation done for task %s", task_id)

        except Exception:
            logger.exception("AI generation failed for task %s", task_id)
            metadata["ai_generation_status"] = "failed"

        task.metadata_ = metadata
        await db.commit()
