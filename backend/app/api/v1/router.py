from fastapi import APIRouter

from app.api.v1 import auth, tasks, queue, annotations, metrics, datasets, finetune

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(tasks.router)
router.include_router(queue.router)
router.include_router(annotations.router)
router.include_router(metrics.router)
router.include_router(datasets.router)
router.include_router(finetune.router)
