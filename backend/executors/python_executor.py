"""
Python executor.

Runs uploaded .py files through pytest inside the sandbox.

PASS: pytest exits 0 (all collected tests passed, or no tests were
      collected but the file itself raised no errors at import time -
      see note below).
FAIL: pytest exits non-zero (assertion failure, exception, collection
      error).

Note on files with no pytest-style tests:
    If an uploaded file isn't actually a pytest test module (no
    `test_*` functions), pytest exits 5 ("no tests collected"), which
    we treat as a FAIL with a clear message, since the platform's
    contract is "this is a test case file."
"""

from __future__ import annotations

from pathlib import Path

from backend.executors.base_executor import BaseExecutor

PYTEST_NO_TESTS_COLLECTED_EXIT_CODE = 5


class PythonExecutor(BaseExecutor):
    language_name = "python"

    def build_commands(self, work_dir: Path, filename: str) -> list[tuple[str, list[str]]]:
    return [
        (
            "execute",
            ["python3", filename],
        )
    ]
