"""Module 4 - Image Forgery Detection service.

Runs five independent techniques and combines them into a single 0-100
forgery score with a risk band and authenticity status:

1. Error Level Analysis (ELA)
2. JPEG compression artifact analysis
3. Metadata consistency verification
4. Basic copy-move (clone) detection via ORB self-matching
5. Block-wise noise inconsistency (splicing indicator)

The service produces *findings only*. Evidence is never rejected, the
original file is never modified, and every run is audited.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import ExifTags, Image

from ...logger import get_logger
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .models import (
    CompressionFinding,
    CopyMoveFinding,
    ELAFinding,
    ForgeryReport,
    MetadataFinding,
    NoiseFinding,
)

MODULE = "forgery_detection"


class ForgeryDetectionService:
    """Authenticity analysis for image evidence, prior to OCR."""

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._log = get_logger("forensics.forgery")

    # ------------------------------------------------------------------ public

    def analyze(
        self,
        image: np.ndarray,
        *,
        evidence_id: str,
        case_id: str,
        source_file: str,
        source_path: Optional[Path] = None,
        persist: bool = True,
    ) -> ForgeryReport:
        """Analyse one RGB image (read-only) and optionally persist the report."""
        started = time.perf_counter()
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        ela = self._error_level_analysis(image)
        compression = self._compression_analysis(gray)
        metadata = self._metadata_consistency(source_path)
        copy_move = self._copy_move(gray)
        noise = self._noise_inconsistency(gray)

        component_scores = self._component_scores(ela, compression, metadata, copy_move, noise)
        forgery_score = self._weighted(component_scores)
        risk = self._risk_band(forgery_score)
        report = ForgeryReport(
            evidence_id=evidence_id,
            case_id=case_id,
            source_file=source_file,
            ela=ela,
            compression=compression,
            metadata=metadata,
            copy_move=copy_move,
            noise=noise,
            component_scores={k: round(v, 1) for k, v in component_scores.items()},
            forgery_score=round(forgery_score, 1),
            forgery_risk=risk,
            authenticity_status=self._authenticity(forgery_score),
            findings=self._findings(ela, compression, metadata, copy_move, noise),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(
                evidence_id, case_id, self._cfg.forgery_report_name, report.model_dump()
            )
            self._audit.record(
                case_id, evidence_id, MODULE, "analyzed",
                f"score={report.forgery_score} risk={report.forgery_risk} "
                f"status={report.authenticity_status}",
                duration_ms=report.analysis_time_ms,
            )
        return report

    # -------------------------------------------------------------- techniques

    def _error_level_analysis(self, image: np.ndarray) -> ELAFinding:
        """Recompress at a known JPEG quality and measure the residual.

        Genuine single-generation JPEGs show a uniform low residual; regions
        pasted from another source or re-saved separately light up."""
        cfg = self._cfg
        pil = Image.fromarray(image)
        buffer = io.BytesIO()
        pil.save(buffer, format="JPEG", quality=cfg.ela_jpeg_quality)
        buffer.seek(0)
        recompressed = np.asarray(Image.open(buffer).convert("RGB"))
        diff = cv2.absdiff(image, recompressed).astype(np.float32)
        magnitude = diff.mean(axis=2)

        grid = cfg.ela_region_grid
        h, w = magnitude.shape
        cell_means: List[float] = []
        for gy in range(grid):
            for gx in range(grid):
                cell = magnitude[
                    gy * h // grid:(gy + 1) * h // grid,
                    gx * w // grid:(gx + 1) * w // grid,
                ]
                if cell.size:
                    cell_means.append(float(cell.mean()))
        mean_diff = float(magnitude.mean())
        threshold = mean_diff * 2.5 + 2.0
        hotspots = sum(1 for c in cell_means if c > threshold)
        fraction = hotspots / max(1, len(cell_means))
        return ELAFinding(
            mean_difference=round(mean_diff, 3),
            max_difference=round(float(magnitude.max()), 3),
            hotspot_region_fraction=round(fraction, 4),
            suspicious=mean_diff > cfg.ela_suspicious_mean or fraction > 0.15,
        )

    def _compression_analysis(self, gray: np.ndarray) -> CompressionFinding:
        """Blockiness at the 8x8 JPEG grid, plus misaligned-grid comparison.

        A second compression with a shifted grid leaves blockiness at more
        than one alignment - a classic recompression/tamper indicator."""
        aligned = self._blockiness(gray, offset=0)
        shifted = self._blockiness(gray, offset=4)
        inconsistency = abs(aligned - shifted)
        recompressions = 0
        if aligned > self._cfg.blockiness_suspicious:
            recompressions = 1
        if aligned > self._cfg.blockiness_suspicious and shifted > aligned * 0.8:
            recompressions = 2
        return CompressionFinding(
            blockiness=round(aligned, 3),
            grid_inconsistency=round(inconsistency, 3),
            estimated_recompressions=recompressions,
            suspicious=recompressions >= 2,
        )

    @staticmethod
    def _blockiness(gray: np.ndarray, offset: int) -> float:
        g = gray.astype(np.float32)
        h, w = g.shape
        if h < 24 or w < 24:
            return 0.0
        cols = np.arange(8 + offset, w - 1, 8)
        rows = np.arange(8 + offset, h - 1, 8)
        v = float(np.mean(np.abs(g[:, cols] - g[:, cols - 1]))) if len(cols) else 0.0
        hz = float(np.mean(np.abs(g[rows, :] - g[rows - 1, :]))) if len(rows) else 0.0
        natural = float(np.mean(np.abs(np.diff(g, axis=1))))
        return max(0.0, (v + hz) / 2.0 - natural)

    def _metadata_consistency(self, source_path: Optional[Path]) -> MetadataFinding:
        finding = MetadataFinding()
        if source_path is None or not source_path.exists():
            finding.issues.append("source file unavailable for metadata checks")
            return finding
        try:
            with Image.open(source_path) as img:
                exif = img.getexif()
        except OSError:
            finding.issues.append("file is not a readable image container")
            return finding
        if not exif:
            finding.issues.append(
                "no EXIF metadata (normal for screenshots/social-media exports; "
                "removes one authenticity signal)"
            )
            return finding

        finding.has_exif = True
        tags = {ExifTags.TAGS.get(tag_id, str(tag_id)): value
                for tag_id, value in exif.items()}
        software = str(tags.get("Software", "")).strip()
        if software:
            finding.software_tags.append(software)
            lowered = software.lower()
            if any(marker in lowered for marker in self._cfg.editing_software_markers):
                finding.editing_software_detected = True
                finding.issues.append(f"editing software in EXIF: '{software}'")
        original = str(tags.get("DateTimeOriginal", tags.get("DateTime", "")))
        modified = str(tags.get("DateTime", ""))
        finding.datetime_original = original
        finding.datetime_modified = modified
        if original and modified and original != modified:
            finding.datetime_mismatch = True
            finding.issues.append(
                f"EXIF capture time '{original}' differs from modification time '{modified}'"
            )
        finding.suspicious = finding.editing_software_detected or finding.datetime_mismatch
        return finding

    def _copy_move(self, gray: np.ndarray) -> CopyMoveFinding:
        """ORB self-matching: duplicated regions produce many keypoint pairs
        sharing a consistent, non-trivial offset vector."""
        cfg = self._cfg
        orb = cv2.ORB_create(nfeatures=cfg.copy_move_max_features)
        keypoints, descriptors = orb.detectAndCompute(gray, None)
        if descriptors is None or len(keypoints) < 20:
            return CopyMoveFinding(keypoints_analyzed=len(keypoints or []))

        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = matcher.knnMatch(descriptors, descriptors, k=3)
        offsets: List[Tuple[int, int]] = []
        for group in matches:
            for match in group:
                if match.queryIdx == match.trainIdx:
                    continue  # trivial self-match
                p1 = np.array(keypoints[match.queryIdx].pt)
                p2 = np.array(keypoints[match.trainIdx].pt)
                distance = float(np.linalg.norm(p1 - p2))
                if distance < cfg.copy_move_min_distance_px:
                    continue  # neighbouring texture, not a clone
                if match.distance > 42:  # Hamming distance: near-identical patches only
                    continue
                dx, dy = p2 - p1
                offsets.append((int(round(dx / 8.0)), int(round(dy / 8.0))))
                break

        clusters: Dict[Tuple[int, int], int] = {}
        for offset in offsets:
            clusters[offset] = clusters.get(offset, 0) + 1
        significant = {k: v for k, v in clusters.items()
                       if v >= cfg.copy_move_min_cluster}
        largest = max(clusters.values()) if clusters else 0
        return CopyMoveFinding(
            keypoints_analyzed=len(keypoints),
            self_matches=len(offsets),
            consistent_offset_clusters=len(significant),
            largest_cluster_size=largest,
            suspicious=bool(significant),
        )

    def _noise_inconsistency(self, gray: np.ndarray) -> NoiseFinding:
        """Estimate sensor noise per block; spliced content carries foreign noise."""
        size = self._cfg.noise_block_size
        h, w = gray.shape
        estimates: List[float] = []
        for y in range(0, h - size + 1, size):
            for x in range(0, w - size + 1, size):
                block = gray[y:y + size, x:x + size]
                denoised = cv2.medianBlur(block, 3)
                residual = float(np.mean(cv2.absdiff(block, denoised)))
                estimates.append(residual)
        if len(estimates) < 4:
            return NoiseFinding(block_count=len(estimates))
        arr = np.asarray(estimates)
        mean = float(arr.mean())
        std = float(arr.std())
        ratio = std / mean if mean > 0.3 else 0.0
        return NoiseFinding(
            block_count=len(estimates),
            noise_mean=round(mean, 3),
            noise_std=round(std, 3),
            inconsistency_ratio=round(ratio, 3),
            suspicious=ratio > self._cfg.noise_inconsistency_suspicious,
        )

    # ----------------------------------------------------------------- scoring

    def _component_scores(
        self,
        ela: ELAFinding,
        compression: CompressionFinding,
        metadata: MetadataFinding,
        copy_move: CopyMoveFinding,
        noise: NoiseFinding,
    ) -> Dict[str, float]:
        cfg = self._cfg
        scores: Dict[str, float] = {}
        scores["ela"] = float(np.clip(
            (ela.mean_difference / cfg.ela_suspicious_mean) * 50.0
            + ela.hotspot_region_fraction * 200.0, 0.0, 100.0,
        ))
        scores["compression"] = float(np.clip(
            compression.estimated_recompressions * 35.0
            + compression.grid_inconsistency * 4.0, 0.0, 100.0,
        ))
        meta_score = 0.0
        if metadata.editing_software_detected:
            meta_score += 60.0
        if metadata.datetime_mismatch:
            meta_score += 30.0
        scores["metadata"] = min(100.0, meta_score)
        cm_score = 0.0
        if copy_move.suspicious:
            cm_score = 50.0 + min(50.0, copy_move.largest_cluster_size * 2.0)
        scores["copy_move"] = cm_score
        scores["noise"] = float(np.clip(
            (noise.inconsistency_ratio / max(0.1, cfg.noise_inconsistency_suspicious))
            * 55.0, 0.0, 100.0,
        ))
        return scores

    def _weighted(self, component_scores: Dict[str, float]) -> float:
        weights = self._cfg.forgery_weights
        total = sum(weights.get(k, 0.0) for k in component_scores)
        if total <= 0:
            return 0.0
        return sum(component_scores[k] * weights.get(k, 0.0)
                   for k in component_scores) / total

    def _risk_band(self, score: float) -> str:
        for band, ceiling in self._cfg.forgery_risk_bands.items():
            if score < ceiling:
                return band
        return "CRITICAL"

    @staticmethod
    def _authenticity(score: float) -> str:
        if score < 25.0:
            return "LIKELY_AUTHENTIC"
        if score < 50.0:
            return "INDETERMINATE"
        if score < 75.0:
            return "SUSPICIOUS"
        return "LIKELY_TAMPERED"

    @staticmethod
    def _findings(
        ela: ELAFinding,
        compression: CompressionFinding,
        metadata: MetadataFinding,
        copy_move: CopyMoveFinding,
        noise: NoiseFinding,
    ) -> List[str]:
        findings: List[str] = []
        if ela.suspicious:
            findings.append(
                f"ELA residual is elevated (mean {ela.mean_difference}, "
                f"{ela.hotspot_region_fraction:.0%} anomalous regions)."
            )
        if compression.suspicious:
            findings.append(
                f"Compression artifacts indicate ~{compression.estimated_recompressions} "
                "re-save generations."
            )
        findings.extend(metadata.issues)
        if copy_move.suspicious:
            findings.append(
                f"Copy-move indicator: {copy_move.consistent_offset_clusters} "
                f"consistent offset cluster(s), largest {copy_move.largest_cluster_size} matches."
            )
        if noise.suspicious:
            findings.append(
                f"Sensor-noise inconsistency across blocks (ratio {noise.inconsistency_ratio})."
            )
        if not findings:
            findings.append("No tampering indicators detected by the implemented techniques.")
        return findings
