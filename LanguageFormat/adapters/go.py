from __future__ import annotations

from LanguageFormat.adapters.base import FormatterAdapter
from LanguageFormat.core.contracts import FormatRequest


class GoFormatAdapter(FormatterAdapter):
    id = "gofmt"
    display_name = "gofmt"
    selectors = ("source.go",)
    supports_range = False
    binary_names = ("gofmt", "gofmt.exe")
    docs_url = "https://pkg.go.dev/cmd/gofmt"
    default_extension = ".go"

    def build_command(
        self,
        request: FormatRequest,
        extra_args: tuple[str, ...],
    ) -> list[str]:
        command = [request.executable]
        command.extend(extra_args)
        return command

    def build_install_help(self, platform_name: str) -> str:
        if platform_name == "Windows":
            command = "winget install GoLang.Go"
        elif platform_name == "Darwin":
            command = "brew install go"
        else:
            command = "sudo apt install golang-go"

        return "\n".join(
            (
                "Recommended install command:",
                f"  {command}",
                "gofmt ships with the Go toolchain.",
                f"Docs: {self.docs_url}",
            )
        )
