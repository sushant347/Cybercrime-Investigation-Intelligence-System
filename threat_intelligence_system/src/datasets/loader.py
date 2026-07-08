"""
Dataset loading module for the Phishing URL Detection Engine.

Provides the ``DatasetLoader`` class which reads each raw data source into
a standardised ``pandas.DataFrame`` with exactly two columns: ``url`` and
``label`` (0 = legitimate, 1 = phishing / malicious).

Supported sources
-----------------
* PhiUSIIL_Phishing_URL_Dataset.csv
* malicious_phish.csv
* PhishTank_2026.csv
* open_phish.txt
* tranco_64W6X.csv  (Tranco top-sites list)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.config.settings import get_settings
from src.utils.logger import get_logger
from src.utils.exceptions import DatasetError

logger = get_logger(__name__)


class DatasetLoader:
    """Load raw phishing / legitimate URL datasets into normalised DataFrames.

    Each public ``load_*`` method returns a ``pd.DataFrame`` with columns
    ``['url', 'label']``.  The class reads file paths and sampling
    parameters from the central ``Settings`` object so that no hard-coded
    paths leak into calling code.

    Attributes:
        raw_dir: Resolved path to the directory containing raw data files.
        settings: Application-wide settings singleton.
    """

    def __init__(self, raw_dir: Path | None = None) -> None:
        """Initialise the loader.

        Args:
            raw_dir: Override for the raw-data directory.  When *None* the
                value is read from ``settings.paths.raw_data_dir``.
        """
        self.settings = get_settings()
        self.raw_dir: Path = Path(raw_dir) if raw_dir else self.settings.paths.raw_data_dir
        logger.info("DatasetLoader initialised - raw_dir=%s", self.raw_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, filename: str) -> Path:
        """Resolve *filename* relative to ``self.raw_dir``.

        Args:
            filename: Basename of the file inside the raw-data directory.

        Returns:
            Fully-resolved ``Path`` object.

        Raises:
            DatasetError: If the resolved path does not exist.
        """
        path = self.raw_dir / filename
        if not path.exists():
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=f"File not found: {path}",
            )
        return path

    @staticmethod
    def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the DataFrame has exactly ``['url', 'label']`` columns.

        Args:
            df: DataFrame that must already contain these two columns.

        Returns:
            DataFrame with only ``['url', 'label']`` in that order.
        """
        return df[["url", "label"]].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Public loaders
    # ------------------------------------------------------------------

    def load_phiusiil(self) -> pd.DataFrame:
        """Load the PhiUSIIL Phishing URL Dataset.

        The CSV contains a ``URL`` column and a ``label`` column
        (0 = legitimate, 1 = phishing) plus ~56 pre-computed feature
        columns which are discarded here.

        Returns:
            DataFrame with columns ``['url', 'label']``.

        Raises:
            DatasetError: If the file cannot be read or expected columns
                are missing.
        """
        filename = self.settings.dataset.phiusiil_filename
        path = self._resolve_path(filename)

        try:
            df = pd.read_csv(
                path,
                encoding="utf-8",
                encoding_errors="replace",
                low_memory=False,
            )
        except Exception as exc:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=str(exc),
            ) from exc

        # Normalise column names to lowercase
        df.columns = df.columns.str.strip().str.lower()

        if "url" not in df.columns or "label" not in df.columns:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=(
                    f"Expected columns 'url' and 'label', "
                    f"found: {list(df.columns)}"
                ),
            )

        df = df[["url", "label"]].copy()
        logger.info(
            "Loaded %s - %d rows  (phishing=%d, legit=%d)",
            filename,
            len(df),
            int((df["label"] == 1).sum()),
            int((df["label"] == 0).sum()),
        )
        return self._standardise_columns(df)

    def load_malicious_phish(self) -> pd.DataFrame:
        """Load the *malicious_phish* dataset.

        Columns: ``url``, ``type``.  Type values are mapped to binary
        labels: ``benign`` -> 0, everything else (``phishing``,
        ``defacement``, ``malware``) -> 1.

        Returns:
            DataFrame with columns ``['url', 'label']``.

        Raises:
            DatasetError: On I/O or schema errors.
        """
        filename = self.settings.dataset.malicious_phish_filename
        path = self._resolve_path(filename)

        try:
            df = pd.read_csv(
                path,
                encoding="utf-8",
                encoding_errors="replace",
                low_memory=False,
            )
        except Exception as exc:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=str(exc),
            ) from exc

        df.columns = df.columns.str.strip().str.lower()

        if "url" not in df.columns or "type" not in df.columns:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=(
                    f"Expected columns 'url' and 'type', "
                    f"found: {list(df.columns)}"
                ),
            )

        # Map type -> binary label
        df["label"] = df["type"].str.strip().str.lower().map(
            lambda t: 0 if t == "benign" else 1
        )
        df = df[["url", "label"]].copy()

        logger.info(
            "Loaded %s - %d rows  (malicious=%d, benign=%d)",
            filename,
            len(df),
            int((df["label"] == 1).sum()),
            int((df["label"] == 0).sum()),
        )
        return self._standardise_columns(df)

    def load_phishtank(self) -> pd.DataFrame:
        """Load the PhishTank dataset.

        Columns: ``URL``, ``Label``.  All rows are phishing (label = 1).

        Returns:
            DataFrame with columns ``['url', 'label']``.

        Raises:
            DatasetError: On I/O or schema errors.
        """
        filename = self.settings.dataset.phishtank_filename
        path = self._resolve_path(filename)

        try:
            df = pd.read_csv(
                path,
                encoding="utf-8",
                encoding_errors="replace",
                low_memory=False,
            )
        except Exception as exc:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=str(exc),
            ) from exc

        df.columns = df.columns.str.strip().str.lower()

        if "url" not in df.columns:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=(
                    f"Expected column 'url', found: {list(df.columns)}"
                ),
            )

        # Ensure label column exists and is 1
        if "label" in df.columns:
            df["label"] = df["label"].fillna(1).astype(int)
        else:
            df["label"] = 1

        df = df[["url", "label"]].copy()
        logger.info("Loaded %s - %d rows (all phishing)", filename, len(df))
        return self._standardise_columns(df)

    def load_openphish(self) -> pd.DataFrame:
        """Load the OpenPhish feed (plain-text, one URL per line).

        Every URL is labelled as phishing (label = 1).

        Returns:
            DataFrame with columns ``['url', 'label']``.

        Raises:
            DatasetError: On I/O errors.
        """
        filename = self.settings.dataset.openphish_filename
        path = self._resolve_path(filename)

        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                urls = [
                    line.strip()
                    for line in fh
                    if line.strip()
                ]
        except Exception as exc:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=str(exc),
            ) from exc

        df = pd.DataFrame({"url": urls, "label": 1})
        logger.info("Loaded %s - %d URLs (all phishing)", filename, len(df))
        return self._standardise_columns(df)

    def load_tranco(self, sample_size: int | None = None) -> pd.DataFrame:
        """Load the Tranco top-sites list.

        The CSV has **no header** and two positional columns: ``rank``
        (integer) and ``domain`` (string).  Domains lack a protocol, so
        ``http://`` is prepended before they are stored.  All entries are
        marked legitimate (label = 0).

        Args:
            sample_size: Number of rows to sample.  When *None* the value
                from ``settings.dataset.tranco_sample_size`` is used.
                Pass ``0`` or a negative value to skip sampling.

        Returns:
            DataFrame with columns ``['url', 'label']``.

        Raises:
            DatasetError: On I/O errors.
        """
        filename = self.settings.dataset.tranco_filename
        path = self._resolve_path(filename)

        if sample_size is None:
            sample_size = self.settings.dataset.tranco_sample_size

        try:
            df = pd.read_csv(
                path,
                header=None,
                names=["rank", "domain"],
                encoding="utf-8",
                encoding_errors="replace",
                low_memory=False,
            )
        except Exception as exc:
            raise DatasetError(
                dataset=filename,
                operation="load",
                reason=str(exc),
            ) from exc

        # Prepend scheme (using a mixture representing real-world HTTPS and WWW prevalence)
        import numpy as np
        np.random.seed(self.settings.dataset.random_seed)
        rands = np.random.rand(len(df))
        
        urls = []
        for domain, r in zip(df["domain"].astype(str).str.strip(), rands):
            if r < 0.70:
                urls.append("https://www." + domain)
            elif r < 0.90:
                urls.append("https://" + domain)
            elif r < 0.95:
                urls.append("http://www." + domain)
            else:
                urls.append("http://" + domain)
                
        df["url"] = urls
        df["label"] = 0

        # Sample if requested
        if sample_size and sample_size > 0 and sample_size < len(df):
            df = df.sample(
                n=sample_size,
                random_state=self.settings.dataset.random_seed,
            )
            logger.info(
                "Sampled %d rows from %s (total available: %d)",
                sample_size,
                filename,
                len(df) + (len(df) - sample_size),  # approximate, logged before sample
            )

        df = df[["url", "label"]].copy()
        logger.info(
            "Loaded %s - %d rows (all legitimate)",
            filename,
            len(df),
        )
        return self._standardise_columns(df)

    # ------------------------------------------------------------------
    # Aggregate loader
    # ------------------------------------------------------------------

    def load_all(self) -> dict[str, pd.DataFrame]:
        """Load every available dataset and return them keyed by name.

        The returned dictionary maps human-readable dataset names to their
        respective DataFrames.  If an individual dataset fails to load a
        ``DatasetError`` is logged and the dataset is skipped rather than
        aborting the entire pipeline.

        Returns:
            Dictionary mapping dataset names to DataFrames.
        """
        loaders: dict[str, Any] = {
            "phiusiil": self.load_phiusiil,
            "malicious_phish": self.load_malicious_phish,
            "phishtank": self.load_phishtank,
            "openphish": self.load_openphish,
            "tranco": self.load_tranco,
        }

        datasets: dict[str, pd.DataFrame] = {}
        for name, loader_fn in loaders.items():
            try:
                datasets[name] = loader_fn()
            except DatasetError as exc:
                logger.error("Failed to load '%s': %s", name, exc)

        logger.info(
            "load_all complete - %d/%d datasets loaded successfully",
            len(datasets),
            len(loaders),
        )
        return datasets
