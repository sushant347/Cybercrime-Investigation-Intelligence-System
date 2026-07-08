"""
Dataset merging and splitting module for the Phishing URL Detection Engine.

Provides the ``DatasetMerger`` class which:

* Concatenates multiple cleaned/validated DataFrames.
* Deduplicates by normalised URL.
* Performs stratified train / validation / test splitting.
* Persists the splits as CSV files.
* Exposes a one-call ``run_pipeline`` that chains every processing stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

from src.config.settings import get_settings
from src.utils.logger import get_logger
from src.utils.exceptions import DatasetError
from src.datasets.loader import DatasetLoader
from src.datasets.cleaner import DatasetCleaner
from src.datasets.validator import DatasetValidator

logger = get_logger(__name__)


class DatasetMerger:
    """Merge, deduplicate, split and persist URL datasets.

    The class reads splitting ratios and the random seed from the
    central ``Settings`` object.

    Attributes:
        settings: Application-wide settings singleton.
    """

    def __init__(self) -> None:
        """Initialise the merger."""
        self.settings = get_settings()
        logger.info(
            "DatasetMerger initialised - ratios train=%.2f, val=%.2f, "
            "test=%.2f, seed=%d",
            self.settings.dataset.train_ratio,
            self.settings.dataset.validation_ratio,
            self.settings.dataset.test_ratio,
            self.settings.dataset.random_seed,
        )

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge(self, datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Concatenate and deduplicate multiple URL DataFrames.

        Args:
            datasets: Dictionary mapping dataset names to DataFrames.
                Each DataFrame must have ``['url', 'label']`` columns.

        Returns:
            A single, deduplicated, shuffled DataFrame.

        Raises:
            DatasetError: If *datasets* is empty or contains no rows.
        """
        if not datasets:
            raise DatasetError(
                dataset="all",
                operation="merge",
                reason="No datasets provided for merging",
            )

        frames: list[pd.DataFrame] = []
        for name, df in datasets.items():
            if df.empty:
                logger.warning("Dataset '%s' is empty - skipping", name)
                continue
            frames.append(df[["url", "label"]])
            logger.info("Queued '%s' for merge - %d rows", name, len(df))

        if not frames:
            raise DatasetError(
                dataset="all",
                operation="merge",
                reason="All provided datasets are empty",
            )

        merged = pd.concat(frames, ignore_index=True)
        total_before = len(merged)
        logger.info("Total rows before deduplication: %d", total_before)

        # Deduplicate on normalised URL, keeping first occurrence
        merged = merged.drop_duplicates(subset=["url"], keep="first")
        total_after = len(merged)
        duplicates_removed = total_before - total_after

        logger.info(
            "Total rows after deduplication: %d  (removed %d duplicates)",
            total_after,
            duplicates_removed,
        )

        # Shuffle
        merged = merged.sample(
            frac=1.0,
            random_state=self.settings.dataset.random_seed,
        ).reset_index(drop=True)

        logger.info(
            "Merged dataset label distribution: %s",
            merged["label"].value_counts().to_dict(),
        )

        return merged

    # ------------------------------------------------------------------
    # Split
    # ------------------------------------------------------------------

    def split(
        self,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Stratified split into train / validation / test sets.

        Uses ``sklearn.model_selection.train_test_split`` twice:
        first to carve out the test set, then to separate train and
        validation from the remainder.

        Args:
            df: Merged DataFrame with ``['url', 'label']``.

        Returns:
            A tuple ``(train_df, val_df, test_df)``.

        Raises:
            DatasetError: If the DataFrame is too small to split or has
                a single class.
        """
        if df.empty:
            raise DatasetError(
                dataset="merged",
                operation="split",
                reason="Cannot split an empty DataFrame",
            )

        unique_labels = df["label"].nunique()
        if unique_labels < 2:
            raise DatasetError(
                dataset="merged",
                operation="split",
                reason=(
                    f"Stratified split requires at least 2 classes, "
                    f"found {unique_labels}"
                ),
            )

        seed = self.settings.dataset.random_seed
        train_ratio = self.settings.dataset.train_ratio
        val_ratio = self.settings.dataset.validation_ratio
        test_ratio = self.settings.dataset.test_ratio

        # First split: separate test set
        train_val_df, test_df = train_test_split(
            df,
            test_size=test_ratio,
            random_state=seed,
            stratify=df["label"],
        )

        # Second split: separate validation from training
        # val_ratio relative to train+val portion
        relative_val_ratio = val_ratio / (train_ratio + val_ratio)
        train_df, val_df = train_test_split(
            train_val_df,
            test_size=relative_val_ratio,
            random_state=seed,
            stratify=train_val_df["label"],
        )

        # Reset indices
        train_df = train_df.reset_index(drop=True)
        val_df = val_df.reset_index(drop=True)
        test_df = test_df.reset_index(drop=True)

        # Log sizes and distributions
        for name, split_df in [
            ("train", train_df),
            ("validation", val_df),
            ("test", test_df),
        ]:
            dist = split_df["label"].value_counts().to_dict()
            total = len(split_df)
            phishing_pct = (
                (dist.get(1, 0) / total * 100) if total else 0.0
            )
            logger.info(
                "Split '%s': %d rows - label distribution %s "
                "(phishing %.1f%%)",
                name,
                total,
                dist,
                phishing_pct,
            )

        return train_df, val_df, test_df

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_splits(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
        output_dir: Path | None = None,
    ) -> None:
        """Save train / validation / test DataFrames as CSV files.

        Args:
            train_df: Training split.
            val_df: Validation split.
            test_df: Test split.
            output_dir: Directory to write into.  Defaults to
                ``settings.paths.processed_data_dir``.
        """
        if output_dir is None:
            output_dir = self.settings.paths.processed_data_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        file_map: dict[str, pd.DataFrame] = {
            "train.csv": train_df,
            "validation.csv": val_df,
            "test.csv": test_df,
        }

        for filename, df in file_map.items():
            path = output_dir / filename
            df.to_csv(path, index=False, encoding="utf-8")
            logger.info("Saved %s - %d rows -> %s", filename, len(df), path)

    # ------------------------------------------------------------------
    # End-to-end pipeline
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Execute the complete dataset preparation pipeline.

        Stages
        ------
        1. **Load** all raw datasets via ``DatasetLoader.load_all``.
        2. **Clean** each dataset via ``DatasetCleaner.clean``.
        3. **Validate** each dataset via ``DatasetValidator.validate``
           (invalid rows are discarded with a warning).
        4. **Merge** all valid datasets into one DataFrame.
        5. **Split** into train / validation / test.
        6. **Save** splits to disk.

        Returns:
            Tuple ``(train_df, val_df, test_df)``.

        Raises:
            DatasetError: If no data survives the pipeline.
        """
        logger.info("=" * 60)
        logger.info("DATASET PIPELINE - START")
        logger.info("=" * 60)

        # 1. Load
        loader = DatasetLoader()
        raw_datasets = loader.load_all()

        if not raw_datasets:
            raise DatasetError(
                dataset="all",
                operation="pipeline",
                reason="No datasets could be loaded",
            )

        # 2. Clean
        cleaner = DatasetCleaner()
        cleaned_datasets: dict[str, pd.DataFrame] = {}
        for name, df in raw_datasets.items():
            try:
                cleaned = cleaner.clean(df)
                cleaned_datasets[name] = cleaned
                logger.info(
                    "Cleaned '%s': %d -> %d rows",
                    name,
                    len(df),
                    len(cleaned),
                )
            except DatasetError as exc:
                logger.error("Cleaning failed for '%s': %s", name, exc)

        # 3. Validate
        validator = DatasetValidator()
        valid_datasets: dict[str, pd.DataFrame] = {}
        for name, df in cleaned_datasets.items():
            valid_df, invalid_df = validator.validate(df)
            if not invalid_df.empty:
                logger.warning(
                    "Validation for '%s': %d invalid rows discarded",
                    name,
                    len(invalid_df),
                )
            if not valid_df.empty:
                valid_datasets[name] = valid_df

        if not valid_datasets:
            raise DatasetError(
                dataset="all",
                operation="pipeline",
                reason="No valid data remains after cleaning and validation",
            )

        # 4. Merge
        merged_df = self.merge(valid_datasets)

        # 5. Split
        train_df, val_df, test_df = self.split(merged_df)

        # 6. Save
        self.save_splits(train_df, val_df, test_df)

        logger.info("=" * 60)
        logger.info("DATASET PIPELINE - COMPLETE")
        logger.info("=" * 60)

        return train_df, val_df, test_df
