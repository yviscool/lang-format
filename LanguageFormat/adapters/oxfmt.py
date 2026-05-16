from __future__ import annotations

from LanguageFormat.adapters.base import FormatterAdapter
from LanguageFormat.core.contracts import FormatRequest


class OxcFormatAdapter(FormatterAdapter):
    id = "oxfmt"
    display_name = "Oxc Formatter"
    selectors = (
        "source.js",
        "source.jsx",
        "source.ts",
        "source.tsx",
        "source.json",
        "source.jsonc",
        "source.json5",
        "source.css",
        "source.scss",
        "source.less",
        "source.graphql",
        "source.yaml",
        "source.toml",
        "text.html",
        "text.html.markdown",
        "text.html.vue",
        "text.html.svelte",
        "text.md",
        "text.mdx",
    )
    supports_range = False
    binary_names = ("oxfmt", "oxfmt.cmd", "oxfmt.exe")
    config_filenames = (
        ".oxfmtrc.json",
        ".oxfmtrc.jsonc",
        "oxfmt.config.ts",
        "oxfmt.config.mts",
        "oxfmt.config.cts",
        "oxfmt.config.js",
        "oxfmt.config.mjs",
        "oxfmt.config.cjs",
    )
    docs_url = "https://oxc.rs/docs/guide/usage/formatter.html"
    default_extension = ".ts"

    def project_binary_relpaths(self) -> tuple[str, ...]:
        return (
            "node_modules/.bin/oxfmt.cmd",
            "node_modules/.bin/oxfmt",
        )

    def build_command(self, request: FormatRequest, extra_args: tuple[str, ...]) -> list[str]:
        command = [request.executable]
        if request.stdin_filename:
            command.extend(["--stdin-filepath", request.stdin_filename])
        command.extend(extra_args)
        return command

    def build_install_help(self, platform_name: str) -> str:
        del platform_name
        return "\n".join(
            (
                "Recommended project-local install command:",
                "  npm install --save-dev oxfmt",
                "Official docs show pnpm examples;",
                "the npm command above is the equivalent inference.",
                f"Docs: {self.docs_url}",
            )
        )
