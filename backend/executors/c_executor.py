"""
C executor.

Pipeline:
    1. Compile with gcc -> binary named after the source file.
    2. Run the compiled binary.

PASS requires both stages to succeed (compile exit 0, run exit 0).
FAIL on a compile error or a non-zero/timeout run.
"""

from __future__ import annotations

from pathlib import Path

from backend.executors.base_executor import BaseExecutor


class CExecutor(BaseExecutor):
    language_name = "c"

    def build_commands(self, work_dir: Path, filename: str) -> list[tuple[str, list[str]]]:
        binary_name = Path(filename).stem + ".out"
        return [
            ("compile", ["gcc", filename, "-o", binary_name]),
            ("run", [f"./{binary_name}"]),
        ]
