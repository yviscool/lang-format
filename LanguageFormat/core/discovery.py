from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional, Union

from LanguageFormat.core.contracts import ExecutableDiscovery

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


SECTION_RE = re.compile(r"^\s*\[(?P<section>[^\]]+)\]\s*$")
KEY_VALUE_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_-]+)\s*=\s*(?P<value>.+?)\s*$")


def iter_ancestor_dirs(start_dir: Optional[str]) -> tuple[Path, ...]:
    if not start_dir:
        return ()

    current = Path(start_dir).resolve()
    dirs = [current]
    dirs.extend(current.parents)
    return tuple(dirs)


def _normalize_override_entries(value: object) -> tuple[str, ...]:
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return tuple(items)
    return ()


def _maybe_resolve_entry(entry: str, start_dir: Optional[str]) -> str:
    expanded = os.path.expandvars(os.path.expanduser(entry))
    candidate = Path(expanded)
    if candidate.is_absolute():
        return str(candidate)
    if start_dir and (any(sep in entry for sep in ("/", "\\")) or entry.startswith(".")):
        return str((Path(start_dir) / candidate).resolve())
    return expanded


def _pick_existing_path(candidate: str) -> Optional[str]:
    if shutil.which(candidate):
        return shutil.which(candidate)

    path = Path(candidate)
    if path.is_file():
        return str(path)
    return None


def _load_toml(path: Union[str, Path]) -> Optional[dict[str, object]]:
    if tomllib is None:
        return None

    try:
        with open(path, "rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    if isinstance(payload, dict):
        return payload
    return None


def _read_text(path: Union[str, Path]) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def _strip_comment(line: str) -> str:
    in_string = False
    quote_char = ""
    escaped = False

    for index, char in enumerate(line):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\" and quote_char == '"':
                escaped = True
            elif char == quote_char:
                in_string = False
            continue

        if char in ('"', "'"):
            in_string = True
            quote_char = char
            continue

        if char == "#":
            return line[:index].rstrip()

    return line.rstrip()


def _unquote_toml_string(value: str) -> Optional[str]:
    if len(value) < 2 or value[0] != value[-1] or value[0] not in ('"', "'"):
        return None
    return value[1:-1]


def _toml_has_table_fallback(path: Union[str, Path], table_path: tuple[str, ...]) -> bool:
    text = _read_text(path)
    if text is None:
        return False

    target = ".".join(table_path)
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        match = SECTION_RE.match(line)
        if not match:
            continue
        section = match.group("section").strip()
        if section == target or section.startswith(f"{target}."):
            return True
    return False


def _toml_string_value_fallback(
    path: Union[str, Path], sections: tuple[str, ...], key: str
) -> Optional[str]:
    text = _read_text(path)
    if text is None:
        return None

    current_section = ""
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        section_match = SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group("section").strip()
            continue

        if current_section not in sections:
            continue

        key_match = KEY_VALUE_RE.match(line)
        if not key_match or key_match.group("key") != key:
            continue

        value = _unquote_toml_string(key_match.group("value").strip())
        if value is not None:
            return value

    return None


def discover_executable(
    *,
    binary_names: tuple[str, ...],
    project_relpaths: tuple[str, ...],
    override: object,
    start_dir: Optional[str],
) -> ExecutableDiscovery:
    searched: list[str] = []

    for entry in _normalize_override_entries(override):
        candidate = _maybe_resolve_entry(entry, start_dir)
        searched.append(candidate)
        resolved = _pick_existing_path(candidate)
        if resolved:
            return ExecutableDiscovery(resolved, "settings", tuple(searched))

    for ancestor in iter_ancestor_dirs(start_dir):
        for relpath in project_relpaths:
            candidate = ancestor / relpath
            searched.append(str(candidate))
            if candidate.is_file():
                return ExecutableDiscovery(str(candidate), "project-local", tuple(searched))

    for name in binary_names:
        searched.append(name)
        resolved = shutil.which(name)
        if resolved:
            return ExecutableDiscovery(resolved, "PATH", tuple(searched))

    return ExecutableDiscovery(None, None, tuple(searched))


def find_named_file_upwards(start_dir: Optional[str], names: tuple[str, ...]) -> Optional[str]:
    for ancestor in iter_ancestor_dirs(start_dir):
        for name in names:
            candidate = ancestor / name
            if candidate.is_file():
                return str(candidate)
    return None


def pyproject_has_tool_table(pyproject_path: str, *table_path: str) -> bool:
    payload = _load_toml(pyproject_path)
    if not payload:
        return _toml_has_table_fallback(pyproject_path, table_path)

    current: object = payload
    for segment in table_path:
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]

    return True


def find_rust_edition(start_dir: Optional[str]) -> Optional[str]:
    valid_editions = {"2015", "2018", "2021", "2024"}

    for ancestor in iter_ancestor_dirs(start_dir):
        cargo_manifest = ancestor / "Cargo.toml"
        if not cargo_manifest.is_file():
            continue

        payload = _load_toml(cargo_manifest)
        if payload:
            sections = (
                payload.get("package"),
                ((payload.get("workspace") or {}).get("package")),
            )
            for section in sections:
                if not isinstance(section, dict):
                    continue
                edition = section.get("edition")
                if isinstance(edition, str) and edition in valid_editions:
                    return edition
            continue

        edition = _toml_string_value_fallback(
            cargo_manifest, ("package", "workspace.package"), "edition"
        )
        if edition in valid_editions:
            return edition

    return None
