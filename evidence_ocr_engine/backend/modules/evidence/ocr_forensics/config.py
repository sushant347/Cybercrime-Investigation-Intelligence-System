"""Configuration for the additive OCR forensic-metadata layer.

Every threshold is env-overridable, matching the ``EvidenceConfig.from_env``
convention used across the project, so nothing is hard-coded. This config is
independent of ``EvidenceConfig`` so the forensic layer stays self-contained
and cannot break the core OCR configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OCRForensicConfig:
    """Tunable thresholds for confidence tiers, quality and de-duplication."""

    # ---- confidence tiers (PP-OCRv5 line scores are 0-1) -------------------
    #: >= this is trusted "high" confidence.
    confidence_high: float = 0.90
    #: >= this (and < high) is "medium" / uncertain.
    confidence_medium: float = 0.60
    #: < this is "very low"; optionally discarded when ``discard_low`` is set.
    confidence_discard_below: float = 0.30
    #: Forensic default is to KEEP everything (only mark), never silently drop.
    discard_low: bool = False

    # ---- image quality diagnostic thresholds ------------------------------
    min_dpi_dimension: int = 900        # px; smaller flagged as low resolution
    blur_warn_below: float = 120.0      # Laplacian variance
    dark_below: float = 70.0            # mean brightness
    bright_above: float = 205.0
    low_contrast_below: float = 45.0    # grayscale std-dev
    noise_warn_above: float = 9.0

    # ---- duplicate detection ----------------------------------------------
    dedup_enabled: bool = True

    # ---- batch processing --------------------------------------------------
    batch_workers: int = 4

    @classmethod
    def from_env(cls) -> "OCRForensicConfig":
        """Build the config, letting ``EVIDENCE_OCR_*`` env vars override."""
        def _f(name: str, default: float) -> float:
            return float(os.environ.get(name, default))

        def _i(name: str, default: int) -> int:
            return int(os.environ.get(name, default))

        def _b(name: str, default: bool) -> bool:
            raw = os.environ.get(name)
            return default if raw is None else raw.strip().lower() in ("1", "true", "yes")

        return cls(
            confidence_high=_f("EVIDENCE_OCR_CONF_HIGH", cls.confidence_high),
            confidence_medium=_f("EVIDENCE_OCR_CONF_MEDIUM", cls.confidence_medium),
            confidence_discard_below=_f(
                "EVIDENCE_OCR_CONF_DISCARD", cls.confidence_discard_below),
            discard_low=_b("EVIDENCE_OCR_DISCARD_LOW", cls.discard_low),
            min_dpi_dimension=_i("EVIDENCE_OCR_MIN_DIM", cls.min_dpi_dimension),
            blur_warn_below=_f("EVIDENCE_OCR_BLUR_WARN", cls.blur_warn_below),
            dark_below=_f("EVIDENCE_OCR_DARK", cls.dark_below),
            bright_above=_f("EVIDENCE_OCR_BRIGHT", cls.bright_above),
            low_contrast_below=_f("EVIDENCE_OCR_CONTRAST", cls.low_contrast_below),
            noise_warn_above=_f("EVIDENCE_OCR_NOISE", cls.noise_warn_above),
            dedup_enabled=_b("EVIDENCE_OCR_DEDUP", cls.dedup_enabled),
            batch_workers=_i("EVIDENCE_OCR_WORKERS", cls.batch_workers),
        )
