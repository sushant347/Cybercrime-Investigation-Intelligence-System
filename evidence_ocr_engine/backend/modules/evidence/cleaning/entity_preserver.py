"""Entity preservation: shields forensic entities from every cleaning stage.

Before any cleaning runs, entity-bearing spans (URLs, emails, phones,
hashes, wallet addresses, money amounts, ...) are located and replaced by
opaque placeholder tokens built from Unicode Private-Use-Area sentinels and
digits. Placeholders are immune to lowercasing, punctuation folding,
whitespace collapsing and line merging. After cleaning, the *original* span
text is restored byte-for-byte - entities are therefore never modified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .regex_patterns import PROTECTED_PATTERNS

_OPEN = ""
_CLOSE = ""
_PLACEHOLDER = re.compile(rf"{_OPEN}(\d+){_CLOSE}")

#: Trailing characters that belong to the sentence, not the entity.
_TRAILING_PUNCT = ".,;:!?)]}'\"।"


@dataclass
class PreservedEntity:
    """One protected span: its original text and its provisional type."""

    index: int
    entity_type: str
    original: str


@dataclass
class PreservationResult:
    """Text with placeholders plus the vault of original spans."""

    text: str
    vault: Dict[int, PreservedEntity] = field(default_factory=dict)

    def placeholder_count(self) -> int:
        return len(self.vault)


class EntityPreserver:
    """Locates entities, swaps them for placeholders, restores them later."""

    def protect(self, text: str) -> PreservationResult:
        """Replace every protected entity span with a placeholder token.

        Spans are collected from all patterns, overlaps resolved in favour
        of the longest (then earliest) match, and replaced right-to-left so
        offsets stay valid.
        """
        spans: List[Tuple[int, int, str, str]] = []  # start, end, type, text
        for entity_type, pattern in PROTECTED_PATTERNS.items():
            for match in pattern.finditer(text):
                value = self._trim(match.group(0))
                if not value:
                    continue
                start = match.start()
                spans.append((start, start + len(value), entity_type, value))

        chosen = self._resolve_overlaps(spans)

        vault: Dict[int, PreservedEntity] = {}
        output = text
        for index, (start, end, entity_type, value) in enumerate(
            sorted(chosen, key=lambda s: s[0], reverse=True)
        ):
            token_id = len(chosen) - 1 - index  # stable ascending ids
            vault[token_id] = PreservedEntity(token_id, entity_type, value)
            output = output[:start] + f"{_OPEN}{token_id}{_CLOSE}" + output[end:]
        return PreservationResult(text=output, vault=vault)

    def restore(self, text: str, result: PreservationResult) -> str:
        """Put every original span back, byte-for-byte."""

        def _replace(match: re.Match[str]) -> str:
            entity = result.vault.get(int(match.group(1)))
            return entity.original if entity else match.group(0)

        return _PLACEHOLDER.sub(_replace, text)

    @staticmethod
    def contains_placeholder(text: str) -> bool:
        return bool(_PLACEHOLDER.search(text))

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _trim(value: str) -> str:
        """Trim sentence punctuation stuck to the end of a match."""
        return value.rstrip(_TRAILING_PUNCT)

    @staticmethod
    def _resolve_overlaps(
        spans: List[Tuple[int, int, str, str]]
    ) -> List[Tuple[int, int, str, str]]:
        """Keep the longest non-overlapping spans (ties: earliest first)."""
        chosen: List[Tuple[int, int, str, str]] = []
        for span in sorted(spans, key=lambda s: (-(s[1] - s[0]), s[0])):
            if all(span[1] <= c[0] or span[0] >= c[1] for c in chosen):
                chosen.append(span)
        return sorted(chosen, key=lambda s: s[0])
