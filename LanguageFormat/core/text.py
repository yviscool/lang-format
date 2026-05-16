from __future__ import annotations

from bisect import bisect_right
from difflib import SequenceMatcher
from typing import List, Sequence, Tuple

from LanguageFormat.core.contracts import TextRange


def detect_newline_style(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def normalize_newlines(text: str, newline: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if newline != "\n":
        normalized = normalized.replace("\n", newline)
    return normalized


def _line_starts(text: str) -> List[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def offset_to_line_col(text: str, offset: int) -> Tuple[int, int]:
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


def _translate_point(
    source_size: int,
    target_size: int,
    opcodes: Sequence[Tuple[str, int, int, int, int]],
    point: int,
) -> int:
    point = clamp_point(point, source_size)
    for tag, source_start, source_end, target_start, target_end in opcodes:
        if tag == "insert":
            if point == source_start:
                return target_end
            continue

        if source_start <= point < source_end:
            if tag == "equal":
                return target_start + (point - source_start)
            if tag == "delete":
                return target_start
            relative = point - source_start
            return target_start + min(relative, max(0, target_end - target_start))

        if point == source_end:
            return target_end

    return clamp_point(point + (target_size - source_size), target_size)


def remap_selection_regions(
    source_text: str, target_text: str, regions: Sequence[Tuple[int, int]]
) -> Tuple[Tuple[int, int], ...]:
    if source_text == target_text:
        return tuple(regions)

    opcodes = SequenceMatcher(a=source_text, b=target_text, autojunk=False).get_opcodes()
    source_size = len(source_text)
    target_size = len(target_text)
    return tuple(
        (
            _translate_point(source_size, target_size, opcodes, begin),
            _translate_point(source_size, target_size, opcodes, end),
        )
        for begin, end in regions
    )
