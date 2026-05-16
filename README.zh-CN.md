# LanguageFormat

[English](README.md)

`LanguageFormat` 是一个从零构建的 Sublime Text 4 多语言格式化插件，目标是把主流语言格式化工作流统一到一个包里，优先覆盖 C++、Python、TypeScript、Go 和 Rust。

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
- 支持格式化前保存、诊断面板、安装指引
- 运行时零第三方 Python 依赖

## 安装

1. 将 `LanguageFormat/` 目录放入 Sublime Text 的 `Packages/` 目录。
2. 安装对应语言的外部格式化工具：

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

默认配置文件见：

- `LanguageFormat/LanguageFormat.sublime-settings`

常用配置项：

- `format_on_save`
- `executables`
- `extra_args`
- `selector_map`
- `show_output_panel_on_error`

## 开发

```powershell
ruff check LanguageFormat tests
python -m compileall LanguageFormat tests
python -m pytest
```

## 当前限制

- `clang-format` 和 `ruff format` 支持单选区格式化
- `gofmt`、`rustfmt`、`oxfmt` 当前只支持整文件格式化
- `rustfmt` 会根据最近的 `Cargo.toml` 推断 edition，再以 `--emit stdout` 模式运行
