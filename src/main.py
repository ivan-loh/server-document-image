"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.config import settings
from src.api.routes import render
from src.core.cache import CacheService
from src.utils.metrics import configure_logging

logger = logging.getLogger(__name__)

cache_service: CacheService | None = None

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    global cache_service

    logger.info("Starting application...")
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)
    cache_service = CacheService()
    logger.info("Application started successfully")

    yield

    logger.info("Shutting down application...")
    logger.info("Application shut down successfully")


app = FastAPI(
    title="Document-to-Image Conversion Service",
    description="High-performance document rendering API with automatic web optimization",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(render.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Document-to-Image Conversion Service",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
