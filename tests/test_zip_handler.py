"""
Unit tests for backend.utils.zip_handler.

Covers the security-critical paths: zip-slip rejection, disallowed
extensions inside archives, and normal safe extraction.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from backend.core.exceptions import UnsupportedFileTypeError, ZipSlipError
from backend.utils.zip_handler import safe_extract_zip


def _make_zip(tmp_path: Path, entries: dict[str, bytes]) -> Path:
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return zip_path


def test_safe_extraction_of_normal_files(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path,
        {
            "test_one.py": b"def test_ok():\n    assert True\n",
            "Helper.java": b"public class Helper {}\n",
        },
    )
    destination = tmp_path / "out"
    extracted = safe_extract_zip(zip_path, destination)

    names = sorted(p.name for p in extracted)
    assert names == ["Helper.java", "test_one.py"]
    assert (destination / "test_one.py").read_bytes() == b"def test_ok():\n    assert True\n"


def test_zip_slip_is_rejected(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path, {"../../etc/passwd": b"malicious"})
    destination = tmp_path / "out"

    with pytest.raises(ZipSlipError):
        safe_extract_zip(zip_path, destination)


def test_disallowed_extension_inside_zip_is_rejected(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path, {"payload.exe": b"MZ\x90\x00"})
    destination = tmp_path / "out"

    with pytest.raises(UnsupportedFileTypeError):
        safe_extract_zip(zip_path, destination)
