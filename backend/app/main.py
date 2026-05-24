"""FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyze, storymap, upload
from app.clients.ddb import close_duckdb, get_duckdb
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm DuckDB + spatial extension at startup so the first request isn't slow.
    get_duckdb()
    yield
    close_duckdb()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Tochka API",
        version="0.1.0",
        description="Agent-driven location intelligence.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(upload.router)
    app.include_router(analyze.router)
    app.include_router(storymap.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env, "demo_mode": str(settings.demo_mode)}

    return app


app = create_app()
