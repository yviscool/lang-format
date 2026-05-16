from __future__ import annotations

from LanguageFormat.adapters.base import FormatterAdapter
from LanguageFormat.core.contracts import FormatRequest
from LanguageFormat.core.text import utf8_byte_offset


class ClangFormatAdapter(FormatterAdapter):
    id = "clang-format"
    display_name = "clang-format"
    selectors = ("source.c", "source.c++", "source.objc", "source.objc++")
    supports_range = True
    binary_names = ("clang-format", "clang-format.exe")
    config_filenames = (".clang-format", "_clang-format")
    docs_url = "https://clang.llvm.org/docs/ClangFormat.html"
    default_extension = ".cpp"

    def build_command(self, request: FormatRequest, extra_args: tuple[str, ...]) -> list[str]:
        command = [request.executable]
        if request.stdin_filename:
            command.extend(["--assume-filename", request.stdin_filename])
        if request.selection_mode == "selection":
            for text_range in request.ranges:
                byte_start = utf8_byte_offset(request.snapshot.text, text_range.start)
                byte_end = utf8_byte_offset(request.snapshot.text, text_range.end)
                command.extend(
                    [
                        "--offset",
                        str(byte_start),
                        "--length",
                        str(byte_end - byte_start),
                    ]
                )
        command.extend(extra_args)
        return command

    def build_install_help(self, platform_name: str) -> str:
        if platform_name == "Windows":
            command = "winget install LLVM.LLVM"
        elif platform_name == "Darwin":
            command = "brew install clang-format"
        else:
            command = "sudo apt install clang-format"

        return "\n".join(
            (
                "Recommended install command:",
                f"  {command}",
                f"Docs: {self.docs_url}",
            )
        )
