"""Module 1 - OCR Quality Assessment Engine.

Analyses every uploaded evidence image *before* OCR and produces a complete
quality report: blur, brightness, contrast, noise, resolution, skew,
compression quality, readability, an overall 0-100 score, the expected OCR
accuracy, and the preprocessing operations recommended for Module 2.

Strictly read-only: the evidence image is never modified here.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image

from ...logger import get_logger
from ...utils import InvalidImageError
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .models import QualityAssessment, QualityMetrics

MODULE = "quality_assessment"


class QualityAssessmentService:
    """Measures image quality and recommends Module-2 preprocessing steps."""

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._log = get_logger("forensics.quality")

    # ------------------------------------------------------------------ public

    def assess(
        self,
        image: np.ndarray,
        *,
        evidence_id: str,
        case_id: str,
        source_file: str,
        source_path: Path | None = None,
        persist: bool = True,
    ) -> QualityAssessment:
        """Assess one RGB image (H x W x 3, uint8) and optionally persist.

        Args:
            image: RGB numpy image - read-only, never modified.
            source_path: Original file path; used only to estimate JPEG
                compression quality from quantisation tables.
            persist: Store ``quality_report.json`` and write audit entries.
        """
        if image is None or image.ndim != 3 or image.shape[2] != 3:
            raise InvalidImageError("Quality assessment expects an RGB HxWx3 image")

        started = time.perf_counter()
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        metrics = QualityMetrics(
            width=image.shape[1],
            height=image.shape[0],
            megapixels=round(image.shape[0] * image.shape[1] / 1e6, 3),
            blur_laplacian_variance=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            brightness_mean=float(gray.mean()),
            contrast_std=float(gray.std()),
            noise_residual=self._estimate_noise(gray),
            skew_angle_deg=self._estimate_skew(gray),
            compression_quality=self._estimate_compression_quality(gray, source_path),
            edge_density=self._edge_density(gray),
            text_like_components=self._count_text_like_components(gray),
        )

        sub_scores = self._sub_scores(metrics)
        readability = self._readability_score(metrics, sub_scores)
        sub_scores["readability"] = readability
        overall = self._weighted_overall(sub_scores)
        assessment = QualityAssessment(
            evidence_id=evidence_id,
            case_id=case_id,
            source_file=source_file,
            metrics=metrics,
            sub_scores={k: round(v, 1) for k, v in sub_scores.items()},
            overall_score=round(overall, 1),
            quality_grade=self._grade(overall),
            expected_ocr_accuracy=round(self._expected_ocr_accuracy(overall), 1),
            readability_score=round(readability, 1),
            recommended_operations=self._recommendations(metrics, sub_scores),
            notes=self._notes(metrics),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )

        if persist:
            self._repo.save(
                evidence_id, case_id,
                self._cfg.quality_report_name, assessment.model_dump(),
            )
            self._audit.record(
                case_id, evidence_id, MODULE, "assessed",
                f"score={assessment.overall_score} grade={assessment.quality_grade} "
                f"expected_ocr={assessment.expected_ocr_accuracy}%",
                duration_ms=assessment.analysis_time_ms,
            )
        return assessment

    # ------------------------------------------------------------ measurements

    @staticmethod
    def _estimate_noise(gray: np.ndarray) -> float:
        denoised = cv2.medianBlur(gray, 3)
        return float(np.mean(cv2.absdiff(gray, denoised)))

    @staticmethod
    def _estimate_skew(gray: np.ndarray) -> float:
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = cv2.findNonZero(thresh)
        if coords is None or len(coords) < 100:
            return 0.0
        angle = cv2.minAreaRect(coords)[-1]
        if angle > 45.0:
            angle -= 90.0
        return float(angle) if abs(angle) <= 15.0 else 0.0

    def _estimate_compression_quality(
        self, gray: np.ndarray, source_path: Path | None
    ) -> float:
        """Estimate JPEG quality; non-JPEG sources are treated as lossless.

        Primary method: mean of the luminance quantisation table (small mean
        => high quality). Fallback: 8x8 blockiness measurement.
        """
        if source_path is not None and source_path.suffix.lower() in (".jpg", ".jpeg"):
            try:
                with Image.open(source_path) as img:
                    tables = getattr(img, "quantization", None)
                    if tables:
                        mean_q = float(np.mean(list(tables.values())[0]))
                        # mean_q ~1 => quality ~100; mean_q ~90 => quality ~10
                        return float(np.clip(105.0 - mean_q * 1.05, 5.0, 100.0))
            except OSError:  # unreadable header - fall through to blockiness
                pass
            return float(np.clip(100.0 - self._blockiness(gray) * 8.0, 5.0, 100.0))
        return 100.0

    @staticmethod
    def _blockiness(gray: np.ndarray) -> float:
        """Mean discontinuity across 8-pixel JPEG block boundaries."""
        g = gray.astype(np.float32)
        h, w = g.shape
        if h < 17 or w < 17:
            return 0.0
        col_idx = np.arange(8, w - 1, 8)
        row_idx = np.arange(8, h - 1, 8)
        v = float(np.mean(np.abs(g[:, col_idx] - g[:, col_idx - 1])))
        hz = float(np.mean(np.abs(g[row_idx, :] - g[row_idx - 1, :])))
        # subtract typical natural-gradient magnitude
        natural = float(np.mean(np.abs(np.diff(g, axis=1))))
        return max(0.0, (v + hz) / 2.0 - natural)

    @staticmethod
    def _edge_density(gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 60, 180)
        return float(np.count_nonzero(edges)) / float(edges.size)

    @staticmethod
    def _count_text_like_components(gray: np.ndarray) -> int:
        """Connected components whose geometry resembles characters/words."""
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 15,
        )
        count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        h_img = gray.shape[0]
        text_like = 0
        for i in range(1, count):
            w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            if 4 <= h <= h_img * 0.2 and w <= h * 25 and h <= w * 25:
                text_like += 1
        return int(text_like)

    # ---------------------------------------------------------------- scoring

    def _sub_scores(self, m: QualityMetrics) -> Dict[str, float]:
        cfg = self._cfg
        scores: Dict[str, float] = {}
        scores["blur"] = _ramp(m.blur_laplacian_variance, cfg.blur_unusable, cfg.blur_excellent)
        lo, hi = cfg.brightness_ideal
        if lo <= m.brightness_mean <= hi:
            scores["brightness"] = 100.0
        elif m.brightness_mean < lo:
            scores["brightness"] = _ramp(m.brightness_mean, 15.0, lo)
        else:
            scores["brightness"] = _ramp(255.0 - m.brightness_mean, 3.0, 255.0 - hi)
        scores["contrast"] = _ramp(m.contrast_std, 8.0, cfg.contrast_excellent)
        scores["noise"] = 100.0 - _ramp(m.noise_residual, cfg.noise_negligible, cfg.noise_unusable)
        scores["resolution"] = _ramp(
            float(min(m.width, m.height)),
            float(cfg.resolution_minimum_px), float(cfg.resolution_adequate_px),
        )
        scores["skew"] = 100.0 - _ramp(abs(m.skew_angle_deg), cfg.skew_tolerance_deg, 10.0)
        scores["compression"] = m.compression_quality
        return scores

    def _readability_score(self, m: QualityMetrics, sub: Dict[str, float]) -> float:
        """Composite of edge structure, text-like components and clarity."""
        structure = min(100.0, m.text_like_components / 3.0)
        edges = _ramp(m.edge_density, 0.005, 0.06)
        clarity = (sub["blur"] + sub["contrast"] + sub["noise"]) / 3.0
        return 0.35 * structure + 0.25 * edges + 0.40 * clarity

    def _weighted_overall(self, sub: Dict[str, float]) -> float:
        weights = self._cfg.quality_weights
        total_w = sum(weights.get(k, 0.0) for k in sub)
        if total_w <= 0:
            return 0.0
        return sum(sub[k] * weights.get(k, 0.0) for k in sub) / total_w

    @staticmethod
    def _grade(score: float) -> str:
        for grade, ceiling in (("UNUSABLE", 25.0), ("POOR", 45.0),
                               ("FAIR", 65.0), ("GOOD", 82.0)):
            if score < ceiling:
                return grade
        return "EXCELLENT"

    @staticmethod
    def _expected_ocr_accuracy(score: float) -> float:
        """Empirical monotone mapping quality score -> expected OCR accuracy."""
        points: List[Tuple[float, float]] = [
            (0.0, 5.0), (25.0, 35.0), (45.0, 62.0),
            (65.0, 82.0), (82.0, 93.0), (100.0, 98.5),
        ]
        return float(np.interp(score, [p[0] for p in points], [p[1] for p in points]))

    # ---------------------------------------------------------- recommendations

    def _recommendations(self, m: QualityMetrics, sub: Dict[str, float]) -> List[str]:
        """Operation names consumed by the Module-2 preprocessing planner."""
        cfg = self._cfg
        ops: List[str] = []
        if sub["noise"] < cfg.op_trigger_score:
            ops.append("adaptive_denoise")
        if sub["brightness"] < cfg.op_trigger_score:
            ops.append("illumination_correction")
            if m.brightness_mean > sum(cfg.brightness_ideal) / 2:
                ops.append("shadow_removal")
        if sub["contrast"] < cfg.op_trigger_score:
            ops.append("clahe")
        if abs(m.skew_angle_deg) >= cfg.skew_tolerance_deg:
            ops.append("deskew")
        if sub["blur"] < cfg.op_trigger_score:
            ops.append("edge_enhancement")
        if min(m.width, m.height) < cfg.super_resolution_trigger_px:
            ops.append("super_resolution")
        if sub["compression"] < cfg.op_trigger_score:
            ops.append("adaptive_denoise") if "adaptive_denoise" not in ops else None
        # perspective/morphology are content-conditional; the planner probes them
        ops.append("perspective_correction")
        if sub["contrast"] < cfg.op_trigger_score and sub["noise"] < cfg.op_trigger_score:
            ops.append("morphological_cleanup")
        # de-duplicate preserving order
        seen: set = set()
        return [op for op in ops if not (op in seen or seen.add(op))]

    def _notes(self, m: QualityMetrics) -> List[str]:
        notes: List[str] = []
        if m.blur_laplacian_variance < self._cfg.blur_unusable * 2:
            notes.append("Severe blur detected - OCR output may be unreliable.")
        if m.compression_quality < self._cfg.jpeg_quality_poor:
            notes.append("Heavy JPEG compression - character edges may be damaged.")
        if min(m.width, m.height) < self._cfg.resolution_minimum_px:
            notes.append("Resolution below forensic minimum for dependable OCR.")
        if m.text_like_components < 5:
            notes.append("Few text-like structures found - image may contain little text.")
        return notes


def _ramp(value: float, floor: float, ceiling: float) -> float:
    """Linear 0-100 ramp: <=floor -> 0, >=ceiling -> 100."""
    if ceiling <= floor:
        return 100.0 if value >= ceiling else 0.0
    return float(np.clip((value - floor) / (ceiling - floor) * 100.0, 0.0, 100.0))
