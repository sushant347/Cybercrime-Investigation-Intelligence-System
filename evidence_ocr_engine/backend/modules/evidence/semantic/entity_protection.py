"""Entity protection for semantic correction.

Before XLM-R ever sees the text, every forensic entity (URL, email, phone,
hash, IP, wallet, ...) is replaced with a readable placeholder token
(``<URL_1>``, ``<PHONE_2>`` ...). Placeholders keep sentences grammatical for
the language model while guaranteeing that no entity character can be altered
by semantic processing. Originals are restored verbatim afterwards.

Reuses the battle-tested regex set from the cleaning module (Prompt 2) - no
pattern duplication.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..cleaning.regex_patterns import PROTECTED_PATTERNS

_TRAILING = ".,;:!?)]}'\"।"
_PLACEHOLDER = re.compile(r"<([A-Z0-9_]+)_(\d+)>")


@dataclass
class ProtectedText:
    """Text with placeholders plus the vault of original spans."""

    text: str
    vault: Dict[str, str] = field(default_factory=dict)  # placeholder -> original

    def placeholder_count(self) -> int:
        return len(self.vault)


class EntityProtector:
    """Placeholder-based entity shielding (``<TYPE_N>`` tokens)."""

    def protect(self, text: str) -> ProtectedText:
        """Replace every protected entity span with a ``<TYPE_N>`` token."""
        spans: List[Tuple[int, int, str, str]] = []
        for entity_type, pattern in PROTECTED_PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(0).rstrip(_TRAILING)
                if value:
                    spans.append((match.start(), match.start() + len(value),
                                  entity_type.upper(), value))

        chosen = self._resolve_overlaps(spans)
        vault: Dict[str, str] = {}
        counters: Dict[str, int] = {}
        # Replace right-to-left so offsets stay valid.
        for start, end, etype, value in sorted(chosen, key=lambda s: s[0], reverse=True):
            counters[etype] = counters.get(etype, 0) + 1
        # Assign ascending indices left-to-right for readability.
        running: Dict[str, int] = {}
        ordered = sorted(chosen, key=lambda s: s[0])
        replacements: List[Tuple[int, int, str]] = []
        for start, end, etype, value in ordered:
            running[etype] = running.get(etype, 0) + 1
            token = f"<{etype}_{running[etype]}>"
            vault[token] = value
            replacements.append((start, end, token))

        output = text
        for start, end, token in sorted(replacements, key=lambda s: s[0], reverse=True):
            output = output[:start] + token + output[end:]
        return ProtectedText(text=output, vault=vault)

    def restore(self, text: str, protected: ProtectedText) -> str:
        """Put every original span back, byte-for-byte."""

        def _sub(match: re.Match[str]) -> str:
            return protected.vault.get(match.group(0), match.group(0))

        return _PLACEHOLDER.sub(_sub, text)

    @staticmethod
    def is_placeholder(token: str) -> bool:
        return bool(_PLACEHOLDER.fullmatch(token))

    @staticmethod
    def _resolve_overlaps(
        spans: List[Tuple[int, int, str, str]]
    ) -> List[Tuple[int, int, str, str]]:
        chosen: List[Tuple[int, int, str, str]] = []
        for span in sorted(spans, key=lambda s: (-(s[1] - s[0]), s[0])):
            if all(span[1] <= c[0] or span[0] >= c[1] for c in chosen):
                chosen.append(span)
        return sorted(chosen, key=lambda s: s[0])
