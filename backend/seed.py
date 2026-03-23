"""
Seed the database with demo users and tasks.
Run: python seed.py
"""
import asyncio

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.auth import hash_password
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.services.ai_agent import generate_for_task
from app.services.queue import publish_task

USERS = [
    # Researchers
    {"email": "alice@annotaterl.dev", "name": "Alice Chen", "role": UserRole.researcher, "password": "researcher123"},
    {"email": "bob@annotaterl.dev",   "name": "Bob Patel",  "role": UserRole.researcher, "password": "researcher123"},
    # Annotators
    {"email": "carol@annotaterl.dev", "name": "Carol Kim",    "role": UserRole.annotator, "password": "annotator123"},
    {"email": "dave@annotaterl.dev",  "name": "Dave Nguyen",  "role": UserRole.annotator, "password": "annotator123"},
    {"email": "eve@annotaterl.dev",   "name": "Eve Martinez", "role": UserRole.annotator, "password": "annotator123"},
]

# Tasks — model_response / response_a / response_b already filled so annotators
# can work immediately without waiting for AI generation.
TASKS = [
    # ── Reasoning ──────────────────────────────────────────────────────────────
    {
        "title": "RLHF vs RLAIF: key differences",
        "prompt": "Explain the key differences between Reinforcement Learning from Human Feedback (RLHF) and Reinforcement Learning from AI Feedback (RLAIF). When would you prefer one over the other?",
        "task_type": "reasoning",
        "priority": 10,
        "annotations_required": 2,
        "published": False,
    },
    {
        "title": "KV cache: purpose and tradeoffs",
        "prompt": "What is a KV (key-value) cache in the context of transformer inference? What are the memory and latency tradeoffs?",
        "task_type": "reasoning",
        "priority": 8,
        "annotations_required": 1,
        "published": False,
    },
    # ── Coding ─────────────────────────────────────────────────────────────────
    {
        "title": "Cosine similarity in Python",
        "prompt": "Write a Python function `cosine_similarity(a, b)` that computes the cosine similarity between two 1D numpy arrays. Handle the zero-vector edge case.",
        "task_type": "coding",
        "priority": 7,
        "annotations_required": 1,
        "published": False,
    },
    {
        "title": "LRU cache implementation",
        "prompt": "Implement an LRU (Least Recently Used) cache in Python with O(1) get and put operations. Support a configurable capacity.",
        "task_type": "coding",
        "priority": 6,
        "annotations_required": 2,
        "published": False,
    },
    # ── Comparison ─────────────────────────────────────────────────────────────
    {
        "title": "Fine-tuning with limited data: two approaches",
        "prompt": "What is the best approach for fine-tuning a large language model when you have very limited labeled data (< 1000 examples)?",
        "task_type": "comparison",
        "priority": 9,
        "annotations_required": 3,
        "published": False,
    },
    # ── Correction ─────────────────────────────────────────────────────────────
    {
        "title": "Backpropagation explanation (find the errors)",
        "prompt": "Explain what backpropagation does in a neural network and how gradients flow.",
        "task_type": "correction",
        "priority": 5,
        "annotations_required": 2,
        "published": False,
    },
    # ── Draft ──────────────────────────────────────────────────────────────────
    {
        "title": "Explain temperature sampling in LLMs",
        "prompt": "How does temperature sampling work in language model decoding? What happens at temperature=0 and temperature=1?",
        "task_type": "reasoning",
        "priority": 5,
        "annotations_required": 1,
        "published": False,
    },
]


async def seed() -> None:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    async with AsyncSessionLocal() as db:
        # ── Users ──────────────────────────────────────────────────────────────
        print("\n── Users ──")
        for u in USERS:
            existing = await db.scalar(select(User).where(User.email == u["email"]))
            if existing:
                print(f"  skip  {u['email']} (already exists)")
                continue
            db.add(User(
                email=u["email"],
                name=u["name"],
                role=u["role"],
                hashed_password=hash_password(u["password"]),
            ))
            print(f"  added {u['email']} ({u['role']})")
        await db.commit()

        # Resolve creator ID (Alice is the default task creator)
        alice = await db.scalar(select(User).where(User.email == "alice@annotaterl.dev"))
        if not alice:
            print("  ERROR: alice not found — skipping tasks")
            return

        # ── Tasks ──────────────────────────────────────────────────────────────
        print("\n── Tasks ──")
        for t in TASKS:
            existing = await db.scalar(select(Task).where(Task.title == t["title"]))
            if existing:
                print(f"  skip  '{t['title']}' (already exists)")
                continue

            status = TaskStatus.available if t["published"] else TaskStatus.draft
            task = Task(
                title=t["title"],
                prompt=t["prompt"],
                task_type=t["task_type"],
                priority=t["priority"],
                annotations_required=t["annotations_required"],
                status=status,
                created_by=alice.id,
                metadata_={},
            )
            db.add(task)
            await db.commit()  # commit first so generate_for_task can see the task

            if t["published"]:
                await publish_task(redis, task.id, task.priority)
                await generate_for_task(task.id)

            print(f"  added '{task.title}' [{task.task_type}, {status}]")

    await redis.aclose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(seed())
