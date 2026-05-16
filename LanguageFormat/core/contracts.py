from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
    selection_regions: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class RuntimeSettings:
    format_on_save: bool = False
    executables: dict[str, tuple[str, ...]] = field(default_factory=dict)
    extra_args: dict[str, tuple[str, ...]] = field(default_factory=dict)
    selector_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    show_output_panel_on_error: bool = True


@dataclass(frozen=True)
class ExecutableDiscovery:
    executable: Optional[str]
    source: Optional[str]
    searched: tuple[str, ...] = ()


@dataclass(frozen=True)
class FormatRequest:
    adapter_id: str
    adapter_name: str
    executable: str
    command: tuple[str, ...]
    cwd: Optional[str]
    stdin_filename: Optional[str]
    config_path: Optional[str]
    selection_mode: str
    ranges: tuple[TextRange, ...]
    snapshot: ViewSnapshot


@dataclass(frozen=True)
class FormatResult:
    request: FormatRequest
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0
