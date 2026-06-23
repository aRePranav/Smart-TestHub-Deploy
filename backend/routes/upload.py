"""
POST /upload

Accepts one or more files (including .zip archives), validates each
one, runs the pre-filter security scan on Python sources, extracts
ZIPs safely, and stashes everything in a fresh session's temp work
directory ready for /execute.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from backend.core.detector import detect_language
from backend.core.exceptions import (
    DangerousContentDetectedError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    ZipBombError,
    ZipSlipError,
)
from backend.core.file_validator import validate_upload
from backend.core.schemas import UploadedFileInfo, UploadResponse
from backend.core.security import scan_source_if_python
from backend.core.session_manager import create_session
from backend.utils.cleanup import cleanup_directory
from backend.utils.zip_handler import safe_extract_zip

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: list[UploadFile]) -> UploadResponse:
    """
    Validate and stage uploaded files into a new execution session.

    Accepts single files, multiple files, or a single ZIP archive in
    the same request. Returns a session_id used by /execute.
    """
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No files were uploaded.")

    session = create_session()
    file_infos: list[UploadedFileInfo] = []

    try:
        for upload in files:
            validated = await validate_upload(upload)

            if validated.extension == ".zip":
                zip_path = session.work_dir / validated.filename
                zip_path.write_bytes(validated.content)
                extracted_paths = safe_extract_zip(zip_path, session.work_dir)
                zip_path.unlink(missing_ok=True)

                for extracted in extracted_paths:
                    content = extracted.read_bytes()
                    scan_source_if_python(extracted.name, extracted.suffix.lower(), content)
                    language = detect_language(extracted.name)
                    session.uploaded_files.append(extracted.name)
                    file_infos.append(
                        UploadedFileInfo(
                            filename=extracted.name,
                            size_bytes=len(content),
                            language=language.value,
                        )
                    )
            else:
                scan_source_if_python(validated.filename, validated.extension, validated.content)
                target_path = session.work_dir / validated.filename
                target_path.write_bytes(validated.content)

                language = detect_language(validated.filename)
                session.uploaded_files.append(validated.filename)
                file_infos.append(
                    UploadedFileInfo(
                        filename=validated.filename,
                        size_bytes=validated.size_bytes,
                        language=language.value,
                    )
                )

        logger.info(
            "Session %s: staged %d file(s) for execution",
            session.session_id,
            len(file_infos),
        )
        return UploadResponse(session_id=session.session_id, files=file_infos)

    except (
        UnsupportedFileTypeError,
        FileTooLargeError,
        DangerousContentDetectedError,
        ZipSlipError,
        ZipBombError,
    ) as exc:
        cleanup_directory(session.work_dir)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected error during upload for session %s", session.session_id)
        cleanup_directory(session.work_dir)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error while processing upload."
        ) from exc
