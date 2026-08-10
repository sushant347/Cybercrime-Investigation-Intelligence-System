"""Evidence-ID citation extraction that cannot confuse prefix IDs."""

from __future__ import annotations

import re
from collections.abc import Iterable


def extract_cited_ids(answer: str, candidate_ids: Iterable[str]) -> set[str]:
    found: set[str] = set()
    for candidate in candidate_ids:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(candidate)}(?![A-Za-z0-9_])"
        if re.search(pattern, answer):
            found.add(candidate)
    return found


def validate_cited_ids(citations: Iterable[str], candidate_ids: Iterable[str]) -> tuple[str, ...]:
    allowed = set(candidate_ids)
    return tuple(sorted({str(value) for value in citations if str(value) in allowed}))
