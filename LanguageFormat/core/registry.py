from __future__ import annotations

from LanguageFormat.adapters.base import FormatterAdapter
from LanguageFormat.adapters.clang import ClangFormatAdapter
from LanguageFormat.adapters.go import GoFormatAdapter
from LanguageFormat.adapters.oxfmt import OxcFormatAdapter
from LanguageFormat.adapters.ruff import RuffFormatAdapter
from LanguageFormat.adapters.rust import RustFormatAdapter

ADAPTERS: tuple[FormatterAdapter, ...] = (
    ClangFormatAdapter(),
    GoFormatAdapter(),
    RuffFormatAdapter(),
    RustFormatAdapter(),
    OxcFormatAdapter(),
)


def adapter_by_id(adapter_id: str) -> FormatterAdapter | None:
    for adapter in ADAPTERS:
        if adapter.id == adapter_id:
            return adapter
    return None


def selectors_for_adapter(
    adapter: FormatterAdapter,
    selector_overrides: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    return adapter.selectors + tuple(selector_overrides.get(adapter.id, ()))
