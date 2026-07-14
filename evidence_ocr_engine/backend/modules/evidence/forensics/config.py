"""Configuration for every Phase-1 forensic module.

All tunables live here (configuration-driven architecture - no hardcoded
values inside services). Values may be overridden through ``FORENSICS_*``
environment variables via :meth:`ForensicsConfig.from_env`.

The forensics storage tree is strictly separate from the existing engine
storage so no legacy file is ever overwritten::

    storage/forensics/
        forensics_audit_log.csv          <- audit trail for every module
        file_fingerprints.csv            <- Module 7 duplicate index
        evidence_confidence.csv          <- Module 8 score index
        <EVIDENCE_ID>/
            quality_report.json          <- Module 1
            preprocessing_report.json    <- Module 2
            ocr_fusion.json              <- Module 3
            forgery_report.json          <- Module 4
            logo_detections.json         <- Module 5
            metadata_report.json         <- Module 6
            file_fingerprint.json        <- Module 7
            evidence_confidence.json     <- Module 8
            derived/                     <- working copies (never originals)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

from ..config import EvidenceConfig


@dataclass(frozen=True)
class ForensicsConfig:
    """Immutable runtime configuration injected into every Phase-1 service."""

    # ------------------------------------------------------------------ paths
    forensics_dir: Path = Path("storage") / "forensics"
    audit_csv_name: str = "forensics_audit_log.csv"
    fingerprint_csv_name: str = "file_fingerprints.csv"
    confidence_csv_name: str = "evidence_confidence.csv"
    derived_dir_name: str = "derived"

    # Report file names (Storage Requirements section of the Phase-1 spec)
    quality_report_name: str = "quality_report"
    preprocessing_report_name: str = "preprocessing_report"
    ocr_fusion_report_name: str = "ocr_fusion"
    forgery_report_name: str = "forgery_report"
    logo_report_name: str = "logo_detections"
    metadata_report_name: str = "metadata_report"
    fingerprint_report_name: str = "file_fingerprint"
    confidence_report_name: str = "evidence_confidence"

    # ------------------------------------------- Module 1: quality assessment
    #: Laplacian variance at/above which an image is considered perfectly sharp.
    blur_excellent: float = 500.0
    #: Laplacian variance at/below which an image is considered unusable.
    blur_unusable: float = 15.0
    #: Ideal brightness band (mean grayscale intensity). The upper bound is
    #: deliberately high: white document pages average ~230-245 and are ideal
    #: for OCR - only near-blown-out captures should be penalised.
    brightness_ideal: Tuple[float, float] = (110.0, 245.0)
    #: Contrast (grayscale std-dev) considered excellent.
    contrast_excellent: float = 60.0
    #: Noise (median-filter residual) considered negligible / unusable.
    noise_negligible: float = 2.0
    noise_unusable: float = 25.0
    #: Minimum image dimension (px) considered fully adequate for OCR.
    resolution_adequate_px: int = 1000
    resolution_minimum_px: int = 250
    #: |skew| in degrees above which the deskew recommendation triggers.
    skew_tolerance_deg: float = 0.4
    #: JPEG estimated quality below which recompression damage is assumed.
    jpeg_quality_poor: float = 55.0
    #: Weights used to combine sub-scores into the overall 0-100 quality score.
    quality_weights: Dict[str, float] = field(default_factory=lambda: {
        "blur": 0.24, "brightness": 0.10, "contrast": 0.14, "noise": 0.14,
        "resolution": 0.14, "skew": 0.06, "compression": 0.08, "readability": 0.10,
    })

    # --------------------------------------- Module 2: advanced preprocessing
    denoise_strength_max: float = 12.0
    clahe_clip_limit: float = 2.5
    clahe_tile_grid: int = 8
    illumination_kernel_frac: float = 0.125   # background blur kernel as frac of min dim
    shadow_dilate_kernel: int = 7
    shadow_median_kernel: int = 21
    morph_kernel_size: int = 2
    edge_enhance_amount: float = 0.6
    super_resolution_trigger_px: int = 700    # only upscale when min dim below this
    super_resolution_max_scale: float = 3.0
    perspective_min_area_frac: float = 0.55
    #: Quality sub-score (0-100) below which the matching operation is planned.
    op_trigger_score: float = 65.0

    # ----------------------------------------------- Module 3: multi-OCR fusion
    fusion_enable_paddle: bool = True
    fusion_enable_easyocr: bool = True
    fusion_enable_tesseract: bool = True
    easyocr_languages: Tuple[str, ...] = ("en", "ne")
    tesseract_languages: str = "eng+nep"
    tesseract_psm: int = 6
    #: Selection score = w_conf*confidence + w_agree*agreement + w_len*coverage.
    fusion_weight_confidence: float = 0.55
    fusion_weight_agreement: float = 0.30
    fusion_weight_coverage: float = 0.15
    #: Line similarity ratio at/above which two engine lines are "the same line".
    fusion_line_similarity: float = 0.60
    #: Merge only when a candidate line beats the chosen line by this margin.
    fusion_merge_margin: float = 0.10
    ocr_min_line_confidence: float = 0.05

    # -------------------------------------------- Module 4: forgery detection
    ela_jpeg_quality: int = 90
    ela_suspicious_mean: float = 14.0
    ela_region_grid: int = 8
    blockiness_suspicious: float = 6.0
    copy_move_max_features: int = 1200
    copy_move_min_distance_px: float = 24.0
    copy_move_match_ratio: float = 0.72
    copy_move_min_cluster: int = 8
    noise_block_size: int = 64
    noise_inconsistency_suspicious: float = 2.4
    #: EXIF "Software" substrings that indicate an editing tool touched the file.
    editing_software_markers: Tuple[str, ...] = (
        "photoshop", "gimp", "lightroom", "snapseed", "picsart", "canva",
        "pixlr", "affinity", "paint.net", "photopea", "remini", "facetune",
    )
    forgery_weights: Dict[str, float] = field(default_factory=lambda: {
        "ela": 0.30, "compression": 0.20, "metadata": 0.15,
        "copy_move": 0.20, "noise": 0.15,
    })
    forgery_risk_bands: Dict[str, float] = field(default_factory=lambda: {
        # score < value  =>  that risk band (evaluated in insertion order)
        "LOW": 25.0, "MEDIUM": 50.0, "HIGH": 75.0, "CRITICAL": 101.0,
    })

    # ---------------------------------------------- Module 5: logo detection
    #: Optional directory of brand template images: <assets>/<brand_key>/*.png
    logo_template_dir: Path = Path("storage") / "forensics" / "logo_templates"
    logo_template_threshold: float = 0.78
    logo_template_scales: Tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
    logo_colour_min_area_frac: float = 0.002
    logo_keyword_confidence: float = 0.55
    logo_colour_confidence: float = 0.45
    logo_template_confidence_floor: float = 0.78

    # -------------------------------------------------- Module 7: integrity
    hash_chunk_bytes: int = 1024 * 1024
    entropy_high_threshold: float = 7.5
    duplicate_scope_limit: int = 100_000

    # ------------------------------------------- Module 8: confidence scoring
    confidence_weights: Dict[str, float] = field(default_factory=lambda: {
        "image_quality": 0.20, "forgery": 0.20, "metadata": 0.10,
        "hash_verification": 0.20, "ocr_confidence": 0.20, "processing": 0.10,
    })
    confidence_bands: Dict[str, float] = field(default_factory=lambda: {
        "VERY_LOW": 20.0, "LOW": 40.0, "MODERATE": 60.0,
        "HIGH": 80.0, "VERY_HIGH": 101.0,
    })

    # ------------------------------------------------------------------ misc
    report_schema_version: str = "1.0"

    # ------------------------------------------------------------- factories
    @classmethod
    def from_evidence_config(cls, evidence_config: EvidenceConfig) -> "ForensicsConfig":
        """Anchor the forensics tree inside the existing storage directory."""
        forensics_dir = evidence_config.storage_dir / "forensics"
        return cls(
            forensics_dir=forensics_dir,
            logo_template_dir=forensics_dir / "logo_templates",
        )

    @classmethod
    def from_env(cls, evidence_config: EvidenceConfig) -> "ForensicsConfig":
        """Build a config honouring ``FORENSICS_*`` environment overrides."""
        base = cls.from_evidence_config(evidence_config)
        forensics_dir = Path(
            os.environ.get("FORENSICS_STORAGE_DIR", str(base.forensics_dir))
        )
        return cls(
            forensics_dir=forensics_dir,
            logo_template_dir=Path(
                os.environ.get("FORENSICS_LOGO_TEMPLATE_DIR",
                               str(forensics_dir / "logo_templates"))
            ),
            ela_jpeg_quality=int(os.environ.get("FORENSICS_ELA_QUALITY", "90")),
            tesseract_languages=os.environ.get("FORENSICS_TESSERACT_LANGS", "eng+nep"),
        )

    # ------------------------------------------------------------------ paths
    @property
    def audit_csv(self) -> Path:
        return self.forensics_dir / self.audit_csv_name

    @property
    def fingerprint_csv(self) -> Path:
        return self.forensics_dir / self.fingerprint_csv_name

    @property
    def confidence_csv(self) -> Path:
        return self.forensics_dir / self.confidence_csv_name

    def evidence_dir(self, evidence_id: str) -> Path:
        """Per-evidence report directory (created on demand by the repository)."""
        return self.forensics_dir / evidence_id

    def derived_dir(self, evidence_id: str) -> Path:
        """Directory for derived working images - originals are never stored here."""
        return self.evidence_dir(evidence_id) / self.derived_dir_name

    def ensure_directories(self) -> None:
        self.forensics_dir.mkdir(parents=True, exist_ok=True)
