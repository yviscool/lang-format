from __future__ import annotations

import os
import platform
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Dict, Optional, Tuple

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
from LanguageFormat.core.templates import (
    ExistingHandlingStrategy,
    GenerationPlan,
    MaterializedTemplate,
    TargetCandidate,
    TemplateFile,
    TemplatePreset,
    apply_generation_plan,
    detect_workspace_languages,
    existing_strategy_options,
    openable_paths_from_results,
    plan_template_generation,
    preset_options,
    python_config_options,
    render_generation_plan,
    resolve_target_candidates,
    template_files_for_adapter,
    template_files_for_workspace,
)
from LanguageFormat.core.text import (
    clamp_point,
    detect_newline_style,
    make_text_range,
    normalize_newlines,
    remap_selection_regions,
)

OUTPUT_PANEL_NAME = "language_format"
PENDING_RESULTS = {}  # type: Dict[str, FormatResult]
SelectionOffsets = Tuple[Tuple[int, int], ...]
BuildRequestResult = Tuple[Optional[FormatRequest], Optional[ExecutableDiscovery], Optional[str]]


def _resolve_base_dir(view: sublime.View) -> Optional[str]:
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


def _view_context_dir(view: sublime.View) -> Optional[str]:
    file_name = view.file_name()
    if file_name:
        return str(Path(file_name).resolve().parent)

    window = view.window()
    if window and window.folders():
        return str(Path(window.folders()[0]).resolve())

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
    view: sublime.View, adapter: FormatterAdapter, base_dir: Optional[str]
) -> Optional[str]:
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
    selector_map: Dict[str, Tuple[str, ...]],
) -> Tuple[Optional[FormatterAdapter], Tuple[str, ...]]:
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
) -> Tuple[SelectionOffsets, Optional[str]]:
    non_empty = [region for region in view.sel() if not region.empty()]
    if mode == "document":
        return (), None

    if mode == "selection" and not non_empty:
        return (), "LanguageFormat: no non-empty selection to format."

    if mode == "auto" and not non_empty:
        return (), None

    if not adapter.supports_range:
        return (), f"LanguageFormat: {adapter.display_name} does not support selection formatting."

    if len(non_empty) > 1 and not adapter.supports_multiple_ranges:
        return (
            (),
            f"LanguageFormat: {adapter.display_name} only supports a single non-empty selection.",
        )

    return tuple((region.begin(), region.end()) for region in non_empty), None


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
        timeout_ms=runtime.format_timeout_ms,
        executable_source=executable_info.source,
    )
    extra_args = runtime.extra_args.get("*", ()) + runtime.extra_args.get(adapter.id, ())
    command = tuple(adapter.build_command(request, extra_args))
    request = replace(request, command=command)
    return request, executable_info, None


def _render_diagnostic(
    view: sublime.View,
    request: Optional[FormatRequest],
    executable_info: Optional[ExecutableDiscovery],
    error: Optional[str],
) -> str:
    runtime = load_runtime_settings(view)
    adapter, selectors = _select_adapter(view, runtime.selector_map)
    non_empty = [region for region in view.sel() if not region.empty()]
    lines = [
        "LanguageFormat Diagnose",
        "",
        f"File: {view.file_name() or '<unsaved>'}",
        f"Syntax: {view.settings().get('syntax') or '<unknown>'}",
        f"Matched adapter: {adapter.id if adapter else '<none>'}",
        f"Selector candidates: {', '.join(selectors) if selectors else '<none>'}",
        f"Base directory: {_resolve_base_dir(view) or '<none>'}",
        f"Selections: {len(view.sel())} total / {len(non_empty)} non-empty",
        "",
    ]

    if request:
        lines.extend(
            (
                f"Executable: {request.executable}",
                f"Executable source: {request.executable_source or '<unknown>'}",
                f"Command: {' '.join(request.command)}",
                f"Working directory: {request.cwd or '<none>'}",
                f"stdin filename: {request.stdin_filename or '<none>'}",
                f"Selection mode: {request.selection_mode}",
                f"Selection ranges: {len(request.ranges)}",
                f"Timeout: {'disabled' if request.timeout_ms <= 0 else f'{request.timeout_ms} ms'}",
                f"Config file: {request.config_path or '<none detected>'}",
            )
        )
    elif executable_info and executable_info.executable:
        lines.extend(
            (
                f"Executable: {executable_info.executable}",
                f"Executable source: {executable_info.source or '<unknown>'}",
            )
        )

    if executable_info:
        lines.extend(("", "Search log:"))
        for item in executable_info.searched:
            lines.append(f"  {item}")

    if error:
        lines.extend(("", f"Error: {error}"))

    return "\n".join(lines)


def _render_install_guide(
    adapter: FormatterAdapter, executable_info: Optional[ExecutableDiscovery]
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


def _open_result_files(
    window: sublime.Window,
    results: Tuple[MaterializedTemplate, ...],
    *,
    include_existing: bool = False,
) -> None:
    for path in openable_paths_from_results(results, include_existing=include_existing):
        window.open_file(path)


def _status_from_materialized(materialized: Tuple[MaterializedTemplate, ...]) -> str:
    labels = (
        ("created", "created"),
        ("replaced", "replaced"),
        ("merged", "merged"),
        ("existing", "kept"),
        ("blocked", "blocked"),
    )
    parts = []
    for status, label in labels:
        count = sum(1 for item in materialized if item.status == status)
        if count:
            parts.append(f"{label} {count}")

    if not parts:
        return "no config files were generated."

    return ", ".join(parts)


def _render_generation_result(
    plan: GenerationPlan,
    results: Tuple[MaterializedTemplate, ...],
) -> str:
    lines = [render_generation_plan(plan), "", "Applied results:"]
    for item in results:
        lines.append(f"  [{item.status.upper()}] {Path(item.path).name}")
    return "\n".join(lines)


def _quick_panel_entries_for_presets(
    presets: Tuple[TemplatePreset, ...],
) -> list:
    entries = []
    for index, preset in enumerate(presets):
        caption = preset.caption
        if index == 0:
            caption = f"{caption} (Recommended)"
        entries.append([caption, preset.description])
    return entries


def _quick_panel_entries_for_targets(
    targets: Tuple[TargetCandidate, ...],
) -> list:
    return [
        [target.caption, f"{target.path} | {target.description}"]
        for target in targets
    ]


def _quick_panel_entries_for_strategies(
    strategies: Tuple[ExistingHandlingStrategy, ...],
) -> list:
    entries = []
    for index, strategy in enumerate(strategies):
        caption = strategy.caption
        if index == 0:
            caption = f"{caption} (Recommended)"
        entries.append([caption, strategy.description])
    return entries


def _quick_panel_entries_for_python_config(options: Tuple[Tuple[str, str, str], ...]) -> list:
    return [[caption, description] for _config_kind, caption, description in options]


def _build_templates_for_selection(
    *,
    adapter: Optional[FormatterAdapter],
    workspace_mode: bool,
    target: TargetCandidate,
    preset_id: str,
    python_config_kind: str,
) -> Tuple[TemplateFile, ...]:
    if workspace_mode:
        return template_files_for_workspace(
            target.path,
            preset_id=preset_id,
            python_config_kind=python_config_kind,
        )
    if not adapter:
        return ()
    return template_files_for_adapter(
        adapter.id,
        preset_id=preset_id,
        python_config_kind=python_config_kind,
    )


def _workspace_needs_python_choice(target: TargetCandidate) -> bool:
    return "ruff" in detect_workspace_languages(target.path)


def _show_output_panel(window: Optional[sublime.Window], content: str) -> None:
    if not window:
        return
    panel = window.create_output_panel(OUTPUT_PANEL_NAME)
    panel.run_command("language_format_render_panel", {"content": content})
    window.run_command("show_panel", {"panel": f"output.{OUTPUT_PANEL_NAME}"})


def _execute_request(request: FormatRequest) -> FormatResult:
    process_result = run_subprocess(
        request.command,
        request.snapshot.text,
        request.cwd,
        request.timeout_ms,
    )
    return FormatResult(
        request=request,
        returncode=process_result.returncode,
        stdout=process_result.stdout,
        stderr=process_result.stderr,
        elapsed_ms=process_result.elapsed_ms,
        timed_out=process_result.timed_out,
        system_error=process_result.system_error,
    )


def _schedule_apply(view: sublime.View, result: FormatResult) -> None:
    token = uuid.uuid4().hex
    PENDING_RESULTS[token] = result
    view.run_command("language_format_apply_result", {"token": token})


def _run_request_async(view: sublime.View, request: FormatRequest) -> None:
    def runner() -> None:
        result = _execute_request(request)
        sublime.set_timeout(lambda: _schedule_apply(view, result))

    sublime.set_timeout_async(runner)


def _result_message(result: FormatResult) -> str:
    if result.system_error:
        return result.system_error
    if result.stderr.strip():
        return result.stderr.strip()
    if result.stdout.strip():
        return result.stdout.strip()
    return f"{result.request.adapter_name} exited with code {result.returncode}."


def _failure_panel_content(result: FormatResult, message: str) -> str:
    lines = [
        f"{result.request.adapter_name} failed",
        "",
        f"Command: {' '.join(result.request.command)}",
        f"Working directory: {result.request.cwd or '<none>'}",
        f"Executable source: {result.request.executable_source or '<unknown>'}",
        f"Elapsed: {result.elapsed_ms} ms",
        "",
        message,
    ]
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if stdout:
        lines.extend(("", "stdout:", stdout))
    if stderr and stderr != message:
        lines.extend(("", "stderr:", stderr))
    return "\n".join(lines)


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
            message = _result_message(result)
            sublime.status_message(f"LanguageFormat: {message}")
            if runtime.show_output_panel_on_error:
                _show_output_panel(self.view.window(), _failure_panel_content(result, message))
            return

        formatted = normalize_newlines(result.stdout, result.request.snapshot.newline)
        if formatted == result.request.snapshot.text:
            sublime.status_message(
                f"LanguageFormat: {result.request.adapter_name} made no changes "
                f"({result.elapsed_ms} ms)."
            )
            return

        remapped_regions = remap_selection_regions(
            result.request.snapshot.text,
            formatted,
            result.request.snapshot.selection_regions,
        )
        self.view.replace(edit, sublime.Region(0, self.view.size()), formatted)
        size = self.view.size()
        selections = [
            sublime.Region(clamp_point(a, size), clamp_point(b, size))
            for a, b in remapped_regions
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
                        f"Elapsed: {result.elapsed_ms} ms",
                        "",
                        result.stderr.strip(),
                    )
                ),
            )
        sublime.status_message(
            f"LanguageFormat: formatted with {result.request.adapter_name} "
            f"({result.elapsed_ms} ms)."
        )


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


def _run_generation_wizard(
    window: sublime.Window,
    *,
    adapter: Optional[FormatterAdapter],
    workspace_mode: bool,
    title: str,
    context_dir: Optional[str],
) -> None:
    targets = resolve_target_candidates(
        context_dir,
        window.folders(),
        adapter_id=adapter.id if adapter else None,
    )
    if not targets:
        sublime.status_message(
            "LanguageFormat: open a file or workspace folder before generating configs."
        )
        return

    presets = preset_options()
    strategies = existing_strategy_options()
    state = {
        "preset": presets[0],
        "target": targets[0],
        "python_config_kind": "ruff.toml",
        "strategy": strategies[0],
    }

    def show_preset_panel() -> None:
        window.show_quick_panel(
            _quick_panel_entries_for_presets(presets),
            on_preset_selected,
        )

    def on_preset_selected(index: int) -> None:
        if index < 0:
            return
        state["preset"] = presets[index]
        window.show_quick_panel(
            _quick_panel_entries_for_targets(targets),
            on_target_selected,
        )

    def on_target_selected(index: int) -> None:
        if index < 0:
            return
        target = targets[index]
        state["target"] = target
        if _needs_python_choice(adapter, workspace_mode, target):
            options = python_config_options(target.path)
            state["python_options"] = options
            window.show_quick_panel(
                _quick_panel_entries_for_python_config(options),
                on_python_config_selected,
            )
            return
        state["python_config_kind"] = "ruff.toml"
        show_strategy_panel()

    def on_python_config_selected(index: int) -> None:
        if index < 0:
            return
        options = state.get("python_options", ())
        if not options:
            state["python_config_kind"] = "ruff.toml"
        else:
            state["python_config_kind"] = options[index][0]
        show_strategy_panel()

    def show_strategy_panel() -> None:
        window.show_quick_panel(
            _quick_panel_entries_for_strategies(strategies),
            on_strategy_selected,
        )

    def on_strategy_selected(index: int) -> None:
        if index < 0:
            return
        strategy = strategies[index]
        state["strategy"] = strategy
        templates = _build_templates_for_selection(
            adapter=adapter,
            workspace_mode=workspace_mode,
            target=state["target"],
            preset_id=state["preset"].id,
            python_config_kind=state["python_config_kind"],
        )
        plan = plan_template_generation(
            title=title,
            preset_id=state["preset"].id,
            target=state["target"],
            existing_strategy_id=strategy.id,
            templates=templates,
        )
        _show_output_panel(window, render_generation_plan(plan))
        if not sublime.ok_cancel_dialog(
            "Apply this LanguageFormat config generation plan?",
            "Apply",
        ):
            return
        _apply_generation_plan(window, plan, include_existing=not workspace_mode)

    show_preset_panel()


def _needs_python_choice(
    adapter: Optional[FormatterAdapter],
    workspace_mode: bool,
    target: TargetCandidate,
) -> bool:
    return bool(
        (adapter and adapter.id == "ruff")
        or (workspace_mode and _workspace_needs_python_choice(target))
    )


def _apply_generation_plan(
    window: sublime.Window,
    plan: GenerationPlan,
    *,
    include_existing: bool,
) -> None:
    results = apply_generation_plan(plan)
    _open_result_files(window, results, include_existing=include_existing)
    _show_output_panel(window, _render_generation_result(plan, results))
    sublime.status_message(
        f"LanguageFormat: {_status_from_materialized(results)} in {plan.target.path}."
    )


class LanguageFormatCreateConfigCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        view = self.window.active_view()
        if not view:
            sublime.status_message("LanguageFormat: no active view to inspect.")
            return

        runtime = load_runtime_settings(view)
        adapter, _selectors = _select_adapter(view, runtime.selector_map)
        if not adapter:
            syntax = view.settings().get("syntax") or "unknown syntax"
            sublime.status_message(f"LanguageFormat: no recommended template for {syntax}.")
            return

        _run_generation_wizard(
            self.window,
            adapter=adapter,
            workspace_mode=False,
            title=f"LanguageFormat Config Generator: {adapter.display_name}",
            context_dir=_view_context_dir(view),
        )


class LanguageFormatCreateWorkspaceConfigsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        view = self.window.active_view()
        _run_generation_wizard(
            self.window,
            adapter=None,
            workspace_mode=True,
            title="LanguageFormat Workspace Config Generator",
            context_dir=_view_context_dir(view) if view else None,
        )


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
