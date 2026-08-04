"""Plain-English helpers for investigator-facing text.

A forensic report is read by prosecutors, magistrates and complainants, not
only by engineers. Writing "3 evidence item(s)" saves the author a conditional
and costs every reader a small stumble; worse, it reads like an unfinished
template, which is precisely the impression an evidentiary document must not
give. These helpers put the grammar back.
"""

from __future__ import annotations

#: Irregular plurals that appear in report text. Anything not listed follows
#: the regular rules in :func:`plural`.
_IRREGULAR = {
    "analysis": "analyses",
    "hypothesis": "hypotheses",
    "index": "indices",
    "is": "are",
    "was": "were",
    "this": "these",
}


def plural(word: str, count: int) -> str:
    """The form of ``word`` that agrees with ``count``.

    Accepts a noun phrase as well as a single word: English puts the head noun
    last, so only the final word is inflected and the modifiers ride along.

    >>> plural("item", 1), plural("item", 3)
    ('item', 'items')
    >>> plural("match", 2), plural("company", 2), plural("analysis", 2)
    ('matches', 'companies', 'analyses')
    >>> plural("critical timeline event", 2)
    'critical timeline events'
    """
    if count == 1:
        return word
    head, sep, last = word.rpartition(" ")
    if sep:
        return f"{head} {plural(last, count)}"
    lowered = word.lower()
    if lowered in _IRREGULAR:
        irregular = _IRREGULAR[lowered]
        return irregular.upper() if word.isupper() else irregular
    if lowered.endswith(("s", "x", "z", "ch", "sh")):
        return f"{word}es"
    if lowered.endswith("y") and len(word) > 1 and lowered[-2] not in "aeiou":
        return f"{word[:-1]}ies"
    return f"{word}s"


def count_of(count: int, word: str, *, zero: str | None = None) -> str:
    """``"3 items"`` - the number and its correctly agreeing noun.

    ``zero`` replaces the whole phrase when ``count`` is 0, for the cases where
    "0 links" reads worse than "no links".

    >>> count_of(1, "case"), count_of(4, "case")
    ('1 case', '4 cases')
    >>> count_of(0, "link", zero="no links")
    'no links'
    """
    if count == 0 and zero is not None:
        return zero
    return f"{count} {plural(word, count)}"


def were(count: int) -> str:
    """``"was"`` or ``"were"``, agreeing with ``count``."""
    return "was" if count == 1 else "were"


def joined(values, *, limit: int = 3, more_word: str = "more") -> str:
    """Comma-joined list, truncated with a count of what was left out.

    Keeps a sentence readable when an entity appears in dozens of items,
    without hiding the scale: ``"a, b, c and 12 more"``.
    """
    values = [str(v) for v in values]
    if not values:
        return ""
    if len(values) <= limit:
        if len(values) == 1:
            return values[0]
        return f"{', '.join(values[:-1])} and {values[-1]}"
    shown = ", ".join(values[:limit])
    return f"{shown} and {len(values) - limit} {more_word}"
