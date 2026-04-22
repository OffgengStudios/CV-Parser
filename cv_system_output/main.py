"""
main.py — FastAPI application factory and entry point.

Startup sequence:
1. Create DB tables (idempotent)
2. Mount API router
3. Serve via uvicorn
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import settings
from database.session import create_tables
from logger import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup/shutdown tasks."""
    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    create_tables()
    yield
    log.info("Shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "CV parsing and classification API. "
        "Accepts PDF/DOCX uploads, extracts structured candidate data, "
        "and classifies into: Administration, Trade, IT, Marketing, Sales."
    ),
    lifespan=lifespan,
)

# Configure CORS with restricted origins
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
allowed_origins = [origin.strip() for origin in allowed_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router)


@app.get("/", tags=["System"])
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )

