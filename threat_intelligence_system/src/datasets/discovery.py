"""
Automatic dataset discovery for the Phishing URL Detection Engine.

Provides the ``DatasetDiscovery`` class which scans a configurable dataset
directory (``settings.paths.dataset_dir`` / ``DATASET_PATH``), automatically
detects the file format, encoding, delimiter, URL column and label column of
every dataset it finds, normalises heterogeneous label vocabularies into the
canonical binary scheme (0 = legitimate, 1 = phishing) and returns
standardised ``pandas.DataFrame`` objects with exactly ``['url', 'label']``
columns -- ready for the existing cleaning / validation / merging pipeline.

Supported formats
-----------------
* CSV  (auto-detected delimiter and encoding)
* TSV
* TXT  (one URL per line; label inferred from the file name)
* JSON (list of records)
* JSONL
* Excel (.xlsx / .xls)

Design notes
------------
* No dataset schema is assumed.  URL and label columns are detected by
  column-name heuristics first and content inspection second.
* Datasets may be mixed (both classes), phishing-only or legitimate-only.
  Single-class datasets are detected and reported as such; the merger is
  responsible for combining them into a balanced whole.
* Files without any recognisable URL column (e.g. e-mail metadata datasets)
  are skipped with an explicit reason rather than mislabelled.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.config.settings import get_settings
from src.utils.exceptions import DatasetError
from src.utils.logger import get_logger

logger = get_logger(__name__)


#: File extensions the discovery engine knows how to read.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".csv", ".tsv", ".txt", ".json", ".jsonl", ".xlsx", ".xls"}
)

#: Column names commonly used for URLs (checked case-insensitively, in order).
URL_COLUMN_CANDIDATES: tuple[str, ...] = (
    "url", "urls", "website", "link", "links", "uri", "address", "site",
    "web_url", "webpage", "page_url", "phish_url", "domain",
)

#: Column names commonly used for labels (checked case-insensitively, in order).
LABEL_COLUMN_CANDIDATES: tuple[str, ...] = (
    "label", "labels", "is_phishing", "phishing", "class", "target",
    "result", "type", "status", "verdict", "category", "classification",
    "is_malicious", "malicious", "phish", "y",
)

#: Canonical mapping of every recognised label token to a binary label.
#: 0 = Legitimate, 1 = Phishing.
LABEL_VALUE_MAP: dict[str, int] = {
    # numeric / boolean
    "0": 0, "1": 1, "0.0": 0, "1.0": 1,
    "true": 1, "false": 0, "yes": 1, "no": 0,
    # phishing-positive vocabulary
    "phishing": 1, "phish": 1, "malicious": 1, "bad": 1, "fraud": 1,
    "suspicious": 1, "malware": 1, "defacement": 1, "spam": 1, "scam": 1,
    "attack": 1, "unsafe": 1,
    # legitimate vocabulary
    "legitimate": 0, "legit": 0, "benign": 0, "good": 0, "normal": 0,
    "clean": 0, "safe": 0, "genuine": 0, "trusted": 0,
}

#: File-name keywords implying an all-phishing single-class dataset.
_PHISHING_FILENAME_HINTS: tuple[str, ...] = (
    "phish", "malicious", "fraud", "scam", "openphish", "blacklist",
)

#: File-name keywords implying an all-legitimate single-class dataset.
_LEGITIMATE_FILENAME_HINTS: tuple[str, ...] = (
    "legit", "benign", "tranco", "alexa", "top-sites", "topsites",
    "whitelist", "majestic", "umbrella",
)

#: Loose pattern used to decide whether a value "looks like" a URL/domain.
#: Userinfo (``user@host``) is only accepted after an explicit scheme so
#: that bare e-mail addresses are NOT mistaken for URLs.
_URL_LIKE_RE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://(?:[^\s/@]+@)?)?"  # optional scheme (+userinfo)
    r"[a-z0-9¡-￿-]+(?:\.[a-z0-9¡-￿-]+)+"  # dotted host
    r"(?:[:/?#]\S*)?$",                      # optional port/path/query
    re.IGNORECASE,
)

#: Number of sample values inspected per column during content detection.
_CONTENT_SAMPLE_SIZE = 200

#: Minimum fraction of sampled values that must look like URLs.
_URL_MATCH_THRESHOLD = 0.70


@dataclass
class DatasetProfile:
    """Per-file analysis result produced by :class:`DatasetDiscovery`.

    Attributes:
        file_name: Basename of the dataset file.
        file_format: Normalised format identifier (csv / tsv / txt / ...).
        encoding: Detected text encoding.
        delimiter: Detected field delimiter (delimited formats only).
        url_column: Name of the detected URL column.
        label_column: Name of the detected label column (``None`` when the
            label was inferred from the file name).
        label_mode: ``'mixed'``, ``'all_phishing'``, ``'all_legitimate'`` or
            ``'skipped'``.
        total_rows: Rows present in the source file.
        usable_rows: Rows that survived label normalisation.
        phishing_rows: Rows labelled 1 after normalisation.
        legitimate_rows: Rows labelled 0 after normalisation.
        missing_values: Rows dropped due to missing URL or label values.
        unmapped_labels: Rows dropped because their label token was not
            recognised.
        skipped_reason: Human-readable reason when the file was skipped.
    """

    file_name: str
    file_format: str = ""
    encoding: str = "utf-8"
    delimiter: Optional[str] = None
    url_column: Optional[str] = None
    label_column: Optional[str] = None
    label_mode: str = "skipped"
    total_rows: int = 0
    usable_rows: int = 0
    phishing_rows: int = 0
    legitimate_rows: int = 0
    missing_values: int = 0
    unmapped_labels: int = 0
    skipped_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return the profile as a JSON-serialisable dictionary."""
        return asdict(self)


class DatasetDiscovery:
    """Discover, analyse and normalise datasets in a configurable folder.

    The discovery engine never assumes a fixed schema.  For every supported
    file in ``dataset_dir`` it detects encoding, delimiter, URL column and
    label column, then emits a standardised DataFrame with the canonical
    ``['url', 'label']`` columns (0 = legitimate, 1 = phishing).

    Usage:
        >>> discovery = DatasetDiscovery()
        >>> datasets, profiles = discovery.load_all()
        >>> merged = DatasetMerger().merge(datasets)

    Attributes:
        dataset_dir: Directory scanned for dataset files.
        settings: Application-wide settings singleton.
    """

    def __init__(self, dataset_dir: Path | str | None = None) -> None:
        """Initialise the discovery engine.

        Args:
            dataset_dir: Override for the dataset directory.  When *None*
                the configurable ``settings.paths.dataset_dir`` is used.
        """
        self.settings = get_settings()
        self.dataset_dir: Path = Path(
            dataset_dir if dataset_dir is not None
            else self.settings.paths.dataset_dir
        )
        logger.info("DatasetDiscovery initialised - dataset_dir=%s", self.dataset_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover_files(self) -> list[Path]:
        """List all supported dataset files inside ``dataset_dir``.

        Returns:
            Sorted list of dataset file paths.

        Raises:
            DatasetError: If the dataset directory does not exist.
        """
        if not self.dataset_dir.exists():
            raise DatasetError(
                dataset=str(self.dataset_dir),
                operation="discover",
                reason=f"Dataset directory not found: {self.dataset_dir}",
            )
        files = sorted(
            p for p in self.dataset_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        logger.info("Discovered %d dataset file(s) in %s", len(files), self.dataset_dir)
        return files

    def load_dataset(self, path: Path) -> tuple[Optional[pd.DataFrame], DatasetProfile]:
        """Load and normalise a single dataset file.

        Args:
            path: Path of the dataset file.

        Returns:
            Tuple ``(dataframe, profile)``.  ``dataframe`` is *None* when
            the file had to be skipped (see ``profile.skipped_reason``); it
            otherwise contains exactly ``['url', 'label']``.
        """
        profile = DatasetProfile(file_name=path.name)
        try:
            raw = self._read_file(path, profile)
        except Exception as exc:  # noqa: BLE001 -- report, don't abort discovery
            profile.skipped_reason = f"Unreadable file: {exc}"
            logger.error("Skipping %s: %s", path.name, profile.skipped_reason)
            return None, profile

        if raw is None or raw.empty:
            profile.skipped_reason = "File contains no rows"
            logger.warning("Skipping %s: empty", path.name)
            return None, profile

        profile.total_rows = len(raw)

        url_column = self._detect_url_column(raw)
        if url_column is None:
            profile.skipped_reason = (
                "No URL column detected (not a URL dataset); "
                f"columns: {list(raw.columns)[:10]}"
            )
            logger.warning("Skipping %s: %s", path.name, profile.skipped_reason)
            return None, profile
        profile.url_column = url_column

        df, label_source = self._extract_labels(raw, url_column, path, profile)
        if df is None:
            return None, profile

        # Drop rows with missing URLs / labels
        before = len(df)
        df = df.dropna(subset=["url", "label"])
        df = df[df["url"].astype(str).str.strip() != ""]
        profile.missing_values = before - len(df)

        df["label"] = df["label"].astype(int)
        profile.usable_rows = len(df)
        profile.phishing_rows = int((df["label"] == 1).sum())
        profile.legitimate_rows = int((df["label"] == 0).sum())
        profile.label_mode = self._label_mode(profile)

        logger.info(
            "Loaded %s [%s] - %d usable rows (phishing=%d, legitimate=%d, "
            "url_col=%s, label=%s, mode=%s)",
            path.name, profile.file_format, profile.usable_rows,
            profile.phishing_rows, profile.legitimate_rows,
            profile.url_column, label_source, profile.label_mode,
        )
        return df[["url", "label"]].reset_index(drop=True), profile

    def load_all(self) -> tuple[dict[str, pd.DataFrame], list[DatasetProfile]]:
        """Discover and load every dataset in the configured folder.

        Returns:
            Tuple ``(datasets, profiles)`` where *datasets* maps file stems
            to normalised DataFrames and *profiles* contains one
            :class:`DatasetProfile` per discovered file (including skipped
            ones).

        Raises:
            DatasetError: If no usable dataset could be loaded at all.
        """
        datasets: dict[str, pd.DataFrame] = {}
        profiles: list[DatasetProfile] = []

        for path in self.discover_files():
            df, profile = self.load_dataset(path)
            profiles.append(profile)
            if df is not None and not df.empty:
                datasets[path.stem] = df

        if not datasets:
            raise DatasetError(
                dataset=str(self.dataset_dir),
                operation="load_all",
                reason="No usable URL datasets found in dataset directory",
            )

        total_phishing = sum(p.phishing_rows for p in profiles)
        total_legit = sum(p.legitimate_rows for p in profiles)
        logger.info(
            "Discovery complete - %d/%d files usable "
            "(total phishing=%d, legitimate=%d)",
            len(datasets), len(profiles), total_phishing, total_legit,
        )
        return datasets, profiles

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_file(self, path: Path, profile: DatasetProfile) -> Optional[pd.DataFrame]:
        """Read *path* into a raw DataFrame, auto-detecting format details."""
        suffix = path.suffix.lower()
        encoding = self._detect_encoding(path)
        profile.encoding = encoding

        if suffix in (".csv", ".tsv"):
            delimiter = "\t" if suffix == ".tsv" else self._detect_delimiter(path, encoding)
            profile.file_format = suffix.lstrip(".")
            profile.delimiter = delimiter
            return pd.read_csv(
                path, sep=delimiter, encoding=encoding,
                encoding_errors="replace", low_memory=False,
                on_bad_lines="skip",
            )

        if suffix == ".txt":
            profile.file_format = "txt"
            with open(path, encoding=encoding, errors="replace") as fh:
                lines = [line.strip() for line in fh if line.strip()]
            # Header-less URL list vs. delimited text file
            if lines and self._looks_like_delimited(lines[0]):
                delimiter = self._detect_delimiter(path, encoding)
                profile.delimiter = delimiter
                return pd.read_csv(
                    path, sep=delimiter, encoding=encoding,
                    encoding_errors="replace", low_memory=False,
                    on_bad_lines="skip",
                )
            return pd.DataFrame({"url": lines})

        if suffix == ".jsonl":
            profile.file_format = "jsonl"
            return pd.read_json(path, lines=True, encoding=encoding)

        if suffix == ".json":
            profile.file_format = "json"
            with open(path, encoding=encoding, errors="replace") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                # Accept {"data": [...]} style wrappers
                for value in payload.values():
                    if isinstance(value, list):
                        payload = value
                        break
            return pd.json_normalize(payload)

        if suffix in (".xlsx", ".xls"):
            profile.file_format = "excel"
            return pd.read_excel(path)

        profile.skipped_reason = f"Unsupported extension: {suffix}"
        return None

    @staticmethod
    def _detect_encoding(path: Path, sample_bytes: int = 65536) -> str:
        """Detect the text encoding of *path* (falls back to UTF-8)."""
        try:
            from charset_normalizer import from_bytes
            with open(path, "rb") as fh:
                sample = fh.read(sample_bytes)
            best = from_bytes(sample).best()
            if best is not None and best.encoding:
                # Normalise ASCII to UTF-8 (superset, safer for full file)
                enc = best.encoding.lower()
                return "utf-8" if enc == "ascii" else enc
        except Exception:  # noqa: BLE001 -- fall back silently
            pass
        return "utf-8"

    @staticmethod
    def _detect_delimiter(path: Path, encoding: str) -> str:
        """Detect the field delimiter of a delimited text file."""
        with open(path, encoding=encoding, errors="replace") as fh:
            sample = fh.read(8192)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            return ","

    @staticmethod
    def _looks_like_delimited(header_line: str) -> bool:
        """Heuristic: does the first line of a .txt file look like a header row?"""
        return any(sep in header_line for sep in (",", "\t", ";", "|"))

    # ------------------------------------------------------------------
    # Column detection
    # ------------------------------------------------------------------

    def _detect_url_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detect which column contains URLs.

        Column-name candidates are checked first; if none match, every
        object-typed column is content-sampled and the best URL-looking
        column above the match threshold wins.
        """
        lower_map = {str(c).strip().lower(): c for c in df.columns}

        for candidate in URL_COLUMN_CANDIDATES:
            column = lower_map.get(candidate)
            if column is not None and self._url_match_ratio(df[column]) >= _URL_MATCH_THRESHOLD:
                return column

        # Content-based fallback
        best_column: Optional[str] = None
        best_ratio = _URL_MATCH_THRESHOLD
        for column in df.columns:
            if df[column].dtype != object:
                continue
            ratio = self._url_match_ratio(df[column])
            if ratio > best_ratio:
                best_ratio = ratio
                best_column = column
        return best_column

    @staticmethod
    def _url_match_ratio(series: pd.Series) -> float:
        """Fraction of sampled non-null values that look like URLs."""
        sample = series.dropna().astype(str).head(_CONTENT_SAMPLE_SIZE)
        if sample.empty:
            return 0.0
        matches = sum(
            1 for value in sample
            if len(value) < 4096 and _URL_LIKE_RE.match(value.strip()) is not None
        )
        return matches / len(sample)

    def _extract_labels(
        self,
        raw: pd.DataFrame,
        url_column: str,
        path: Path,
        profile: DatasetProfile,
    ) -> tuple[Optional[pd.DataFrame], str]:
        """Build the standardised ``['url', 'label']`` frame from *raw*.

        Returns:
            Tuple ``(dataframe_or_none, label_source_description)``.
        """
        label_column = self._detect_label_column(raw, url_column)

        if label_column is not None:
            profile.label_column = label_column
            normalised = self._normalise_label_series(raw[label_column])
            df = pd.DataFrame({
                "url": raw[url_column].astype(str),
                "label": normalised,
            })
            profile.unmapped_labels = int(normalised.isna().sum())
            if profile.unmapped_labels:
                logger.warning(
                    "%s: dropped %d rows with unrecognised label values",
                    path.name, profile.unmapped_labels,
                )
            df = df.dropna(subset=["label"])
            if df.empty:
                profile.skipped_reason = (
                    f"Label column '{label_column}' contained no recognisable "
                    "binary labels"
                )
                return None, label_column
            return df, f"column '{label_column}'"

        # No label column: try single-class inference from the file name
        inferred = self._infer_label_from_filename(path.name)
        if inferred is not None:
            df = pd.DataFrame({
                "url": raw[url_column].astype(str),
                "label": inferred,
            })
            return df, f"filename => all {'phishing' if inferred else 'legitimate'}"

        profile.skipped_reason = (
            "No label column detected and file name gives no class hint; "
            "cannot safely assign labels"
        )
        logger.warning("Skipping %s: %s", path.name, profile.skipped_reason)
        return None, "none"

    def _detect_label_column(
        self, df: pd.DataFrame, url_column: str
    ) -> Optional[str]:
        """Detect the label column of *df*.

        Detection order:
            1. Candidate column names whose values map onto the recognised
               binary label vocabulary.
            2. Any textual column whose distinct values are a subset of the
               *textual* label vocabulary (e.g. Phishing / Legitimate).

        Numeric non-candidate columns are never auto-selected -- binary
        feature flags (``has_ip`` etc.) must not be mistaken for labels.
        """
        lower_map = {str(c).strip().lower(): c for c in df.columns}

        for candidate in LABEL_COLUMN_CANDIDATES:
            column = lower_map.get(candidate)
            if column is None or column == url_column:
                continue
            if self._is_binary_label_series(df[column]):
                return column

        textual_vocab = {
            token for token, _ in LABEL_VALUE_MAP.items() if token.isalpha()
        }
        for column in df.columns:
            if column == url_column or df[column].dtype != object:
                continue
            values = {
                str(v).strip().lower()
                for v in df[column].dropna().unique()[:20]
            }
            if values and values <= textual_vocab:
                return column
        return None

    @staticmethod
    def _is_binary_label_series(series: pd.Series) -> bool:
        """Check whether *series* holds recognisable binary labels.

        A column qualifies when at least half of its (sampled) non-null rows
        carry a recognised binary label token.  This tolerates label noise
        without rejecting the column outright -- this check is only applied
        to columns whose *name* already marks them as label candidates, and
        unrecognised rows are dropped later during normalisation.
        """
        sample = series.dropna().astype(str).str.strip().str.lower().head(1000)
        if sample.empty or sample.nunique() > 10:
            return False
        recognised = set(LABEL_VALUE_MAP) | {"-1", "-1.0"}
        return (sample.isin(recognised).mean()) >= 0.50

    @staticmethod
    def _normalise_label_series(series: pd.Series) -> pd.Series:
        """Map heterogeneous label tokens onto {0, 1} (NaN if unmappable)."""
        tokens = series.astype(str).str.strip().str.lower()
        unique = set(tokens.dropna().unique())
        mapping = dict(LABEL_VALUE_MAP)
        # Special case: {-1, 1} convention (-1 = legitimate)
        if unique <= {"-1", "1", "-1.0", "1.0"}:
            mapping.update({"-1": 0, "-1.0": 0})
        return tokens.map(mapping)

    @staticmethod
    def _infer_label_from_filename(file_name: str) -> Optional[int]:
        """Infer a single-class label from the dataset file name."""
        name = file_name.lower()
        if any(hint in name for hint in _LEGITIMATE_FILENAME_HINTS):
            return 0
        if any(hint in name for hint in _PHISHING_FILENAME_HINTS):
            return 1
        return None

    @staticmethod
    def _label_mode(profile: DatasetProfile) -> str:
        """Classify the label composition of a dataset."""
        if profile.usable_rows == 0:
            return "skipped"
        if profile.legitimate_rows == 0:
            return "all_phishing"
        if profile.phishing_rows == 0:
            return "all_legitimate"
        return "mixed"
