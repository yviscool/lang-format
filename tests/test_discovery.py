from __future__ import annotations

from pathlib import Path

from LanguageFormat.core.discovery import (
    discover_executable,
    find_named_file_upwards,
    find_rust_edition,
    pyproject_has_tool_table,
)


def test_find_named_file_upwards_walks_to_parent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    config = project / ".clang-format"
    config.write_text("BasedOnStyle: LLVM\n", encoding="utf-8")

    assert find_named_file_upwards(str(nested), (".clang-format",)) == str(config)


def test_pyproject_has_tool_table_detects_nested_table(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff]\nline-length = 88\n", encoding="utf-8")

    assert pyproject_has_tool_table(str(pyproject), "tool", "ruff") is True
    assert pyproject_has_tool_table(str(pyproject), "tool", "missing") is False


def test_discover_executable_prefers_project_local_binary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    local_bin = project / "node_modules" / ".bin"
    local_bin.mkdir(parents=True)
    executable = local_bin / "oxfmt.cmd"
    executable.write_text("@echo off\n", encoding="utf-8")

    result = discover_executable(
        binary_names=("missing-binary",),
        project_relpaths=("node_modules/.bin/oxfmt.cmd",),
        override=None,
        start_dir=str(project),
    )

    assert result.executable == str(executable)
    assert result.source == "project-local"


def test_find_rust_edition_uses_nearest_manifest_then_workspace_parent(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    crate = workspace / "crates" / "demo"
    crate.mkdir(parents=True)

    (workspace / "Cargo.toml").write_text(
        '[workspace]\nmembers = ["crates/demo"]\n[workspace.package]\nedition = "2024"\n',
        encoding="utf-8",
    )
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    assert find_rust_edition(str(crate)) == "2024"

    (crate / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    assert find_rust_edition(str(crate)) == "2021"
