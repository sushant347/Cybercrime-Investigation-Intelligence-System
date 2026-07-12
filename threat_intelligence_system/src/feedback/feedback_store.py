"""
Active-learning feedback interface (Phase 3-E).

Investigators can mark engine predictions as ``correct``, ``incorrect`` or
``unknown``.  Feedback is persisted to an append-only JSONL file so that
corrections can later be folded into the retraining pipeline (Phase 3-F).

The engine NEVER retrains automatically -- this module only records and
exposes feedback.

Usage::

    from src.feedback.feedback_store import FeedbackStore

    store = FeedbackStore()
    store.record(
        url="https://paypal-verify.xyz/login",
        predicted_label="Phishing",
        verdict="correct",
        investigator="analyst-7",
    )
    corrections = store.get_corrections()
    store.export_for_retraining(Path("data/feedback/corrections.csv"))
"""

from __future__ import annotations

import csv
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Allowed investigator verdicts.
VALID_VERDICTS = ("correct", "incorrect", "unknown")

#: Label mapping used when exporting corrections for retraining.
_LABEL_TO_INT = {"legitimate": 0, "suspicious": 1, "phishing": 1}


@dataclass
class FeedbackEntry:
    """A single piece of investigator feedback.

    Attributes:
        feedback_id: Unique identifier (UUID4 hex).
        url: The analysed URL.
        predicted_label: The engine's prediction at analysis time.
        verdict: Investigator verdict -- 'correct', 'incorrect' or 'unknown'.
        correct_label: The true label supplied by the investigator when the
            verdict is 'incorrect' (e.g. 'Legitimate' or 'Phishing').
        investigator: Free-form investigator/analyst identifier.
        comment: Optional free-form comment.
        model_version: Model version that produced the prediction.
        risk_score: Risk score at analysis time.
        timestamp: ISO-8601 UTC timestamp of the feedback.
    """

    url: str
    predicted_label: str
    verdict: str
    feedback_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    correct_label: Optional[str] = None
    investigator: str = ""
    comment: str = ""
    model_version: str = "unknown"
    risk_score: Optional[int] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "feedback_id": self.feedback_id,
            "url": self.url,
            "predicted_label": self.predicted_label,
            "verdict": self.verdict,
            "correct_label": self.correct_label,
            "investigator": self.investigator,
            "comment": self.comment,
            "model_version": self.model_version,
            "risk_score": self.risk_score,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeedbackEntry":
        """Deserialise from a plain dictionary (unknown keys ignored)."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class FeedbackStore:
    """Thread-safe, append-only JSONL feedback store (Phase 3-E).

    Args:
        path: Path to the JSONL file.  Defaults to
            ``<project_root>/data/feedback/feedback.jsonl``.
    """

    def __init__(self, path: Path | None = None) -> None:
        settings = get_settings()
        default = settings.paths.project_root / "data" / "feedback" / "feedback.jsonl"
        self.path = Path(path or default)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.debug("FeedbackStore initialised at %s", self.path)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        url: str,
        predicted_label: str,
        verdict: str,
        correct_label: Optional[str] = None,
        investigator: str = "",
        comment: str = "",
        model_version: str = "unknown",
        risk_score: Optional[int] = None,
    ) -> FeedbackEntry:
        """Record one investigator verdict.

        Args:
            url: The analysed URL.
            predicted_label: The engine's prediction.
            verdict: 'correct', 'incorrect' or 'unknown'.
            correct_label: True label when verdict is 'incorrect'.
            investigator: Analyst identifier.
            comment: Optional comment.
            model_version: Version of the model that predicted.
            risk_score: Risk score at analysis time.

        Returns:
            The persisted ``FeedbackEntry``.

        Raises:
            ValueError: If *verdict* is not one of ``VALID_VERDICTS`` or an
                'incorrect' verdict is missing ``correct_label``.
        """
        verdict = verdict.strip().lower()
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid verdict '{verdict}'. Must be one of {VALID_VERDICTS}."
            )
        if verdict == "incorrect" and not correct_label:
            raise ValueError(
                "Verdict 'incorrect' requires correct_label "
                "(e.g. 'Legitimate' or 'Phishing')."
            )

        entry = FeedbackEntry(
            url=url,
            predicted_label=predicted_label,
            verdict=verdict,
            correct_label=correct_label,
            investigator=investigator,
            comment=comment,
            model_version=model_version,
            risk_score=risk_score,
        )
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        logger.info(
            "Feedback recorded: %s verdict=%s url=%s",
            entry.feedback_id, verdict, url[:60],
        )
        return entry

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_all(self) -> list[FeedbackEntry]:
        """Load every feedback entry (empty list when no file exists)."""
        if not self.path.exists():
            return []
        entries: list[FeedbackEntry] = []
        with self._lock:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(FeedbackEntry.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, TypeError) as exc:
                        logger.warning("Skipping malformed feedback line: %s", exc)
        return entries

    def get_corrections(self) -> list[FeedbackEntry]:
        """Return entries marked 'incorrect' (with the true label)."""
        return [
            e for e in self.get_all()
            if e.verdict == "incorrect" and e.correct_label
        ]

    def counts(self) -> dict[str, int]:
        """Return verdict counts: {'correct': n, 'incorrect': n, 'unknown': n}."""
        summary = {v: 0 for v in VALID_VERDICTS}
        for entry in self.get_all():
            if entry.verdict in summary:
                summary[entry.verdict] += 1
        return summary

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_for_retraining(self, output_csv: Path) -> int:
        """Export corrections as a training CSV with 'url' and 'label' columns.

        Args:
            output_csv: Destination CSV path.

        Returns:
            Number of exported rows.
        """
        corrections = self.get_corrections()
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        rows = 0
        with open(output_csv, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["url", "label"])
            for entry in corrections:
                label = _LABEL_TO_INT.get(str(entry.correct_label).lower())
                if label is None:
                    logger.warning(
                        "Skipping correction with unknown label: %s",
                        entry.correct_label,
                    )
                    continue
                writer.writerow([entry.url, label])
                rows += 1

        logger.info("Exported %d corrections to %s", rows, output_csv)
        return rows
