"""FastAPI application for ArxivBot."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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
