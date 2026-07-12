"""Professional logging for the evidence engine.

Provides a single ``get_logger`` factory (console + rotating file handler)
and a :class:`StageTimer` context manager used to measure upload, OCR,
preprocessing and total processing durations.
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured_root = False


def get_logger(name: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """Return a namespaced logger under the ``evidence`` hierarchy.

    The first call configures the shared handlers; later calls reuse them.

    Args:
        name: Sub-component name, e.g. ``"upload"`` or ``"ocr"``.
        log_dir: Directory for the rotating log file (created if missing).
    """
    global _configured_root
    root = logging.getLogger("evidence")
    if not _configured_root:
        root.setLevel(logging.DEBUG)
        formatter = logging.Formatter(_FORMAT)

        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        root.addHandler(console)

        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "evidence_engine.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        _configured_root = True
    return root.getChild(name)


class StageTimer:
    """Context manager that measures a processing stage in milliseconds.

    Example::

        with StageTimer(logger, "ocr") as timer:
            result = ocr.recognize(image)
        duration = timer.elapsed_ms
    """

    def __init__(self, logger: logging.Logger, stage: str) -> None:
        self._logger = logger
        self.stage = stage
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "StageTimer":
        self._start = time.perf_counter()
        self._logger.debug("stage '%s' started", self.stage)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        if exc is None:
            self._logger.info("stage '%s' finished in %.1f ms", self.stage, self.elapsed_ms)
        else:
            self._logger.error(
                "stage '%s' failed after %.1f ms: %s", self.stage, self.elapsed_ms, exc
            )
