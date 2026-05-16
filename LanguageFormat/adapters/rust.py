from __future__ import annotations

from typing import List, Tuple

from LanguageFormat.adapters.base import FormatterAdapter
from LanguageFormat.core.contracts import FormatRequest
from LanguageFormat.core.discovery import find_rust_edition


class RustFormatAdapter(FormatterAdapter):
    id = "rustfmt"
    display_name = "rustfmt"
    selectors = ("source.rust",)
    supports_range = False
    binary_names = ("rustfmt", "rustfmt.exe")
    config_filenames = ("rustfmt.toml", ".rustfmt.toml")
    docs_url = "https://github.com/rust-lang/rustfmt"
    default_extension = ".rs"

    def build_command(
        self,
        request: FormatRequest,
        extra_args: Tuple[str, ...],
    ) -> List[str]:
        command = [request.executable, "--emit", "stdout"]
        edition = find_rust_edition(request.cwd)
        if edition:
            command.extend(["--edition", edition])
        command.extend(extra_args)
        return command

    def build_install_help(self, platform_name: str) -> str:
        del platform_name
        return "\n".join(
            (
                "Recommended install command:",
                "  rustup component add rustfmt",
                "rustfmt is installed as a Rust toolchain component.",
                f"Docs: {self.docs_url}",
            )
        )
