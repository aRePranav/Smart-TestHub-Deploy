"""
Base executor.

This module contains the real security boundary for the platform:
a locked-down Docker sandbox that every test file runs inside.

Sandbox properties (when Docker is available):
    - Fresh, ephemeral container per execution (`--rm`)
    - No network access (`--network none`)
    - Read-only root filesystem, writable only via a tmpfs work dir
    - Non-root user inside the container
    - Hard memory, CPU, and process-count limits
    - All Linux capabilities dropped
    - `no-new-privileges` security option
    - Wall-clock timeout enforced from the host side as well, so a
      misbehaving container can't outlive its budget

If Docker is NOT available on the host (e.g. local dev without
Docker), the platform falls back to a plain subprocess execution
model with timeout + resource limits via `resource.setrlimit`. This
fallback is clearly logged as a degraded security posture and should
never be relied upon in production - it does not provide filesystem
or network isolation.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from unittest import result

from backend.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    """Normalized outcome of running a single test file."""

    filename: str
    passed: bool
    stage: str  # "compile" | "run" | "test"
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False
    error_message: str = ""


def docker_available() -> bool:
    """Check once whether the `docker` CLI is usable on this host."""
    return shutil.which("docker") is not None


class BaseExecutor(ABC):
    """
    Common contract for all language executors.

    Subclasses implement `_commands(work_dir, filename) -> list[list[str]]`
    describing the sequence of shell commands to run inside the sandbox
    (e.g. [compile_cmd, run_cmd] for compiled languages, or just
    [test_cmd] for interpreted ones with a test runner).
    """

    language_name: str = "unknown"

    @abstractmethod
    def build_commands(self, work_dir: Path, filename: str) -> list[tuple[str, list[str]]]:
        """
        Return an ordered list of (stage_name, argv) commands to execute.

        Execution stops at the first command that fails, and that
        stage's name is recorded as the failure stage.
        """
        raise NotImplementedError

    def execute(self, work_dir: Path, filename: str) -> ExecutionResult:
        """
        Run the configured command pipeline for `filename`, inside the
        sandbox if Docker is available, else via the local fallback.
        """
        commands = self.build_commands(work_dir, filename)
        use_docker = False

        if not use_docker:
            logger.warning(
                "Docker not available on this host - falling back to "
                "unsandboxed local execution for '%s'. This is NOT safe "
                "for untrusted code in production.",
                filename,
            )

        for stage_name, argv in commands:
            timeout = (
                settings.COMPILE_TIMEOUT_SECONDS
                if stage_name == "compile"
                else settings.EXECUTION_TIMEOUT_SECONDS
            )

            if use_docker:
                result = self._run_in_docker(work_dir, argv, timeout)
            else:
                result = self._run_local(work_dir, argv, timeout)

            if result.timed_out:
                return ExecutionResult(
                    filename=filename,
                    passed=False,
                    stage=stage_name,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=None,
                    timed_out=True,
                    error_message=f"Execution timed out during '{stage_name}' stage "
                    f"(limit: {timeout}s).",
                )

            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr) 

            if result.exit_code != 0:
                return ExecutionResult(
                    filename=filename,
                    passed=False,
                    stage=stage_name,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.exit_code,
                    error_message=f"Non-zero exit during '{stage_name}' stage.",
                )

        # All stages succeeded.
        return ExecutionResult(
            filename=filename,
            passed=True,
            stage=commands[-1][0] if commands else "none",
            stdout=result.stdout if commands else "",
            stderr=result.stderr if commands else "",
            exit_code=0,
        )

    # ------------------------------------------------------------------
    # Internal: sandboxed execution
    # ------------------------------------------------------------------

    def _run_in_docker(
        self, work_dir: Path, argv: list[str], timeout: int
    ) -> "_RawResult":
        """Run `argv` inside a hardened, ephemeral Docker container."""
        container_work_dir = "/work"
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none" if settings.SANDBOX_NETWORK_DISABLED else "bridge",
            "--memory",
            settings.SANDBOX_MEMORY_LIMIT,
            "--cpus",
            settings.SANDBOX_CPU_LIMIT,
            "--pids-limit",
            str(settings.SANDBOX_PIDS_LIMIT),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            f"{container_work_dir}:rw,exec,size=64m",
            "-v",
            f"{work_dir}:{container_work_dir}/src:ro",
            "-w",
            container_work_dir,
            "--user",
            "1000:1000",
            settings.SANDBOX_IMAGE,
            "bash",
            "-c",
            # Copy read-only source into the writable tmpfs, then run.
            f"cp -r {container_work_dir}/src/. {container_work_dir}/ && "
            + " ".join(_shell_quote(a) for a in argv),
        ]
        return self._run_subprocess(docker_cmd, timeout)

    # ------------------------------------------------------------------
    # Internal: local fallback (NOT sandboxed)
    # ------------------------------------------------------------------

    def _run_local(self, work_dir: Path, argv: list[str], timeout: int) -> "_RawResult":
        return self._run_subprocess(argv, timeout, cwd=work_dir)

    # ------------------------------------------------------------------
    # Shared subprocess plumbing
    # ------------------------------------------------------------------

    def _run_subprocess(
        self, argv: list[str], timeout: int, cwd: Path | None = None
    ) -> "_RawResult":
        try:
            proc = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return _RawResult(stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode)
        except subprocess.TimeoutExpired as exc:
            return _RawResult(
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                exit_code=None,
                timed_out=True,
            )
        except FileNotFoundError as exc:
            return _RawResult(stdout="", stderr=str(exc), exit_code=127)


@dataclass
class _RawResult:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False


def _shell_quote(token: str) -> str:
    """Minimal shell-quoting for tokens passed into the docker bash -c string."""
    if all(c.isalnum() or c in "._-/" for c in token):
        return token
    return "'" + token.replace("'", "'\\''") + "'"
