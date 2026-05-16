from __future__ import annotations

import os
import subprocess


def run_subprocess(command: tuple[str, ...], text: str, cwd: str | None) -> tuple[int, str, str]:
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

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
    )
    return completed.returncode, completed.stdout, completed.stderr
