"""Deterministic OCR correction rules (structure and punctuation only).

Rules never touch word *content* - that is the dictionaries' job. They fix
structural artefacts that OCR reliably produces, and they are the only kind
of fix allowed inside protected entities (e.g. ``http//`` -> ``http://``):
the entity's substance (domain, digits, hash characters) is never altered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Pattern, Tuple

#: (pattern, replacement, rule name). Applied in order.
STRUCTURAL_RULES: List[Tuple[Pattern[str], str, str]] = [
    (re.compile(r"\bhttp\s*[,;]?//", re.IGNORECASE), "http://", "url_scheme_fix"),
    (re.compile(r"\bhttps\s*[,;]?//", re.IGNORECASE), "https://", "url_scheme_fix"),
    (re.compile(r"\bhttp:/(?!/)", re.IGNORECASE), "http://", "url_scheme_fix"),
    (re.compile(r"\bhttps:/(?!/)", re.IGNORECASE), "https://", "url_scheme_fix"),
    (re.compile(r"\bwww[,;]", re.IGNORECASE), "www.", "www_prefix_fix"),
    (re.compile(r"\bvvww\.", re.IGNORECASE), "www.", "www_prefix_fix"),
    # Devanagari danda stutter and misplacement.
    (re.compile(r"।{2,}"), "।", "danda_dedup"),
    (re.compile(r" +।"), "।", "danda_spacing"),
    # OCR'd pipe between letters where danda was meant (Devanagari context).
    (re.compile(r"(?<=[ऀ-ॿ])\s*\|\s*(?=\s|$)", re.MULTILINE), "। ", "pipe_to_danda"),
]


@dataclass(frozen=True)
class RuleFix:
    """One structural fix (audit record)."""

    original: str
    corrected: str
    rule: str


class OCRCorrectionRules:
    """Applies the structural rule set and records every fix."""

    def apply(self, text: str) -> Tuple[str, List[RuleFix]]:
        """Run all rules over ``text``; returns ``(text, fixes)``."""
        fixes: List[RuleFix] = []
        for pattern, replacement, rule in STRUCTURAL_RULES:
            for match in pattern.finditer(text):
                if match.group(0) != replacement:
                    fixes.append(RuleFix(match.group(0), replacement, rule))
            text = pattern.sub(replacement, text)
        return text, fixes

    def apply_to_entity(self, entity_text: str) -> Tuple[str, List[RuleFix]]:
        """Entity-safe subset: only scheme/prefix punctuation, nothing else.

        Domain names, digits, wallet characters and hash content are never
        modified - the substance of the entity stays byte-identical.
        """
        fixes: List[RuleFix] = []
        for pattern, replacement, rule in STRUCTURAL_RULES:
            if rule not in ("url_scheme_fix", "www_prefix_fix"):
                continue
            for match in pattern.finditer(entity_text):
                if match.group(0) != replacement:
                    fixes.append(RuleFix(match.group(0), replacement, rule))
            entity_text = pattern.sub(replacement, entity_text)
        return entity_text, fixes
