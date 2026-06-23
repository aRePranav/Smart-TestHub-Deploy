"""Unit tests for backend.core.detector."""

from __future__ import annotations

import pytest

from backend.core.detector import Language, detect_language
from backend.core.exceptions import LanguageDetectionError


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("test_login.py", Language.PYTHON),
        ("Calculator.c", Language.C),
        ("MainTest.java", Language.JAVA),
    ],
)
def test_detect_language_known_extensions(filename: str, expected: Language) -> None:
    assert detect_language(filename) == expected


def test_detect_language_unknown_extension_raises() -> None:
    with pytest.raises(LanguageDetectionError):
        detect_language("script.exe")


def test_detect_language_no_extension_raises() -> None:
    with pytest.raises(LanguageDetectionError):
        detect_language("noextension")
