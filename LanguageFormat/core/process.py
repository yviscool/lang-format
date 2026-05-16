from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Tuple

TIMEOUT_RETURN_CODE = -2
SYSTEM_ERROR_RETURN_CODE = -1


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int
    timed_out: bool = False
    system_error: Optional[str] = None


def _output_text(value: Optional[str]) -> str:
    if isinstance(value, str):
        return value
    return ""


def run_subprocess(
    command: Tuple[str, ...], text: str, cwd: Optional[str], timeout_ms: int
) -> ProcessResult:
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    timeout_seconds = None
    if timeout_ms > 0:
        timeout_seconds = timeout_ms / 1000.0

    started_at = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=text,
            capture_output=True,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        message = f"LanguageFormat: formatter timed out after {timeout_ms} ms."
        stderr = _output_text(exc.stderr).strip()
        stderr = f"{message}\n\n{stderr}" if stderr else message
        return ProcessResult(
            returncode=TIMEOUT_RETURN_CODE,
            stdout=_output_text(exc.stdout),
            stderr=stderr,
            elapsed_ms=elapsed_ms,
            timed_out=True,
        )
    except OSError as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        message = f"{exc.__class__.__name__}: {exc}"
        return ProcessResult(
            returncode=SYSTEM_ERROR_RETURN_CODE,
            stdout="",
            stderr=message,
            elapsed_ms=elapsed_ms,
            system_error=message,
        )

    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    return ProcessResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        elapsed_ms=elapsed_ms,
    )
