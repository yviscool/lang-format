from __future__ import annotations

import os
import platform
import uuid
from pathlib import Path

import sublime
import sublime_plugin

from LanguageFormat.adapters.base import FormatterAdapter
from LanguageFormat.core.contracts import (
    ExecutableDiscovery,
    FormatRequest,
    FormatResult,
    ViewSnapshot,
)
from LanguageFormat.core.discovery import discover_executable
from LanguageFormat.core.process import run_subprocess
from LanguageFormat.core.registry import ADAPTERS, selectors_for_adapter
from LanguageFormat.core.settings import load_runtime_settings
from LanguageFormat.core.text import clamp_point, detect_newline_style, make_text_range

OUTPUT_PANEL_NAME = "language_format"
PENDING_RESULTS: dict[str, FormatResult] = {}
SelectionOffsets = tuple[tuple[int, int], ...]
BuildRequestResult = tuple[FormatRequest | None, ExecutableDiscovery | None, str | None]


def _resolve_base_dir(view: sublime.View) -> str | None:
    file_name = view.file_name()
    if file_name:
        return str(Path(file_name).resolve().parent)

    window = view.window()
    if window and window.folders():
        return str(Path(window.folders()[0]).resolve())

    try:
        return str(Path(os.getcwd()).resolve())
    except OSError:
        return None


def _snapshot_view(view: sublime.View) -> ViewSnapshot:
    text = view.substr(sublime.Region(0, view.size()))
    selections = tuple((region.a, region.b) for region in view.sel())
    return ViewSnapshot(
        buffer_id=view.buffer_id(),
        change_count=view.change_count(),
        text=text,
        file_name=view.file_name(),
        syntax=view.settings().get("syntax"),
        base_dir=_resolve_base_dir(view),
        newline=detect_newline_style(text),
        selection_regions=selections,
    )


def _guess_stdin_filename(
    view: sublime.View, adapter: FormatterAdapter, base_dir: str | None
) -> str | None:
    if view.file_name():
        return view.file_name()

    stem = "untitled"
    if view.name():
        candidate = Path(view.name())
        if candidate.suffix:
            stem = candidate.stem
            return str((Path(base_dir or os.getcwd()) / f"{stem}{candidate.suffix}").resolve())

    if not base_dir:
        return None

    return str((Path(base_dir) / f"{stem}{adapter.default_extension}").resolve())


def _select_adapter(
    view: sublime.View,
    selector_map: dict[str, tuple[str, ...]],
) -> tuple[FormatterAdapter | None, tuple[str, ...]]:
    point = 0
    if view.size() > 0 and len(view.sel()) > 0:
        point = min(view.sel()[0].begin(), view.size() - 1)

    for adapter in ADAPTERS:
        selectors = selectors_for_adapter(adapter, selector_map)
        if any(view.match_selector(point, selector) for selector in selectors):
            return adapter, selectors
    return None, ()


def _format_ranges(
    view: sublime.View, mode: str, adapter: FormatterAdapter
) -> tuple[SelectionOffsets, str | None]:
    non_empty = [region for region in view.sel() if not region.empty()]
    if mode == "document":
        return (), None

    if mode == "selection" and not non_empty:
        return (), "LanguageFormat: no non-empty selection to format."

    if mode == "auto" and not non_empty:
        return (), None

    if len(non_empty) != 1:
        return (), "LanguageFormat: V1 only supports a single non-empty selection."

    if not adapter.supports_range:
        return (), f"LanguageFormat: {adapter.display_name} does not support selection formatting."

    region = non_empty[0]
    return ((region.begin(), region.end()),), None


def _build_request(view: sublime.View, mode: str) -> BuildRequestResult:
    runtime = load_runtime_settings(view)
    adapter, _selectors = _select_adapter(view, runtime.selector_map)
    if not adapter:
        syntax = view.settings().get("syntax") or "unknown syntax"
        return None, None, f"LanguageFormat: no formatter matched {syntax}."

    offset_ranges, error = _format_ranges(view, mode, adapter)
    if error:
        return None, None, error

    snapshot = _snapshot_view(view)
    ranges = tuple(make_text_range(snapshot.text, start, end) for start, end in offset_ranges)
    stdin_filename = _guess_stdin_filename(view, adapter, snapshot.base_dir)
    executable_info = discover_executable(
        binary_names=adapter.binary_names,
        project_relpaths=adapter.project_binary_relpaths(),
        override=runtime.executables.get(adapter.id),
        start_dir=snapshot.base_dir,
    )
    if not executable_info.executable:
        return (
            None,
            executable_info,
            f"LanguageFormat: {adapter.display_name} executable not found.",
        )

    selection_mode = "selection" if ranges else "document"
    request = FormatRequest(
        adapter_id=adapter.id,
        adapter_name=adapter.display_name,
        executable=executable_info.executable,
        command=(),
        cwd=snapshot.base_dir,
        stdin_filename=stdin_filename,
        config_path=adapter.discover_config(snapshot.base_dir),
        selection_mode=selection_mode,
        ranges=ranges,
        snapshot=snapshot,
    )
    extra_args = runtime.extra_args.get("*", ()) + runtime.extra_args.get(adapter.id, ())
    command = tuple(adapter.build_command(request, extra_args))
    request = FormatRequest(
        adapter_id=request.adapter_id,
        adapter_name=request.adapter_name,
        executable=request.executable,
        command=command,
        cwd=request.cwd,
        stdin_filename=request.stdin_filename,
        config_path=request.config_path,
        selection_mode=request.selection_mode,
        ranges=request.ranges,
        snapshot=request.snapshot,
    )
    return request, executable_info, None


def _render_diagnostic(
    view: sublime.View,
    request: FormatRequest | None,
    executable_info: ExecutableDiscovery | None,
    error: str | None,
) -> str:
    runtime = load_runtime_settings(view)
    adapter, selectors = _select_adapter(view, runtime.selector_map)
    lines = [
        "LanguageFormat Diagnose",
        "",
        f"File: {view.file_name() or '<unsaved>'}",
        f"Syntax: {view.settings().get('syntax') or '<unknown>'}",
        f"Matched adapter: {adapter.id if adapter else '<none>'}",
        f"Selector candidates: {', '.join(selectors) if selectors else '<none>'}",
        f"Base directory: {_resolve_base_dir(view) or '<none>'}",
        "",
    ]

    if request:
        lines.extend(
            (
                f"Executable: {request.executable}",
                f"Command: {' '.join(request.command)}",
                f"stdin filename: {request.stdin_filename or '<none>'}",
                f"Selection mode: {request.selection_mode}",
                f"Config file: {request.config_path or '<none detected>'}",
            )
        )
    elif executable_info and executable_info.executable:
        lines.append(f"Executable: {executable_info.executable}")

    if executable_info:
        lines.extend(("", "Search log:"))
        for item in executable_info.searched:
            lines.append(f"  {item}")

    if error:
        lines.extend(("", f"Error: {error}"))

    return "\n".join(lines)


def _render_install_guide(
    adapter: FormatterAdapter, executable_info: ExecutableDiscovery | None
) -> str:
    lines = [
        f"LanguageFormat Install Guide: {adapter.display_name}",
        "",
        adapter.build_install_help(platform.system()),
    ]
    if executable_info:
        lines.extend(("", "Search log:"))
        for item in executable_info.searched:
            lines.append(f"  {item}")
    return "\n".join(lines)


def _show_output_panel(window: sublime.Window | None, content: str) -> None:
    if not window:
        return
    panel = window.create_output_panel(OUTPUT_PANEL_NAME)
    panel.run_command("language_format_render_panel", {"content": content})
    window.run_command("show_panel", {"panel": f"output.{OUTPUT_PANEL_NAME}"})


def _execute_request(request: FormatRequest) -> FormatResult:
    returncode, stdout, stderr = run_subprocess(request.command, request.snapshot.text, request.cwd)
    return FormatResult(request=request, returncode=returncode, stdout=stdout, stderr=stderr)


def _schedule_apply(view: sublime.View, result: FormatResult) -> None:
    token = uuid.uuid4().hex
    PENDING_RESULTS[token] = result
    view.run_command("language_format_apply_result", {"token": token})


def _run_request_async(view: sublime.View, request: FormatRequest) -> None:
    def runner() -> None:
        result = _execute_request(request)
        sublime.set_timeout(lambda: _schedule_apply(view, result))

    sublime.set_timeout_async(runner)


class LanguageFormatCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, mode: str = "auto", trigger: str = "manual") -> None:
        del edit
        runtime = load_runtime_settings(self.view)
        request, executable_info, error = _build_request(self.view, mode)
        if error:
            sublime.status_message(error)
            if executable_info and not request:
                adapter, _ = _select_adapter(self.view, runtime.selector_map)
                if adapter and runtime.show_output_panel_on_error:
                    _show_output_panel(
                        self.view.window(), _render_install_guide(adapter, executable_info)
                    )
            return

        if not request:
            return

        if trigger == "save":
            _schedule_apply(self.view, _execute_request(request))
            return

        sublime.status_message(f"LanguageFormat: running {request.adapter_name}...")
        _run_request_async(self.view, request)


class LanguageFormatDocumentCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        del edit
        self.view.run_command("language_format", {"mode": "document"})


class LanguageFormatSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        del edit
        self.view.run_command("language_format", {"mode": "selection"})


class LanguageFormatApplyResultCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, token: str) -> None:
        result = PENDING_RESULTS.pop(token, None)
        if not result:
            return

        if self.view.change_count() != result.request.snapshot.change_count:
            _show_output_panel(
                self.view.window(),
                "\n".join(
                    (
                        "LanguageFormat",
                        "",
                        "The buffer changed before the formatter result could be applied.",
                        "The formatter output was discarded to avoid overwriting newer edits.",
                    )
                ),
            )
            return

        if not result.ok:
            runtime = load_runtime_settings(self.view)
            message = (
                result.stderr.strip()
                or f"{result.request.adapter_name} exited with code {result.returncode}."
            )
            sublime.status_message(f"LanguageFormat: {message}")
            if runtime.show_output_panel_on_error:
                _show_output_panel(
                    self.view.window(),
                    "\n".join(
                        (
                            f"{result.request.adapter_name} failed",
                            "",
                            f"Command: {' '.join(result.request.command)}",
                            f"Working directory: {result.request.cwd or '<none>'}",
                            "",
                            message,
                        )
                    ),
                )
            return

        formatted = result.stdout
        if formatted == result.request.snapshot.text:
            sublime.status_message(
                f"LanguageFormat: {result.request.adapter_name} made no changes."
            )
            return

        self.view.replace(edit, sublime.Region(0, self.view.size()), formatted)
        size = self.view.size()
        selections = [
            sublime.Region(clamp_point(a, size), clamp_point(b, size))
            for a, b in result.request.snapshot.selection_regions
        ]
        self.view.sel().clear()
        for region in selections:
            self.view.sel().add(region)

        if result.stderr.strip():
            _show_output_panel(
                self.view.window(),
                "\n".join(
                    (
                        f"{result.request.adapter_name} warnings",
                        "",
                        result.stderr.strip(),
                    )
                ),
            )
        sublime.status_message(f"LanguageFormat: formatted with {result.request.adapter_name}.")


class LanguageFormatDiagnoseCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        view = self.window.active_view()
        if not view:
            return
        request, executable_info, error = _build_request(view, "auto")
        _show_output_panel(self.window, _render_diagnostic(view, request, executable_info, error))


class LanguageFormatInstallGuideCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        view = self.window.active_view()
        if not view:
            return

        runtime = load_runtime_settings(view)
        adapter, _selectors = _select_adapter(view, runtime.selector_map)
        if not adapter:
            guide = ["LanguageFormat Install Guide", ""]
            for item in ADAPTERS:
                guide.extend((f"[{item.display_name}]", item.build_install_help(platform.system())))
                guide.append("")
            _show_output_panel(self.window, "\n".join(guide).rstrip())
            return

        executable_info = discover_executable(
            binary_names=adapter.binary_names,
            project_relpaths=adapter.project_binary_relpaths(),
            override=runtime.executables.get(adapter.id),
            start_dir=_resolve_base_dir(view),
        )
        _show_output_panel(self.window, _render_install_guide(adapter, executable_info))


class LanguageFormatRenderPanelCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, content: str) -> None:
        self.view.set_read_only(False)
        self.view.replace(edit, sublime.Region(0, self.view.size()), content)
        self.view.set_read_only(True)


class LanguageFormatEventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view: sublime.View) -> None:
        runtime = load_runtime_settings(view)
        if runtime.format_on_save and _select_adapter(view, runtime.selector_map)[0]:
            view.run_command("language_format", {"mode": "document", "trigger": "save"})
