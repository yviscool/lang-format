from __future__ import annotations

from dataclasses import dataclass, field


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
    file_name: str | None
    syntax: str | None
    base_dir: str | None
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
    executable: str | None
    source: str | None
    searched: tuple[str, ...] = ()


@dataclass(frozen=True)
class FormatRequest:
    adapter_id: str
    adapter_name: str
    executable: str
    command: tuple[str, ...]
    cwd: str | None
    stdin_filename: str | None
    config_path: str | None
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
