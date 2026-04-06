"""
Eval suite service.
Runs a held-out set of prompts through both a candidate model and the current
baseline, uses Claude-as-judge to pick the winner per prompt, and computes an
overall win rate. Results are stored in EvalResult for the researcher to review
before deciding whether to activate the candidate model version.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.eval import EvalResult, EvalSet
from app.models.finetune import ModelVersion
from app.models.task import Task, TaskStatus
from app.services.ai_agent import _chat, _get_api_key, _SYSTEM, DEFAULT_MODEL

logger = logging.getLogger(__name__)


def _resolve_model_id(version: ModelVersion | None) -> str:
    """Return the actual API model ID, replacing stub IDs with the base model."""
    if version is None:
        return DEFAULT_MODEL
    mid = version.finetuned_model_id or ""
    if not mid or mid.startswith("stub-"):
        return version.base_model or DEFAULT_MODEL
    return mid


async def _build_default_eval_set(db, max_prompts: int = 5) -> EvalSet:
    """
    Auto-generate an eval set from the most recent completed tasks.
    Used when no explicit eval set is provided.
    """
    result = await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.completed)
        .order_by(Task.created_at.desc())
        .limit(max_prompts)
    )
    tasks = result.scalars().all()

    prompts = [
        {
            "prompt": t.prompt,
            "task_type": t.task_type,
            "reference_response": (t.metadata_ or {}).get("model_response", ""),
        }
        for t in tasks
        if t.task_type in ("reasoning", "coding")  # only single-response tasks
    ]

    if not prompts:
        # Fallback: a generic sanity-check prompt
        prompts = [{"prompt": "What is 2 + 2?", "task_type": "reasoning"}]

    eval_set = EvalSet(name="Auto-generated eval set", prompts=prompts)
    db.add(eval_set)
    await db.flush()
    return eval_set


async def run_eval(eval_result_id: uuid.UUID) -> None:
    """
    Background task: runs evaluation and stores win_rate in EvalResult.
    Opens its own DB session.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("Eval: no API key, skipping eval result %s", eval_result_id)
        async with AsyncSessionLocal() as db:
            result = await db.get(EvalResult, eval_result_id)
            if result:
                result.status = "failed"
                result.error_message = "No API key configured"
                await db.commit()
        return

    async with AsyncSessionLocal() as db:
        eval_result = await db.get(EvalResult, eval_result_id)
        if not eval_result:
            return

        eval_set = await db.get(EvalSet, eval_result.eval_set_id)
        model_version = await db.get(ModelVersion, eval_result.model_version_id)

        # Baseline = current active model
        active_q = await db.execute(
            select(ModelVersion).where(ModelVersion.is_active == True)  # noqa: E712
        )
        active_version = active_q.scalar_one_or_none()

        candidate_model = _resolve_model_id(model_version)
        baseline_model = _resolve_model_id(active_version)

        eval_result.status = "running"
        await db.commit()

        try:
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )

            wins = 0
            per_prompt = []

            for item in eval_set.prompts:
                prompt = item.get("prompt", "")
                task_type = item.get("task_type", "reasoning")
                system = _SYSTEM.get(task_type, _SYSTEM["reasoning"])

                # Generate from both models
                candidate_resp = await _chat(client, candidate_model, system, prompt, max_tokens=512)
                baseline_resp = await _chat(client, baseline_model, system, prompt, max_tokens=512)

                # Claude-as-judge
                judge_prompt = (
                    f"Question: {prompt}\n\n"
                    f"Response A:\n{candidate_resp}\n\n"
                    f"Response B:\n{baseline_resp}\n\n"
                    "Which response is better overall? Consider accuracy, completeness, and clarity.\n"
                    "Reply with ONLY the letter 'A' or 'B'."
                )
                judgment = await _chat(
                    client, DEFAULT_MODEL, _SYSTEM["reasoning"], judge_prompt, max_tokens=10
                )
                m = re.search(r"\b[AB]\b", judgment.upper())
                winner = "candidate" if (m and m.group() == "A") else "baseline"
                if winner == "candidate":
                    wins += 1

                per_prompt.append({
                    "prompt": prompt[:200],
                    "winner": winner,
                    "candidate_snippet": candidate_resp[:200],
                    "baseline_snippet": baseline_resp[:200],
                })

            total = len(eval_set.prompts)
            eval_result.win_rate = round(wins / total, 3) if total > 0 else None
            eval_result.results = {"wins": wins, "total": total, "per_prompt": per_prompt}
            eval_result.status = "completed"
            eval_result.completed_at = datetime.now(timezone.utc)

            logger.info(
                "Eval %s completed: win_rate=%.1f%% (%d/%d prompts)",
                eval_result_id, (eval_result.win_rate or 0) * 100, wins, total,
            )

        except Exception as e:
            logger.exception("Eval %s failed", eval_result_id)
            eval_result.status = "failed"
            eval_result.error_message = f"{type(e).__name__}: {e}"

        await db.commit()
