"""
ZIP handling utilities.

Provides safe extraction of user-uploaded ZIP archives, defending
against:

    - Zip-slip (entries with path traversal like "../../etc/passwd"
      or absolute paths that would write outside the target dir).
    - Zip bombs (archives that decompress to a huge size, or contain
      an excessive number of entries).
    - Disallowed file types smuggled inside the archive.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

from backend.core.config import settings
from backend.core.detector import is_supported_extension
from backend.core.exceptions import UnsupportedFileTypeError, ZipBombError, ZipSlipError

logger = logging.getLogger(__name__)


def _resolve_within(base_dir: Path, member_name: str) -> Path:
    """
    Resolve a ZIP member's target path and guarantee it stays within
    `base_dir`. Raises ZipSlipError if it would escape.
    """
    target = (base_dir / member_name).resolve()
    base_resolved = base_dir.resolve()

    if base_resolved not in target.parents and target != base_resolved:
        raise ZipSlipError(
            f"ZIP entry '{member_name}' resolves outside the extraction "
            "directory and was rejected."
        )
    return target


def safe_extract_zip(zip_path: Path, destination_dir: Path) -> list[Path]:
    """
    Safely extract `zip_path` into `destination_dir`.

    Returns the list of extracted file paths (directories are created
    but not returned).

    Raises:
        ZipSlipError: on path-traversal attempts.
        ZipBombError: if file count or uncompressed size exceeds limits.
        UnsupportedFileTypeError: if a member has a disallowed extension.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()

        if len(infos) > settings.MAX_FILES_PER_ZIP:
            raise ZipBombError(
                f"ZIP contains {len(infos)} entries, exceeding the limit of "
                f"{settings.MAX_FILES_PER_ZIP}."
            )

        total_uncompressed = sum(info.file_size for info in infos)
        if total_uncompressed > settings.MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ZipBombError(
                f"ZIP would decompress to {total_uncompressed} bytes, exceeding "
                f"the limit of {settings.MAX_ZIP_UNCOMPRESSED_BYTES} bytes."
            )

        for info in infos:
            if info.is_dir():
                continue

            member_name = info.filename
            target_path = _resolve_within(destination_dir, member_name)

            extension = "." + member_name.rsplit(".", 1)[-1].lower() if "." in member_name else ""
            if not is_supported_extension(extension):
                logger.warning(
                    "Skipping ZIP member '%s': unsupported extension '%s'",
                    member_name,
                    extension,
                )
                raise UnsupportedFileTypeError(
                    f"ZIP entry '{member_name}' has disallowed extension '{extension}'."
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, open(target_path, "wb") as dest:
                dest.write(source.read())

            extracted.append(target_path)

    logger.info("Safely extracted %d file(s) from '%s'", len(extracted), zip_path.name)
    return extracted
