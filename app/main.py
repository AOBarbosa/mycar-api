from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Infrastructure endpoint (used by orchestrators/healthchecks),
    # hence mounted outside the versioned API prefix (settings.API_V1_PREFIX).
    app.include_router(health_router)

    # ARCH.md documents these routes unprefixed (e.g. `/auth/register`,
    # not `/api/v1/auth/register`) — settings.API_V1_PREFIX isn't used by
    # any endpoint in the approved contract yet.
    app.include_router(auth_router)

    return app


app = create_app()
