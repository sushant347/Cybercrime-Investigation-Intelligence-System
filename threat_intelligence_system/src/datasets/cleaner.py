"""
Dataset cleaning module for the Phishing URL Detection Engine.

Provides the ``DatasetCleaner`` class which applies a deterministic
sequence of cleaning steps to a DataFrame with ``['url', 'label']``
columns, producing a sanitised copy ready for validation and merging.

Cleaning pipeline
-----------------
1. Drop rows with null / empty URLs.
2. Strip leading and trailing whitespace from URLs.
3. Normalise URLs via ``helpers.normalize_url``.
4. Coerce the ``label`` column to ``int`` (0 or 1).
5. Drop rows whose URL is still empty after normalisation.
6. Remove URLs that are extremely short (< 8 chars) or long (> 2 048 chars).
"""

from __future__ import annotations

import pandas as pd

from src.config.settings import get_settings
from src.utils.logger import get_logger
from src.utils.exceptions import DatasetError
from src.utils.helpers import normalize_url

logger = get_logger(__name__)

# Length boundaries -- chosen to filter obvious garbage while retaining
# all realistic URLs.
_MIN_URL_LENGTH: int = 8
_MAX_URL_LENGTH: int = 2048


class DatasetCleaner:
    """Apply cleaning transformations to a URL dataset.

    All operations are **non-destructive** -- a new DataFrame is returned
    and the original is never modified.

    Attributes:
        min_url_length: Minimum URL length to keep (inclusive).
        max_url_length: Maximum URL length to keep (inclusive).
    """

    def __init__(
        self,
        min_url_length: int = _MIN_URL_LENGTH,
        max_url_length: int = _MAX_URL_LENGTH,
    ) -> None:
        """Initialise the cleaner.

        Args:
            min_url_length: Minimum acceptable URL length.  Defaults to 8.
            max_url_length: Maximum acceptable URL length.  Defaults to 2048.
        """
        self.min_url_length = min_url_length
        self.max_url_length = max_url_length
        self._settings = get_settings()
        
        # Load official domains registry for label noise correction
        try:
            self._official_registered_domains = []
            for brand, domains in self._settings.threat.official_domains.items():
                self._official_registered_domains.extend(domains)
        except Exception as e:
            logger.warning("Failed to load official domains in DatasetCleaner: %s", e)
            self._official_registered_domains = []

        logger.info(
            "DatasetCleaner initialised - length bounds [%d, %d]",
            self.min_url_length,
            self.max_url_length,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run the full cleaning pipeline on *df*.

        Args:
            df: Input DataFrame with at least ``['url', 'label']`` columns.

        Returns:
            Cleaned ``pd.DataFrame`` with columns ``['url', 'label']`` and
            a reset integer index.

        Raises:
            DatasetError: If the input DataFrame is missing required
                columns.
        """
        self._validate_input(df)

        initial_count: int = len(df)
        df = df[["url", "label"]].copy()

        logger.info("Cleaning started - %d rows", initial_count)

        # Step 1: Drop null / empty URLs
        df = self._drop_null_urls(df)

        # Step 2: Strip whitespace
        df["url"] = df["url"].str.strip()

        # Step 2b: Drop URLs containing control characters or raw quotes.
        # RFC 3986 requires these to be percent-encoded; raw occurrences
        # indicate malformed data and break CSV round-tripping.
        df = df[~df["url"].str.contains(r'[\x00-\x1f"\\]', regex=True, na=False)]

        # Step 3: Normalise URLs
        df = self._normalise_urls(df)

        # Step 4: Coerce label to int
        df = self._coerce_labels(df)

        # Step 5: Drop rows where URL is empty after normalisation
        df = self._drop_empty_after_normalisation(df)

        # Step 6: Length filtering
        df = self._filter_by_length(df)

        # Step 7: Correct labels for official domains to prevent dataset label noise
        df = self._correct_official_domain_labels(df)

        final_count: int = len(df)
        removed_total = initial_count - final_count
        logger.info(
            "Cleaning complete - kept %d / %d rows (removed %d, %.1f%%)",
            final_count,
            initial_count,
            removed_total,
            (removed_total / initial_count * 100) if initial_count else 0.0,
        )

        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_input(df: pd.DataFrame) -> None:
        """Ensure the DataFrame contains the required columns.

        Args:
            df: DataFrame to check.

        Raises:
            DatasetError: If ``url`` or ``label`` is missing.
        """
        missing = {"url", "label"} - set(df.columns)
        if missing:
            raise DatasetError(
                dataset="unknown",
                operation="clean",
                reason=f"Missing required columns: {missing}",
            )

    @staticmethod
    def _drop_null_urls(df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows where the URL is null or an empty string.

        Args:
            df: DataFrame with a ``url`` column.

        Returns:
            Filtered DataFrame.
        """
        before = len(df)
        df = df.dropna(subset=["url"])
        df = df[df["url"].astype(str).str.strip().ne("")]
        removed = before - len(df)
        if removed:
            logger.info("Dropped %d rows with null/empty URLs", removed)
        return df

    @staticmethod
    def _normalise_urls(df: pd.DataFrame) -> pd.DataFrame:
        """Apply ``normalize_url`` to every row.

        Rows that raise exceptions during normalisation have their URL
        replaced with an empty string so they can be filtered downstream.

        Args:
            df: DataFrame with a ``url`` column.

        Returns:
            DataFrame with normalised URLs.
        """
        import re
        import hashlib

        def _prepend_scheme_if_missing(url: str) -> str:
            url_str = str(url).strip()
            if not url_str:
                return ""
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", url_str):
                # Deterministic pseudo-random number from URL hash
                h = int(hashlib.md5(url_str.encode("utf-8")).hexdigest(), 16)
                r = (h % 100) / 100.0
                if r < 0.70:
                    prefix = "https://www."
                elif r < 0.90:
                    prefix = "https://"
                elif r < 0.95:
                    prefix = "http://www."
                else:
                    prefix = "http://"
                
                # Strip leading www. if present to avoid duplication
                if url_str.lower().startswith("www."):
                    url_str = url_str[4:]
                return prefix + url_str
            return url_str

        def _safe_normalize(url: str) -> str:
            """Wrapper that never raises."""
            try:
                prefixed = _prepend_scheme_if_missing(str(url))
                return normalize_url(prefixed)
            except Exception:
                return ""

        df["url"] = df["url"].apply(_safe_normalize)
        logger.debug("URL normalisation applied")
        return df

    @staticmethod
    def _coerce_labels(df: pd.DataFrame) -> pd.DataFrame:
        """Coerce the label column to integer (0 or 1).

        Non-numeric values and values outside {0, 1} are dropped.

        Args:
            df: DataFrame with a ``label`` column.

        Returns:
            DataFrame with integer labels.
        """
        before = len(df)
        df["label"] = pd.to_numeric(df["label"], errors="coerce")
        df = df.dropna(subset=["label"])
        df["label"] = df["label"].astype(int)
        # Keep only valid binary labels
        df = df[df["label"].isin([0, 1])]
        removed = before - len(df)
        if removed:
            logger.info("Dropped %d rows with invalid labels", removed)
        return df

    @staticmethod
    def _drop_empty_after_normalisation(df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows whose URL is empty after normalisation.

        Args:
            df: DataFrame with a ``url`` column.

        Returns:
            Filtered DataFrame.
        """
        before = len(df)
        df = df[df["url"].astype(str).str.strip().ne("")]
        removed = before - len(df)
        if removed:
            logger.info(
                "Dropped %d rows with empty URLs after normalisation",
                removed,
            )
        return df

    def _filter_by_length(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove URLs shorter than *min_url_length* or longer than *max_url_length*.

        Args:
            df: DataFrame with a ``url`` column.

        Returns:
            Filtered DataFrame.
        """
        url_lengths = df["url"].str.len()
        before = len(df)

        too_short = url_lengths < self.min_url_length
        too_long = url_lengths > self.max_url_length

        short_count = int(too_short.sum())
        long_count = int(too_long.sum())

        df = df[~too_short & ~too_long]

        if short_count:
            logger.info(
                "Dropped %d URLs shorter than %d characters",
                short_count,
                self.min_url_length,
            )
        if long_count:
            logger.info(
                "Dropped %d URLs longer than %d characters",
                long_count,
                self.max_url_length,
            )

        return df

    def _correct_official_domain_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Correct labels for official registered domains to prevent label noise.

        Args:
            df: DataFrame with URL and label columns.

        Returns:
            DataFrame with corrected labels.
        """
        if not self._official_registered_domains:
            return df
            
        import tldextract
        
        # User content subdomains where phishing forms can actually be hosted
        USER_CONTENT_SUBDOMAINS = {
            "docs.google.com", "drive.google.com", "sites.google.com", 
            "groups.google.com", "github.io", "githubusercontent.com",
            "pages.github.com"
        }
        
        corrected_count = 0
        
        urls = df["url"].tolist()
        labels = df["label"].tolist()
        new_labels = []
        
        for url, label in zip(urls, labels):
            new_label = label
            if label == 1:
                try:
                    ext = tldextract.extract(str(url))
                    reg_domain = ext.registered_domain.lower()
                    
                    if reg_domain in self._official_registered_domains:
                        hostname = ".".join(filter(None, [ext.subdomain, ext.domain, ext.suffix])).lower()
                        # Avoid correcting subdomains that host user content
                        if hostname not in USER_CONTENT_SUBDOMAINS and not any(sub in hostname for sub in ["docs.google.", "drive.google.", "sites.google."]):
                            new_label = 0
                            corrected_count += 1
                except Exception:
                    pass
            new_labels.append(new_label)
            
        if corrected_count > 0:
            logger.info("Corrected label of %d official domain URLs from Phishing (1) to Legitimate (0)", corrected_count)
            df["label"] = new_labels
            
        return df
