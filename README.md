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
- Install guidance, diagnostics panel, and format-on-save support
- Runtime stays dependency-free on the Python side

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

Default key bindings:

- Windows / Linux: `ctrl+alt+f`
- macOS: `super+alt+f`

## Configuration

Default settings live in `LanguageFormat/LanguageFormat.sublime-settings`.

Primary keys:

- `format_on_save`
- `executables`
- `extra_args`
- `selector_map`
- `show_output_panel_on_error`

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

- `clang-format` and `ruff format` support single-selection formatting
- `gofmt`, `rustfmt`, and `oxfmt` currently format the whole buffer only
- `rustfmt` is invoked with `--emit stdout` and tries to infer the edition from the nearest `Cargo.toml`
