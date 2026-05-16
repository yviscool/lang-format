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
- 内置配置生成向导，支持按当前文件或整个工作区生成配置
- 支持 `compact`、`recommended`、`wide` 三种预设
- 支持 monorepo 智能目标目录识别、预览确认、已有文件处理策略
- 支持将 Ruff 配置直接合并写入 `pyproject.toml`
- 支持安装指引、诊断面板、保存时格式化
- Python 运行时保持零第三方依赖
- 兼容 Sublime Text 当前常见的 Python 3.8 到 3.14 运行时

## 安装

1. 将 `LanguageFormat/` 目录放入 Sublime Text 的 `Packages/` 目录。
   手动更新时请整体替换整个 `LanguageFormat/` 目录，不要只覆盖单个文件；更新后执行 `Tools -> Developer -> Reload Plugins` 或直接重启 Sublime Text。
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
- `LanguageFormat: Create Config For Current File`
- `LanguageFormat: Create Workspace Configs`

配置生成向导流程：

1. 运行 `LanguageFormat: Create Config For Current File` 为当前语言生成配置，或运行 `LanguageFormat: Create Workspace Configs` 扫描整个工作区。
2. 选择预设：`Recommended`、`Compact`、`Wide`。
3. 选择目标目录。默认第一项是插件根据当前文件或工作区推断的项目根目录。
4. 如果是 Python，再选择 Ruff 配置写入 `ruff.toml`，还是合并进 `pyproject.toml`。
5. 选择已有文件处理方式：跳过、替换，或者生成并排的 `.example` 文件。
6. 查看预览面板并确认，插件才会真正写入文件。

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

推荐使用方式：

- 编辑器设置只保留运行相关配置，例如 `format_on_save`、`executables`、超时等
- 风格规则放到项目原生配置文件里，例如 `.clang-format`、`pyproject.toml`、`ruff.toml`、`rustfmt.toml`、`.oxfmtrc.jsonc`
- `extra_args` 只保留少量运行参数，不要再塞整段风格定义

生成的配置文件：

- 当前文件生成模式会写入 `.editorconfig`，并根据当前语言写入对应 formatter 配置
- 工作区生成模式会根据仓库中已检测到的语言生成对应配置
- Python 配置可以独立写入 `ruff.toml`，也可以合并进 `pyproject.toml`
- 已有配置冲突时可以跳过、替换，或生成 `.example` 文件
- 每次写入前都会先显示预览面板

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
