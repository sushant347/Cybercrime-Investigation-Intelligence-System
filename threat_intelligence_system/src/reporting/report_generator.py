"""
Structured JSON report generator for the Phishing URL Detection Engine.

The ``ReportGenerator`` converts ``PredictionResult`` objects (and lists
thereof) into richly-structured, human-readable JSON reports suitable for:

- Single-URL analysis reports.
- Batch URL analysis summaries with statistics.
- CIIE integration payloads consumed by downstream modules.

Report structure (single URL)
------------------------------
.. code-block:: json

    {
      "report_id": "phish-20240101-abc123",
      "generated_at": "2024-01-01T12:00:00+00:00",
      "engine_version": "2.0.0",
      "analysis": {
        "url": "https://paypal-login-security.xyz/login",
        "prediction": "phishing",
        "confidence": 0.97,
        "risk_score": 91,
        "risk_level": "Critical",
        "model_type": "xgboost",
        "analysis_timestamp": "...",
        "reasons": ["..."],
        "verdict_summary": "PHISHING — Critical risk (score 91/100)"
      },
      "features": { ... },
      "threat_intelligence": { ... },
      "rule_engine": { ... },      # if available
      "metadata": { ... }
    }

Report structure (batch)
--------------------------
.. code-block:: json

    {
      "report_id": "...",
      "generated_at": "...",
      "engine_version": "2.0.0",
      "summary": {
        "total_urls": 10,
        "phishing_count": 3,
        "legitimate_count": 7,
        "high_risk_count": 4,
        "average_risk_score": 48.5,
        "average_confidence": 0.82
      },
      "results": [ ... ]
    }
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.prediction.result import PredictionResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Engine version — increment when the engine protocol changes
_ENGINE_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# AnalysisReport dataclass
# ---------------------------------------------------------------------------

class AnalysisReport:
    """A structured report wrapping one or more ``PredictionResult`` objects.

    Provides JSON serialization, file export, and rich summary statistics.

    Attributes:
        report_id: Unique report identifier.
        generated_at: ISO 8601 UTC timestamp of report generation.
        engine_version: Detection engine version string.
        results: List of ``PredictionResult`` objects included in the report.
        metadata: Optional additional metadata (analyst notes, job ID, etc.).
    """

    def __init__(
        self,
        results: list[PredictionResult],
        metadata: Optional[dict[str, Any]] = None,
        report_id: Optional[str] = None,
    ) -> None:
        """Create an analysis report.

        Args:
            results: One or more ``PredictionResult`` instances.
            metadata: Optional metadata dict to embed in the report.
            report_id: Optional custom report ID.  If ``None``, a deterministic
                ID is generated from the URL(s) and timestamp.
        """
        if not results:
            raise ValueError("At least one PredictionResult is required.")

        self.results = results
        self.metadata: dict[str, Any] = metadata or {}
        self.generated_at: str = datetime.now(timezone.utc).isoformat()
        self.engine_version: str = _ENGINE_VERSION

        # Build deterministic report ID
        if report_id:
            self.report_id = report_id
        else:
            payload = (
                "|".join(r.url for r in results) + self.generated_at
            ).encode("utf-8")
            digest = hashlib.sha256(payload).hexdigest()[:12]
            self.report_id = f"phish-{digest}"

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self, include_features: bool = True) -> dict[str, Any]:
        """Convert the report to a plain dictionary.

        Args:
            include_features: If ``True``, include the full feature dict in
                each result.  Set to ``False`` for compact summaries.

        Returns:
            Report dictionary ready for JSON serialization.
        """
        if len(self.results) == 1:
            return self._single_result_dict(self.results[0], include_features)
        return self._batch_result_dict(include_features)

    def to_json(self, indent: int = 2, include_features: bool = True) -> str:
        """Serialize the report to a JSON string.

        Args:
            indent: JSON indentation level.
            include_features: Whether to include feature data.

        Returns:
            JSON string.
        """
        return json.dumps(
            self.to_dict(include_features=include_features),
            indent=indent,
            ensure_ascii=False,
            default=str,
        )

    def save(
        self,
        output_dir: Path,
        filename: Optional[str] = None,
        include_features: bool = True,
    ) -> Path:
        """Write the report to a JSON file.

        Args:
            output_dir: Directory to write the report to.  Created if missing.
            filename: Custom filename (without extension).  Defaults to the
                report ID.
            include_features: Whether to include features in the output.

        Returns:
            Path to the written file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        fname = (filename or self.report_id) + ".json"
        output_path = output_dir / fname

        content = self.to_json(indent=2, include_features=include_features)
        output_path.write_text(content, encoding="utf-8")

        logger.info(
            "Report saved: %s (%d bytes)", output_path, len(content)
        )
        return output_path

    # ------------------------------------------------------------------
    # Summary statistics (batch)
    # ------------------------------------------------------------------

    def summary_stats(self) -> dict[str, Any]:
        """Compute aggregate statistics over all results.

        Returns:
            Dictionary with count, averages, and distribution breakdowns.
        """
        n = len(self.results)
        phishing = [r for r in self.results if r.is_phishing]
        legitimate = [r for r in self.results if not r.is_phishing]
        high_risk = [r for r in self.results if r.is_high_risk]

        avg_score = sum(r.risk_score for r in self.results) / n if n else 0.0
        avg_confidence = sum(r.confidence for r in self.results) / n if n else 0.0

        risk_distribution = {
            level: sum(1 for r in self.results if r.risk_level == level)
            for level in ("Critical", "High", "Medium", "Low", "Safe", "Unknown")
        }

        return {
            "total_urls": n,
            "phishing_count": len(phishing),
            "legitimate_count": len(legitimate),
            "high_risk_count": len(high_risk),
            "phishing_rate": round(len(phishing) / n, 4) if n else 0.0,
            "average_risk_score": round(avg_score, 2),
            "average_confidence": round(avg_confidence, 4),
            "risk_distribution": risk_distribution,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _single_result_dict(
        self, result: PredictionResult, include_features: bool
    ) -> dict[str, Any]:
        """Build a single-URL report dictionary."""
        report: dict[str, Any] = {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "engine_version": self.engine_version,
            "analysis": self._result_analysis_dict(result),
            "threat_intelligence": result.threat_intelligence,
        }

        if include_features:
            report["features"] = result.features

        if result.metadata:
            report["metadata"] = result.metadata

        if self.metadata:
            report.setdefault("metadata", {}).update(self.metadata)

        return report

    def _batch_result_dict(self, include_features: bool) -> dict[str, Any]:
        """Build a batch-URL report dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "engine_version": self.engine_version,
            "summary": self.summary_stats(),
            "results": [
                {
                    **self._result_analysis_dict(r),
                    "threat_intelligence": r.threat_intelligence,
                    **({"features": r.features} if include_features else {}),
                }
                for r in self.results
            ],
            "metadata": self.metadata,
        }

    @staticmethod
    def _result_analysis_dict(result: PredictionResult) -> dict[str, Any]:
        """Build the ``analysis`` section for a single result."""
        verdict = (
            f"{result.prediction.upper()} — {result.risk_level} risk "
            f"(score {result.risk_score}/100)"
        )
        return {
            "url": result.url,
            "prediction": result.prediction,
            "confidence": result.confidence,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "model_type": result.model_type,
            "analysis_timestamp": result.analysis_timestamp,
            "reasons": result.reasons,
            "verdict_summary": verdict,
            "is_phishing": result.is_phishing,
            "is_high_risk": result.is_high_risk,
        }


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Factory for creating and persisting ``AnalysisReport`` objects.

    The ``ReportGenerator`` wraps ``AnalysisReport`` creation with optional
    automatic persistence to the results directory configured in settings.

    Usage::

        generator = ReportGenerator()

        # Single URL
        result = predictor.predict("https://paypal-login-security.xyz/login")
        report = generator.generate(result)
        print(report.to_json())

        # Batch
        results = predictor.predict_batch(url_list)
        batch_report = generator.generate_batch(results)
        batch_report.save(output_dir=Path("results"))
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """Initialise the report generator.

        Args:
            output_dir: Default directory for saving reports.  Defaults to
                ``settings.paths.results_dir``.
        """
        from src.config.settings import get_settings
        settings = get_settings()
        self._output_dir = Path(output_dir or settings.paths.results_dir)
        logger.debug("ReportGenerator initialised: output_dir=%s", self._output_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        result: PredictionResult,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AnalysisReport:
        """Generate a report for a single URL analysis.

        Args:
            result: ``PredictionResult`` from ``PhishingPredictor.predict()``.
            metadata: Optional metadata to embed in the report.

        Returns:
            ``AnalysisReport`` instance.
        """
        report = AnalysisReport(results=[result], metadata=metadata)
        logger.info(
            "Report generated: id=%s, url=%s, verdict=%s",
            report.report_id,
            result.url[:60],
            result.prediction,
        )
        return report

    def generate_batch(
        self,
        results: list[PredictionResult],
        metadata: Optional[dict[str, Any]] = None,
    ) -> AnalysisReport:
        """Generate a report for a batch of URL analyses.

        Args:
            results: List of ``PredictionResult`` objects.
            metadata: Optional metadata to embed in the report.

        Returns:
            ``AnalysisReport`` instance with batch summary statistics.
        """
        if not results:
            raise ValueError("At least one PredictionResult is required.")

        report = AnalysisReport(results=results, metadata=metadata)
        stats = report.summary_stats()
        logger.info(
            "Batch report generated: id=%s, total=%d, phishing=%d, "
            "legitimate=%d, avg_score=%.1f",
            report.report_id,
            stats["total_urls"],
            stats["phishing_count"],
            stats["legitimate_count"],
            stats["average_risk_score"],
        )
        return report

    def generate_and_save(
        self,
        result: PredictionResult,
        metadata: Optional[dict[str, Any]] = None,
        output_dir: Optional[Path] = None,
        include_features: bool = True,
    ) -> tuple["AnalysisReport", Path]:
        """Generate a single-URL report and save it to disk.

        Args:
            result: Prediction result to report on.
            metadata: Optional metadata dict.
            output_dir: Override the default output directory.
            include_features: Whether to include features in the saved file.

        Returns:
            Tuple of ``(AnalysisReport, saved_file_path)``.
        """
        report = self.generate(result, metadata)
        saved_path = report.save(
            output_dir=output_dir or self._output_dir,
            include_features=include_features,
        )
        return report, saved_path

    def generate_batch_and_save(
        self,
        results: list[PredictionResult],
        metadata: Optional[dict[str, Any]] = None,
        output_dir: Optional[Path] = None,
        include_features: bool = True,
    ) -> tuple["AnalysisReport", Path]:
        """Generate a batch report and save it to disk.

        Args:
            results: List of prediction results.
            metadata: Optional metadata dict.
            output_dir: Override the default output directory.
            include_features: Whether to include features in the saved file.

        Returns:
            Tuple of ``(AnalysisReport, saved_file_path)``.
        """
        report = self.generate_batch(results, metadata)
        saved_path = report.save(
            output_dir=output_dir or self._output_dir,
            include_features=include_features,
        )
        return report, saved_path
