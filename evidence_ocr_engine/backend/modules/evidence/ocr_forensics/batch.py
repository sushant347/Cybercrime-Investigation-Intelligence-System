"""Batch OCR-forensics processing over a folder.

Processes every supported image in a directory in parallel (configurable
worker count), reports progress via an optional callback, and continues on
per-file failure - one bad file never aborts the batch.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Sequence

from ..logger import get_logger
from .analyzer import OCRForensicAnalyzer
from .config import OCRForensicConfig

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

#: A callable that runs OCR on one image and returns pages (text/conf/bbox).
OCRFn = Callable[[Path], Sequence[Mapping[str, Any]]]


@dataclass
class BatchItemResult:
    """Outcome for one file in a batch."""

    path: str
    ok: bool
    metadata: Optional[Any] = None      # OCRForensicMetadata when ok
    error: str = ""


@dataclass
class BatchReport:
    """Aggregate outcome of a batch run."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: List[BatchItemResult] = field(default_factory=list)


class BatchProcessor:
    """Parallel, fault-tolerant folder processor for OCR forensic metadata."""

    def __init__(
        self,
        ocr_fn: OCRFn,
        config: Optional[OCRForensicConfig] = None,
        analyzer: Optional[OCRForensicAnalyzer] = None,
    ) -> None:
        self._ocr = ocr_fn
        self._cfg = config or OCRForensicConfig()
        self._analyzer = analyzer or OCRForensicAnalyzer(self._cfg)
        self._log = get_logger("ocr_forensics.batch")

    def process_folder(
        self,
        folder: Path | str,
        progress: Optional[Callable[[int, int, str], None]] = None,
        recursive: bool = False,
    ) -> BatchReport:
        """Process every image under ``folder``; never aborts on one failure."""
        paths = self._discover(Path(folder), recursive)
        report = BatchReport(total=len(paths))
        if not paths:
            return report

        done = 0
        with ThreadPoolExecutor(max_workers=max(1, self._cfg.batch_workers)) as pool:
            futures = {pool.submit(self._process_one, p): p for p in paths}
            for future in as_completed(futures):
                item = future.result()  # _process_one never raises
                report.results.append(item)
                report.succeeded += int(item.ok)
                report.failed += int(not item.ok)
                done += 1
                if progress is not None:
                    progress(done, report.total, item.path)

        report.results.sort(key=lambda r: r.path)
        self._log.info("batch complete: %d ok, %d failed of %d",
                       report.succeeded, report.failed, report.total)
        return report

    # ---------------------------------------------------------------- internal

    def _process_one(self, path: Path) -> BatchItemResult:
        try:
            pages = self._ocr(path)
            metadata = self._analyzer.analyze(pages, image_path=path,
                                              evidence_id=path.name)
            return BatchItemResult(str(path), True, metadata)
        except Exception as exc:  # noqa: BLE001 - graceful per-file failure
            self._log.warning("batch item failed (%s): %s", path, exc)
            return BatchItemResult(str(path), False, error=str(exc))

    @staticmethod
    def _discover(folder: Path, recursive: bool) -> List[Path]:
        if not folder.is_dir():
            return []
        it = folder.rglob("*") if recursive else folder.iterdir()
        return sorted(p for p in it if p.suffix.lower() in _IMAGE_EXTENSIONS)
