"""
Tests for the automatic dataset discovery engine and the full retraining
pipeline's dataset preparation stage.

Covers:
    * Dataset file discovery across formats (CSV, TSV, TXT, JSON, JSONL, XLSX)
    * Automatic URL column detection
    * Automatic label column detection and label normalisation
    * Mixed, phishing-only and legitimate-only datasets
    * Skipping of non-URL datasets (e.g. e-mail metadata)
    * Merging of multiple datasets with conflict removal
    * Configurable dataset path
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.datasets.discovery import (
    DatasetDiscovery,
    DatasetProfile,
    LABEL_VALUE_MAP,
    SUPPORTED_EXTENSIONS,
)
from src.utils.exceptions import DatasetError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHISH_URLS = [f"http://phish-{i}.bad-domain.xyz/login" for i in range(10)]
LEGIT_URLS = [f"https://www.legit-site-{i}.com/about" for i in range(10)]


@pytest.fixture()
def dataset_dir(tmp_path: Path) -> Path:
    """Empty temporary dataset directory."""
    return tmp_path


def _make_csv(path: Path, df: pd.DataFrame, **kwargs) -> Path:
    df.to_csv(path, index=False, **kwargs)
    return path


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverFiles:
    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        discovery = DatasetDiscovery(tmp_path / "does-not-exist")
        with pytest.raises(DatasetError):
            discovery.discover_files()

    def test_only_supported_extensions(self, dataset_dir: Path) -> None:
        (dataset_dir / "a.csv").write_text("url,label\nhttp://x.com,0\n")
        (dataset_dir / "b.parquet").write_bytes(b"xx")
        (dataset_dir / "notes.docx").write_bytes(b"xx")
        files = DatasetDiscovery(dataset_dir).discover_files()
        assert [f.name for f in files] == ["a.csv"]

    def test_supported_extension_set(self) -> None:
        assert {".csv", ".tsv", ".txt", ".json", ".jsonl", ".xlsx"} <= set(
            SUPPORTED_EXTENSIONS
        )


class TestMultipleFormats:
    def test_csv_tsv_txt_json_jsonl(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "mixed.csv", pd.DataFrame({
            "url": PHISH_URLS + LEGIT_URLS,
            "label": [1] * 10 + [0] * 10,
        }))
        pd.DataFrame({"URL": PHISH_URLS, "Label": [1] * 10}).to_csv(
            dataset_dir / "phish.tsv", sep="\t", index=False
        )
        (dataset_dir / "openphish_feed.txt").write_text(
            "\n".join(PHISH_URLS), encoding="utf-8"
        )
        (dataset_dir / "records.json").write_text(json.dumps([
            {"url": u, "label": "phishing"} for u in PHISH_URLS
        ] + [
            {"url": u, "label": "legitimate"} for u in LEGIT_URLS
        ]), encoding="utf-8")
        with open(dataset_dir / "feed.jsonl", "w", encoding="utf-8") as fh:
            for u in LEGIT_URLS:
                fh.write(json.dumps({"link": u, "class": "benign"}) + "\n")

        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert len(datasets) == 5
        for df in datasets.values():
            assert list(df.columns) == ["url", "label"]
            assert set(df["label"].unique()) <= {0, 1}

    def test_excel(self, dataset_dir: Path) -> None:
        pytest.importorskip("openpyxl")
        pd.DataFrame({
            "website": PHISH_URLS + LEGIT_URLS,
            "is_phishing": [True] * 10 + [False] * 10,
        }).to_excel(dataset_dir / "data.xlsx", index=False)
        datasets, _ = DatasetDiscovery(dataset_dir).load_all()
        df = datasets["data"]
        assert int(df["label"].sum()) == 10
        assert len(df) == 20


# ---------------------------------------------------------------------------
# Label detection & normalisation
# ---------------------------------------------------------------------------

class TestLabelDetection:
    @pytest.mark.parametrize("phish_token,legit_token", [
        ("1", "0"),
        ("true", "false"),
        ("Phishing", "Safe"),
        ("Phishing", "Legitimate"),
        ("malicious", "benign"),
        ("bad", "good"),
        ("fraud", "normal"),
        ("suspicious", "clean"),
    ])
    def test_binary_vocabularies(
        self, dataset_dir: Path, phish_token: str, legit_token: str
    ) -> None:
        _make_csv(dataset_dir / "d.csv", pd.DataFrame({
            "url": PHISH_URLS + LEGIT_URLS,
            "label": [phish_token] * 10 + [legit_token] * 10,
        }))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        df = datasets["d"]
        assert int((df["label"] == 1).sum()) == 10
        assert int((df["label"] == 0).sum()) == 10
        assert profiles[0].label_mode == "mixed"

    def test_nonstandard_label_column_name(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "d.csv", pd.DataFrame({
            "URL": PHISH_URLS + LEGIT_URLS,
            "Verdict": ["Phishing"] * 10 + ["Legitimate"] * 10,
        }))
        datasets, _ = DatasetDiscovery(dataset_dir).load_all()
        assert int(datasets["d"]["label"].sum()) == 10

    def test_binary_feature_flags_not_mistaken_for_labels(
        self, dataset_dir: Path
    ) -> None:
        """Numeric 0/1 feature columns must never be selected over 'label'."""
        _make_csv(dataset_dir / "features.csv", pd.DataFrame({
            "url": PHISH_URLS + LEGIT_URLS,
            "label": [1] * 10 + [0] * 10,
            "has_ip": [0] * 20,
            "is_https": [1] * 20,
        }))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert profiles[0].label_column == "label"
        assert int(datasets["features"]["label"].sum()) == 10

    def test_unmapped_labels_dropped(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "d.csv", pd.DataFrame({
            "url": PHISH_URLS + LEGIT_URLS[:5],
            "label": ["phishing"] * 10 + ["weird-token"] * 5,
        }))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert len(datasets["d"]) == 10
        assert profiles[0].unmapped_labels == 5

    def test_label_map_covers_required_vocab(self) -> None:
        for token, expected in [
            ("safe", 0), ("phishing", 1), ("legitimate", 0), ("benign", 0),
            ("malicious", 1), ("good", 0), ("bad", 1), ("normal", 0),
            ("fraud", 1), ("clean", 0), ("suspicious", 1),
            ("true", 1), ("false", 0), ("0", 0), ("1", 1),
        ]:
            assert LABEL_VALUE_MAP[token] == expected


# ---------------------------------------------------------------------------
# Single-class and non-URL datasets
# ---------------------------------------------------------------------------

class TestSingleClassAndSkipping:
    def test_phishing_only_dataset(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "d.csv", pd.DataFrame({
            "URL": PHISH_URLS, "Label": [1] * 10,
        }))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert profiles[0].label_mode == "all_phishing"
        assert int(datasets["d"]["label"].sum()) == 10

    def test_legitimate_only_dataset(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "d.csv", pd.DataFrame({
            "url": LEGIT_URLS, "label": [0] * 10,
        }))
        _, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert profiles[0].label_mode == "all_legitimate"

    def test_txt_feed_label_from_filename(self, dataset_dir: Path) -> None:
        (dataset_dir / "openphish_feed.txt").write_text("\n".join(PHISH_URLS))
        (dataset_dir / "tranco_top.txt").write_text("\n".join(LEGIT_URLS))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        modes = {p.file_name: p.label_mode for p in profiles}
        assert modes["openphish_feed.txt"] == "all_phishing"
        assert modes["tranco_top.txt"] == "all_legitimate"

    def test_non_url_dataset_is_skipped(self, dataset_dir: Path) -> None:
        """An e-mail metadata dataset must be skipped, not mislabelled."""
        _make_csv(dataset_dir / "emails.csv", pd.DataFrame({
            "email_id": [1, 2], "subject": ["Hi", "Urgent"],
            "urgency_score": [1, 9], "is_phishing": [0, 1],
        }))
        _make_csv(dataset_dir / "urls.csv", pd.DataFrame({
            "url": PHISH_URLS + LEGIT_URLS, "label": [1] * 10 + [0] * 10,
        }))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert "emails" not in datasets
        skipped = next(p for p in profiles if p.file_name == "emails.csv")
        assert skipped.skipped_reason is not None
        assert skipped.label_mode == "skipped"

    def test_all_files_unusable_raises(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "emails.csv", pd.DataFrame({
            "email_id": [1], "subject": ["x"],
        }))
        with pytest.raises(DatasetError):
            DatasetDiscovery(dataset_dir).load_all()

    def test_unlabelled_ambiguous_file_skipped(self, dataset_dir: Path) -> None:
        (dataset_dir / "mystery.txt").write_text("\n".join(LEGIT_URLS))
        _make_csv(dataset_dir / "ok.csv", pd.DataFrame({
            "url": PHISH_URLS, "label": [1] * 10,
        }))
        datasets, profiles = DatasetDiscovery(dataset_dir).load_all()
        assert "mystery" not in datasets


# ---------------------------------------------------------------------------
# Merging via the full pipeline preparation stage
# ---------------------------------------------------------------------------

class TestDatasetMergingPipeline:
    def _write_three_datasets(self, dataset_dir: Path) -> None:
        _make_csv(dataset_dir / "mixed.csv", pd.DataFrame({
            "url": PHISH_URLS[:5] + LEGIT_URLS[:5],
            "label": [1] * 5 + [0] * 5,
        }))
        _make_csv(dataset_dir / "phish_only.csv", pd.DataFrame({
            "URL": PHISH_URLS[5:], "Label": [1] * 5,
        }))
        _make_csv(dataset_dir / "legit_only.csv", pd.DataFrame({
            "url": LEGIT_URLS[5:], "label": ["Legitimate"] * 5,
        }))

    def test_merge_multiple_datasets(self, dataset_dir: Path) -> None:
        self._write_three_datasets(dataset_dir)
        from src.training.full_retraining import FullRetrainingPipeline

        pipeline = FullRetrainingPipeline(
            dataset_dir=dataset_dir,
            processed_dir=dataset_dir / "processed",
            checkpoint_dir=dataset_dir / "checkpoints",
            results_dir=dataset_dir / "results",
            n_workers=1,
        )
        train_df, val_df, test_df, stats = pipeline.prepare_datasets()

        assert stats.files_discovered == 3
        assert stats.files_used == 3
        total = len(train_df) + len(val_df) + len(test_df)
        assert total == stats.final_rows
        assert stats.final_phishing > 0
        assert stats.final_legitimate > 0
        # Never accidentally label everything as phishing
        assert 0 < stats.final_phishing < stats.final_rows
        # Splits overwritten on disk
        assert (dataset_dir / "processed" / "train.csv").exists()
        assert (dataset_dir / "processed" / "validation.csv").exists()
        assert (dataset_dir / "processed" / "test.csv").exists()

    def test_conflicting_labels_removed(self, dataset_dir: Path) -> None:
        conflict_url = "http://conflict.example-site.com/page"
        _make_csv(dataset_dir / "a.csv", pd.DataFrame({
            "url": [conflict_url] + PHISH_URLS,
            "label": [1] * 11,
        }))
        _make_csv(dataset_dir / "b.csv", pd.DataFrame({
            "url": [conflict_url] + LEGIT_URLS,
            "label": [0] * 11,
        }))
        from src.training.full_retraining import FullRetrainingPipeline

        pipeline = FullRetrainingPipeline(
            dataset_dir=dataset_dir,
            processed_dir=dataset_dir / "processed",
            checkpoint_dir=dataset_dir / "checkpoints",
            results_dir=dataset_dir / "results",
            n_workers=1,
        )
        train_df, val_df, test_df, stats = pipeline.prepare_datasets()
        assert stats.conflicting_labels_removed >= 2
        all_urls = pd.concat([train_df, val_df, test_df])["url"]
        assert not all_urls.str.contains("conflict.example-site.com").any()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestConfigurableDatasetPath:
    def test_settings_expose_dataset_dir(self) -> None:
        from src.config.settings import get_settings

        settings = get_settings()
        assert isinstance(settings.paths.dataset_dir, Path)
        assert settings.paths.dataset_dir.is_absolute()

    def test_dataset_path_env_override(self, monkeypatch, tmp_path: Path) -> None:
        from src.config.settings import _resolve_dataset_dir

        monkeypatch.setenv("DATASET_PATH", str(tmp_path))
        assert _resolve_dataset_dir() == tmp_path

    def test_discovery_uses_explicit_override(self, dataset_dir: Path) -> None:
        discovery = DatasetDiscovery(dataset_dir)
        assert discovery.dataset_dir == dataset_dir


# ---------------------------------------------------------------------------
# Profile serialisation
# ---------------------------------------------------------------------------

class TestDatasetProfile:
    def test_profile_round_trip(self) -> None:
        profile = DatasetProfile(
            file_name="x.csv", file_format="csv", url_column="url",
            label_column="label", label_mode="mixed",
            total_rows=10, usable_rows=9, phishing_rows=5, legitimate_rows=4,
        )
        payload = profile.to_dict()
        assert payload["file_name"] == "x.csv"
        assert json.dumps(payload)  # JSON-serialisable
