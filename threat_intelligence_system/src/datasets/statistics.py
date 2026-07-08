"""
Dataset statistics module for the Phishing URL Detection Engine.

Provides the ``DatasetStatistics`` class which computes descriptive
statistics over URL datasets.  Statistics include label distributions,
URL length analytics, top-level domain (TLD) frequency, and duplicate
counts.  Results are returned as plain dictionaries and can optionally
be pretty-printed via the logger.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatasetStatistics:
    """Compute and report descriptive statistics for URL datasets.

    All public methods accept DataFrames with at least ``['url', 'label']``
    columns and return JSON-serialisable dictionaries.

    Usage::

        stats = DatasetStatistics()
        report = stats.summary(train_df, name="train")
        stats.print_summary(train_df, name="train")
    """

    def __init__(self) -> None:
        """Initialise the statistics helper."""
        logger.info("DatasetStatistics initialised")

    # ------------------------------------------------------------------
    # Core summary
    # ------------------------------------------------------------------

    def summary(
        self,
        df: pd.DataFrame,
        name: str = "dataset",
    ) -> dict[str, Any]:
        """Compute a comprehensive summary of the dataset.

        Args:
            df: DataFrame with ``['url', 'label']`` columns.
            name: Human-readable name used in log messages.

        Returns:
            Dictionary with keys:

            * ``total_rows`` -- number of rows.
            * ``label_distribution`` -- counts and percentages per label.
            * ``url_length_stats`` -- min, max, mean, median, std of URL
              character lengths.
            * ``top_tlds`` -- the 20 most frequent TLDs.
            * ``duplicate_count`` -- number of duplicate URLs.
        """
        if df.empty:
            logger.warning("summary('%s'): received empty DataFrame", name)
            return self._empty_summary(name)

        total_rows: int = len(df)

        # Label distribution
        label_dist = self._label_distribution(df, total_rows)

        # URL length statistics
        url_lengths = df["url"].astype(str).str.len()
        url_length_stats = self._url_length_stats(url_lengths)

        # Top TLDs
        top_tlds = self._top_tlds(df, top_n=20)

        # Duplicate count
        duplicate_count = int(df["url"].duplicated().sum())

        result: dict[str, Any] = {
            "name": name,
            "total_rows": total_rows,
            "label_distribution": label_dist,
            "url_length_stats": url_length_stats,
            "top_tlds": top_tlds,
            "duplicate_count": duplicate_count,
        }
        return result

    # ------------------------------------------------------------------
    # Pretty-print
    # ------------------------------------------------------------------

    def print_summary(
        self,
        df: pd.DataFrame,
        name: str = "dataset",
    ) -> None:
        """Compute and log a human-readable summary of the dataset.

        Args:
            df: DataFrame with ``['url', 'label']`` columns.
            name: Human-readable name used in log messages.
        """
        report = self.summary(df, name=name)
        self._log_report(report)

    # ------------------------------------------------------------------
    # Cross-split comparison
    # ------------------------------------------------------------------

    def compare_splits(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
    ) -> dict[str, Any]:
        """Compare label distributions across train / val / test splits.

        Args:
            train_df: Training split.
            val_df: Validation split.
            test_df: Test split.

        Returns:
            Dictionary mapping split names to their distribution info.
        """
        result: dict[str, Any] = {}

        for split_name, split_df in [
            ("train", train_df),
            ("validation", val_df),
            ("test", test_df),
        ]:
            total = len(split_df)
            if total == 0:
                result[split_name] = {
                    "total": 0,
                    "label_counts": {},
                    "label_percentages": {},
                }
                continue

            counts = split_df["label"].value_counts().to_dict()
            percentages = {
                label: round(count / total * 100, 2)
                for label, count in counts.items()
            }
            result[split_name] = {
                "total": total,
                "label_counts": counts,
                "label_percentages": percentages,
            }

        # Log comparison table
        logger.info("=" * 60)
        logger.info("SPLIT COMPARISON")
        logger.info("=" * 60)
        logger.info(
            "%-15s %10s %12s %12s",
            "Split", "Total", "Legit (%)", "Phish (%)",
        )
        logger.info("-" * 55)
        for split_name in ("train", "validation", "test"):
            info = result[split_name]
            legit_pct = info["label_percentages"].get(0, 0.0)
            phish_pct = info["label_percentages"].get(1, 0.0)
            logger.info(
                "%-15s %10d %11.1f%% %11.1f%%",
                split_name,
                info["total"],
                legit_pct,
                phish_pct,
            )
        logger.info("=" * 60)

        return result

    # ------------------------------------------------------------------
    # Multi-dataset report
    # ------------------------------------------------------------------

    def full_report(
        self,
        datasets: dict[str, pd.DataFrame],
    ) -> dict[str, dict[str, Any]]:
        """Generate summaries for every dataset in the dictionary.

        Args:
            datasets: Mapping of dataset names to DataFrames.

        Returns:
            Dictionary mapping each name to its summary dict.
        """
        combined: dict[str, dict[str, Any]] = {}
        for name, df in datasets.items():
            report = self.summary(df, name=name)
            self._log_report(report)
            combined[name] = report

        logger.info(
            "Full report generated for %d datasets", len(combined),
        )
        return combined

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _label_distribution(
        df: pd.DataFrame,
        total: int,
    ) -> dict[str, Any]:
        """Compute label counts and percentages.

        Args:
            df: DataFrame with a ``label`` column.
            total: Total number of rows (for percentage calculation).

        Returns:
            Dictionary with ``counts`` and ``percentages`` sub-dicts.
        """
        counts = df["label"].value_counts().to_dict()
        percentages = {
            str(label): round(count / total * 100, 2)
            for label, count in counts.items()
        }
        counts_str = {str(k): v for k, v in counts.items()}
        return {"counts": counts_str, "percentages": percentages}

    @staticmethod
    def _url_length_stats(url_lengths: pd.Series) -> dict[str, float]:
        """Compute descriptive statistics for URL character lengths.

        Args:
            url_lengths: Series of integer URL lengths.

        Returns:
            Dictionary with min, max, mean, median, and std.
        """
        return {
            "min": int(url_lengths.min()),
            "max": int(url_lengths.max()),
            "mean": round(float(url_lengths.mean()), 2),
            "median": round(float(url_lengths.median()), 2),
            "std": round(float(url_lengths.std()), 2) if len(url_lengths) > 1 else 0.0,
        }

    @staticmethod
    def _top_tlds(df: pd.DataFrame, top_n: int = 20) -> dict[str, int]:
        """Extract the *top_n* most frequent TLDs from the URL column.

        Args:
            df: DataFrame with a ``url`` column.
            top_n: Number of TLDs to return.

        Returns:
            Ordered dictionary mapping TLD strings to occurrence counts.
        """

        def _extract_tld(url: str) -> str:
            """Extract the TLD from a URL string."""
            try:
                hostname = urlparse(str(url)).hostname or ""
                parts = hostname.rsplit(".", 1)
                return parts[-1].lower() if parts else ""
            except Exception:
                return ""

        tlds = df["url"].apply(_extract_tld)
        tld_counts = (
            tlds[tlds.ne("")]
            .value_counts()
            .head(top_n)
            .to_dict()
        )
        return tld_counts

    @staticmethod
    def _empty_summary(name: str) -> dict[str, Any]:
        """Return a summary dict for an empty DataFrame.

        Args:
            name: Dataset name.

        Returns:
            Summary dictionary with zero-valued metrics.
        """
        return {
            "name": name,
            "total_rows": 0,
            "label_distribution": {"counts": {}, "percentages": {}},
            "url_length_stats": {
                "min": 0,
                "max": 0,
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
            },
            "top_tlds": {},
            "duplicate_count": 0,
        }

    @staticmethod
    def _log_report(report: dict[str, Any]) -> None:
        """Pretty-print a summary report via the logger.

        Args:
            report: Dictionary produced by ``summary()``.
        """
        name = report.get("name", "dataset")
        logger.info("=" * 60)
        logger.info("DATASET SUMMARY: %s", name)
        logger.info("=" * 60)
        logger.info("Total rows:       %d", report["total_rows"])

        # Label distribution
        label_dist = report.get("label_distribution", {})
        counts = label_dist.get("counts", {})
        percentages = label_dist.get("percentages", {})
        logger.info("Label distribution:")
        for label in sorted(counts.keys()):
            logger.info(
                "  Label %s: %d  (%.1f%%)",
                label,
                counts[label],
                float(percentages.get(label, 0)),
            )

        # URL length stats
        url_stats = report.get("url_length_stats", {})
        logger.info("URL length statistics:")
        logger.info("  Min:    %s", url_stats.get("min", "N/A"))
        logger.info("  Max:    %s", url_stats.get("max", "N/A"))
        logger.info("  Mean:   %s", url_stats.get("mean", "N/A"))
        logger.info("  Median: %s", url_stats.get("median", "N/A"))
        logger.info("  Std:    %s", url_stats.get("std", "N/A"))

        # Top TLDs
        top_tlds = report.get("top_tlds", {})
        if top_tlds:
            logger.info("Top TLDs (up to 20):")
            for tld, count in list(top_tlds.items())[:20]:
                logger.info("  .%-10s %d", tld, count)

        # Duplicates
        logger.info("Duplicate URLs:   %d", report.get("duplicate_count", 0))
        logger.info("=" * 60)
