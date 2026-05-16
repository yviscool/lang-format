from __future__ import annotations

from collections.abc import Mapping
from typing import Dict, Tuple

import sublime

from LanguageFormat.core.contracts import RuntimeSettings

SETTINGS_FILENAME = "LanguageFormat.sublime-settings"

DEFAULT_SETTINGS = RuntimeSettings(
    format_on_save=False,
    executables={},
    extra_args={},
    selector_map={},
    format_timeout_ms=10000,
    show_output_panel_on_error=True,
)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _normalize_string_map(value: object) -> Dict[str, Tuple[str, ...]]:
    normalized = {}  # type: Dict[str, Tuple[str, ...]]
    for key, raw in _mapping(value).items():
        if isinstance(raw, str) and raw.strip():
            normalized[str(key)] = (raw.strip(),)
        elif isinstance(raw, (list, tuple)):
            items = tuple(str(item).strip() for item in raw if str(item).strip())
            if items:
                normalized[str(key)] = items
    return normalized


def _merge_string_maps(*maps: object) -> Dict[str, Tuple[str, ...]]:
    merged = {}  # type: Dict[str, Tuple[str, ...]]
    for value in maps:
        merged.update(_normalize_string_map(value))
    return merged


def _project_settings(window: sublime.Window) -> Mapping[str, object]:
    if not window:
        return {}

    project_data = window.project_data() or {}
    settings = project_data.get("settings") or {}
    if isinstance(settings, Mapping):
        return _mapping(settings.get("LanguageFormat", {}))
    return {}


def _setting_value(
    settings: sublime.Settings,
    view_settings: Mapping[str, object],
    project_settings: Mapping[str, object],
    key: str,
    default: object,
) -> object:
    return project_settings.get(
        key,
        view_settings.get(
            key,
            settings.get(key, default),
        ),
    )


def _int_setting(
    settings: sublime.Settings,
    view_settings: Mapping[str, object],
    project_settings: Mapping[str, object],
    key: str,
    default: int,
) -> int:
    raw_value = _setting_value(settings, view_settings, project_settings, key, default)
    if isinstance(raw_value, bool):
        return default
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return default


def load_runtime_settings(view: sublime.View) -> RuntimeSettings:
    settings = sublime.load_settings(SETTINGS_FILENAME)
    project_settings = _project_settings(view.window())
    view_settings = _mapping(view.settings().get("LanguageFormat", {}))

    format_on_save = bool(
        _setting_value(
            settings,
            view_settings,
            project_settings,
            "format_on_save",
            DEFAULT_SETTINGS.format_on_save,
        )
    )
    show_output_panel_on_error = bool(
        _setting_value(
            settings,
            view_settings,
            project_settings,
            "show_output_panel_on_error",
            DEFAULT_SETTINGS.show_output_panel_on_error,
        )
    )
    format_timeout_ms = _int_setting(
        settings,
        view_settings,
        project_settings,
        "format_timeout_ms",
        DEFAULT_SETTINGS.format_timeout_ms,
    )

    executables = _merge_string_maps(
        settings.get("executables", {}),
        view_settings.get("executables", {}),
        project_settings.get("executables", {}),
    )
    extra_args = _merge_string_maps(
        settings.get("extra_args", {}),
        view_settings.get("extra_args", {}),
        project_settings.get("extra_args", {}),
    )
    selector_map = _merge_string_maps(
        settings.get("selector_map", {}),
        view_settings.get("selector_map", {}),
        project_settings.get("selector_map", {}),
    )

    return RuntimeSettings(
        format_on_save=format_on_save,
        executables=executables,
        extra_args=extra_args,
        selector_map=selector_map,
        format_timeout_ms=format_timeout_ms,
        show_output_panel_on_error=show_output_panel_on_error,
    )
