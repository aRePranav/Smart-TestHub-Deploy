"""
Executor package.

Exposes `get_executor(language)`, the single factory function the
rest of the app uses to route a detected language to its executor
implementation. Adding a new language means adding one new executor
class and one new entry in `_EXECUTORS` - no other code changes.
"""

from __future__ import annotations

from backend.core.detector import Language
from backend.executors.base_executor import BaseExecutor
from backend.executors.c_executor import CExecutor
from backend.executors.java_executor import JavaExecutor
from backend.executors.python_executor import PythonExecutor

_EXECUTORS: dict[Language, type[BaseExecutor]] = {
    Language.PYTHON: PythonExecutor,
    Language.C: CExecutor,
    Language.JAVA: JavaExecutor,
}


def get_executor(language: Language) -> BaseExecutor:
    """Return an instantiated executor for the given detected language."""
    executor_cls = _EXECUTORS.get(language)
    if executor_cls is None:
        raise ValueError(f"No executor registered for language: {language}")
    return executor_cls()


__all__ = ["get_executor", "BaseExecutor"]
