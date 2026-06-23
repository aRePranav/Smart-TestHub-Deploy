"""
File validation layer.

Responsible ONLY for structural/type/size validation of uploads.
Does not execute anything and does not inspect file content for
dangerous patterns (that's core/security.py's job) - single
responsibility per module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import UploadFile

from backend.core.config import settings
from backend.core.exceptions import FileTooLargeError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidatedFile:
    """Result of validating a single uploaded file."""

    filename: str
    extension: str
    size_bytes: int
    content: bytes


def _extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


async def validate_upload(file: UploadFile) -> ValidatedFile:
    """
    Validate a single FastAPI UploadFile.

    Reads the file fully into memory (bounded by MAX_FILE_SIZE_BYTES,
    enforced via streaming read below) and returns a ValidatedFile.

    Raises:
        UnsupportedFileTypeError: if extension isn't in the allow-list.
        FileTooLargeError: if content exceeds MAX_FILE_SIZE_BYTES.
    """
    filename = file.filename or "unnamed"
    extension = _extension_of(filename)

    if extension not in settings.ALLOWED_EXTENSIONS:
        logger.warning("Rejected upload '%s': disallowed extension '%s'", filename, extension)
        raise UnsupportedFileTypeError(
            f"File '{filename}' has disallowed extension '{extension}'. "
            f"Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}"
        )

    # Stream-read in chunks so we never buffer more than the limit + 1 chunk
    # before rejecting an oversized upload.
    chunk_size = 1024 * 1024  # 1 MB
    total = 0
    chunks: list[bytes] = []

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.MAX_FILE_SIZE_BYTES:
            logger.warning("Rejected upload '%s': exceeds size limit", filename)
            raise FileTooLargeError(
                f"File '{filename}' exceeds the maximum allowed size of "
                f"{settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    await file.seek(0)

    logger.info("Validated upload '%s' (%d bytes)", filename, total)
    return ValidatedFile(
        filename=filename,
        extension=extension,
        size_bytes=total,
        content=content,
    )
