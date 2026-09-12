"""
FastAPI application entry point.

Responsibilities:
    - Application factory with lifespan context for startup/shutdown.
    - Clean Console and Daily Rotating File Logging setup.
    - Scalar API documentation mounted at /docs.
    - Router registration for gateway and monitoring endpoints.
    - Static file serving for the frontend at /app.
    - Clean HTTP access logging middleware.
    - Shared service instances stored in application state.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from scalar_fastapi import get_scalar_api_reference

from app.api import gateway, monitoring
from app.api import notifications, audit, telescope
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.pipeline import layer_3_intelligence
from app.db.session import init_db
from app.services.llm_client import LLMClientService
from app.services.vector_db import VectorDBService

# ---------------------------------------------------------------------------
# Setup logging: Clean console output + Daily file logs in ./logs/
# ---------------------------------------------------------------------------
setup_logging(log_dir="./logs")
# AI Gateway Perimetral - Multilingual Pipeline Entrypoint
logger = logging.getLogger("app.main")


# ---------------------------------------------------------------------------
# Application lifespan: startup and shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle.

    Startup:
        1. Ensures required directories exist (data, models_cache, logs).
        2. Initializes ChromaDB vector store and seeds it if empty.
        3. Pre-warms AI classifier model into RAM.
        4. Opens async HTTP client connection pool for the LLM.

    Shutdown:
        1. Closes the HTTP connection pool gracefully.
    """
    settings = get_settings()

    # Ensure local data, cache, and log directories exist.
    Path(settings.vector_db_path).mkdir(parents=True, exist_ok=True)
    Path(settings.hf_home).mkdir(parents=True, exist_ok=True)
    Path("./logs").mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = settings.hf_home

    logger.info("Starting %s [env: %s]", settings.app_name, settings.app_env)

    # Initialize relational database tables.
    await init_db()
    logger.info("Database tables verified/created.")

    # Initialize ChromaDB service.
    vector_db = VectorDBService(settings)
    vector_db.initialize()
    app.state.vector_db = vector_db

    # Pre-warm the AI classifier (loads model into RAM once).
    layer_3_intelligence.load_model(settings)

    # Initialize the async LLM HTTP client.
    llm_client = LLMClientService(settings)
    llm_client.initialize()
    app.state.llm_client = llm_client

    logger.info("%s is ready. Endpoints: /app (UI) | /docs (Scalar)", settings.app_name)
    yield

    # Graceful shutdown.
    logger.info("Shutting down %s...", settings.app_name)
    await llm_client.close()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.

    Returns:
        A fully configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "A perimeter security proxy for LLM-based applications. "
            "Intercepts, inspects, and sanitizes prompts through a 5-layer "
            "security pipeline before they reach the backend LLM, and audits "
            "responses before returning them to the client."
        ),
        # Disable default Swagger UI; Scalar is used exclusively.
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # Clean HTTP Access Logging Middleware
    # Logs clean, high-level request/response summaries to console and file.
    # -----------------------------------------------------------------------
    @app.middleware("http")
    async def clean_http_logging_middleware(request: Request, call_next):
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        # Omit noisy static file requests from console clutter
        path = request.url.path
        if not path.startswith("/app/style") and not path.startswith("/app/app.js") and not path.startswith("/favicon"):
            log_level = logging.INFO if response.status_code < 400 else logging.WARNING
            logger.log(
                log_level,
                "HTTP %s %s -> %d (%.1fms)",
                request.method,
                path,
                response.status_code,
                duration_ms,
            )

        return response

    # -----------------------------------------------------------------------
    # CORS Middleware
    # -----------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # API Routers
    # -----------------------------------------------------------------------
    app.include_router(gateway.router)
    app.include_router(monitoring.router)
    app.include_router(notifications.router)
    app.include_router(audit.router)
    app.include_router(telescope.router)

    # -----------------------------------------------------------------------
    # Telescope redirect: GET /telescope → SPA
    # -----------------------------------------------------------------------
    @app.get("/telescope", include_in_schema=False)
    async def telescope_redirect():
        """Convenience redirect to the Telescope & Stress-Lab SPA."""
        return RedirectResponse(url="/app/telescope/")

    # -----------------------------------------------------------------------
    # Scalar API Documentation
    # -----------------------------------------------------------------------
    @app.get("/docs", include_in_schema=False)
    async def scalar_docs():
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{settings.app_name} | API Reference",
        )

    # -----------------------------------------------------------------------
    # Frontend Static Files
    # -----------------------------------------------------------------------
    frontend_path = Path("./frontend")
    if frontend_path.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    else:
        logger.warning("Frontend directory not found at ./frontend")

    # -----------------------------------------------------------------------
    # Archify Architecture Explorer Static Files & Redirect
    # -----------------------------------------------------------------------
    archify_path = Path("./docs/archify")
    if archify_path.exists():
        app.mount("/archify", StaticFiles(directory=str(archify_path), html=True), name="archify")

    @app.get("/architecture", include_in_schema=False)
    async def architecture_redirect():
        """Convenience redirect to the Interactive Architecture Suite."""
        return RedirectResponse(url="/archify/")

    # -----------------------------------------------------------------------
    # Direct Markdown Documentation Endpoints for Thesis & Technical Specs
    # -----------------------------------------------------------------------
    @app.get("/{filename}.md", include_in_schema=False)
    async def serve_markdown(filename: str):
        """Serve project markdown files directly for thesis inspection."""
        from fastapi import HTTPException
        from fastapi.responses import FileResponse

        file_candidates = [
            Path(f"./docs/{filename}.md"),
            Path(f"./{filename}.md")
        ]
        for candidate in file_candidates:
            if candidate.exists() and candidate.is_file():
                return FileResponse(
                    path=candidate,
                    media_type="text/markdown; charset=utf-8"
                )
        raise HTTPException(status_code=404, detail=f"Documentation file {filename}.md not found")

    return app


# Module-level application instance used by Uvicorn.
app = create_app()
