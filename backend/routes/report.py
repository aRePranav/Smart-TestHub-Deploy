"""
GET /download-report/{session_id}

Streams back the generated .xlsx report for a completed session.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.core.exceptions import SessionNotFoundError
from backend.core.session_manager import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["report"])


@router.get("/download-report/{session_id}")
async def download_report(session_id: str) -> FileResponse:
    """Download the Excel report generated for `session_id`."""
    try:
        session = get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if session.report_path is None or not session.report_path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Report not found. Run /execute for this session first.",
        )

    return FileResponse(
        path=session.report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"test_execution_report_{session_id[:8]}.xlsx",
    )
