"""
Security layer.

IMPORTANT - READ BEFORE MODIFYING:

This module implements a *defense-in-depth pre-filter*, not the
platform's actual security boundary. The pre-filter scans Python
source text for an explicit deny-list of risky calls (os.system,
eval, exec, subprocess, etc.) and rejects matches outright. This is
useful for catching obviously hostile or accidental dangerous code
early, with a clear error message, before any sandbox is spun up.

It is **not** sufficient on its own. String-level blocklists are
trivially bypassed (string concatenation, base64-encoded payloads,
`__import__`, `getattr(os, "sys" + "tem")`, etc.) and must never be
treated as a real isolation mechanism.

The real security boundary is the sandbox in
`backend/executors/base_executor.py`, which runs every execution
inside a locked-down, network-disabled, resource-limited Docker
container as a non-root user. Treat this module as a cheap, fast
"reject obvious garbage" step - not as the thing keeping the host
safe.
"""

from __future__ import annotations

import logging

from backend.core.config import settings
from backend.core.exceptions import DangerousContentDetectedError

logger = logging.getLogger(__name__)


def scan_python_source(filename: str, source: str) -> None:
    """
    Pre-filter scan for an explicit deny-list of dangerous Python patterns.

    This is a heuristic convenience check, not a security guarantee.
    See module docstring.

    Raises:
        DangerousContentDetectedError: if a banned pattern is found.
    """
    for pattern in settings.DANGEROUS_PY_PATTERNS:
        if pattern in source:
            logger.warning(
                "Pre-filter rejected '%s': matched banned pattern '%s'",
                filename,
                pattern,
            )
            raise DangerousContentDetectedError(
                f"File '{filename}' contains a disallowed pattern "
                f"('{pattern}') and was rejected before execution. "
                "Test files should not perform system calls, network "
                "access, or dynamic code evaluation."
            )


def scan_source_if_python(filename: str, extension: str, content: bytes) -> None:
    """Run the pre-filter scan only for .py files; no-op otherwise."""
    if extension != ".py":
        return
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:  # pragma: no cover - decode is best-effort
        logger.warning("Could not decode '%s' as UTF-8 for pre-filter scan", filename)
        return
    scan_python_source(filename, text)
