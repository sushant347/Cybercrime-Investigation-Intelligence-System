"""Cybersecurity keyword detection and risk-signal counting.

Counts scam-indicative keywords (bilingual: English, Roman Nepali and
Nepali Unicode variants) and aggregates them into four risk-signal
categories: urgency, financial, credential-theft and threat. This module
only *counts* - it performs no phishing classification (Module 1) and no
threat-intelligence lookup (Module 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

#: keyword -> (risk category, variant spellings/synonyms counted under it).
#: Variants include Roman Nepali and Nepali Unicode forms - counted, never
#: translated.
KEYWORD_GROUPS: Dict[str, tuple[str, tuple[str, ...]]] = {
    "otp": ("credential", ("otp", "one time password", "ओटीपी")),
    "password": ("credential", ("password", "passworda")),
    "pin": ("credential", ("pin",)),
    "cvv": ("credential", ("cvv", "cvc")),
    "login": ("credential", ("login", "log in", "sign in")),
    "verify": ("credential", ("verify", "verification", "verified", "प्रमाणित")),
    "password_reset": ("credential", ("password reset", "reset your password")),
    "kyc": ("credential", ("kyc",)),
    "pan": ("credential", ("pan",)),
    "card": ("credential", ("card", "debit card", "credit card")),
    "account": ("credential", ("account", "khata", "खाता")),
    "update": ("urgency", ("update", "अपडेट")),
    "suspended": ("urgency", ("suspended", "suspend", "deactivated", "blocked",
                              "locked", "निलम्बित")),
    "urgent": ("urgency", ("urgent", "immediately", "turunta", "jhattai",
                           "तुरुन्त", "अहिले नै", "within 24 hours", "expire",
                           "expires", "last chance", "act now")),
    "bank": ("financial", ("bank", "banka", "बैंक")),
    "refund": ("financial", ("refund", "फिर्ता")),
    "lottery": ("financial", ("lottery", "chitthi", "चिठ्ठा")),
    "winner": ("financial", ("winner", "won", "jitnu", "jityo", "विजेता")),
    "reward": ("financial", ("reward", "cashback", "bonus", "inam", "इनाम")),
    "prize": ("financial", ("prize", "puraskar", "पुरस्कार")),
    "money": ("financial", ("money", "paisa", "rupaiya", "पैसा", "रुपैयाँ")),
    "crypto": ("financial", ("crypto", "cryptocurrency", "bitcoin", "btc",
                             "ethereum", "usdt")),
    "wallet": ("financial", ("wallet", "esewa", "khalti", "ime pay", "imepay")),
    "payment": ("financial", ("payment", "transfer", "send money", "pathaunus",
                              "pathau", "भुक्तानी")),
    "threat": ("threat", ("police", "legal action", "lawsuit", "arrest", "fine",
                          "penalty", "court", "jail", "प्रहरी", "कारबाही",
                          "will be closed", "will be terminated")),
}

_CATEGORIES = ("urgency", "financial", "credential", "threat")


@dataclass
class KeywordReport:
    """Keyword frequencies plus aggregated risk-signal counts."""

    keyword_frequency: Dict[str, int] = field(default_factory=dict)
    risk_signals: Dict[str, int] = field(default_factory=dict)

    @property
    def total_hits(self) -> int:
        return sum(self.keyword_frequency.values())


class KeywordAnalyzer:
    """Counts scam-indicative vocabulary in cleaned evidence text."""

    def __init__(self) -> None:
        # Pre-compile one pattern per keyword group (word-boundary safe for
        # Latin; Devanagari variants matched as plain substrings since \b
        # does not apply cleanly across scripts).
        self._patterns: Dict[str, re.Pattern[str]] = {}
        for keyword, (_category, variants) in KEYWORD_GROUPS.items():
            parts = []
            for variant in variants:
                escaped = re.escape(variant)
                if re.match(r"[a-z]", variant):
                    parts.append(rf"\b{escaped}\b")
                else:
                    parts.append(escaped)
            self._patterns[keyword] = re.compile("|".join(parts), re.IGNORECASE)

    def analyze(self, text: str) -> KeywordReport:
        """Count keyword occurrences and roll them up into risk signals."""
        frequency: Dict[str, int] = {}
        signals: Dict[str, int] = {category: 0 for category in _CATEGORIES}
        for keyword, (category, _variants) in KEYWORD_GROUPS.items():
            count = len(self._patterns[keyword].findall(text))
            if count:
                frequency[keyword] = count
                signals[category] += count
        return KeywordReport(
            keyword_frequency=dict(sorted(frequency.items(),
                                          key=lambda kv: -kv[1])),
            risk_signals=signals,
        )

    @staticmethod
    def categories() -> List[str]:
        return list(_CATEGORIES)
