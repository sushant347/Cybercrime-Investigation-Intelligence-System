"""Deterministic, dependency-free text chunking."""

from __future__ import annotations


def split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split at natural boundaries while retaining a bounded overlap."""
    text = (text or "").strip()
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(len(text), start + max_chars)
        end = hard_end
        if hard_end < len(text):
            search_from = start + max_chars // 2
            newline = text.rfind("\n", search_from, hard_end)
            space = text.rfind(" ", search_from, hard_end)
            boundary = max(newline, space)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap_chars)
        while next_start < end and text[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks or [""]
