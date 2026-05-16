from __future__ import annotations

from LanguageFormat.core.text import (
    make_text_range,
    normalize_newlines,
    offset_to_line_col,
    remap_selection_regions,
)


def test_offset_to_line_col_is_one_based() -> None:
    text = "alpha\nbeta\ngamma\n"
    assert offset_to_line_col(text, 0) == (1, 1)
    assert offset_to_line_col(text, 6) == (2, 1)
    assert offset_to_line_col(text, 10) == (2, 5)


def test_make_text_range_uses_absolute_offsets_and_lines() -> None:
    text = "one\ntwo\nthree\n"
    text_range = make_text_range(text, 4, 7)

    assert text_range.start == 4
    assert text_range.end == 7
    assert (text_range.start_line, text_range.start_col) == (2, 1)
    assert (text_range.end_line, text_range.end_col) == (2, 4)


def test_normalize_newlines_preserves_requested_style() -> None:
    assert normalize_newlines("a\nb\n", "\r\n") == "a\r\nb\r\n"
    assert normalize_newlines("a\r\nb\r\n", "\n") == "a\nb\n"


def test_remap_selection_regions_tracks_insertions() -> None:
    source = "hello world\n"
    target = "hello, world\n"
    regions = ((6, 11),)

    assert remap_selection_regions(source, target, regions) == ((7, 12),)


def test_remap_selection_regions_collapses_deleted_text_to_boundary() -> None:
    source = "abcXYZdef"
    target = "abcdef"
    regions = ((3, 6),)

    assert remap_selection_regions(source, target, regions) == ((3, 3),)
