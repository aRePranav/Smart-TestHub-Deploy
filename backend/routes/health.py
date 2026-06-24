"""
GET /health

Basic liveness/readiness check. Also reports whether the Docker
sandbox is available, since that materially affects the platform's
actual security posture - useful for ops dashboards and alerting.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.core.schemas import HealthResponse
from backend.executors.base_executor import docker_available

router = APIRouter(tags=["health"])

PLATFORM_VERSION = "1.0.0"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        docker_sandbox_available=False,
        version=PLATFORM_VERSION,
    )
