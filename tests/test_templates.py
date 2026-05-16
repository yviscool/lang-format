from __future__ import annotations

from pathlib import Path

from LanguageFormat.core.templates import (
    MaterializedTemplate,
    apply_generation_plan,
    detect_smart_project_root,
    detect_workspace_languages,
    merge_pyproject_ruff,
    openable_paths_from_results,
    plan_template_generation,
    preset_options,
    python_config_options,
    resolve_target_candidates,
    resolve_workspace_root,
    template_files_for_adapter,
    template_files_for_workspace,
)


def test_template_files_for_adapter_includes_editorconfig_and_language_file() -> None:
    templates = template_files_for_adapter("clang-format")

    assert [item.filename for item in templates] == [".editorconfig", ".clang-format"]


def test_template_files_for_go_adapter_only_includes_editorconfig() -> None:
    templates = template_files_for_adapter("gofmt")

    assert [item.filename for item in templates] == [".editorconfig"]


def test_preset_changes_line_width_for_multiple_languages() -> None:
    compact = template_files_for_adapter("clang-format", preset_id="compact")[1]
    wide = template_files_for_adapter("ruff", preset_id="wide")[1]

    assert "ColumnLimit: 88" in compact.content
    assert "line-length = 120" in wide.content


def test_resolve_workspace_root_prefers_deepest_window_folder(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested_project = repo / "apps" / "demo"
    source_dir = nested_project / "src"
    source_dir.mkdir(parents=True)
    (repo / ".git").mkdir()

    root = resolve_workspace_root(str(source_dir), (str(repo), str(nested_project)))

    assert root == str(repo.resolve())


def test_resolve_workspace_root_falls_back_to_vcs_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "pkg"
    source_dir.mkdir(parents=True)
    (repo / ".git").mkdir()

    root = resolve_workspace_root(str(source_dir), ())

    assert root == str(repo.resolve())


def test_detect_smart_project_root_prefers_nearest_subproject_marker(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    package = repo / "packages" / "web"
    source_dir = package / "src"
    source_dir.mkdir(parents=True)
    (repo / ".git").mkdir()
    (package / "package.json").write_text('{"name":"web"}\n', encoding="utf-8")

    root, reason = detect_smart_project_root(source_dir.resolve(), adapter_id="oxfmt")

    assert root == package.resolve()
    assert "package.json" in reason


def test_resolve_target_candidates_orders_project_root_first(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    package = repo / "packages" / "api"
    source_dir = package / "src"
    source_dir.mkdir(parents=True)
    (repo / ".git").mkdir()
    (package / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")

    candidates = resolve_target_candidates(
        str(source_dir),
        (str(repo),),
        adapter_id="ruff",
    )

    assert [item.id for item in candidates] == [
        "smart-project",
        "workspace-folder",
        "current-directory",
    ]
    assert candidates[0].path == str(package.resolve())


def test_detect_workspace_languages_ignores_common_generated_directories(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (project / "src" / "lib.cpp").write_text("int main() {}\n", encoding="utf-8")
    (project / "Cargo.toml").write_text('[package]\nname = "demo"\n', encoding="utf-8")
    (project / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    ignored = project / "node_modules"
    ignored.mkdir()
    (ignored / "generated.rs").write_text("fn main() {}\n", encoding="utf-8")

    languages = detect_workspace_languages(str(project))

    assert languages == ("clang-format", "ruff", "rustfmt", "oxfmt")


def test_template_files_for_workspace_include_detected_languages(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.ts").write_text("const value = 1;\n", encoding="utf-8")
    (project / "worker.py").write_text("print('ok')\n", encoding="utf-8")

    templates = template_files_for_workspace(
        str(project),
        python_config_kind="pyproject.toml",
    )

    assert [item.filename for item in templates] == [
        ".editorconfig",
        "pyproject.toml",
        ".oxfmtrc.jsonc",
    ]


def test_python_config_options_recommend_pyproject_when_present(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    options = python_config_options(str(project))

    assert options[1][1].endswith("(Recommended)")


def test_plan_template_generation_creates_example_files_for_collisions(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    (target / ".clang-format").write_text("BasedOnStyle: LLVM\n", encoding="utf-8")
    target_candidate = resolve_target_candidates(str(target), ())[0]

    plan = plan_template_generation(
        title="demo",
        preset_id="recommended",
        target=target_candidate,
        existing_strategy_id="example",
        templates=template_files_for_adapter("clang-format"),
    )

    actions = {Path(item.path).name: item.action for item in plan.items}

    assert actions == {
        ".editorconfig": "create",
        ".clang-format.recommended.example": "create-example",
    }


def test_plan_template_generation_merges_into_existing_pyproject(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    (target / "pyproject.toml").write_text(
        "[project]\nname = \"demo\"\n\n[tool.ruff]\nline-length = 79\n",
        encoding="utf-8",
    )
    target_candidate = resolve_target_candidates(str(target), ())[0]

    plan = plan_template_generation(
        title="demo",
        preset_id="recommended",
        target=target_candidate,
        existing_strategy_id="skip",
        templates=template_files_for_adapter(
            "ruff",
            python_config_kind="pyproject.toml",
        ),
    )

    pyproject_item = next(item for item in plan.items if Path(item.path).name == "pyproject.toml")

    assert pyproject_item.action == "merge"
    assert pyproject_item.content is not None
    assert 'line-length = 100' in pyproject_item.content
    assert "[tool.ruff.format]" in pyproject_item.content


def test_merge_pyproject_ruff_preserves_unrelated_sections_and_updates_keys() -> None:
    existing = """[project]
name = "demo"

[tool.ruff]
line-length = 79
target-version = "py311"

[tool.ruff.lint]
select = ["E"]
"""
    generated = template_files_for_adapter(
        "ruff",
        preset_id="wide",
        python_config_kind="pyproject.toml",
    )[1].content

    merged = merge_pyproject_ruff(existing, generated)

    assert '[project]' in merged
    assert 'target-version = "py311"' in merged
    assert 'line-length = 120' in merged
    assert '[tool.ruff.format]' in merged
    assert 'select = ["E", "F", "I"]' in merged


def test_apply_generation_plan_writes_created_replaced_and_merged_files(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    (target / ".clang-format").write_text("BasedOnStyle: LLVM\n", encoding="utf-8")
    (target / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    target_candidate = resolve_target_candidates(str(target), ())[0]
    templates = (
        template_files_for_adapter("clang-format")[1],
        template_files_for_adapter("ruff", python_config_kind="pyproject.toml")[1],
    )

    plan = plan_template_generation(
        title="demo",
        preset_id="recommended",
        target=target_candidate,
        existing_strategy_id="replace",
        templates=templates,
    )
    results = apply_generation_plan(plan)

    statuses = {Path(item.path).name: item.status for item in results}

    assert statuses[".clang-format"] == "replaced"
    assert statuses["pyproject.toml"] == "merged"
    assert "ColumnLimit: 100" in (target / ".clang-format").read_text(encoding="utf-8")
    assert "[tool.ruff]" in (target / "pyproject.toml").read_text(encoding="utf-8")


def test_openable_paths_include_existing_when_requested() -> None:
    templates = template_files_for_adapter("ruff")
    results = (
        MaterializedTemplate(
            template=templates[0],
            path="a",
            status="created",
        ),
        MaterializedTemplate(
            template=templates[1],
            path="b",
            status="existing",
        ),
    )

    assert openable_paths_from_results(results) == ("a",)
    assert openable_paths_from_results(results, include_existing=True) == ("a", "b")


def test_preset_options_keep_recommended_first() -> None:
    presets = preset_options()

    assert presets[0].id == "recommended"
