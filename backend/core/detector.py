"""
Language detection.

Version 1 detects language purely from file extension, which is
reliable and unambiguous for the supported set (.py, .c, .java).

The function signature is intentionally generic (filename + optional
content) so future languages that need content-sniffing (e.g.
distinguishing TypeScript from JavaScript) can be added without
changing call sites.
"""

from __future__ import annotations

from enum import Enum

from backend.core.exceptions import LanguageDetectionError


class Language(str, Enum):
    PYTHON = "python"
    C = "c"
    JAVA = "java"


_EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".c": Language.C,
    ".java": Language.JAVA,
}


def detect_language(filename: str) -> Language:
    """
    Detect the programming language of a file from its extension.

    Raises:
        LanguageDetectionError: if the extension has no known mapping.
    """
    if "." not in filename:
        raise LanguageDetectionError(f"Cannot detect language for '{filename}': no extension.")

    extension = "." + filename.rsplit(".", 1)[-1].lower()
    language = _EXTENSION_MAP.get(extension)

    if language is None:
        raise LanguageDetectionError(
            f"Cannot detect language for '{filename}': unsupported extension '{extension}'."
        )

    return language


def is_supported_extension(extension: str) -> bool:
    """Whether the extension maps to a known executable language."""
    return extension in _EXTENSION_MAP
