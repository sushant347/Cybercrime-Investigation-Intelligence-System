"""Central configuration for the Digital Evidence Acquisition and OCR Engine.

All tunable parameters live here so behaviour can be adjusted without touching
business logic. Values may be overridden through ``EVIDENCE_*`` environment
variables (see :meth:`EvidenceConfig.from_env`).

This module intentionally has **no** third-party dependencies so it can be
imported anywhere (tests, scripts, services) without side effects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Module root = evidence_ocr_engine/  (config.py lives 3 levels below it)
_MODULE_ROOT: Path = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class EvidenceConfig:
    """Immutable runtime configuration (injected into every service)."""

    # ------------------------------------------------------------------ paths
    base_dir: Path = _MODULE_ROOT
    storage_dir: Path = _MODULE_ROOT / "storage"
    json_dir: Path = _MODULE_ROOT / "storage" / "json"
    originals_dir: Path = _MODULE_ROOT / "storage" / "originals"
    log_dir: Path = _MODULE_ROOT / "logs"

    # CSV repositories
    cases_csv: Path = _MODULE_ROOT / "storage" / "cases.csv"
    evidence_csv: Path = _MODULE_ROOT / "storage" / "evidence.csv"
    ocr_results_csv: Path = _MODULE_ROOT / "storage" / "ocr_results.csv"
    processing_log_csv: Path = _MODULE_ROOT / "storage" / "processing_log.csv"
    #: Maps the investigator-supplied case reference to its hashed case id.
    case_registry_csv: Path = _MODULE_ROOT / "storage" / "case_registry.csv"

    # ------------------------------------------------------------- acquisition
    #: ``.url`` is a first-class evidence type: a submitted link is stored as a
    #: small text artifact so it gets the same hashing / chain-of-custody /
    #: entity-extraction treatment as any uploaded file.
    supported_extensions: frozenset[str] = frozenset(
        {".png", ".jpeg", ".jpg", ".pdf", ".txt", ".csv", ".docx", ".url"}
    )
    image_extensions: frozenset[str] = frozenset({".png", ".jpeg", ".jpg"})
    text_extensions: frozenset[str] = frozenset({".txt", ".csv"})
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    # --------------------------------------------------------------------- OCR
    #: OCR language - an official PaddleOCR 3.x language identifier.
    #: "ne" (Nepali) belongs to PaddleOCR's DEVANAGARI_LANGS group and
    #: resolves to the multilingual `devanagari_PP-OCRv5_mobile_rec` model,
    #: whose dictionary covers Devanagari *and* Latin characters - i.e.
    #: English, Nepali, and mixed English+Nepali in the same image.
    #: Use "en" for English-only evidence (dedicated English model).
    #: NOTE: script-group names like "devanagari" are NOT valid languages
    #: in PaddleOCR 3.x and raise "No models are available for lang=...".
    ocr_lang: str = "ne"
    #: OCR model generation. Pinned to **PP-OCRv5** for the whole project:
    #: `PP-OCRv5_server_det` + the multilingual `devanagari_PP-OCRv5_mobile_rec`
    #: recogniser (which covers Devanagari + Latin). Pinning guarantees a single
    #: model generation everywhere - without it, `lang="en"` would auto-select a
    #: different generation. Only "PP-OCRv5" is supported by this engine.
    ocr_version: str = "PP-OCRv5"
    ocr_timeout_seconds: float = 180.0
    #: Largest image (in pixels) handed to PaddleOCR in a single call. Above
    #: this the image is read as overlapping horizontal bands instead.
    #: Paddle's cost grows much faster than linearly with pixel count - on
    #: Apple Silicon a 1.6 MP screenshot took 245s where 0.5 MP takes ~17s -
    #: and beyond roughly 2 MP it segfaults, killing the host process. This
    #: budget keeps every call in the fast, stable region without downscaling
    #: (which would shrink the text and cost accuracy).
    ocr_max_pixels: int = 700_000
    #: Vertical overlap between bands, so a text line sitting on a cut is
    #: still read whole by one of them. Duplicates are merged afterwards.
    ocr_band_overlap_px: int = 200
    #: OCR text lines below this confidence are kept but flagged in logs.
    low_confidence_threshold: float = 0.50
    #: Raise EmptyOCRError instead of storing an empty result.
    strict_empty_ocr: bool = False

    # --------------------------------------------------------------------- PDF
    #: A PDF page whose embedded text layer has at least this many characters
    #: is read directly; below it the page is treated as scanned and OCR'd.
    pdf_text_layer_min_chars: int = 20
    pdf_render_dpi: int = 220
    pdf_max_pages: int = 200

    # ----------------------------------------------------------- preprocessing
    max_image_dimension: int = 3000   # larger images are downscaled
    min_image_dimension: int = 900    # smaller images are upscaled
    blur_threshold: float = 120.0     # Laplacian variance below => blurry
    low_contrast_threshold: float = 45.0
    dark_brightness_threshold: float = 70.0
    noise_threshold: float = 9.0
    deskew_min_angle: float = 0.4     # degrees; skip tiny corrections

    # ------------------------------------------------------------------- misc
    case_id_prefix: str = "CASE"
    evidence_id_prefix: str = "EVID"
    directories: tuple[str, ...] = field(default=("storage", "json", "originals", "log"))

    @classmethod
    def from_env(cls) -> "EvidenceConfig":
        """Build a config, letting environment variables override defaults.

        Supported variables: ``EVIDENCE_STORAGE_DIR``, ``EVIDENCE_OCR_LANG``,
        ``EVIDENCE_OCR_VERSION``, ``EVIDENCE_MAX_FILE_MB``,
        ``EVIDENCE_OCR_TIMEOUT``, ``EVIDENCE_PDF_DPI``.
        """
        storage = Path(os.environ.get("EVIDENCE_STORAGE_DIR", str(_MODULE_ROOT / "storage")))
        base = storage.parent
        return cls(
            base_dir=base,
            storage_dir=storage,
            json_dir=storage / "json",
            originals_dir=storage / "originals",
            log_dir=base / "logs",
            cases_csv=storage / "cases.csv",
            evidence_csv=storage / "evidence.csv",
            ocr_results_csv=storage / "ocr_results.csv",
            processing_log_csv=storage / "processing_log.csv",
            case_registry_csv=storage / "case_registry.csv",
            ocr_lang=os.environ.get("EVIDENCE_OCR_LANG", "ne"),
            ocr_version=os.environ.get("EVIDENCE_OCR_VERSION") or "PP-OCRv5",
            max_file_size_bytes=int(float(os.environ.get("EVIDENCE_MAX_FILE_MB", "50")) * 1024 * 1024),
            ocr_timeout_seconds=float(os.environ.get("EVIDENCE_OCR_TIMEOUT", "180")),
            pdf_render_dpi=int(os.environ.get("EVIDENCE_PDF_DPI", "220")),
            ocr_max_pixels=int(os.environ.get("EVIDENCE_OCR_MAX_PIXELS", "700000")),
        )

    def ensure_directories(self) -> None:
        """Create every storage directory required by the engine."""
        for path in (self.storage_dir, self.json_dir, self.originals_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)
