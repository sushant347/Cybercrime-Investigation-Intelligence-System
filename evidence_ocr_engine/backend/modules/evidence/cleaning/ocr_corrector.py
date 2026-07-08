"""Conservative OCR error correction.

Only *unambiguous* OCR mistakes are corrected - the kind where the intended
token is certain (protocol typos, digit/letter homoglyphs inside known
words). Anything below full confidence is left untouched: in forensic text,
a conservative non-correction is always safer than a guess, and the raw
text is preserved regardless.

Every applied correction is recorded (before -> after) for the audit trail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Pattern, Tuple

#: Structural fixes: broken URL schemes and web prefixes.
_STRUCTURAL_FIXES: List[Tuple[Pattern[str], str]] = [
    (re.compile(r"\bhttp\s*//", re.IGNORECASE), "http://"),
    (re.compile(r"\bhttps\s*//", re.IGNORECASE), "https://"),
    (re.compile(r"\bhttp:/(?!/)", re.IGNORECASE), "http://"),
    (re.compile(r"\bhttps:/(?!/)", re.IGNORECASE), "https://"),
    (re.compile(r"\bhttp,//", re.IGNORECASE), "http://"),
    (re.compile(r"\bhttps,//", re.IGNORECASE), "https://"),
    (re.compile(r"\bwww,", re.IGNORECASE), "www."),
    (re.compile(r"\bwww\s+\.", re.IGNORECASE), "www."),
    (re.compile(r"\bvvww\.", re.IGNORECASE), "www."),
]

#: Whole-token homoglyph corrections (0<->o, 1<->l, 5<->s, rn<->m inside a
#: fixed vocabulary). Matched case-insensitively; the replacement mirrors
#: the original casing (lower / UPPER / Capitalised).
_TOKEN_FIXES: dict[str, str] = {
    "emall": "email",
    "ernail": "email",
    "e-mall": "e-mail",
    "acc0unt": "account",
    "acccount": "account",
    "accaunt": "account",
    "1ogin": "login",
    "log1n": "login",
    "l0gin": "login",
    "supp0rt": "support",
    "passw0rd": "password",
    "pa5sword": "password",
    "verlfy": "verify",
    "ver1fy": "verify",
    "banl": "bank",
    "0tp": "otp",
    "c0de": "code",
    "securlty": "security",
    "custorner": "customer",
    "lnvoice": "invoice",
    "payrnent": "payment",
    "transacti0n": "transaction",
    "suspendedl": "suspended",
    "c1ick": "click",
    "cllck": "click",
}

_TOKEN = re.compile(r"[A-Za-z0-9-]+")


@dataclass(frozen=True)
class Correction:
    """One applied OCR correction (audit record)."""

    original: str
    corrected: str
    kind: str  # structural | token


class OCRCorrector:
    """Rule-based, high-confidence-only OCR error correction."""

    def correct(self, text: str) -> Tuple[str, List[Correction]]:
        """Apply both passes; returns ``(corrected_text, corrections)``."""
        text, structural = self.correct_structural(text)
        text, tokens = self.correct_tokens(text)
        return text, structural + tokens

    def correct_structural(self, text: str) -> Tuple[str, List[Correction]]:
        """Fix broken URL schemes / web prefixes (run BEFORE entity
        preservation so repaired URLs are protected in full)."""
        corrections: List[Correction] = []
        for pattern, replacement in _STRUCTURAL_FIXES:
            for match in pattern.finditer(text):
                if match.group(0) != replacement:
                    corrections.append(
                        Correction(match.group(0), replacement, "structural")
                    )
            text = pattern.sub(replacement, text)
        return text, corrections

    def correct_tokens(self, text: str) -> Tuple[str, List[Correction]]:
        """Fix known homoglyph tokens (run AFTER entity preservation so a
        token inside an entity - e.g. supp0rt@bank.com - is never altered)."""
        corrections: List[Correction] = []

        def _fix_token(match: re.Match[str]) -> str:
            token = match.group(0)
            fixed = _TOKEN_FIXES.get(token.lower())
            if fixed is None:
                return token  # not in the certain-fix vocabulary: leave as is
            replacement = self._mirror_case(token, fixed)
            corrections.append(Correction(token, replacement, "token"))
            return replacement

        return _TOKEN.sub(_fix_token, text), corrections

    @staticmethod
    def _mirror_case(original: str, fixed: str) -> str:
        """Return ``fixed`` cased like ``original`` (SUPP0RT -> SUPPORT)."""
        if original.isupper():
            return fixed.upper()
        if original[:1].isupper():
            return fixed.capitalize()
        return fixed
