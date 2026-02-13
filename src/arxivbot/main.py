"""FastAPI application for ArxivBot."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from arxivbot.limiter import limiter
from arxivbot.routes import api, pages
from arxivbot.services.db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="ArxivBot",
    description="Chat with arXiv papers using AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Attach limiter to app state
app.state.limiter = limiter

# Add SlowAPIMiddleware
from slowapi.middleware import SlowAPIMiddleware

app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Return JSON for rate limit errors instead of plain text."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please wait a moment before trying again.",
            "retry_after": exc.retry_after if hasattr(exc, "retry_after") else 60,
        },
        headers={
            "Retry-After": str(exc.retry_after if hasattr(exc, "retry_after") else 60)
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint for Fly.io."""
    from arxivbot.config import get_settings

    try:
        db_path = get_settings().database_path
        return {"status": "ok", "database": "connected", "path": str(db_path)}
    except Exception as e:
        from fastapi.responses import JSONResponse

        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(api.router)
app.include_router(pages.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
