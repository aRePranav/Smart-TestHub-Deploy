"""
Automated Test Execution Platform - FastAPI application entrypoint.

Wires together all route modules, configures logging, CORS, global
exception handling, and serves the static frontend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import configure_logging, settings
from backend.core.exceptions import PlatformError
from backend.routes import execute, health, report, upload

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Smart-TestHub starting up.")
    logger.info("Upload dir: %s | Temp dir: %s", settings.UPLOAD_DIR, settings.TEMP_DIR)
    yield
    logger.info("Smart-TestHub shutting down.")


app = FastAPI(
    title="Smart-TestHub",
    description=(
        "Production-grade platform for automated execution of uploaded "
        "software test case files (Python, C, Java) with sandboxed "
        "execution and Excel reporting."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: permissive by default for local/dev use behind the bundled
# frontend. In production, restrict `allow_origins` to your actual
# frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PlatformError)
async def platform_error_handler(request: Request, exc: PlatformError) -> JSONResponse:
    logger.warning("PlatformError on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(upload.router, prefix="/api")
app.include_router(execute.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(health.router, prefix="/api")

# Serve the vanilla HTML/CSS/JS frontend at the root path.
app.mount("/", StaticFiles(directory=str(settings.BASE_DIR.parent / "frontend"), html=True), name="frontend")
