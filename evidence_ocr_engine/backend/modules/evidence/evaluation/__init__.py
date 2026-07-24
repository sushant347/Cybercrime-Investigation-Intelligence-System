"""Research evaluation harnesses for the evidence engine.

This package holds the *measurement* code for the project's headline research
claims. It is deliberately separate from the production pipeline so evaluation
never affects forensic processing.

Modules:
    * :mod:`ocr_metrics`    - Character/Word Error Rate (CER/WER) for OCR.
    * :mod:`entity_metrics` - Precision/Recall/F1 for entity extraction.

Every metric is computed against a **labelled ground-truth set** supplied by
the caller (see ``scripts/benchmark_ocr.py`` and ``scripts/benchmark_entities.py``
and the ``samples/ground_truth/`` corpus). The functions here contain no data;
they are reproducible, dependency-light implementations so results can be
regenerated on any machine.
"""

from .ocr_metrics import (
    OCRMetrics,
    character_error_rate,
    corpus_ocr_metrics,
    normalize_text,
    word_error_rate,
)
from .entity_metrics import (
    EntityScore,
    PRF1,
    entity_prf1,
    micro_macro_average,
)

__all__ = [
    "OCRMetrics",
    "character_error_rate",
    "word_error_rate",
    "corpus_ocr_metrics",
    "normalize_text",
    "EntityScore",
    "PRF1",
    "entity_prf1",
    "micro_macro_average",
]
