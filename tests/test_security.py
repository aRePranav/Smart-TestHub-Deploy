"""
Unit tests for backend.core.security (the pre-filter scan).

Note: these tests validate the pre-filter heuristic only. They are
NOT a substitute for verifying the sandbox itself - see
test_base_executor.py / manual sandbox verification for that.
"""

from __future__ import annotations

import pytest

from backend.core.exceptions import DangerousContentDetectedError
from backend.core.security import scan_python_source


def test_clean_source_passes() -> None:
    source = "def test_addition():\n    assert 1 + 1 == 2\n"
    scan_python_source("test_math.py", source)  # should not raise


@pytest.mark.parametrize(
    "snippet",
    [
        "import os\nos.system('rm -rf /')",
        "import subprocess\nsubprocess.run(['ls'])",
        "import socket\ns = socket.socket()",
        "eval('1+1')",
        "exec('print(1)')",
        "import shutil\nshutil.rmtree('/')",
    ],
)
def test_dangerous_patterns_are_rejected(snippet: str) -> None:
    with pytest.raises(DangerousContentDetectedError):
        scan_python_source("malicious.py", snippet)
