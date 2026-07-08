"""OCR confidence filtering and statistics.

Uses the per-line PP-OCRv5 confidence scores already produced by the OCR
engine. Original confidence values are always preserved; lines are only
*tiered* (high / medium / low / discarded). Discarding is opt-in via config
and, even then, discarded lines are reported (never silently lost).
"""

from __future__ import annotations

import statistics
from typing import Any, List, Mapping, Sequence, Tuple

from .config import OCRForensicConfig
from .schemas import ConfidenceStatistics, LineConfidence


class ConfidenceAnalyzer:
    """Computes confidence tiers and document-level statistics."""

    def __init__(self, config: OCRForensicConfig | None = None) -> None:
        self._cfg = config or OCRForensicConfig()

    def tier_for(self, confidence: float) -> str:
        """Classify one confidence value into its tier."""
        cfg = self._cfg
        if confidence >= cfg.confidence_high:
            return "high"
        if confidence >= cfg.confidence_medium:
            return "medium"
        if cfg.discard_low and confidence < cfg.confidence_discard_below:
            return "discarded"
        return "low"

    def analyze(
        self, ocr_pages: Sequence[Mapping[str, Any]]
    ) -> Tuple[List[LineConfidence], ConfidenceStatistics]:
        """Return per-line tiers and the aggregate statistics.

        Args:
            ocr_pages: Prompt 1 ``pages`` list; each page has ``lines`` with
                ``text``, ``confidence`` and ``bbox``.
        """
        lines: List[LineConfidence] = []
        scores: List[float] = []
        tiers = {"high": 0, "medium": 0, "low": 0, "discarded": 0}

        for page in ocr_pages or []:
            page_no = int(page.get("page", 1))
            for raw in page.get("lines", []):
                confidence = float(raw.get("confidence", 0.0))
                tier = self.tier_for(confidence)
                tiers[tier] += 1
                scores.append(confidence)  # original value preserved
                lines.append(LineConfidence(
                    text=str(raw.get("text", "")),
                    confidence=confidence,
                    tier=tier,
                    bbox=raw.get("bbox", []) or [],
                    page=page_no,
                ))

        stats = ConfidenceStatistics(
            count=len(scores),
            average=round(statistics.fmean(scores), 4) if scores else 0.0,
            minimum=round(min(scores), 4) if scores else 0.0,
            maximum=round(max(scores), 4) if scores else 0.0,
            median=round(statistics.median(scores), 4) if scores else 0.0,
            high_count=tiers["high"],
            medium_count=tiers["medium"],
            low_count=tiers["low"],
            discarded_count=tiers["discarded"],
            tier_thresholds={
                "high": self._cfg.confidence_high,
                "medium": self._cfg.confidence_medium,
                "discard_below": self._cfg.confidence_discard_below,
            },
        )
        return lines, stats

    @staticmethod
    def kept_lines(lines: List[LineConfidence]) -> List[LineConfidence]:
        """Lines that survive filtering (everything except ``discarded``)."""
        return [line for line in lines if line.tier != "discarded"]
