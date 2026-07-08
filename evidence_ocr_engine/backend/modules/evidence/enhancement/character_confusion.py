"""Hybrid character-confusion resolution (data-driven, offline).

Repairs OCR errors where individual characters were recognised as visually
similar characters of the *wrong* script or the wrong Devanagari matra:

* ``Seवson`` -> ``Season``  (Devanagari व inside a Latin word)
* ``Nepव``   -> ``Nepal``   (confusion substitution + vocabulary snapping)
* ``F८``     -> ``FC``      (Devanagari digit ८ inside a Latin token)
* ``धैरै``    -> ``धेरै``     (matra confusion ै/े)
* ``मं``     -> ``म``       (spurious trailing anusvara)
* ``ऋसार्वजनिक`` -> ``सार्वजनिक`` (spurious leading character)

All confusable characters live in ``data/character_confusion_matrix.json``
and can be extended without touching Python code. A repair is only a
*candidate* here - the confidence tier and context gate still decide
whether it is applied (triple-agreement principle of Prompt 2.5).
"""

from __future__ import annotations

import itertools
import json
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..logger import get_logger
from .english_dictionary import EnglishDictionary
from .nepali_dictionary import NepaliDictionary
from .script_detector import ScriptDetector

_DATA_FILE = Path(__file__).resolve().parent / "data" / "character_confusion_matrix.json"

#: Bound on substitution combinations per token (keeps resolution cheap).
_MAX_VARIANTS = 128

#: Vocabulary snapping cutoff after substitution ("Nepa" -> "nepal").
_SNAP_CUTOFF = 0.80


@dataclass(frozen=True)
class ConfusionCandidate:
    """A proposed repair with its provenance."""

    corrected: str
    rule: str                  # character_confusion | script_consistency
    replacements: str          # e.g. "व→a" or "व→a, ८→C"
    validated_by: str          # english_vocabulary | nepali_vocabulary | single_script


class ConfusionMatrix:
    """Loads and indexes the JSON confusion matrix."""

    def __init__(self, path: Path | None = None) -> None:
        self._log = get_logger("enhancement.confusion_matrix")
        try:
            with open(path or _DATA_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            self._log.error("cannot load confusion matrix: %s", exc)
            data = {}
        self.groups: List[List[str]] = data.get("groups", [])
        self.multi_char: Dict[str, str] = data.get("multi_char", {})
        self.cross_script: Dict[str, List[str]] = data.get("cross_script", {})
        self.latin_to_devanagari: Dict[str, List[str]] = data.get(
            "latin_to_devanagari", {})
        self.nepali_internal: List[List[str]] = data.get("nepali_internal", [])
        self.spurious: Dict[str, List[str]] = data.get(
            "spurious", {"leading": [], "trailing": []})

        # index: char -> alternatives within its same-script group
        self.group_alternatives: Dict[str, List[str]] = {}
        for group in self.groups:
            for char in group:
                self.group_alternatives.setdefault(char, [])
                self.group_alternatives[char].extend(
                    c for c in group if c != char)
        # index: devanagari char -> matra/letter alternatives
        self.internal_alternatives: Dict[str, List[str]] = {}
        for group in self.nepali_internal:
            for char in group:
                self.internal_alternatives.setdefault(char, [])
                self.internal_alternatives[char].extend(
                    c for c in group if c != char)

    def to_dominant(self, char: str, dominant_script: str) -> List[str]:
        """Replacements for ``char`` in the dominant script of the word."""
        if dominant_script == "english":
            return self.cross_script.get(char, [])
        if dominant_script == "nepali":
            return self.latin_to_devanagari.get(char, [])
        return []


class CharacterConfusionResolver:
    """Produces repair candidates for confusion-damaged tokens."""

    def __init__(
        self,
        matrix: Optional[ConfusionMatrix] = None,
        nepali: Optional[NepaliDictionary] = None,
        english: Optional[EnglishDictionary] = None,
        script_detector: Optional[ScriptDetector] = None,
    ) -> None:
        self._matrix = matrix or ConfusionMatrix()
        self._nepali = nepali or NepaliDictionary()
        self._english = english or EnglishDictionary()
        self._scripts = script_detector or ScriptDetector()
        self._log = get_logger("enhancement.confusion")

    # ------------------------------------------------------------------ public

    def resolve(self, token: str) -> Optional[ConfusionCandidate]:
        """Best repair candidate for ``token``, or ``None`` (never guesses)."""
        profile = self._scripts.profile(token)
        if profile.is_mixed:
            return self._resolve_mixed_script(token, profile)
        if profile.classification == "nepali":
            return self._resolve_nepali_internal(token)
        return None

    # ------------------------------------------------------- mixed-script repair

    def _resolve_mixed_script(self, token, profile) -> Optional[ConfusionCandidate]:
        """Replace minority-script characters with dominant-script look-alikes."""
        options: List[List[Tuple[str, str]]] = []  # per position: (replacement, note)
        for position in profile.minority_positions:
            char = token[position]
            replacements = self._matrix.to_dominant(char, profile.dominant_script)
            if not replacements:
                return None  # an unmapped minority char: cannot repair safely
            options.append([(r, f"{char}→{r}") for r in replacements])

        if not options:
            return None
        combinations = 1
        for opts in options:
            combinations *= len(opts)
        if combinations > _MAX_VARIANTS:
            return None

        best: Optional[ConfusionCandidate] = None
        for combo in itertools.product(*options):
            chars = list(token)
            for (replacement, _note), position in zip(
                    combo, profile.minority_positions):
                chars[position] = replacement
            candidate = "".join(chars)
            notes = ", ".join(note for _r, note in combo)
            validated = self._validate(candidate, profile.dominant_script)
            if validated:
                corrected, validated_by, exact = validated
                rule = ("character_confusion" if exact or validated_by != "single_script"
                        else "script_consistency")
                result = ConfusionCandidate(corrected, rule, notes, validated_by)
                if exact:
                    return result  # vocabulary hit wins immediately
                best = best or result
        return best

    def _validate(
        self, candidate: str, dominant_script: str
    ) -> Optional[Tuple[str, str, bool]]:
        """Validate a substituted candidate.

        Returns ``(final_word, validated_by, exact)`` or ``None``.
        ``exact`` means a direct vocabulary hit; vocabulary *snapping*
        (``Nepa`` -> ``Nepal``) and pure single-script fallbacks are inexact.
        """
        if dominant_script == "english":
            if self._english.is_valid_word(candidate):
                return candidate, "english_vocabulary", True
            snapped = get_close_matches(
                candidate.lower(),
                list(self._english_vocab()), n=1, cutoff=_SNAP_CUTOFF)
            if snapped:
                return (self._mirror_case(candidate, snapped[0]),
                        "english_vocabulary", False)
            if candidate.isalpha() and len(candidate) <= 4:
                # Short initialisms (FC, TV): single-script repair is enough.
                return candidate, "single_script", False
            return None

        candidate_nfc = unicodedata.normalize("NFC", candidate)
        if self._nepali.is_valid_word(candidate_nfc):
            return candidate_nfc, "nepali_vocabulary", True
        fuzzy = self._nepali.lookup_fuzzy(candidate_nfc)
        if fuzzy:
            return fuzzy, "nepali_vocabulary", False
        return None

    # -------------------------------------------------- Devanagari-internal repair

    def _resolve_nepali_internal(self, token: str) -> Optional[ConfusionCandidate]:
        """Fix matra confusions and spurious leading/trailing characters."""
        word = unicodedata.normalize("NFC", token)
        if self._nepali.is_valid_word(word):
            return None

        # 1. Spurious leading / trailing characters (ऋसार्वजनिक, मं).
        for char in self._matrix.spurious.get("leading", []):
            if word.startswith(char) and self._nepali.is_valid_word(word[len(char):]):
                return ConfusionCandidate(
                    word[len(char):], "character_confusion",
                    f"{char}→∅(leading)", "nepali_vocabulary")
        for char in self._matrix.spurious.get("trailing", []):
            if word.endswith(char) and self._nepali.is_valid_word(word[:-len(char)]):
                return ConfusionCandidate(
                    word[:-len(char)], "character_confusion",
                    f"{char}→∅(trailing)", "nepali_vocabulary")

        # 2. Single matra/letter substitutions (धैरै -> धेरै).
        for position, char in enumerate(word):
            for alternative in self._matrix.internal_alternatives.get(char, []):
                candidate = word[:position] + alternative + word[position + 1:]
                if self._nepali.is_valid_word(candidate):
                    return ConfusionCandidate(
                        candidate, "character_confusion",
                        f"{char}→{alternative}", "nepali_vocabulary")
        return None

    # ---------------------------------------------------------------- helpers

    def _english_vocab(self):
        return self._english._vocabulary  # intentional: shared vocabulary set

    @staticmethod
    def _mirror_case(original: str, fixed: str) -> str:
        if original.isupper():
            return fixed.upper()
        if original[:1].isupper():
            return fixed.capitalize()
        return fixed
