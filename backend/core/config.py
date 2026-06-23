"""
Central configuration for the Automated Test Execution Platform.

All tunables (limits, timeouts, paths) live here so the rest of the
codebase never hardcodes magic numbers.
"""

from __future__ import annotations

import logging
from pathlib import Path


class Settings:
    """Application-wide settings, loaded once at import time."""

    # --- Paths -------------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TEMP_DIR: Path = BASE_DIR / "temp"
    REPORTS_DIR: Path = BASE_DIR / "uploads" / "reports"

    # --- Upload limits -------------------------------------------------
    # NOTE: per user request, raised from the original 50 MB spec to 100 MB.
    MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
    MAX_ZIP_UNCOMPRESSED_BYTES: int = 300 * 1024 * 1024  # zip-bomb guard
    MAX_FILES_PER_ZIP: int = 500

    ALLOWED_EXTENSIONS: set[str] = {".py", ".c", ".java", ".zip"}

    # --- Execution limits ----------------------------------------------
    EXECUTION_TIMEOUT_SECONDS: int = 5
    COMPILE_TIMEOUT_SECONDS: int = 15  # compilation gets a bit more room

    # --- Sandbox (Docker) settings --------------------------------------
    # If Docker is unavailable on the host, the platform falls back to a
    # restricted local subprocess sandbox (see executors/base_executor.py),
    # but this is clearly logged as a degraded security posture.
    SANDBOX_IMAGE: str = "test-platform-sandbox:latest"
    SANDBOX_MEMORY_LIMIT: str = "256m"
    SANDBOX_CPU_LIMIT: str = "1"
    SANDBOX_PIDS_LIMIT: int = 64
    SANDBOX_NETWORK_DISABLED: bool = True

    # --- Dangerous pattern pre-filter (NOT a security boundary) ---------
    # This is a cheap heuristic to reject obviously hostile uploads before
    # they even reach the sandbox. The actual security boundary is the
    # Docker sandbox itself (network-disabled, read-only fs, resource
    # limits, non-root). This list is intentionally NOT relied upon alone.
    DANGEROUS_PY_PATTERNS: list[str] = [
        "os.system",
        "subprocess",
        "socket",
        "shutil.rmtree",
        "eval(",
        "exec(",
        "__import__",
        "ctypes",
        "pty.spawn",
    ]

    # --- Logging ---------------------------------------------------------
    LOG_LEVEL: int = logging.INFO
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


settings = Settings()

for directory in (
    settings.UPLOAD_DIR,
    settings.TEMP_DIR,
    settings.REPORTS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


def configure_logging() -> None:
    """Configure root logging once at app startup."""
    logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT)
