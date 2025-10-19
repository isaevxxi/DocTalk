"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.logging import setup_logging

# Initialize logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan events.

    Handles startup and shutdown tasks:
    - Database connection verification
    - Service initialization (MinIO, etc.)
    - Resource cleanup on shutdown
    """
    # Startup
    logger.info(
        "Starting DokTalk API",
        extra={
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "debug": settings.APP_DEBUG,
        },
    )

    # Verify database connection
    try:
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            logger.info("Database connection verified")
            break
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    # Initialize MinIO buckets (if MinIO service is available)
    try:
        from app.services.storage import get_minio_service

        minio_service = get_minio_service()
        await minio_service.ensure_buckets_exist()
        logger.info("MinIO buckets verified")
    except Exception as e:
        logger.warning(f"MinIO initialization skipped: {e}")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down DokTalk API")

    # Close database connections
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Ambient Clinical Scribe and Assistant for Russian Healthcare",
    docs_url="/api/docs" if settings.APP_DEBUG else None,
    redoc_url="/api/redoc" if settings.APP_DEBUG else None,
    openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint for load balancers and monitoring."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
        },
    )


# Readiness check endpoint
@app.get("/ready", tags=["Health"])
async def readiness_check() -> JSONResponse:
    """Readiness check endpoint - verifies all dependencies are available."""
    checks = {
        "database": "unknown",
        "redis": "not_configured",
        "minio": "not_configured",
        "vault": "not_configured",
    }

    # Check database connection
    try:
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            checks["database"] = "ok"
            break
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = "error"
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": settings.APP_NAME,
                "checks": checks,
            },
        )

    # TODO: Check Redis connection when configured
    # TODO: Check MinIO connection when configured
    # TODO: Check Vault connection when configured

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "service": settings.APP_NAME,
            "checks": checks,
        },
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }


# Include API routers
from app.api.v1 import api_router

app.include_router(api_router, prefix="/api/v1")
