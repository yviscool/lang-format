from __future__ import annotations

from LanguageFormat.core.text import make_text_range, offset_to_line_col


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
