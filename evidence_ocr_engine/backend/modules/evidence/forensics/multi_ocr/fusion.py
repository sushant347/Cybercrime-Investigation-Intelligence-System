"""Module 3 - Multi-OCR Fusion service.

Runs every available OCR engine independently, stores each raw output and
confidence, compares the outputs, selects the best one, and - when the
line-level evidence justifies it - builds an intelligently merged text.

The legacy pipeline's PaddleOCR result remains the canonical ``raw_text``;
fusion output is stored separately in ``ocr_fusion.json`` and never replaces
any existing storage.
"""

from __future__ import annotations

import time
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Sequence

import numpy as np

from ...logger import get_logger
from ...models import OCRLine
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .engines import OCREngineAdapter
from .models import EngineRun, FusedLine, FusionResult

MODULE = "multi_ocr_fusion"


class MultiOCRFusionService:
    """Executes, compares, selects and merges multi-engine OCR output."""

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
        engines: Sequence[OCREngineAdapter],
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._engines = list(engines)
        self._log = get_logger("forensics.fusion")

    @property
    def enabled(self) -> bool:
        """False when no OCR engine is configured for fusion.

        Fusion is the most expensive Phase-1 module (one full OCR pass per
        engine). A deployment that configures no engines wants it skipped
        entirely - including the advanced preprocessing that exists only to
        feed it - rather than a fusion report over zero engines.
        """
        return bool(self._engines)

    # ------------------------------------------------------------------ public

    def run(
        self,
        image: np.ndarray,
        *,
        evidence_id: str,
        case_id: str,
        page: int = 1,
        persist: bool = True,
    ) -> FusionResult:
        """Full fusion cycle for one image page."""
        started = time.perf_counter()
        runs: Dict[str, EngineRun] = {}
        lines_by_engine: Dict[str, List[OCRLine]] = {}

        for adapter in self._engines:
            run, lines = self._run_engine(adapter, image, evidence_id, case_id, persist)
            runs[adapter.key] = run
            lines_by_engine[adapter.key] = lines

        result = self._fuse(runs, lines_by_engine, evidence_id, case_id, page)
        result.total_time_ms = round((time.perf_counter() - started) * 1000.0, 1)

        if persist:
            self._repo.save(
                evidence_id, case_id,
                self._cfg.ocr_fusion_report_name, result.model_dump(),
            )
            self._audit.record(
                case_id, evidence_id, MODULE, "completed",
                f"selected={result.selected_engine} source={result.final_source} "
                f"confidence={result.final_confidence:.2f}",
                duration_ms=result.total_time_ms,
            )
        return result

    # -------------------------------------------------------------- execution

    def _run_engine(
        self,
        adapter: OCREngineAdapter,
        image: np.ndarray,
        evidence_id: str,
        case_id: str,
        persist: bool,
    ) -> tuple[EngineRun, List[OCRLine]]:
        """One engine, independently; failures never abort the fusion."""
        if not adapter.available:
            if persist:
                self._audit.record(
                    case_id, evidence_id, MODULE, f"engine:{adapter.key}",
                    "unavailable (library or binary not installed)", level="WARNING",
                )
            return EngineRun(engine=adapter.key, available=False), []

        started = time.perf_counter()
        try:
            lines = adapter.recognize(image)
            duration = round((time.perf_counter() - started) * 1000.0, 1)
            confidences = [ln.confidence for ln in lines]
            run = EngineRun(
                engine=adapter.key,
                available=True,
                succeeded=True,
                text="\n".join(ln.text for ln in lines),
                line_confidences=[round(c, 4) for c in confidences],
                average_confidence=round(float(np.mean(confidences)), 4) if confidences else 0.0,
                line_count=len(lines),
                duration_ms=duration,
            )
            if persist:
                self._audit.record(
                    case_id, evidence_id, MODULE, f"engine:{adapter.key}",
                    f"{run.line_count} lines, avg conf {run.average_confidence:.2f}",
                    duration_ms=duration,
                )
            return run, lines
        except Exception as exc:  # noqa: BLE001
            duration = round((time.perf_counter() - started) * 1000.0, 1)
            if persist:
                self._audit.record(
                    case_id, evidence_id, MODULE, f"engine:{adapter.key}",
                    f"failed: {exc}", level="ERROR", duration_ms=duration,
                )
            return EngineRun(
                engine=adapter.key, available=True, succeeded=False,
                error=str(exc), duration_ms=duration,
            ), []

    # ------------------------------------------------------------------ fusion

    def _fuse(
        self,
        runs: Dict[str, EngineRun],
        lines_by_engine: Dict[str, List[OCRLine]],
        evidence_id: str,
        case_id: str,
        page: int,
    ) -> FusionResult:
        succeeded = {k: r for k, r in runs.items() if r.succeeded and r.text.strip()}
        agreement = self._pairwise_agreement(succeeded)
        scores = self._selection_scores(succeeded, agreement)
        selected = max(scores, key=scores.get) if scores else ""

        merged_lines: List[FusedLine] = []
        merged_text = ""
        merge_applied = False
        if selected and len(succeeded) > 1:
            merged_lines, merge_applied = self._merge(
                selected, lines_by_engine
            )
            merged_text = "\n".join(fl.text for fl in merged_lines)

        final_source = "merged" if merge_applied else "selected"
        if merge_applied:
            final_text = merged_text
            final_confidence = (
                float(np.mean([fl.confidence for fl in merged_lines]))
                if merged_lines else 0.0
            )
        else:
            final_text = succeeded[selected].text if selected else ""
            final_confidence = succeeded[selected].average_confidence if selected else 0.0

        paddle_run = runs.get("paddleocr")
        return FusionResult(
            evidence_id=evidence_id,
            case_id=case_id,
            page=page,
            raw_text=paddle_run.text if paddle_run else "",
            paddle_text=paddle_run.text if paddle_run else "",
            easyocr_text=runs["easyocr"].text if "easyocr" in runs else "",
            tesseract_text=runs["tesseract"].text if "tesseract" in runs else "",
            merged_text=merged_text,
            final_text=final_text,
            engine_runs=list(runs.values()),
            engine_confidences={k: r.average_confidence for k, r in runs.items()},
            selection_scores={k: round(v, 4) for k, v in scores.items()},
            pairwise_agreement={k: round(v, 4) for k, v in agreement.items()},
            selected_engine=selected,
            final_source=final_source if final_text else "none",
            final_confidence=round(final_confidence, 4),
            merge_applied=merge_applied,
            merged_lines=merged_lines,
        )

    def _pairwise_agreement(self, runs: Dict[str, EngineRun]) -> Dict[str, float]:
        keys = sorted(runs)
        agreement: Dict[str, float] = {}
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ratio = SequenceMatcher(
                    None, _normalise(runs[a].text), _normalise(runs[b].text)
                ).ratio()
                agreement[f"{a}|{b}"] = ratio
        return agreement

    def _selection_scores(
        self, runs: Dict[str, EngineRun], agreement: Dict[str, float]
    ) -> Dict[str, float]:
        """score = w_conf*confidence + w_agree*mean_agreement + w_cov*coverage."""
        cfg = self._cfg
        if not runs:
            return {}
        max_len = max(len(r.text) for r in runs.values()) or 1
        scores: Dict[str, float] = {}
        for key, run in runs.items():
            agreements = [v for pair, v in agreement.items() if key in pair.split("|")]
            mean_agreement = float(np.mean(agreements)) if agreements else 1.0
            coverage = len(run.text) / max_len
            scores[key] = (
                cfg.fusion_weight_confidence * run.average_confidence
                + cfg.fusion_weight_agreement * mean_agreement
                + cfg.fusion_weight_coverage * coverage
            )
        return scores

    def _merge(
        self,
        selected: str,
        lines_by_engine: Dict[str, List[OCRLine]],
    ) -> tuple[List[FusedLine], bool]:
        """Line-level merge: keep the selected engine's reading order, but
        substitute a line when another engine read the *same* line with a
        confidence that beats it by the configured margin."""
        cfg = self._cfg
        base_lines = lines_by_engine.get(selected, [])
        others = {
            k: v for k, v in lines_by_engine.items() if k != selected and v
        }
        fused: List[FusedLine] = []
        improved = 0
        for line in base_lines:
            best_text, best_conf, best_src = line.text, line.confidence, selected
            for engine, candidates in others.items():
                match = self._best_match(line.text, candidates)
                if match is None:
                    continue
                if match.confidence >= best_conf + cfg.fusion_merge_margin:
                    best_text, best_conf, best_src = match.text, match.confidence, engine
            if best_src != selected:
                improved += 1
            fused.append(FusedLine(
                text=best_text, confidence=round(best_conf, 4), source_engine=best_src
            ))
        return fused, improved > 0

    def _best_match(self, text: str, candidates: List[OCRLine]) -> Optional[OCRLine]:
        best, best_ratio = None, self._cfg.fusion_line_similarity
        norm = _normalise(text)
        for candidate in candidates:
            ratio = SequenceMatcher(None, norm, _normalise(candidate.text)).ratio()
            if ratio >= best_ratio:
                best, best_ratio = candidate, ratio
        return best


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())
