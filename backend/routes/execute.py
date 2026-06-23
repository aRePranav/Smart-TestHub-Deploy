"""
POST /execute

Runs every staged file in a session through its language-appropriate
executor (inside the Docker sandbox where available), collects PASS/
FAIL results, generates the Excel report, and returns a structured
summary. The temp work directory's source files are removed after
execution; only the generated report is kept (in REPORTS_DIR) for
the subsequent /download-report call.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from backend.core.config import settings
from backend.core.detector import detect_language
from backend.core.exceptions import LanguageDetectionError, SessionNotFoundError
from backend.core.excel_generator import generate_excel_report
from backend.core.schemas import ExecuteResponse, TestResultRow
from backend.core.session_manager import get_session
from backend.executors import get_executor
from backend.executors.base_executor import ExecutionResult
from backend.utils.cleanup import cleanup_directory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["execute"])


@router.post("/execute/{session_id}", response_model=ExecuteResponse)
async def execute_session(session_id: str) -> ExecuteResponse:
    """Execute all files staged under `session_id` and produce a report."""
    try:
        session = get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not session.uploaded_files:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Session has no uploaded files to execute."
        )

    session.status = "executing"
    results: list[ExecutionResult] = []

    for filename in session.uploaded_files:
        try:
            language = detect_language(filename)
            executor = get_executor(language)
            result = executor.execute(session.work_dir, filename)
        except LanguageDetectionError as exc:
            result = ExecutionResult(
                filename=filename,
                passed=False,
                stage="detect",
                stdout="",
                stderr="",
                exit_code=None,
                error_message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - safety net per-file
            logger.exception("Unexpected error executing '%s'", filename)
            result = ExecutionResult(
                filename=filename,
                passed=False,
                stage="execute",
                stdout="",
                stderr="",
                exit_code=None,
                error_message=f"Unexpected error: {exc}",
            )
        results.append(result)
        logger.info(
            "Session %s: '%s' -> %s (stage=%s)",
            session_id,
            filename,
            "PASS" if result.passed else "FAIL",
            result.stage,
        )

    session.results = results

    report_path = settings.REPORTS_DIR / f"{session_id}.xlsx"
    generate_excel_report(results, report_path)
    session.report_path = report_path
    session.status = "completed"

    # Per the "no persistent storage" requirement: wipe the uploaded
    # source files now that execution is done. Only the report remains.
    cleanup_directory(session.work_dir)

    rows = [
        TestResultRow(
            **{
                "File Name": r.filename,
                "Test Case No": f"TC{i:03d}",
                "Result": "PASS" if r.passed else "FAIL",
            },
            stage=r.stage,
            error_message=r.error_message or None,
        )
        for i, r in enumerate(results, start=1)
    ]

    passed_count = sum(1 for r in results if r.passed)
    return ExecuteResponse(
        session_id=session_id,
        total=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        results=rows,
    )
