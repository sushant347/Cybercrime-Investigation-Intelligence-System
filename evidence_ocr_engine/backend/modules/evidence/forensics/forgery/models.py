"""Pydantic models for Image Forgery Detection (Module 4)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class ELAFinding(BaseModel):
    """Error Level Analysis measurements."""

    mean_difference: float = Field(ge=0.0)
    max_difference: float = Field(ge=0.0)
    hotspot_region_fraction: float = Field(
        ge=0.0, le=1.0,
        description="Fraction of grid cells whose ELA energy is anomalous",
    )
    suspicious: bool = False


class CompressionFinding(BaseModel):
    """JPEG compression artifact analysis."""

    blockiness: float = Field(ge=0.0)
    grid_inconsistency: float = Field(
        ge=0.0, description="Blockiness variance across the 8x8 grid alignment"
    )
    estimated_recompressions: int = Field(ge=0, le=3)
    suspicious: bool = False


class MetadataFinding(BaseModel):
    """Metadata consistency verification."""

    has_exif: bool = False
    software_tags: List[str] = Field(default_factory=list)
    editing_software_detected: bool = False
    datetime_original: str = ""
    datetime_modified: str = ""
    datetime_mismatch: bool = False
    issues: List[str] = Field(default_factory=list)
    suspicious: bool = False


class CopyMoveFinding(BaseModel):
    """Basic copy-move (clone) forgery detection."""

    keypoints_analyzed: int = 0
    self_matches: int = 0
    consistent_offset_clusters: int = 0
    largest_cluster_size: int = 0
    suspicious: bool = False


class NoiseFinding(BaseModel):
    """Block-wise noise inconsistency (splicing indicator)."""

    block_count: int = 0
    noise_mean: float = 0.0
    noise_std: float = 0.0
    inconsistency_ratio: float = Field(
        ge=0.0, description="std/mean of per-block noise; high => inconsistent"
    )
    suspicious: bool = False


class ForgeryReport(BaseModel):
    """Complete Module-4 output stored as ``forgery_report.json``."""

    evidence_id: str
    case_id: str
    source_file: str

    ela: ELAFinding
    compression: CompressionFinding
    metadata: MetadataFinding
    copy_move: CopyMoveFinding
    noise: NoiseFinding

    component_scores: Dict[str, float] = Field(
        default_factory=dict, description="Per-technique suspicion 0-100"
    )
    forgery_score: float = Field(ge=0.0, le=100.0, description="0 = pristine")
    forgery_risk: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    authenticity_status: str = Field(
        description="LIKELY_AUTHENTIC | INDETERMINATE | SUSPICIOUS | LIKELY_TAMPERED"
    )
    findings: List[str] = Field(default_factory=list)
    analysis_time_ms: float = 0.0
    note: str = Field(
        default="Findings are investigative indicators only; evidence is never rejected.",
    )
