from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.core.config import settings
from app.core.redis import init_redis, close_redis
from app.services.queue import expire_stale_claims
from app.core.db import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    # Expire any stale claims left over from previous run
    async with AsyncSessionLocal() as db:
        expired = await expire_stale_claims(db)
        if expired:
            print(f"Expired {expired} stale assignment(s) on startup")
    yield
    await close_redis()


app = FastAPI(
    title="AnnotateRL",
    description="RLHF/RLAIF data collection platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )


app.include_router(router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready():
    from app.core.redis import get_redis
    from app.core.db import engine
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await get_redis().ping()
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": str(e)})


@app.get("/", include_in_schema=False)
async def root():
    return {"name": "AnnotateRL API", "docs": "/docs"}
