"""FastAPI application for ArxivBot."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from arxivbot.limiter import limiter
from arxivbot.routes import api, pages
from arxivbot.services.db import check_db, init_db

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

WWW_HOST = "www.arxivbot.org"
APEX_ORIGIN = "https://arxivbot.org"


@app.middleware("http")
async def redirect_www_to_apex(request: Request, call_next):
    """Redirect www.arxivbot.org to the apex domain so each page has one URL.

    308 preserves method and body, so POSTs to www keep working. Every other
    host (apex, arxivbot.fly.dev, internal health probes) passes through.
    """
    host = request.headers.get("host", "").split(":")[0].lower()
    if host == WWW_HOST:
        location = APEX_ORIGIN + request.url.path
        if request.url.query:
            location += "?" + request.url.query
        return RedirectResponse(location, status_code=308)
    return await call_next(request)


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
    """Health check endpoint for Fly.io: verifies the database is reachable."""
    try:
        await check_db()
    except Exception:
        logger.exception("Health check failed: database unavailable")
        return JSONResponse(
            {"status": "error", "database": "unavailable"}, status_code=503
        )
    return {"status": "ok", "database": "connected"}


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(api.router)
app.include_router(pages.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
