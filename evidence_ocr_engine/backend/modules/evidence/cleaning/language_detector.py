"""Line-level language detection (Strategy pattern, no external models).

Detects: ``english`` | ``nepali_unicode`` | ``roman_nepali`` | ``mixed`` |
``unknown``. Detection is purely lexical/script-based - no translation, no
LLMs, no transformer models (research constraint of this framework).

Roman Nepali (Nepali written in Latin script, ubiquitous in SMS/chat scams)
is detected through a curated marker lexicon of high-frequency Nepali
function words, verb endings and scam vocabulary.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")
WORD = re.compile(r"[A-Za-z]+")

#: High-frequency Roman-Nepali marker words. A Latin-script line containing
#: enough of these is Roman Nepali rather than English. The list favours
#: function words / verb endings (which English never contains) plus common
#: scam vocabulary observed in Nepali cybercrime evidence.
ROMAN_NEPALI_MARKERS: frozenset[str] = frozenset(
    {
        # pronouns / determiners / particles
        "tapai", "tapaiko", "timro", "mero", "hamro", "usko", "yo", "tyo",
        "ko", "ka", "ki", "lai", "le", "ma", "bata", "dekhi", "samma",
        "chha", "cha", "chaina", "hunuhuncha", "ho", "hoina", "huncha",
        "bhayo", "vayo", "bhaneko", "bhanne", "ani", "ra", "tara", "kina",
        "kasari", "kaha", "kahile", "aba", "ahile", "yaha", "tyaha",
        # verbs / imperatives (scam-typical)
        "garnus", "garnuhos", "gara", "garne", "gareko", "garna",
        "pathaunus", "pathaunuhos", "pathau", "pathaune", "pathaideu",
        "halnus", "halnuhos", "hala", "halne", "rakhnu", "rakhnus",
        "dinus", "dinuhos", "deu", "linus", "linuhos", "leu", "aaunus",
        "hernus", "hernuhos", "bujhnus", "bhannus", "khojnu", "milau",
        # nouns (scam-typical)
        "paisa", "rupaiya", "khata", "banka", "inam", "puraskar", "chitthi",
        "suchana", "jankari", "sahayog", "samasya", "turunta", "jhattai",
    }
)


@dataclass(frozen=True)
class LineLanguage:
    """Detection result for one line of text."""

    line_number: int
    text: str
    language: str  # english | nepali_unicode | roman_nepali | mixed | unknown


class BaseLanguageDetector(ABC):
    """Strategy interface so alternative detectors can be injected later."""

    @abstractmethod
    def detect_line(self, line: str) -> str:
        """Classify a single line."""

    def detect_lines(self, text: str) -> List[LineLanguage]:
        """Classify every line of ``text`` (1-based line numbers)."""
        return [
            LineLanguage(line_number=index + 1, text=line, language=self.detect_line(line))
            for index, line in enumerate(text.splitlines())
        ]

    def detect_document(self, text: str) -> str:
        """Aggregate line results into one document-level label."""
        labels = {
            result.language
            for result in self.detect_lines(text)
            if result.language != "unknown"
        }
        if not labels:
            return "unknown"
        if len(labels) == 1:
            return next(iter(labels))
        return "mixed"


class HeuristicLanguageDetector(BaseLanguageDetector):
    """Script-ratio + marker-lexicon detector (deterministic, offline).

    Decision procedure per line:
        1. No letters at all                        -> unknown
        2. Devanagari and Latin letters both present -> mixed
        3. Devanagari only                           -> nepali_unicode
        4. Latin only: marker-word ratio >= threshold -> roman_nepali,
           some markers but below threshold          -> mixed,
           otherwise                                 -> english
    """

    def __init__(self, roman_marker_threshold: float = 0.30) -> None:
        self._threshold = roman_marker_threshold

    def detect_line(self, line: str) -> str:
        has_devanagari = bool(DEVANAGARI.search(line))
        has_latin = bool(LATIN.search(line))

        if not has_devanagari and not has_latin:
            return "unknown"
        if has_devanagari and has_latin:
            return "mixed"
        if has_devanagari:
            return "nepali_unicode"

        words = [word.lower() for word in WORD.findall(line)]
        if not words:
            return "unknown"
        marker_hits = sum(1 for word in words if word in ROMAN_NEPALI_MARKERS)
        ratio = marker_hits / len(words)
        if ratio >= self._threshold and marker_hits >= 2:
            return "roman_nepali"
        if marker_hits >= 2:
            return "mixed"  # Roman Nepali sprinkled into English
        if marker_hits == 1 and len(words) <= 3:
            return "roman_nepali"  # short imperative like "OTP halnus"
        return "english"
