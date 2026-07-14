"""Module 5 - Logo & Brand Detection service.

Detects application/brand presence inside screenshot evidence using three
complementary strategies (strongest available evidence wins per brand):

1. **Template matching** - multi-scale ``cv2.matchTemplate`` against logo
   template images the investigator drops into
   ``storage/forensics/logo_templates/<brand>/``. Highest confidence.
2. **Colour signature** - brand-coloured regions (HSV ranges from the
   registry) of meaningful size, e.g. the eSewa green header bar.
3. **OCR keyword** - brand keywords found in the OCR text (bounding box of
   the matching OCR line when available).

The module *complements* OCR: detections carry brand, confidence, bbox and a
UTC timestamp, and are stored separately as ``logo_detections.json``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ...logger import get_logger
from ...models import OCRLine
from ...utils import utc_now_iso
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .models import LogoDetection, LogoDetectionReport
from .registry import BrandDefinition, BrandRegistry

MODULE = "logo_detection"


class LogoDetectionService:
    """Brand/logo detection over screenshot evidence."""

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
        registry: Optional[BrandRegistry] = None,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._registry = registry or BrandRegistry()
        self._log = get_logger("forensics.logos")

    # ------------------------------------------------------------------ public

    def detect(
        self,
        image: np.ndarray,
        *,
        evidence_id: str,
        case_id: str,
        source_file: str,
        ocr_lines: Optional[Sequence[OCRLine]] = None,
        persist: bool = True,
    ) -> LogoDetectionReport:
        """Detect brands in one RGB image, optionally aided by OCR lines."""
        started = time.perf_counter()
        brands = self._registry.all()
        detections: List[LogoDetection] = []

        templates_root = self._cfg.logo_template_dir
        templates_available = templates_root.is_dir() and any(templates_root.iterdir()) \
            if templates_root.exists() else False

        for brand in brands:
            best = self._detect_brand(image, brand, ocr_lines or [], templates_root)
            if best is not None:
                detections.append(best)

        report = LogoDetectionReport(
            evidence_id=evidence_id,
            case_id=case_id,
            source_file=source_file,
            brands_checked=[b.display_name for b in brands],
            detections=detections,
            detected_brands=sorted({d.brand for d in detections}),
            template_assets_available=templates_available,
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(
                evidence_id, case_id, self._cfg.logo_report_name, report.model_dump()
            )
            self._audit.record(
                case_id, evidence_id, MODULE, "detected",
                f"brands={report.detected_brands or 'none'}",
                duration_ms=report.analysis_time_ms,
            )
        return report

    # -------------------------------------------------------------- strategies

    def _detect_brand(
        self,
        image: np.ndarray,
        brand: BrandDefinition,
        ocr_lines: Sequence[OCRLine],
        templates_root: Path,
    ) -> Optional[LogoDetection]:
        """Try strategies strongest-first; return the best single detection."""
        detection = self._template_match(image, brand, templates_root)
        if detection is not None:
            return detection

        keyword_hit = self._keyword_match(brand, ocr_lines)
        colour_hit = self._colour_match(image, brand)

        # Keyword + colour corroboration boosts confidence.
        if keyword_hit is not None and colour_hit is not None:
            keyword_hit.confidence = round(
                min(1.0, keyword_hit.confidence + colour_hit.confidence * 0.5), 4
            )
            keyword_hit.detail += " + corroborating colour signature"
            return keyword_hit
        return keyword_hit or colour_hit

    def _template_match(
        self, image: np.ndarray, brand: BrandDefinition, templates_root: Path
    ) -> Optional[LogoDetection]:
        brand_dir = templates_root / brand.key
        if not brand_dir.is_dir():
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        best: Optional[Tuple[float, List[float], str]] = None
        for template_path in sorted(brand_dir.glob("*.png")) + sorted(brand_dir.glob("*.jpg")):
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue
            for scale in self._cfg.logo_template_scales:
                th = int(template.shape[0] * scale)
                tw = int(template.shape[1] * scale)
                if th < 8 or tw < 8 or th >= gray.shape[0] or tw >= gray.shape[1]:
                    continue
                resized = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val >= self._cfg.logo_template_threshold and (
                    best is None or max_val > best[0]
                ):
                    x, y = max_loc
                    best = (
                        float(max_val),
                        [float(x), float(y), float(x + tw), float(y + th)],
                        f"{template_path.name}@x{scale}",
                    )
        if best is None:
            return None
        return LogoDetection(
            brand=brand.display_name,
            confidence=round(max(best[0], self._cfg.logo_template_confidence_floor), 4),
            bbox=best[1],
            detection_method="template_match",
            detected_at=utc_now_iso(),
            detail=best[2],
        )

    def _keyword_match(
        self, brand: BrandDefinition, ocr_lines: Sequence[OCRLine]
    ) -> Optional[LogoDetection]:
        for line in ocr_lines:
            lowered = line.text.lower()
            for keyword in brand.keywords:
                if keyword in lowered:
                    bbox: List[float] = []
                    if line.bbox:
                        xs = [p[0] for p in line.bbox]
                        ys = [p[1] for p in line.bbox]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]
                    confidence = min(
                        1.0, self._cfg.logo_keyword_confidence + line.confidence * 0.3
                    )
                    return LogoDetection(
                        brand=brand.display_name,
                        confidence=round(confidence, 4),
                        bbox=bbox,
                        detection_method="ocr_keyword",
                        detected_at=utc_now_iso(),
                        detail=f"keyword '{keyword}' in OCR line",
                    )
        return None

    def _colour_match(
        self, image: np.ndarray, brand: BrandDefinition
    ) -> Optional[LogoDetection]:
        if not brand.hsv_ranges:
            return None
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        frame_area = image.shape[0] * image.shape[1]
        mask_total = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in brand.hsv_ranges:
            if tuple(lo) == (0, 0, 0) and tuple(hi) == (0, 0, 0):
                return None  # brand opted out of colour matching
            mask_total |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        mask_total = cv2.morphologyEx(
            mask_total, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)
        )
        contours, _ = cv2.findContours(mask_total, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < self._cfg.logo_colour_min_area_frac * frame_area:
            return None
        x, y, w, h = cv2.boundingRect(largest)
        area_frac = area / frame_area
        confidence = min(0.75, self._cfg.logo_colour_confidence + area_frac * 2.0)
        return LogoDetection(
            brand=brand.display_name,
            confidence=round(confidence, 4),
            bbox=[float(x), float(y), float(x + w), float(y + h)],
            detection_method="colour_signature",
            detected_at=utc_now_iso(),
            detail=f"brand-colour region {area_frac:.1%} of frame",
        )
