"""Case registry: maps an investigator-supplied reference to a stable case id.

This engine has no user accounts. The *case reference* someone types on the
intake screen ("nabil-bank-phishing-2026") is the handle they use to find
their work again later, so it must resolve to the same case every time.

The reference is therefore hashed into a deterministic case id::

    "Nabil Bank Phishing 2026"  ->  CASE_7F3A9C2E11

Normalisation makes the lookup forgiving (case- and whitespace-insensitive),
and because the id is a pure function of the reference, re-entering it
reopens the same case, its evidence, and its reports - no login required.

Records live in ``storage/case_registry.csv``. Per the project's design
decision, this prototype keeps every structured record in CSV files and
never a database.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional, Tuple

from .config import EvidenceConfig
from .csv_storage import BaseCSVRepository
from .logger import get_logger
from .utils import utc_now_iso

Row = Dict[str, str]

_WHITESPACE = re.compile(r"\s+")

#: Hex characters kept from the digest. 10 hex chars = 40 bits, which keeps
#: ids short enough to type while making an accidental collision negligible.
_ID_WIDTH = 10


def normalize_reference(reference: str) -> str:
    """Canonical form used for hashing and lookups.

    Case- and whitespace-insensitive, so "Nabil Bank" , "nabil bank" and
    "  NABIL   BANK " all resolve to the same case.
    """
    return _WHITESPACE.sub(" ", reference.strip().lower())


def make_case_id(reference: str, prefix: str = "CASE") -> str:
    """Deterministic case id derived from a case reference."""
    digest = hashlib.sha256(normalize_reference(reference).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:_ID_WIDTH].upper()}"


class CaseRegistry(BaseCSVRepository):
    """CSV mapping of case reference -> hashed case id (+ display metadata)."""

    fieldnames = (
        "case_id",
        "case_reference",
        "title",
        "created_at",
        "last_opened_at",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.case_registry_csv)
        self._prefix = config.case_id_prefix
        self._log = get_logger("csv.case_registry")

    # ------------------------------------------------------------------ lookup

    def case_id_for(self, reference: str) -> str:
        return make_case_id(reference, self._prefix)

    def get(self, case_id: str) -> Optional[Row]:
        return next((r for r in self.read_all() if r["case_id"] == case_id), None)

    def get_by_reference(self, reference: str) -> Optional[Row]:
        return self.get(self.case_id_for(reference))

    def list_all(self) -> List[Row]:
        """Every registered case, most recently opened first."""
        return sorted(
            self.read_all(),
            key=lambda r: r.get("last_opened_at") or r.get("created_at") or "",
            reverse=True,
        )

    # ------------------------------------------------------------------ writes

    def resolve_or_create(
        self, reference: str, title: str = ""
    ) -> Tuple[Row, bool]:
        """Return ``(record, created)`` for a case reference.

        An existing reference returns its record untouched (only
        ``last_opened_at`` moves); a new one is registered.
        """
        if not normalize_reference(reference):
            raise ValueError("Case reference cannot be empty.")

        case_id = self.case_id_for(reference)
        existing = self.get(case_id)
        if existing is not None:
            self.touch(case_id)
            return self.get(case_id) or existing, False

        now = utc_now_iso()
        row: Row = {
            "case_id": case_id,
            "case_reference": reference.strip(),
            "title": title.strip() or reference.strip(),
            "created_at": now,
            "last_opened_at": now,
        }
        self.append(row)
        self._log.info("registered case %s for reference %r", case_id, reference)
        return row, True

    def touch(self, case_id: str) -> None:
        """Record that a case was opened (most-recent ordering on the intake)."""
        rows = self.read_all()
        for row in rows:
            if row["case_id"] == case_id:
                row["last_opened_at"] = utc_now_iso()
                self.overwrite_all(rows)
                return
