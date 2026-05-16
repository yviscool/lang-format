from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Set, Tuple

from LanguageFormat.core.discovery import iter_ancestor_dirs

WORKSPACE_TEMPLATE_ORDER = ("clang-format", "ruff", "rustfmt", "oxfmt")
SUPPORTED_ADAPTER_ORDER = ("clang-format", "gofmt", "ruff", "rustfmt", "oxfmt")
IGNORED_SCAN_DIRS = frozenset(
    (
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "target",
    )
)
VCS_ROOT_MARKERS = (".git", ".hg", ".svn")
SECTION_RE = re.compile(r"^\s*\[(?P<section>[^\]]+)\]\s*$")
KEY_VALUE_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_-]+)\s*=")


@dataclass(frozen=True)
class TemplatePreset:
    id: str
    caption: str
    description: str
    line_width: int


@dataclass(frozen=True)
class TemplateFile:
    filename: str
    description: str
    content: str
    adapter_id: Optional[str] = None
    write_mode: str = "plain"


@dataclass(frozen=True)
class MaterializedTemplate:
    template: TemplateFile
    path: str
    status: str


@dataclass(frozen=True)
class TargetCandidate:
    id: str
    caption: str
    description: str
    path: str
    reason: str


@dataclass(frozen=True)
class ExistingHandlingStrategy:
    id: str
    caption: str
    description: str


@dataclass(frozen=True)
class PlannedTemplateWrite:
    template: TemplateFile
    path: str
    action: str
    description: str
    content: Optional[str] = None
    existing_path: Optional[str] = None


@dataclass(frozen=True)
class GenerationPlan:
    title: str
    preset: TemplatePreset
    target: TargetCandidate
    existing_strategy: ExistingHandlingStrategy
    items: Tuple[PlannedTemplateWrite, ...]


PRESETS = (
    TemplatePreset(
        id="recommended",
        caption="Recommended",
        description="Balanced defaults with 100-column width.",
        line_width=100,
    ),
    TemplatePreset(
        id="compact",
        caption="Compact",
        description="Tighter 88-column width for denser diffs.",
        line_width=88,
    ),
    TemplatePreset(
        id="wide",
        caption="Wide",
        description="Looser 120-column width for larger displays.",
        line_width=120,
    ),
)

EXISTING_STRATEGIES = (
    ExistingHandlingStrategy(
        id="skip",
        caption="Skip Existing",
        description="Leave existing config files untouched.",
    ),
    ExistingHandlingStrategy(
        id="example",
        caption="Create .example",
        description="Write side-by-side example files for collisions.",
    ),
    ExistingHandlingStrategy(
        id="replace",
        caption="Replace Existing",
        description="Overwrite colliding formatter config files.",
    ),
)

PYTHON_CONFIG_CHOICES = (
    ("ruff.toml", "Use ruff.toml", "Create or update a dedicated Ruff config file."),
    ("pyproject.toml", "Use pyproject.toml", "Create or merge Ruff settings into pyproject.toml."),
)

DETECTION_MARKERS = {
    "clang-format": (
        ".clang-format",
        "_clang-format",
        "cmakelists.txt",
        "compile_commands.json",
        "meson.build",
    ),
    "ruff": ("pyproject.toml", "ruff.toml", ".ruff.toml", "requirements.txt", "setup.py"),
    "rustfmt": ("cargo.toml", "rustfmt.toml", ".rustfmt.toml"),
    "gofmt": ("go.mod", "go.work"),
    "oxfmt": (
        "package.json",
        "tsconfig.json",
        "jsconfig.json",
        "deno.json",
        "deno.jsonc",
        ".oxfmtrc.json",
        ".oxfmtrc.jsonc",
        "oxfmt.config.ts",
        "oxfmt.config.mts",
        "oxfmt.config.cts",
        "oxfmt.config.js",
        "oxfmt.config.mjs",
        "oxfmt.config.cjs",
    ),
}

DETECTION_EXTENSIONS = {
    "clang-format": frozenset(
        (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".m", ".mm")
    ),
    "ruff": frozenset((".py", ".pyi", ".pyw")),
    "rustfmt": frozenset((".rs",)),
    "gofmt": frozenset((".go",)),
    "oxfmt": frozenset(
        (
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
            ".ts",
            ".tsx",
            ".mts",
            ".cts",
            ".css",
            ".scss",
            ".less",
            ".html",
            ".vue",
            ".svelte",
            ".md",
            ".mdx",
            ".graphql",
            ".gql",
            ".json",
            ".jsonc",
            ".json5",
            ".yaml",
            ".yml",
        )
    ),
}


def preset_options() -> Tuple[TemplatePreset, ...]:
    return PRESETS


def preset_by_id(preset_id: str) -> TemplatePreset:
    for preset in PRESETS:
        if preset.id == preset_id:
            return preset
    return PRESETS[0]


def existing_strategy_options() -> Tuple[ExistingHandlingStrategy, ...]:
    return EXISTING_STRATEGIES


def existing_strategy_by_id(strategy_id: str) -> ExistingHandlingStrategy:
    for strategy in EXISTING_STRATEGIES:
        if strategy.id == strategy_id:
            return strategy
    return EXISTING_STRATEGIES[0]


def python_config_options(target_dir: str) -> Tuple[Tuple[str, str, str], ...]:
    preferred = _preferred_python_config_kind(target_dir)
    options = []
    for config_kind, caption, description in PYTHON_CONFIG_CHOICES:
        label = caption
        if config_kind == preferred:
            label = f"{caption} (Recommended)"
        options.append((config_kind, label, description))
    return tuple(options)


def template_files_for_adapter(
    adapter_id: str,
    *,
    preset_id: str = "recommended",
    python_config_kind: str = "ruff.toml",
) -> Tuple[TemplateFile, ...]:
    preset = preset_by_id(preset_id)
    templates = [_editorconfig_template()]
    language_template = _language_template(adapter_id, preset, python_config_kind)
    if language_template:
        templates.append(language_template)
    return tuple(templates)


def template_files_for_workspace(
    root_dir: str,
    *,
    preset_id: str = "recommended",
    python_config_kind: str = "ruff.toml",
) -> Tuple[TemplateFile, ...]:
    preset = preset_by_id(preset_id)
    detected = set(detect_workspace_languages(root_dir))
    templates = [_editorconfig_template()]
    for adapter_id in WORKSPACE_TEMPLATE_ORDER:
        if adapter_id not in detected:
            continue
        language_template = _language_template(adapter_id, preset, python_config_kind)
        if language_template:
            templates.append(language_template)
    return tuple(templates)


def materialize_template_files(
    target_dir: str,
    templates: Sequence[TemplateFile],
) -> Tuple[MaterializedTemplate, ...]:
    directory = Path(target_dir)
    directory.mkdir(parents=True, exist_ok=True)

    materialized = []
    seen = set()  # type: Set[str]
    for template in templates:
        if template.filename in seen:
            continue
        seen.add(template.filename)

        path = directory / template.filename
        if path.exists():
            status = "existing" if path.is_file() else "blocked"
        else:
            path.write_text(_normalize_template_content(template.content), encoding="utf-8")
            status = "created"
        materialized.append(MaterializedTemplate(template, str(path), status))

    return tuple(materialized)


def resolve_workspace_root(
    start_dir: Optional[str],
    window_folders: Sequence[str],
) -> Optional[str]:
    candidates = resolve_target_candidates(start_dir, window_folders)
    if candidates:
        return candidates[0].path
    return None


def resolve_target_candidates(
    start_dir: Optional[str],
    window_folders: Sequence[str],
    *,
    adapter_id: Optional[str] = None,
) -> Tuple[TargetCandidate, ...]:
    resolved_start = Path(start_dir).resolve() if start_dir else None
    resolved_folders = tuple(Path(folder).resolve() for folder in window_folders if folder)

    candidates = []
    seen = set()  # type: Set[str]

    smart_root, smart_reason = detect_smart_project_root(resolved_start, adapter_id=adapter_id)
    if smart_root:
        _append_target_candidate(
            candidates,
            seen,
            TargetCandidate(
                id="smart-project",
                caption="Project Root (Recommended)",
                description=smart_reason,
                path=str(smart_root),
                reason=smart_reason,
            ),
        )

    workspace_root = None
    if resolved_start:
        workspace_root = _deepest_matching_folder(resolved_start, resolved_folders)
    elif resolved_folders:
        workspace_root = resolved_folders[0]
    if workspace_root is not None:
        _append_target_candidate(
            candidates,
            seen,
            TargetCandidate(
                id="workspace-folder",
                caption="Window Folder",
                description="Use the matching top-level folder opened in Sublime Text.",
                path=str(workspace_root),
                reason="Matched an open workspace folder.",
            ),
        )

    if resolved_start is not None:
        _append_target_candidate(
            candidates,
            seen,
            TargetCandidate(
                id="current-directory",
                caption="Current File Directory",
                description="Write config files beside the current file.",
                path=str(resolved_start),
                reason="Uses the active file directory directly.",
            ),
        )

    return tuple(candidates)


def detect_workspace_languages(root_dir: str) -> Tuple[str, ...]:
    found = set()  # type: Set[str]
    all_known = set(DETECTION_MARKERS).union(DETECTION_EXTENSIONS)

    for _current_root, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_SCAN_DIRS]
        _detect_from_filenames(found, filenames)
        if found >= all_known:
            break

    ordered = [adapter_id for adapter_id in SUPPORTED_ADAPTER_ORDER if adapter_id in found]
    return tuple(ordered)


def detect_smart_project_root(
    start_dir: Optional[Path],
    *,
    adapter_id: Optional[str] = None,
) -> Tuple[Optional[Path], str]:
    if start_dir is None:
        return None, "No active file or workspace folder was available."

    for ancestor in iter_ancestor_dirs(str(start_dir)):
        marker = _first_matching_marker(ancestor, adapter_id=adapter_id)
        if marker:
            return ancestor, f"Nearest project marker: {marker}"
        for marker in VCS_ROOT_MARKERS:
            if (ancestor / marker).exists():
                return ancestor, f"Nearest VCS root: {marker}"

    return start_dir, "No project marker was found; using the current directory."


def plan_template_generation(
    *,
    title: str,
    preset_id: str,
    target: TargetCandidate,
    existing_strategy_id: str,
    templates: Sequence[TemplateFile],
) -> GenerationPlan:
    preset = preset_by_id(preset_id)
    strategy = existing_strategy_by_id(existing_strategy_id)

    planned = []
    seen = set()  # type: Set[str]
    for template in templates:
        if template.filename in seen:
            continue
        seen.add(template.filename)
        planned.append(_plan_template_write(target.path, template, strategy, preset))

    return GenerationPlan(
        title=title,
        preset=preset,
        target=target,
        existing_strategy=strategy,
        items=tuple(planned),
    )


def apply_generation_plan(plan: GenerationPlan) -> Tuple[MaterializedTemplate, ...]:
    target_dir = Path(plan.target.path)
    target_dir.mkdir(parents=True, exist_ok=True)

    applied = []
    for item in plan.items:
        status = _apply_planned_write(item)
        applied.append(MaterializedTemplate(item.template, item.path, status))
    return tuple(applied)


def render_generation_plan(plan: GenerationPlan) -> str:
    lines = [
        plan.title,
        "",
        f"Preset: {plan.preset.caption} ({plan.preset.line_width} columns)",
        f"Target directory: {plan.target.path}",
        f"Target reason: {plan.target.reason}",
        f"Existing-file strategy: {plan.existing_strategy.caption}",
    ]

    if not plan.items:
        lines.extend(("", "No template files were selected."))
        return "\n".join(lines)

    lines.extend(("", "Planned operations:"))
    for item in plan.items:
        lines.append(f"  [{item.action.upper()}] {Path(item.path).name} - {item.description}")
    return "\n".join(lines)


def openable_paths_from_results(
    results: Sequence[MaterializedTemplate],
    *,
    include_existing: bool = False,
) -> Tuple[str, ...]:
    paths = []
    seen = set()  # type: Set[str]
    for item in results:
        should_open = item.status in ("created", "replaced", "merged") or (
            include_existing and item.status == "existing"
        )
        if should_open and item.path not in seen:
            seen.add(item.path)
            paths.append(item.path)
    return tuple(paths)


def _append_target_candidate(
    candidates: list,
    seen: Set[str],
    candidate: TargetCandidate,
) -> None:
    normalized = str(Path(candidate.path).resolve())
    if normalized in seen:
        return
    seen.add(normalized)
    candidates.append(candidate)


def _editorconfig_template() -> TemplateFile:
    return TemplateFile(
        filename=".editorconfig",
        description="Cross-language editor defaults",
        content="""root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{c,cc,cpp,cxx,h,hh,hpp,hxx,m,mm,py,rs}]
indent_style = space
indent_size = 4

[*.go]
indent_style = tab
tab_width = 4

[*.{js,jsx,mjs,cjs,ts,tsx,mts,cts,css,scss,less,html,vue,svelte,json,jsonc,json5,yml,yaml,md,mdx,graphql,gql}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
""",
    )


def _language_template(
    adapter_id: str,
    preset: TemplatePreset,
    python_config_kind: str,
) -> Optional[TemplateFile]:
    if adapter_id == "clang-format":
        return TemplateFile(
            filename=".clang-format",
            description=f"{preset.caption} clang-format profile",
            content=_clang_format_content(preset),
            adapter_id=adapter_id,
        )
    if adapter_id == "ruff":
        if python_config_kind == "pyproject.toml":
            return TemplateFile(
                filename="pyproject.toml",
                description=f"{preset.caption} Ruff config merged into pyproject.toml",
                content=_ruff_pyproject_content(preset),
                adapter_id=adapter_id,
                write_mode="merge-pyproject-ruff",
            )
        return TemplateFile(
            filename="ruff.toml",
            description=f"{preset.caption} Ruff formatter and lint profile",
            content=_ruff_toml_content(preset),
            adapter_id=adapter_id,
        )
    if adapter_id == "rustfmt":
        return TemplateFile(
            filename="rustfmt.toml",
            description=f"{preset.caption} rustfmt profile",
            content=_rustfmt_content(preset),
            adapter_id=adapter_id,
        )
    if adapter_id == "oxfmt":
        return TemplateFile(
            filename=".oxfmtrc.jsonc",
            description=f"{preset.caption} Oxc formatter profile",
            content=_oxfmt_content(preset),
            adapter_id=adapter_id,
        )
    return None


def _clang_format_content(preset: TemplatePreset) -> str:
    return f"""BasedOnStyle: Google
IndentWidth: 4
TabWidth: 4
UseTab: Never
ColumnLimit: {preset.line_width}
SortIncludes: true
AlignTrailingComments: true
BreakBeforeBraces: Attach
AllowShortIfStatementsOnASingleLine: false
AllowShortLoopsOnASingleLine: false
IndentCaseLabels: true
"""


def _ruff_toml_content(preset: TemplatePreset) -> str:
    return f"""line-length = {preset.line_width}

[format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"

[lint]
select = ["E", "F", "I"]
"""


def _ruff_pyproject_content(preset: TemplatePreset) -> str:
    return f"""[tool.ruff]
line-length = {preset.line_width}

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"

[tool.ruff.lint]
select = ["E", "F", "I"]
"""


def _rustfmt_content(preset: TemplatePreset) -> str:
    return f"""max_width = {preset.line_width}
hard_tabs = false
tab_spaces = 4
"""


def _oxfmt_content(preset: TemplatePreset) -> str:
    return f"""{{
  "printWidth": {preset.line_width},
  "tabWidth": 2,
  "useTabs": false,
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all"
}}
"""


def _normalize_template_content(content: str) -> str:
    return content.strip() + "\n"


def _first_matching_marker(path: Path, *, adapter_id: Optional[str]) -> Optional[str]:
    adapter_ids = (adapter_id,) if adapter_id else SUPPORTED_ADAPTER_ORDER
    for current_adapter in adapter_ids:
        if not current_adapter:
            continue
        for marker in DETECTION_MARKERS.get(current_adapter, ()):
            if (path / marker).exists():
                return marker
    return None


def _plan_template_write(
    target_dir: str,
    template: TemplateFile,
    strategy: ExistingHandlingStrategy,
    preset: TemplatePreset,
) -> PlannedTemplateWrite:
    path = Path(target_dir) / template.filename
    normalized_content = _normalize_template_content(template.content)

    if template.write_mode == "merge-pyproject-ruff":
        return _plan_pyproject_write(path, template, normalized_content)

    if path.exists() and not path.is_file():
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="blocked",
            description="A directory already exists at this path.",
            existing_path=str(path),
        )

    if not path.exists():
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="create",
            description="Create a new config file.",
            content=normalized_content,
        )

    existing_text = path.read_text(encoding="utf-8", errors="replace")
    if _normalize_template_content(existing_text) == normalized_content:
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="existing",
            description="The existing file already matches this preset.",
            existing_path=str(path),
        )

    if strategy.id == "replace":
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="replace",
            description="Replace the existing file with this preset.",
            content=normalized_content,
            existing_path=str(path),
        )

    if strategy.id == "example":
        example_path = _next_example_path(path, preset.id)
        return PlannedTemplateWrite(
            template=template,
            path=str(example_path),
            action="create-example",
            description=f"Keep the existing file and write {example_path.name}.",
            content=normalized_content,
            existing_path=str(path),
        )

    return PlannedTemplateWrite(
        template=template,
        path=str(path),
        action="existing",
        description="Leave the existing file untouched.",
        existing_path=str(path),
    )


def _plan_pyproject_write(
    path: Path,
    template: TemplateFile,
    normalized_content: str,
) -> PlannedTemplateWrite:
    if path.exists() and not path.is_file():
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="blocked",
            description="A directory already exists at pyproject.toml.",
            existing_path=str(path),
        )

    if not path.exists():
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="create",
            description="Create pyproject.toml with Ruff sections.",
            content=normalized_content,
        )

    existing_text = path.read_text(encoding="utf-8", errors="replace")
    merged = merge_pyproject_ruff(existing_text, normalized_content)
    if merged == existing_text:
        return PlannedTemplateWrite(
            template=template,
            path=str(path),
            action="existing",
            description="pyproject.toml already contains this Ruff preset.",
            existing_path=str(path),
        )

    return PlannedTemplateWrite(
        template=template,
        path=str(path),
        action="merge",
        description="Merge Ruff sections into the existing pyproject.toml.",
        content=merged,
        existing_path=str(path),
    )


def _apply_planned_write(item: PlannedTemplateWrite) -> str:
    if item.action == "blocked":
        return "blocked"
    if item.action == "existing":
        return "existing"
    if item.content is None:
        return "blocked"

    path = Path(item.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(item.content, encoding="utf-8")
    if item.action == "replace":
        return "replaced"
    if item.action == "merge":
        return "merged"
    return "created"


def merge_pyproject_ruff(existing_text: str, generated_text: str) -> str:
    newline = _detect_newline(existing_text)
    lines = existing_text.splitlines(True)
    generated_sections = _parse_toml_sections(generated_text, newline)

    for section_name, body_lines in generated_sections:
        lines = _upsert_toml_section(lines, section_name, body_lines, newline)

    merged = "".join(lines)
    if merged and not merged.endswith(("\n", "\r")):
        merged += newline
    return merged


def _parse_toml_sections(text: str, newline: str) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
    lines = _normalize_template_content(text).splitlines(True)
    sections = []
    current_name = None
    current_body = []  # type: list[str]

    for line in lines:
        match = SECTION_RE.match(line.strip())
        if match:
            if current_name is not None:
                sections.append((current_name, tuple(current_body)))
            current_name = match.group("section").strip()
            current_body = []
            continue
        if current_name is not None:
            current_body.append(_ensure_newline(line, newline))

    if current_name is not None:
        sections.append((current_name, tuple(current_body)))

    return tuple(sections)


def _upsert_toml_section(
    lines: Sequence[str],
    section_name: str,
    body_lines: Sequence[str],
    newline: str,
) -> list[str]:
    mutable = list(lines)
    section_range = _find_toml_section_range(mutable, section_name)

    if section_range is None:
        if mutable and mutable[-1].strip():
            mutable.append(newline)
        mutable.append(f"[{section_name}]{newline}")
        mutable.extend(_normalize_body_lines(body_lines, newline))
        return mutable

    start, end = section_range
    existing_body = mutable[start + 1 : end]
    merged_body = _merge_toml_section_body(existing_body, body_lines, newline)
    mutable[start + 1 : end] = merged_body
    return mutable


def _find_toml_section_range(lines: Sequence[str], section_name: str) -> Optional[Tuple[int, int]]:
    start = None
    for index, line in enumerate(lines):
        match = SECTION_RE.match(line.strip())
        if not match:
            continue
        current_section = match.group("section").strip()
        if current_section == section_name:
            start = index
            continue
        if start is not None:
            return start, index

    if start is None:
        return None
    return start, len(lines)


def _merge_toml_section_body(
    existing_body: Sequence[str],
    generated_body: Sequence[str],
    newline: str,
) -> list[str]:
    normalized_generated = _normalize_body_lines(generated_body, newline)
    generated_key_map = []
    for line in normalized_generated:
        key = _toml_key_for_line(line)
        if key:
            generated_key_map.append((key, line))

    generated_lookup = {key: line for key, line in generated_key_map}
    seen = set()  # type: Set[str]
    merged = []

    for line in existing_body:
        key = _toml_key_for_line(line)
        if key and key in generated_lookup:
            merged.append(generated_lookup[key])
            seen.add(key)
            continue
        merged.append(_ensure_newline(line, newline))

    missing = [line for key, line in generated_key_map if key not in seen]
    if missing:
        if merged and merged[-1].strip():
            merged.append(newline)
        merged.extend(missing)

    if not merged:
        return list(normalized_generated)

    return merged


def _normalize_body_lines(lines: Sequence[str], newline: str) -> Tuple[str, ...]:
    normalized = []
    for line in lines:
        stripped = line.rstrip("\r\n")
        normalized.append(f"{stripped}{newline}")
    return tuple(normalized)


def _toml_key_for_line(line: str) -> Optional[str]:
    match = KEY_VALUE_RE.match(line)
    if not match:
        return None
    return match.group("key")


def _detect_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    return "\n"


def _ensure_newline(line: str, newline: str) -> str:
    return line.rstrip("\r\n") + newline


def _next_example_path(path: Path, preset_id: str) -> Path:
    base_name = f"{path.name}.{preset_id}.example"
    candidate = path.with_name(base_name)
    index = 2
    while candidate.exists():
        candidate = path.with_name(f"{base_name}.{index}")
        index += 1
    return candidate


def _preferred_python_config_kind(target_dir: str) -> str:
    path = Path(target_dir)
    if (path / "pyproject.toml").is_file():
        return "pyproject.toml"
    return "ruff.toml"


def _detect_from_filenames(found: Set[str], filenames: Sequence[str]) -> None:
    for filename in filenames:
        lower_name = filename.lower()
        suffix = Path(lower_name).suffix

        for adapter_id, markers in DETECTION_MARKERS.items():
            if lower_name in markers:
                found.add(adapter_id)

        for adapter_id, extensions in DETECTION_EXTENSIONS.items():
            if suffix in extensions:
                found.add(adapter_id)


def _deepest_matching_folder(start_dir: Path, folders: Iterable[Path]) -> Optional[Path]:
    matches = [folder for folder in folders if _is_relative_to(start_dir, folder)]
    if not matches:
        return None
    return max(matches, key=lambda item: len(item.parts))


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False
