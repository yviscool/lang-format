from __future__ import annotations

from pathlib import Path

from LanguageFormat.adapters.clang import ClangFormatAdapter
from LanguageFormat.adapters.go import GoFormatAdapter
from LanguageFormat.adapters.oxfmt import OxcFormatAdapter
from LanguageFormat.adapters.ruff import RuffFormatAdapter
from LanguageFormat.adapters.rust import RustFormatAdapter
from LanguageFormat.core.contracts import FormatRequest, TextRange, ViewSnapshot


def _request(
    adapter_id: str,
    executable: str,
    selection_mode: str,
    ranges: tuple[TextRange, ...],
) -> FormatRequest:
    snapshot = ViewSnapshot(
        buffer_id=1,
        change_count=1,
        text="print('hello')\n",
        file_name="demo.py",
        syntax="Packages/Python/Python.sublime-syntax",
        base_dir="C:/demo",
        newline="\n",
        selection_regions=((0, 0),),
    )
    return FormatRequest(
        adapter_id=adapter_id,
        adapter_name=adapter_id,
        executable=executable,
        command=(),
        cwd=snapshot.base_dir,
        stdin_filename=snapshot.file_name,
        config_path=None,
        selection_mode=selection_mode,
        ranges=ranges,
        snapshot=snapshot,
    )


def test_clang_command_uses_offset_and_length() -> None:
    request = _request(
        "clang-format",
        "clang-format",
        "selection",
        (TextRange(4, 9, 1, 5, 1, 10),),
    )

    command = ClangFormatAdapter().build_command(request, ("--style=file",))
    assert command == [
        "clang-format",
        "--assume-filename",
        "demo.py",
        "--offset",
        "4",
        "--length",
        "5",
        "--style=file",
    ]


def test_ruff_command_uses_stdin_range() -> None:
    request = _request(
        "ruff",
        "ruff",
        "selection",
        (TextRange(0, 5, 1, 1, 1, 6),),
    )

    command = RuffFormatAdapter().build_command(request, ("--line-length", "100"))
    assert command == [
        "ruff",
        "format",
        "--stdin-filename",
        "demo.py",
        "--range",
        "1:1-1:6",
        "--line-length",
        "100",
        "-",
    ]


def test_oxfmt_command_uses_stdin_filepath() -> None:
    request = _request("oxfmt", "oxfmt", "document", ())
    command = OxcFormatAdapter().build_command(request, ())

    assert command == [
        "oxfmt",
        "--stdin-filepath",
        "demo.py",
    ]


def test_gofmt_command_uses_plain_stdout_mode() -> None:
    request = _request("gofmt", "gofmt", "document", ())
    command = GoFormatAdapter().build_command(request, ("-s",))

    assert command == [
        "gofmt",
        "-s",
    ]


def test_rustfmt_command_infers_edition_from_cargo_manifest(tmp_path: Path) -> None:
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    snapshot = ViewSnapshot(
        buffer_id=1,
        change_count=1,
        text='fn main(){println!("hi");}\n',
        file_name="demo.rs",
        syntax="Packages/Rust/Rust.sublime-syntax",
        base_dir=str(tmp_path),
        newline="\n",
        selection_regions=((0, 0),),
    )
    request = FormatRequest(
        adapter_id="rustfmt",
        adapter_name="rustfmt",
        executable="rustfmt",
        command=(),
        cwd=str(tmp_path),
        stdin_filename=snapshot.file_name,
        config_path=None,
        selection_mode="document",
        ranges=(),
        snapshot=snapshot,
    )

    command = RustFormatAdapter().build_command(request, ())
    assert command == [
        "rustfmt",
        "--emit",
        "stdout",
        "--edition",
        "2021",
    ]


def test_clang_command_uses_utf8_byte_offsets() -> None:
    snapshot = ViewSnapshot(
        buffer_id=1,
        change_count=1,
        text="// \u00e9\u20ac\nvalue\n",
        file_name="demo.cpp",
        syntax="Packages/C++/C++.sublime-syntax",
        base_dir="C:/demo",
        newline="\n",
        selection_regions=((3, 5),),
    )
    request = FormatRequest(
        adapter_id="clang-format",
        adapter_name="clang-format",
        executable="clang-format",
        command=(),
        cwd=snapshot.base_dir,
        stdin_filename=snapshot.file_name,
        config_path=None,
        selection_mode="selection",
        ranges=(TextRange(3, 5, 1, 4, 1, 6),),
        snapshot=snapshot,
    )

    command = ClangFormatAdapter().build_command(request, ())
    assert command == [
        "clang-format",
        "--assume-filename",
        "demo.cpp",
        "--offset",
        "3",
        "--length",
        "5",
    ]
