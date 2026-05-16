from __future__ import annotations

from abc import ABC, abstractmethod

from LanguageFormat.core.contracts import FormatRequest
from LanguageFormat.core.discovery import find_named_file_upwards


class FormatterAdapter(ABC):
    id = ""
    display_name = ""
    selectors: tuple[str, ...] = ()
    supports_range = False
    binary_names: tuple[str, ...] = ()
    config_filenames: tuple[str, ...] = ()
    docs_url = ""
    default_extension = ".txt"

    def project_binary_relpaths(self) -> tuple[str, ...]:
        return ()

    def discover_config(self, start_dir: str | None) -> str | None:
        return find_named_file_upwards(start_dir, self.config_filenames)

    @abstractmethod
    def build_command(self, request: FormatRequest, extra_args: tuple[str, ...]) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def build_install_help(self, platform_name: str) -> str:
        raise NotImplementedError
