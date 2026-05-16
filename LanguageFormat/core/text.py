from __future__ import annotations

from bisect import bisect_right

from LanguageFormat.core.contracts import TextRange


def detect_newline_style(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def offset_to_line_col(text: str, offset: int) -> tuple[int, int]:
    starts = _line_starts(text)
    line_index = bisect_right(starts, offset) - 1
    line_start = starts[max(line_index, 0)]
    return line_index + 1, (offset - line_start) + 1


def make_text_range(text: str, start: int, end: int) -> TextRange:
    start_line, start_col = offset_to_line_col(text, start)
    end_line, end_col = offset_to_line_col(text, end)
    return TextRange(
        start=start,
        end=end,
        start_line=start_line,
        start_col=start_col,
        end_line=end_line,
        end_col=end_col,
    )


def clamp_point(point: int, size: int) -> int:
    return max(0, min(point, size))


def utf8_byte_offset(text: str, offset: int) -> int:
    return len(text[:offset].encode("utf-8"))
