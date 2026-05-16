# LanguageFormat

[中文说明](README.zh-CN.md)

`LanguageFormat` is a from-scratch Sublime Text 4 formatter package focused on one practical goal: a single formatter workflow across multiple languages, with first-class support for C++, Python, TypeScript, Go, and Rust.

## Formatter Stack

- `clang-format` for C / C++ / Objective-C / Objective-C++
- `ruff format` for Python
- `oxfmt` for TypeScript / JavaScript / JSX / TSX / JSON / YAML / TOML / HTML / Vue / Svelte / CSS / SCSS / Less / Markdown / MDX / GraphQL
- `gofmt` for Go
- `rustfmt` for Rust

## Highlights

- Single command surface inside Sublime Text
- Scope-based formatter routing
- Native project config first: `.clang-format`, `pyproject.toml`, `Cargo.toml`, `oxfmt.config.*`
- Built-in config generation wizard for current files and whole workspaces
- Preset selection with `compact`, `recommended`, and `wide` profiles
- Smart target detection for monorepos, preview before apply, and explicit existing-file handling
- Optional Ruff config merge into `pyproject.toml`
- Install guidance, diagnostics panel, and format-on-save support
- Runtime stays dependency-free on the Python side
- Python runtime compatibility from Sublime Text's Python 3.8 up through 3.14

## Install

1. Copy `LanguageFormat/` into your Sublime Text `Packages/` directory.
2. Install the formatter binaries you need:

- C / C++: `winget install LLVM.LLVM`
- Python: `uv tool install ruff`
- TypeScript / JavaScript: `npm install --save-dev oxfmt`
- Go: install Go, which includes `gofmt`
- Rust: `rustup component add rustfmt`

## Commands

- `LanguageFormat: Format`
- `LanguageFormat: Format Document`
- `LanguageFormat: Format Selection`
- `LanguageFormat: Diagnose Current File`
- `LanguageFormat: Install Guide`
- `LanguageFormat: Create Config For Current File`
- `LanguageFormat: Create Workspace Configs`

Default key bindings:

- Windows / Linux: `ctrl+alt+f`
- macOS: `super+alt+f`

## Configuration

Default settings live in `LanguageFormat/LanguageFormat.sublime-settings`.

Primary keys:

- `format_on_save`
- `format_timeout_ms`
- `executables`
- `extra_args`
- `selector_map`
- `show_output_panel_on_error`

Recommended workflow:

- Keep editor settings focused on execution (`format_on_save`, `executables`, timeouts)
- Store style in project-native config files such as `.clang-format`, `pyproject.toml`, `ruff.toml`, `rustfmt.toml`, and `.oxfmtrc.jsonc`
- Use the built-in config generator commands when a project does not have formatter configs yet
- Keep `extra_args` for execution details, not for large embedded style definitions

Generated config files:

- The generator walks you through preset selection, target-directory selection, and existing-file handling
- Current-file generation writes `.editorconfig` plus the formatter config that matches the active syntax
- Workspace generation writes `.editorconfig` and any formatter configs inferred from supported files already present in the workspace
- Python configs can be written to `ruff.toml` or merged into `pyproject.toml`
- Existing config collisions can be skipped, replaced, or emitted as `.example` files
- Every run shows a preview panel before writing files

## Releases

- CI runs on every push to `main`
- Every successful push to `main` creates a GitHub prerelease
- Each prerelease publishes:
  - `LanguageFormat.sublime-package`
  - `LanguageFormat.sublime-package.sha256`

This keeps stable semantic tags separate from edge builds while still giving you a downloadable artifact for every commit.

## Development

```powershell
ruff check LanguageFormat tests
python -m compileall LanguageFormat tests
python -m pytest
```

## Current Limits

- `clang-format` supports multi-selection formatting; `ruff format` supports a single selection
- `gofmt`, `rustfmt`, and `oxfmt` currently format the whole buffer only
- `rustfmt` is invoked with `--emit stdout` and tries to infer the edition from the nearest `Cargo.toml`
