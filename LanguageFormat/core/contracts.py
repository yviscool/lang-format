from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class TextRange:
    start: int
    end: int
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class ViewSnapshot:
    buffer_id: int
    change_count: int
    text: str
    file_name: Optional[str]
    syntax: Optional[str]
    base_dir: Optional[str]
    newline: str
    selection_regions: Tuple[Tuple[int, int], ...] = ()


@dataclass(frozen=True)
class RuntimeSettings:
    format_on_save: bool = False
    executables: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    extra_args: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    selector_map: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    format_timeout_ms: int = 10000
    show_output_panel_on_error: bool = True


@dataclass(frozen=True)
class ExecutableDiscovery:
    executable: Optional[str]
    source: Optional[str]
    searched: Tuple[str, ...] = ()


@dataclass(frozen=True)
class FormatRequest:
    adapter_id: str
    adapter_name: str
    executable: str
    command: Tuple[str, ...]
    cwd: Optional[str]
    stdin_filename: Optional[str]
    config_path: Optional[str]
    selection_mode: str
    ranges: Tuple[TextRange, ...]
    snapshot: ViewSnapshot
    timeout_ms: int = 10000
    executable_source: Optional[str] = None


@dataclass(frozen=True)
class FormatResult:
    request: FormatRequest
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int = 0
    timed_out: bool = False
    system_error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.system_error is None
