"""Mixed-script suspicious-token detection.

Flags tokens whose characters mix scripts in a way OCR produces but real
words never do: Latin+Devanagari (``Seवson``, ``Nepव``, ``Aज``) or
Latin+Devanagari-digit (``Go०gle``). These become the candidates the
semantic engine tries to validate; clean single-script tokens are ignored.

Any token that contains a protected-entity placeholder (``<URL_1>`` ...) is
ignored completely - entity content is never a correction candidate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_LATIN = re.compile(r"[A-Za-z]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_DEVANAGARI_DIGIT = re.compile(r"[०-९]")
_TOKEN = re.compile(r"\S+")
#: Matches a placeholder ANYWHERE inside a token (``search``), so a token that
#: merely contains ``<URL_1>`` is treated as protected, not just tokens that
#: are exactly a placeholder.
_PLACEHOLDER = re.compile(r"<[A-Z0-9_]+_\d+>")


@dataclass(frozen=True)
class SuspiciousToken:
    """A mixed-script token flagged for semantic validation."""

    token: str
    start: int
    end: int
    reason: str


class MixedScriptDetector:
    """Detects mixed-script OCR artefacts (offline, deterministic)."""

    def find(self, text: str) -> List[SuspiciousToken]:
        """Return every suspicious mixed-script token with its offsets."""
        suspects: List[SuspiciousToken] = []
        for match in _TOKEN.finditer(text):
            token = match.group(0)
            if _PLACEHOLDER.search(token):
                continue  # any token containing a placeholder is protected
            core = token.strip(".,;:!?()[]{}\"'“”‘’।")
            if not core:
                continue
            has_latin = bool(_LATIN.search(core))
            has_deva = bool(_DEVANAGARI.search(core))
            has_deva_digit = bool(_DEVANAGARI_DIGIT.search(core))
            if has_latin and has_deva:
                reason = ("latin+devanagari-digit" if has_deva_digit
                          else "latin+devanagari")
                suspects.append(SuspiciousToken(core, match.start(),
                                                match.end(), reason))
        return suspects

    def is_suspicious(self, token: str) -> bool:
        if _PLACEHOLDER.search(token):
            return False  # protected entity content is never a candidate
        core = token.strip(".,;:!?()[]{}\"'“”‘’।")
        return bool(_LATIN.search(core) and _DEVANAGARI.search(core))
