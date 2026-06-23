"""
Custom exception hierarchy for the platform.

Using specific exception types (instead of bare Exception) lets API
routes translate failures into precise HTTP responses and lets us log
distinct failure categories cleanly.
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for all platform-specific errors."""


class UnsupportedFileTypeError(PlatformError):
    """Raised when an uploaded file's extension is not allowed."""


class FileTooLargeError(PlatformError):
    """Raised when an uploaded file exceeds the configured size limit."""


class DangerousContentDetectedError(PlatformError):
    """Raised when the pre-filter flags a file as containing a banned pattern."""


class ZipSlipError(PlatformError):
    """Raised when a ZIP entry would extract outside the target directory."""


class ZipBombError(PlatformError):
    """Raised when a ZIP's uncompressed size or file count exceeds limits."""


class LanguageDetectionError(PlatformError):
    """Raised when the language of an uploaded file cannot be determined."""


class ExecutionTimeoutError(PlatformError):
    """Raised when a test execution exceeds the allotted time budget."""


class SandboxUnavailableError(PlatformError):
    """Raised when the Docker sandbox cannot be started."""


class SessionNotFoundError(PlatformError):
    """Raised when an execute/download request references an unknown session."""
