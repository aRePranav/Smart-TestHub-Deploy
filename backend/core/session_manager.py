"""
Session manager.

A "session" represents one batch of uploaded files from one user
interaction: upload -> execute -> download report. Sessions are
in-memory and ephemeral (no database, per the "no persistent
storage" requirement) and identified by a UUID4 session_id.

This is a deliberately simple in-process store. For a true
multi-instance production deployment, swap `_SESSIONS` for Redis -
the interface below (`create_session`, `get_session`, etc.) would not
need to change at call sites.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.core.config import settings
from backend.core.exceptions import SessionNotFoundError
from backend.executors.base_executor import ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_id: str
    work_dir: Path
    uploaded_files: list[str] = field(default_factory=list)
    results: list[ExecutionResult] = field(default_factory=list)
    report_path: Path | None = None
    status: str = "uploaded"  # uploaded -> executing -> completed -> failed


_SESSIONS: dict[str, Session] = {}


def create_session() -> Session:
    session_id = str(uuid.uuid4())
    work_dir = settings.TEMP_DIR / session_id
    work_dir.mkdir(parents=True, exist_ok=True)
    session = Session(session_id=session_id, work_dir=work_dir)
    _SESSIONS[session_id] = session
    logger.info("Created session %s", session_id)
    return session


def get_session(session_id: str) -> Session:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise SessionNotFoundError(f"Session '{session_id}' not found.")
    return session


def delete_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)
    logger.info("Removed session %s from registry", session_id)
