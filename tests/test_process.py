from __future__ import annotations

import sys

from LanguageFormat.core.process import (
    SYSTEM_ERROR_RETURN_CODE,
    TIMEOUT_RETURN_CODE,
    run_subprocess,
)


def test_run_subprocess_returns_system_error_for_missing_executable() -> None:
    result = run_subprocess(("command-that-does-not-exist",), "", None, 1000)

    assert result.returncode == SYSTEM_ERROR_RETURN_CODE
    assert result.system_error is not None
    assert result.stderr


def test_run_subprocess_reports_timeout() -> None:
    result = run_subprocess(
        (
            sys.executable,
            "-c",
            "import time; time.sleep(0.2)",
        ),
        "",
        None,
        50,
    )

    assert result.returncode == TIMEOUT_RETURN_CODE
    assert result.timed_out is True
    assert "timed out" in result.stderr
