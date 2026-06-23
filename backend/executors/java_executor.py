"""
Java executor.

Pipeline:
    1. Compile with javac.
    2. Run with java, using the public class name as the entry point.

The "main class" is derived from the filename (Java requires the
public class name to match the filename), e.g. `LoginTest.java` ->
class `LoginTest`.

PASS requires both stages to succeed. FAIL on compile error,
non-zero run exit, or timeout.
"""

from __future__ import annotations

from pathlib import Path

from backend.executors.base_executor import BaseExecutor


class JavaExecutor(BaseExecutor):
    language_name = "java"

    def build_commands(self, work_dir: Path, filename: str) -> list[tuple[str, list[str]]]:
        class_name = Path(filename).stem
        return [
            ("compile", ["javac", filename]),
            ("run", ["java", class_name]),
        ]
