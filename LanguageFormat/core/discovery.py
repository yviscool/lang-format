from __future__ import annotations

import os
import shutil
import tomllib
from pathlib import Path

from LanguageFormat.core.contracts import ExecutableDiscovery


def iter_ancestor_dirs(start_dir: str | None) -> tuple[Path, ...]:
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


def _maybe_resolve_entry(entry: str, start_dir: str | None) -> str:
    expanded = os.path.expandvars(os.path.expanduser(entry))
    candidate = Path(expanded)
    if candidate.is_absolute():
        return str(candidate)
    if start_dir and (any(sep in entry for sep in ("/", "\\")) or entry.startswith(".")):
        return str((Path(start_dir) / candidate).resolve())
    return expanded


def _pick_existing_path(candidate: str) -> str | None:
    if shutil.which(candidate):
        return shutil.which(candidate)

    path = Path(candidate)
    if path.is_file():
        return str(path)
    return None


def _load_toml(path: str | Path) -> dict[str, object] | None:
    try:
        with open(path, "rb") as handle:
            payload = tomllib.load(handle)
    except OSError, tomllib.TOMLDecodeError:
        return None

    if isinstance(payload, dict):
        return payload
    return None


def discover_executable(
    *,
    binary_names: tuple[str, ...],
    project_relpaths: tuple[str, ...],
    override: object,
    start_dir: str | None,
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


def find_named_file_upwards(start_dir: str | None, names: tuple[str, ...]) -> str | None:
    for ancestor in iter_ancestor_dirs(start_dir):
        for name in names:
            candidate = ancestor / name
            if candidate.is_file():
                return str(candidate)
    return None


def pyproject_has_tool_table(pyproject_path: str, *table_path: str) -> bool:
    payload = _load_toml(pyproject_path)
    if not payload:
        return False

    current: object = payload
    for segment in table_path:
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]

    return True


def find_rust_edition(start_dir: str | None) -> str | None:
    valid_editions = {"2015", "2018", "2021", "2024"}

    for ancestor in iter_ancestor_dirs(start_dir):
        cargo_manifest = ancestor / "Cargo.toml"
        if not cargo_manifest.is_file():
            continue

        payload = _load_toml(cargo_manifest)
        if not payload:
            continue

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

    return None
