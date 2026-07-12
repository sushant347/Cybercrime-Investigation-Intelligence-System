"""Word-level script consistency detection.

Classifies a single token as ``english`` (Latin letters), ``nepali``
(Devanagari), ``numeric``, ``mixed_script`` (Latin *and* Devanagari inside
one word - almost always an OCR confusion, e.g. ``Seवson``) or ``other``.

For mixed-script words it reports which script dominates and exactly which
characters belong to the minority script - the characters the
:class:`CharacterConfusionResolver` will try to repair.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


def _is_devanagari(char: str) -> bool:
    return "ऀ" <= char <= "ॿ"


def _is_latin(char: str) -> bool:
    return ("a" <= char <= "z") or ("A" <= char <= "Z")


@dataclass(frozen=True)
class ScriptProfile:
    """Script analysis of one token."""

    token: str
    classification: str          # english | nepali | numeric | mixed_script | other
    dominant_script: str         # english | nepali | none
    latin_count: int = 0
    devanagari_count: int = 0
    digit_count: int = 0
    minority_positions: Tuple[int, ...] = field(default=())

    @property
    def is_mixed(self) -> bool:
        return self.classification == "mixed_script"


class ScriptDetector:
    """Deterministic, offline word-script classifier."""

    def profile(self, token: str) -> ScriptProfile:
        """Analyse one token's script composition."""
        latin = [i for i, c in enumerate(token) if _is_latin(c)]
        devanagari = [i for i, c in enumerate(token) if _is_devanagari(c)]
        digits = [i for i, c in enumerate(token) if c.isdigit()]

        if latin and devanagari:
            # Mixed script: the minority characters are the suspects.
            if len(latin) >= len(devanagari):
                dominant, minority = "english", tuple(devanagari)
            else:
                dominant, minority = "nepali", tuple(latin)
            classification = "mixed_script"
        elif devanagari:
            dominant, minority, classification = "nepali", (), "nepali"
        elif latin:
            dominant, minority, classification = "english", (), "english"
        elif digits and len(digits) == len(token):
            dominant, minority, classification = "none", (), "numeric"
        else:
            dominant, minority, classification = "none", (), "other"

        return ScriptProfile(
            token=token,
            classification=classification,
            dominant_script=dominant,
            latin_count=len(latin),
            devanagari_count=len(devanagari),
            digit_count=len(digits),
            minority_positions=minority,
        )

    def detect(self, token: str) -> str:
        """Shorthand: classification label only."""
        return self.profile(token).classification

    @staticmethod
    def minority_characters(profile: ScriptProfile) -> List[str]:
        return [profile.token[i] for i in profile.minority_positions]
