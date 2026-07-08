"""
Dataset validation module for the Phishing URL Detection Engine.

Provides the ``DatasetValidator`` class which partitions a DataFrame into
*valid* and *invalid* subsets according to structural URL checks and label
constraints.

Validation rules
----------------
1. URL must start with ``http://`` or ``https://``.
2. URL must contain at least one dot (``domain.tld``).
3. Label must be 0 or 1.
4. URL must **not** be purely numeric (after stripping the scheme).
"""

from __future__ import annotations

import re

import pandas as pd

from src.utils.logger import get_logger
from src.utils.exceptions import DatasetError

logger = get_logger(__name__)

# Pre-compiled patterns for performance
_SCHEME_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
_NUMERIC_ONLY_PATTERN = re.compile(r"^https?://[\d./:]+$", re.IGNORECASE)


class DatasetValidator:
    """Validate URL dataset rows and separate valid from invalid entries.

    Each row is tested against every rule independently.  A row must
    pass **all** rules to be placed in the *valid* partition; otherwise
    it goes into the *invalid* partition.

    Usage::

        validator = DatasetValidator()
        valid_df, invalid_df = validator.validate(cleaned_df)
    """

    def __init__(self) -> None:
        """Initialise the validator."""
        logger.info("DatasetValidator initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Partition *df* into valid and invalid subsets.

        Args:
            df: DataFrame with columns ``['url', 'label']``.

        Returns:
            A tuple ``(valid_df, invalid_df)`` where both DataFrames
            share the same schema as the input.

        Raises:
            DatasetError: If the input is missing required columns.
        """
        self._validate_input(df)

        if df.empty:
            logger.warning("Received empty DataFrame - nothing to validate")
            empty = pd.DataFrame(columns=["url", "label"])
            return empty.copy(), empty.copy()

        total = len(df)
        logger.info("Validation started - %d rows", total)

        # Build a boolean mask for each rule
        has_scheme = df["url"].apply(self._check_scheme)
        has_dot = df["url"].str.contains(".", regex=False)
        valid_label = df["label"].isin([0, 1])
        not_numeric = ~df["url"].apply(self._check_numeric_only)

        # Combine masks
        all_valid = has_scheme & has_dot & valid_label & not_numeric

        valid_df = df.loc[all_valid].reset_index(drop=True)
        invalid_df = df.loc[~all_valid].reset_index(drop=True)

        # Detailed per-rule failure logging
        self._log_rule_stats("scheme (http/https)", ~has_scheme, total)
        self._log_rule_stats("contains dot", ~has_dot, total)
        self._log_rule_stats("valid label (0/1)", ~valid_label, total)
        self._log_rule_stats("not purely numeric", df["url"].apply(self._check_numeric_only), total)

        valid_count = len(valid_df)
        invalid_count = len(invalid_df)
        valid_pct = (valid_count / total * 100) if total else 0.0
        invalid_pct = (invalid_count / total * 100) if total else 0.0

        logger.info(
            "Validation complete - total=%d  valid=%d (%.1f%%)  "
            "invalid=%d (%.1f%%)",
            total,
            valid_count,
            valid_pct,
            invalid_count,
            invalid_pct,
        )

        return valid_df, invalid_df

    # ------------------------------------------------------------------
    # Rule checkers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_scheme(url: str) -> bool:
        """Return *True* if the URL starts with ``http://`` or ``https://``.

        Args:
            url: URL string to check.

        Returns:
            Boolean indicating whether the scheme is valid.
        """
        try:
            return bool(_SCHEME_PATTERN.match(str(url)))
        except Exception:
            return False

    @staticmethod
    def _check_numeric_only(url: str) -> bool:
        """Return *True* if the URL (after scheme) is purely numeric / dots / slashes.

        This catches garbage entries like ``http://12345`` that are not
        real domains.

        Args:
            url: URL string to check.

        Returns:
            Boolean -- *True* means the URL **is** purely numeric.
        """
        try:
            return bool(_NUMERIC_ONLY_PATTERN.match(str(url)))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_input(df: pd.DataFrame) -> None:
        """Ensure required columns are present.

        Args:
            df: DataFrame to check.

        Raises:
            DatasetError: On missing columns.
        """
        missing = {"url", "label"} - set(df.columns)
        if missing:
            raise DatasetError(
                dataset="unknown",
                operation="validate",
                reason=f"Missing required columns: {missing}",
            )

    @staticmethod
    def _log_rule_stats(
        rule_name: str,
        failure_mask: pd.Series,
        total: int,
    ) -> None:
        """Log the number of rows failing a specific rule.

        Args:
            rule_name: Human-readable name of the rule.
            failure_mask: Boolean Series where *True* = failure.
            total: Total number of rows evaluated.
        """
        failed = int(failure_mask.sum())
        if failed:
            pct = (failed / total * 100) if total else 0.0
            logger.info(
                "  Rule '%s': %d failures (%.1f%%)",
                rule_name,
                failed,
                pct,
            )
