from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from LanguageFormat.core.contracts import FormatRequest
from LanguageFormat.core.discovery import find_named_file_upwards


class FormatterAdapter(ABC):
    id = ""
    display_name = ""
    selectors = ()  # type: Tuple[str, ...]
    supports_range = False
    supports_multiple_ranges = False
    binary_names = ()  # type: Tuple[str, ...]
    config_filenames = ()  # type: Tuple[str, ...]
    docs_url = ""
    default_extension = ".txt"

    def project_binary_relpaths(self) -> Tuple[str, ...]:
        return ()

    def discover_config(self, start_dir: Optional[str]) -> Optional[str]:
        return find_named_file_upwards(start_dir, self.config_filenames)

    @abstractmethod
    def build_command(self, request: FormatRequest, extra_args: Tuple[str, ...]) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def build_install_help(self, platform_name: str) -> str:
        raise NotImplementedError
