# LanguageFormat

[English](README.md)

`LanguageFormat` 是一个从零构建的 Sublime Text 4 多语言格式化插件，目标很直接：把多种语言的格式化工作流统一到一个包里，优先覆盖 C++、Python、TypeScript、Go 和 Rust。

## 当前格式化栈

- `clang-format`：C / C++ / Objective-C / Objective-C++
- `ruff format`：Python
- `oxfmt`：TypeScript / JavaScript / JSX / TSX / JSON / YAML / TOML / HTML / Vue / Svelte / CSS / SCSS / Less / Markdown / MDX / GraphQL
- `gofmt`：Go
- `rustfmt`：Rust

## 核心特性

- 单一命令入口：`LanguageFormat: Format`
- 按语法作用域自动选择 formatter
- 优先读取项目原生配置：`.clang-format`、`pyproject.toml`、`Cargo.toml`、`oxfmt.config.*`
- 支持安装指引、诊断面板、保存时格式化
- Python 运行时保持零第三方依赖
- 兼容 Sublime Text 当前常见的 Python 3.8 到 3.14 运行时

## 安装

1. 将 `LanguageFormat/` 目录放入 Sublime Text 的 `Packages/` 目录。
2. 安装你需要的外部 formatter：

- C / C++：`winget install LLVM.LLVM`
- Python：`uv tool install ruff`
- TypeScript / JavaScript：`npm install --save-dev oxfmt`
- Go：安装 Go，自带 `gofmt`
- Rust：`rustup component add rustfmt`

## 使用

命令面板：

- `LanguageFormat: Format`
- `LanguageFormat: Format Document`
- `LanguageFormat: Format Selection`
- `LanguageFormat: Diagnose Current File`
- `LanguageFormat: Install Guide`

默认快捷键：

- Windows / Linux：`ctrl+alt+f`
- macOS：`super+alt+f`

## 配置

默认配置文件：

- `LanguageFormat/LanguageFormat.sublime-settings`

主要配置项：

- `format_on_save`
- `format_timeout_ms`
- `executables`
- `extra_args`
- `selector_map`
- `show_output_panel_on_error`

## 发布策略

- CI 会在每次推送到 `main` 时运行
- 每次成功推送到 `main` 都会自动创建一个 GitHub prerelease
- 每个 prerelease 会附带：
  - `LanguageFormat.sublime-package`
  - `LanguageFormat.sublime-package.sha256`

这样可以保证每个 commit 都有可下载构建，同时又不污染正式语义化版本标签。

## 开发

```powershell
ruff check LanguageFormat tests
python -m compileall LanguageFormat tests
python -m pytest
```

## 当前限制

- `clang-format` 支持多选区格式化，`ruff format` 支持单选区格式化
- `gofmt`、`rustfmt`、`oxfmt` 当前只支持整文件格式化
- `rustfmt` 会根据最近的 `Cargo.toml` 推断 edition，再以 `--emit stdout` 模式运行
