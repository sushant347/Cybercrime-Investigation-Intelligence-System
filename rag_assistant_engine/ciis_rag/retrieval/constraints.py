"""Deterministic exact-value constraints extracted from investigator queries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.models import RetrievalHit


@dataclass(frozen=True)
class QueryConstraint:
    kind: str
    display: str
    normalized: str


_MONEY = re.compile(
    r"(?i)(?<!\w)(?:NPR|Rs\.?)\s*([0-9][0-9,]*(?:\.\d+)?)"
)
_EVIDENCE_ID = re.compile(r"(?i)(?<![A-Z0-9_])EVID_[A-Z0-9_-]+(?![A-Z0-9_])")
_EMAIL = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Z]{2,}(?![\w.-])")
_URL = re.compile(r"(?i)https?://[^\s<>\"']+")
_HASH = re.compile(r"(?i)(?<![A-F0-9])[A-F0-9]{32,128}(?![A-F0-9])")
_PHONE = re.compile(r"(?<!\d)\+?\d(?:[\s-]?\d){6,14}(?!\d)")


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def extract_query_constraints(query: str) -> tuple[QueryConstraint, ...]:
    """Return explicit values for which semantic substitution is unsafe."""
    constraints: dict[tuple[str, str], QueryConstraint] = {}
    money_spans: list[tuple[int, int]] = []
    for match in _MONEY.finditer(query):
        amount = _digits(match.group(1))
        display = match.group(0).strip().rstrip(".,;:")
        constraint = QueryConstraint("money", display, amount)
        constraints[(constraint.kind, constraint.normalized)] = constraint
        money_spans.append(match.span())

    patterns = (
        ("evidence_id", _EVIDENCE_ID, lambda value: value.upper()),
        ("email", _EMAIL, lambda value: value.lower()),
        ("url", _URL, lambda value: value.rstrip(".,);]").lower()),
        ("hash", _HASH, lambda value: value.lower()),
    )
    for kind, pattern, normalize in patterns:
        for match in pattern.finditer(query):
            value = match.group(0)
            normalized = normalize(value)
            constraints[(kind, normalized)] = QueryConstraint(kind, value, normalized)

    for match in _PHONE.finditer(query):
        if any(start <= match.start() < end for start, end in money_spans):
            continue
        normalized = _digits(match.group(0))
        constraint = QueryConstraint("phone", match.group(0), normalized)
        constraints[(constraint.kind, constraint.normalized)] = constraint
    return tuple(constraints[key] for key in sorted(constraints))


def missing_query_constraints(
    query: str,
    hits: list[RetrievalHit],
) -> tuple[QueryConstraint, ...]:
    constraints = extract_query_constraints(query)
    if not constraints:
        return ()
    context = "\n".join(hit.chunk.text for hit in hits)
    money_values = {_digits(match.group(1)) for match in _MONEY.finditer(context)}
    available = {
        "evidence_id": {hit.chunk.evidence_id.upper() for hit in hits},
        "email": {match.group(0).lower() for match in _EMAIL.finditer(context)},
        "url": {
            match.group(0).rstrip(".,);]").lower()
            for match in _URL.finditer(context)
        },
        "hash": {match.group(0).lower() for match in _HASH.finditer(context)},
        "phone": {_digits(match.group(0)) for match in _PHONE.finditer(context)},
    }
    missing: list[QueryConstraint] = []
    for constraint in constraints:
        if constraint.kind == "money":
            present = constraint.normalized in money_values
        else:
            present = constraint.normalized in available[constraint.kind]
        if not present:
            missing.append(constraint)
    return tuple(missing)
