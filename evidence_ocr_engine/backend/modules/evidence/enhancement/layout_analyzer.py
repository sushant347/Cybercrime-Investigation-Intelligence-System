"""Layout-aware reconstruction for mobile-screenshot OCR.

Mobile screenshots mix real conversation content with UI chrome: the status
bar (time, battery, signal), chat input box, send button, navigation icons,
delivery ticks and standalone chat timestamps. Merging that chrome into the
message text corrupts the evidence record.

The analyzer classifies every line of the (already corrected) text into
roles and returns three views:

* ``ui_text``       - status bar, input box, navigation, delivery marks
* ``message_text``  - sender names, chat timestamps and message bodies,
  with boundaries preserved (a timestamp or UI line never glues two
  messages together)
* ``layout``        - the full per-line classification for the audit trail

Nothing is deleted from ``enhanced_text`` itself - separation is an
additional view, never a modification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from ..logger import get_logger

# ---------------------------------------------------------------- role patterns

_TIME_ONLY = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s?(?:AM|PM|am|pm)?$")

_STATUS_BAR = re.compile(
    r"(\d{1,3}\s?%)"                                   # battery percentage
    r"|(\b(?:4G|5G|3G|LTE|VoLTE|Wi-?Fi|WIFI)\b)"       # network indicators
    r"|(\b(?:NTC|Ncell|Nepal Telecom|SmartCell)\b)"    # Nepali carriers
    r"|([▲▼◢◣📶🔋🔇🔕✈])",                              # status icons
    re.IGNORECASE,
)

_CHAT_INPUT = re.compile(
    r"^(?:type a message|message|write a message|send a message|"
    r"enter message|text message|aa message|message\.{2,3})\s*[.…]*$",
    re.IGNORECASE,
)

_NAVIGATION = re.compile(
    r"^[<>←→⇦⋮⋯☰◀▶●○■□⌂+/-]{1,6}$"
    r"|^(?:back|home|menu|search|calls?|chats?|status|updates|communities)$",
    re.IGNORECASE,
)

_DELIVERY = re.compile(
    r"^(?:✓{1,2}|√{1,2}|seen|delivered|read|sent|sending\.{0,3})$",
    re.IGNORECASE,
)

_PRESENCE = re.compile(
    r"^(?:online|typing\.{0,3}|last seen(?:\s.+)?|tap for more info|"
    r"end-to-end encrypted.*)$",
    re.IGNORECASE,
)

_CHAT_TIMESTAMP = re.compile(
    r"^(?:today|yesterday|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|आज|हिजो)$"
    r"|^\d{1,2}[:/.-]\d{1,2}(?:[/.-]\d{2,4})?,?\s*(?:\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?)?$"
    r"|^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?$",
    re.IGNORECASE,
)

#: Short title-cased line (or +977 number) that a message follows -> sender.
_SENDER_LIKE = re.compile(
    r"^(?:you|me|तपाईं)$"
    r"|^\+?977[-\s]?9\d{9}$"
    r"|^(?:[A-Z][a-zA-Z.]{1,14})(?:\s[A-Z][a-zA-Z.]{1,14}){0,2}:?$",
)

#: Symbol/emoji-only rows (toolbars, attachment strips).
_ICON_ROW = re.compile(r"^[\W_]{2,}$")


@dataclass(frozen=True)
class LayoutLine:
    """Classification of one line."""

    line: int          # 1-based line number in the enhanced text
    role: str          # status_bar | chat_input | navigation | delivery |
                       # presence | timestamp | sender | message | icon_row
    text: str

    @property
    def is_ui(self) -> bool:
        return self.role in ("status_bar", "chat_input", "navigation",
                             "delivery", "presence", "icon_row")


@dataclass
class LayoutResult:
    """Separated views over the enhanced text."""

    lines: List[LayoutLine]

    @property
    def ui_text(self) -> str:
        return "\n".join(l.text for l in self.lines if l.is_ui)

    @property
    def message_text(self) -> str:
        return "\n".join(
            l.text for l in self.lines
            if l.role in ("sender", "timestamp", "message"))

    @property
    def ui_line_count(self) -> int:
        return sum(1 for l in self.lines if l.is_ui)


class LayoutAnalyzer:
    """Classifies enhanced-text lines into UI chrome vs. conversation."""

    def __init__(self) -> None:
        self._log = get_logger("enhancement.layout")

    def analyze(self, text: str) -> LayoutResult:
        """Classify every non-empty line of ``text``."""
        raw_lines = text.split("\n")
        classified: List[LayoutLine] = []
        for number, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            role = self._classify(stripped, number, raw_lines)
            classified.append(LayoutLine(line=number, role=role, text=stripped))
        result = LayoutResult(lines=classified)
        if result.ui_line_count:
            self._log.info("layout: %d UI line(s) separated from %d line(s)",
                           result.ui_line_count, len(classified))
        return result

    # ---------------------------------------------------------------- internal

    def _classify(self, line: str, number: int, all_lines: List[str]) -> str:
        if _CHAT_INPUT.match(line):
            return "chat_input"
        if _DELIVERY.match(line):
            return "delivery"
        if _PRESENCE.match(line):
            return "presence"
        if _NAVIGATION.match(line):
            return "navigation"
        if _TIME_ONLY.match(line) and number <= 2:
            return "status_bar"      # a lone clock at the top = status bar
        if len(line) <= 40 and _STATUS_BAR.search(line) and not self._wordy(line):
            return "status_bar"
        if _CHAT_TIMESTAMP.match(line):
            return "timestamp"
        if _ICON_ROW.match(line):
            return "icon_row"
        if self._is_sender(line, number, all_lines):
            return "sender"
        return "message"

    @staticmethod
    def _wordy(line: str) -> bool:
        """More than three real words -> conversation, not a status bar."""
        return len(re.findall(r"[A-Za-zऀ-ॿ]{2,}", line)) > 3

    @staticmethod
    def _is_sender(line: str, number: int, all_lines: List[str]) -> bool:
        """Short name-like line immediately followed by more content."""
        if len(line) > 30 or not _SENDER_LIKE.match(line):
            return False
        following = [l for l in all_lines[number:] if l.strip()]
        return bool(following)  # a sender label must introduce something
