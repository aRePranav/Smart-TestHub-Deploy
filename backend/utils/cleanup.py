"""
Cleanup utilities.

Ensures no uploaded user code or execution artifacts persist on disk
after a session completes (or fails). This is a hard platform
requirement: no persistent storage of arbitrary uploaded code.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_directory(path: Path) -> None:
    """Recursively delete `path` if it exists. Never raises."""
    try:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Cleaned up temporary directory: %s", path)
    except Exception:
        logger.exception("Failed to clean up directory: %s", path)
