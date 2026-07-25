"""End-to-end evidence processing pipeline (composition root helper).

Orchestrates: upload -> hash(before) -> preprocessing -> OCR (per page) ->
hash(after) + verification -> CSV + JSON storage. All collaborators are
injected, so any component (notably the OCR engine) can be swapped without
modifying this class.

This module performs acquisition, hashing, preprocessing, OCR and storage
ONLY - no text cleaning, language detection, entity extraction, phishing
detection or threat intelligence (later modules).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from .config import EvidenceConfig
from .csv_storage import (
    CaseRepository,
    EvidenceRepository,
    OCRResultRepository,
    ProcessingLogRepository,
)
from .hash_service import HashService
from .json_storage import JSONCaseStorage
from .logger import StageTimer, get_logger
from .models import EvidenceRecord, OCRLine, OCRPageResult
from .ocr_interface import BaseOCR
from .pdf_processor import PDFProcessor
from .preprocessing import ImagePreprocessor, load_image
from .schemas import EvidenceOCRResult, PageResult
from .upload import EvidenceUploader
from .utils import EmptyOCRError, EvidenceError, file_extension, utc_now_iso


class EvidencePipeline:
    """Coordinates the full acquisition + OCR workflow for one evidence file."""

    def __init__(
        self,
        config: EvidenceConfig,
        ocr_engine: BaseOCR,
        *,
        hash_service: Optional[HashService] = None,
        preprocessor: Optional[ImagePreprocessor] = None,
        pdf_processor: Optional[PDFProcessor] = None,
        case_repo: Optional[CaseRepository] = None,
        evidence_repo: Optional[EvidenceRepository] = None,
        ocr_repo: Optional[OCRResultRepository] = None,
        log_repo: Optional[ProcessingLogRepository] = None,
        json_storage: Optional[JSONCaseStorage] = None,
        uploader: Optional[EvidenceUploader] = None,
    ) -> None:
        config.ensure_directories()
        self._cfg = config
        self._ocr = ocr_engine
        self._hash = hash_service or HashService()
        self._preprocessor = preprocessor or ImagePreprocessor(config)
        self._pdf = pdf_processor or PDFProcessor(config)
        self._cases = case_repo or CaseRepository(config)
        self._evidence = evidence_repo or EvidenceRepository(config)
        self._ocr_results = ocr_repo or OCRResultRepository(config)
        self._audit = log_repo or ProcessingLogRepository(config)
        self._json = json_storage or JSONCaseStorage(config)
        self._uploader = uploader or EvidenceUploader(
            config, self._hash, self._evidence, self._audit
        )
        self._log = get_logger("pipeline", config.log_dir)

    # ------------------------------------------------------------------ public

    def process_file(
        self,
        source: Path | str,
        case_id: Optional[str] = None,
        notes: str = "",
        case_title: str = "",
    ) -> EvidenceOCRResult:
        """Acquire and OCR one evidence file, returning the structured result.

        Args:
            source: Path to the evidence file (PNG/JPEG/JPG/PDF/TXT/CSV/DOCX).
            case_id: Existing case to attach the evidence to. When ``None``
                a new case is created automatically.
            notes: Investigator notes for the evidence row (empty by default).
            case_title: Title used only when a new case is created.

        Returns:
            :class:`EvidenceOCRResult` - also persisted to CSV and case JSON.
        """
        started = time.perf_counter()
        case_id = self._resolve_case(case_id, case_title)
        record = self._uploader.upload(source, case_id, notes)
        stored = self._uploader.stored_path(record)

        try:
            pages = self._extract_pages(stored, record)
            self._check_empty(pages, record)
            result = self._finalise(record, pages, started)
            return result
        except EvidenceError:
            self._mark_failed(record)
            raise
        except Exception as exc:  # noqa: BLE001 - normalise unexpected failures
            self._mark_failed(record)
            self._audit.log_stage(
                case_id, record.evidence_id, "pipeline",
                f"unexpected failure: {exc}", level="ERROR",
            )
            raise EvidenceError(f"Processing failed for '{record.original_file_name}': {exc}") from exc

    # ------------------------------------------------------- extraction stages

    def _extract_pages(self, stored: Path, record: EvidenceRecord) -> List[OCRPageResult]:
        """Dispatch to the correct extractor based on evidence type."""
        extension = record.file_extension
        if extension in self._cfg.image_extensions:
            return [self._ocr_image_page(load_image(stored), 1, record)]
        if extension == ".pdf":
            return self._extract_pdf(stored, record)
        if extension in self._cfg.text_extensions:
            return [self._extract_plain_text(stored, record)]
        if extension == ".docx":
            return [self._extract_docx(stored, record)]
        if extension == ".url":
            return [self._extract_url(stored, record)]
        raise EvidenceError(f"No extractor for '{extension}'")  # defensive; upload validates

    def _ocr_image_page(
        self, image, page_number: int, record: EvidenceRecord
    ) -> OCRPageResult:
        """Preprocess one image and run OCR, keeping the verbatim output."""
        with StageTimer(self._log, f"preprocess p{page_number}") as pre_timer:
            processed, steps = self._preprocessor.preprocess(image)
        self._audit.log_stage(
            record.case_id, record.evidence_id, "preprocessing",
            f"page {page_number}: {', '.join(steps)}", duration_ms=pre_timer.elapsed_ms,
        )
        with StageTimer(self._log, f"ocr p{page_number}") as ocr_timer:
            lines = self._ocr.recognize(processed)
        self._audit.log_stage(
            record.case_id, record.evidence_id, "ocr",
            f"page {page_number}: {len(lines)} lines via {self._ocr.name}",
            duration_ms=ocr_timer.elapsed_ms,
        )
        return OCRPageResult(
            page_number=page_number,
            lines=lines,
            processing_time_ms=round(pre_timer.elapsed_ms + ocr_timer.elapsed_ms, 1),
            preprocessing_steps=steps,
        )

    def _extract_pdf(self, stored: Path, record: EvidenceRecord) -> List[OCRPageResult]:
        """Hybrid PDF extraction: embedded text first, OCR only when needed.

        A digital PDF carries its text verbatim, so reading that text layer is
        exact and fast; running OCR over a rendered image of it would be slower
        and *less* accurate. Pages with no usable text layer (i.e. scanned
        images) fall back to render + OCR, so scanned evidence still works.
        Page order is preserved either way.
        """
        text_pages: dict[int, str] = {}
        try:
            for page_number, text in self._pdf.iter_page_text(stored):
                text_pages[page_number] = text or ""
        except Exception as exc:  # noqa: BLE001 - fall back to OCR wholesale
            self._log.warning("PDF text layer unavailable (%s); using OCR", exc)

        pages: List[OCRPageResult] = []
        needs_ocr: List[int] = []
        for page_number, text in sorted(text_pages.items()):
            if len(text.strip()) >= self._cfg.pdf_text_layer_min_chars:
                lines = [OCRLine(text=ln, confidence=1.0)
                         for ln in text.splitlines() if ln.strip()]
                self._audit.log_stage(
                    record.case_id, record.evidence_id, "ocr",
                    f"page {page_number}: {len(lines)} lines from PDF text layer "
                    "(no OCR needed)",
                )
                pages.append(OCRPageResult(
                    page_number=page_number, lines=lines,
                    preprocessing_steps=["none(pdf_text_layer)"],
                ))
            else:
                needs_ocr.append(page_number)

        # Scanned pages (and the whole file if the text layer was unreadable).
        if needs_ocr or not text_pages:
            wanted = set(needs_ocr)
            for page_number, image in self._pdf.iter_page_images(stored):
                if text_pages and page_number not in wanted:
                    continue
                pages.append(self._ocr_image_page(image, page_number, record))

        pages.sort(key=lambda p: p.page_number)  # guarantee page order on merge
        return pages

    def _extract_plain_text(self, stored: Path, record: EvidenceRecord) -> OCRPageResult:
        """TXT/CSV evidence needs no OCR - content is stored verbatim."""
        text = stored.read_text(encoding="utf-8", errors="replace")
        lines = [OCRLine(text=ln, confidence=1.0) for ln in text.splitlines()]
        self._audit.log_stage(
            record.case_id, record.evidence_id, "ocr",
            f"plain-text evidence: {len(lines)} lines read directly",
        )
        return OCRPageResult(page_number=1, lines=lines, preprocessing_steps=["none(text_file)"])

    def _extract_url(self, stored: Path, record: EvidenceRecord) -> OCRPageResult:
        """URL evidence: the link (plus any captured page text) read verbatim.

        A submitted link is persisted as a ``.url`` text artifact, so it flows
        through the identical acquisition path as a file: hashed for chain of
        custody, stored, and read here without OCR. The URL then surfaces as a
        ``urls`` entity, which is what lets threat intelligence score it and
        cross-case correlation match it against other cases.
        """
        text = stored.read_text(encoding="utf-8", errors="replace")
        lines = [OCRLine(text=ln, confidence=1.0)
                 for ln in text.splitlines() if ln.strip()]
        self._audit.log_stage(
            record.case_id, record.evidence_id, "ocr",
            f"URL evidence: {len(lines)} line(s) read directly (no OCR)",
        )
        return OCRPageResult(page_number=1, lines=lines,
                             preprocessing_steps=["none(url)"])

    def _extract_docx(self, stored: Path, record: EvidenceRecord) -> OCRPageResult:
        """Optional DOCX support via python-docx (text extracted verbatim)."""
        try:
            import docx  # python-docx - optional dependency
        except ImportError as exc:
            raise EvidenceError(
                "DOCX support requires python-docx (pip install python-docx)"
            ) from exc
        try:
            document = docx.Document(str(stored))
        except Exception as exc:  # noqa: BLE001
            raise EvidenceError(f"Corrupted DOCX '{record.original_file_name}': {exc}") from exc
        lines = [
            OCRLine(text=para.text, confidence=1.0)
            for para in document.paragraphs
            if para.text
        ]
        self._audit.log_stage(
            record.case_id, record.evidence_id, "ocr",
            f"docx evidence: {len(lines)} paragraphs extracted",
        )
        return OCRPageResult(page_number=1, lines=lines, preprocessing_steps=["none(docx)"])

    # ------------------------------------------------------------ finalisation

    def _resolve_case(self, case_id: Optional[str], title: str) -> str:
        """Use the existing case or create a new one with a fresh CASE id."""
        if case_id:
            if self._cases.get(case_id) is None:
                raise EvidenceError(f"Unknown case '{case_id}'")
            return case_id
        return self._cases.create(title=title).case_id

    def _check_empty(self, pages: List[OCRPageResult], record: EvidenceRecord) -> None:
        """Empty OCR handling: warn (default) or raise in strict mode."""
        if any(page.lines for page in pages):
            return
        message = f"OCR produced no text for '{record.original_file_name}'"
        self._audit.log_stage(
            record.case_id, record.evidence_id, "ocr", message, level="WARNING"
        )
        self._log.warning(message)
        if self._cfg.strict_empty_ocr:
            raise EmptyOCRError(message)

    def _finalise(
        self, record: EvidenceRecord, pages: List[OCRPageResult], started: float
    ) -> EvidenceOCRResult:
        """Post-processing hash verification, then persist CSV + JSON."""
        stored = self._uploader.stored_path(record)

        # Forensic integrity: re-hash after processing; must match pre-hash.
        with StageTimer(self._log, "hash-verify") as hash_timer:
            sha_after = self._hash.sha256_file(stored)
            verified = sha_after.lower() == record.sha256_before.lower()
        record.sha256_after = sha_after
        record.hash_verified = verified
        record.processing_time = utc_now_iso()
        record.status = "processed" if verified else "failed"
        self._audit.log_stage(
            record.case_id, record.evidence_id, "hashing",
            f"post-processing hash {'VERIFIED' if verified else 'MISMATCH'}",
            level="INFO" if verified else "ERROR",
            duration_ms=hash_timer.elapsed_ms,
        )
        self._evidence.update(record)

        total_ms = round((time.perf_counter() - started) * 1000.0, 1)
        result = EvidenceOCRResult(
            case_id=record.case_id,
            evidence_id=record.evidence_id,
            file_name=record.original_file_name,
            file_hash=record.sha256_before,
            file_size=str(record.file_size_bytes),
            upload_time=record.upload_time,
            processing_time_ms=total_ms,
            pages=[PageResult.from_page(page) for page in pages],
            hash_verified=verified,
            ocr_engine=self._ocr.name,
        )
        result.build_raw_text()

        json_path = self._json.save_result(result)
        self._ocr_results.add_summary(
            evidence_id=record.evidence_id,
            case_id=record.case_id,
            ocr_engine=self._ocr.name,
            page_count=len(result.pages),
            line_count=sum(len(p.lines) for p in result.pages),
            average_confidence=result.average_confidence,
            processing_time_ms=total_ms,
            raw_text=result.raw_text,
            json_file=json_path.name,
        )
        self._cases.increment_evidence_count(record.case_id)
        self._audit.log_stage(
            record.case_id, record.evidence_id, "pipeline",
            f"completed: {len(result.pages)} page(s), "
            f"avg confidence {result.average_confidence:.2f}",
            duration_ms=total_ms,
        )
        self._log.info(
            "evidence %s processed in %.0f ms (%d pages)",
            record.evidence_id, total_ms, len(result.pages),
        )
        return result

    def _mark_failed(self, record: EvidenceRecord) -> None:
        """Graceful recovery: keep the chain-of-custody row, flag it failed."""
        record.status = "failed"
        record.processing_time = utc_now_iso()
        try:
            self._evidence.update(record)
        except EvidenceError:  # storage itself failing must not mask the cause
            self._log.exception("could not mark %s as failed", record.evidence_id)
