"""
Automatic error analysis for trained phishing-detection models.

After every evaluation run the misclassified URLs are exported as CSV so
threat analysts can triage them:

* ``false_positives.csv``  - legitimate URLs flagged as phishing.
* ``false_negatives.csv``  - phishing URLs classified as legitimate.
* ``high_confidence_mistakes.csv`` - the mistakes the model was most
  confident about (most dangerous errors, both directions).

Each CSV contains the URL, true/predicted label, the model's phishing
probability and the confidence in the (wrong) prediction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ErrorAnalysisSummary:
    """Summary of one error-analysis run.

    Attributes:
        model_name: Evaluated model.
        total: Number of evaluated samples.
        false_positives: Count of legitimate URLs flagged as phishing.
        false_negatives: Count of missed phishing URLs.
        high_confidence_mistakes: Rows exported to the high-confidence CSV.
        output_dir: Directory containing the CSV files.
        files: Mapping of artifact name to CSV path.
    """

    model_name: str
    total: int
    false_positives: int
    false_negatives: int
    high_confidence_mistakes: int
    output_dir: str
    files: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "model_name": self.model_name,
            "total_samples": self.total,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "high_confidence_mistakes": self.high_confidence_mistakes,
            "output_dir": self.output_dir,
            "files": self.files,
        }


class ErrorAnalyzer:
    """Export model mistakes (FP / FN / high-confidence errors) as CSV.

    Args:
        results_dir: Base results directory; CSVs are written to
            ``<results_dir>/error_analysis/<model_name>/``.
        high_confidence_top_k: Number of highest-confidence mistakes to
            export.
    """

    def __init__(
        self,
        results_dir: Path | None = None,
        high_confidence_top_k: int = 200,
    ) -> None:
        settings = get_settings()
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        self.high_confidence_top_k = int(high_confidence_top_k)

    def analyze(
        self,
        model_name: str,
        urls: Sequence[str],
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray,
    ) -> ErrorAnalysisSummary:
        """Run the error analysis and write the CSV artifacts.

        Args:
            model_name: Model registry key (used for the output folder).
            urls: URLs aligned with the label arrays.
            y_true: Ground-truth labels (0 = legitimate, 1 = phishing).
            y_pred: Predicted labels.
            y_proba: Predicted phishing probabilities.

        Returns:
            ``ErrorAnalysisSummary`` describing the exported artifacts.
        """
        y_true = np.asarray(y_true, dtype=int)
        y_pred = np.asarray(y_pred, dtype=int)
        y_proba = np.asarray(y_proba, dtype=float)

        frame = pd.DataFrame({
            "url": list(urls),
            "true_label": y_true,
            "predicted_label": y_pred,
            "phishing_probability": np.round(y_proba, 6),
        })
        # Confidence in the *predicted* class.
        frame["prediction_confidence"] = np.round(
            np.where(frame["predicted_label"] == 1,
                     frame["phishing_probability"],
                     1.0 - frame["phishing_probability"]),
            6,
        )

        mistakes = frame[frame["true_label"] != frame["predicted_label"]]
        false_positives = mistakes[mistakes["predicted_label"] == 1]
        false_negatives = mistakes[mistakes["predicted_label"] == 0]
        high_confidence = mistakes.sort_values(
            "prediction_confidence", ascending=False
        ).head(self.high_confidence_top_k)

        out_dir = self.results_dir / "error_analysis" / model_name
        out_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, str] = {}
        for stem, df in (
            ("false_positives", false_positives),
            ("false_negatives", false_negatives),
            ("high_confidence_mistakes", high_confidence),
        ):
            path = out_dir / f"{stem}.csv"
            df.to_csv(path, index=False, encoding="utf-8")
            files[stem] = str(path)

        summary = ErrorAnalysisSummary(
            model_name=model_name,
            total=int(len(frame)),
            false_positives=int(len(false_positives)),
            false_negatives=int(len(false_negatives)),
            high_confidence_mistakes=int(len(high_confidence)),
            output_dir=str(out_dir),
            files=files,
        )
        logger.info(
            "Error analysis for %s: %d FP, %d FN, %d high-confidence "
            "mistakes -> %s",
            model_name, summary.false_positives, summary.false_negatives,
            summary.high_confidence_mistakes, out_dir,
        )
        return summary
