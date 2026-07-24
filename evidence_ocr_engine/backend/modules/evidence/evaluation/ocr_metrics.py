"""OCR accuracy metrics: Character Error Rate (CER) and Word Error Rate (WER).

Both metrics are edit-distance based and follow the standard ASR/OCR
definitions::

    CER = (S_c + D_c + I_c) / N_c        (character level)
    WER = (S_w + D_w + I_w) / N_w        (word level)

where ``S``/``D``/``I`` are substitutions/deletions/insertions from the
Levenshtein alignment of hypothesis (OCR output) against reference (ground
truth), and ``N`` is the number of reference characters/words. A perfect
transcription scores 0.0; the value can exceed 1.0 when the hypothesis is much
longer than the reference (many insertions).

**Normalization is explicit and reproducible** (see :func:`normalize_text`):
callers choose whether case, surrounding whitespace, and Unicode form are
folded, and the choice is recorded next to the numbers. This matters for a
dual-script (English + Nepali/Devanagari) corpus, where NFC normalization
avoids spurious errors from combining-character differences.

No third-party dependency is required (a small pure-Python Levenshtein is
included); if ``jiwer`` is installed it is *not* used, so numbers are stable
across environments.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Sequence


# --------------------------------------------------------------- normalization
def normalize_text(
    text: str,
    *,
    lowercase: bool = True,
    collapse_whitespace: bool = True,
    strip: bool = True,
    unicode_form: str = "NFC",
) -> str:
    """Apply the documented, reproducible normalization to one string.

    Args:
        text: raw string (reference or hypothesis).
        lowercase: fold case (recommended for OCR accuracy of Latin script).
        collapse_whitespace: collapse runs of whitespace to a single space.
        strip: strip leading/trailing whitespace.
        unicode_form: Unicode normalization form (``NFC`` recommended so
            Devanagari combining sequences compare equal).

    Returns:
        The normalized string.
    """
    if unicode_form:
        text = unicodedata.normalize(unicode_form, text)
    if lowercase:
        text = text.lower()
    if collapse_whitespace:
        text = " ".join(text.split())
    if strip:
        text = text.strip()
    return text


# ------------------------------------------------------------- edit distance
def levenshtein(a: Sequence, b: Sequence) -> int:
    """Levenshtein (edit) distance between two sequences.

    Works on any sequence of hashables (characters for CER, tokens for WER).
    O(len(a) * len(b)) time, O(min(len)) space.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Ensure b is the shorter row for lower memory use.
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(
                min(
                    previous[j] + 1,        # deletion
                    current[j - 1] + 1,     # insertion
                    previous[j - 1] + cost,  # substitution / match
                )
            )
        previous = current
    return previous[-1]


# ----------------------------------------------------------------- single-pair
def character_error_rate(
    reference: str, hypothesis: str, *, normalize: bool = True, **norm_kwargs
) -> float:
    """CER for one (reference, hypothesis) pair.

    An empty reference returns 0.0 when the hypothesis is also empty, else 1.0
    (fully inserted) to avoid division by zero.
    """
    if normalize:
        reference = normalize_text(reference, **norm_kwargs)
        hypothesis = normalize_text(hypothesis, **norm_kwargs)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein(list(reference), list(hypothesis)) / len(reference)


def word_error_rate(
    reference: str, hypothesis: str, *, normalize: bool = True, **norm_kwargs
) -> float:
    """WER for one (reference, hypothesis) pair (whitespace tokenization)."""
    if normalize:
        reference = normalize_text(reference, **norm_kwargs)
        hypothesis = normalize_text(hypothesis, **norm_kwargs)
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return levenshtein(ref_words, hyp_words) / len(ref_words)


# --------------------------------------------------------------------- corpus
@dataclass
class OCRMetrics:
    """Aggregate OCR accuracy over a labelled corpus.

    ``cer``/``wer`` are *micro-averaged* (total edits / total reference units),
    which is the standard headline number. Per-sample rates are retained so a
    full distribution can be reported instead of a single cherry-picked value.
    """

    samples: int = 0
    cer: float = 0.0
    wer: float = 0.0
    char_accuracy: float = 0.0
    word_accuracy: float = 0.0
    per_sample_cer: List[float] = field(default_factory=list)
    per_sample_wer: List[float] = field(default_factory=list)
    normalization: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        def _dist(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}
            ordered = sorted(values)
            mid = len(ordered) // 2
            median = (
                ordered[mid]
                if len(ordered) % 2
                else (ordered[mid - 1] + ordered[mid]) / 2
            )
            return {
                "min": round(ordered[0], 4),
                "max": round(ordered[-1], 4),
                "mean": round(sum(ordered) / len(ordered), 4),
                "median": round(median, 4),
            }

        return {
            "samples": self.samples,
            "cer": round(self.cer, 4),
            "wer": round(self.wer, 4),
            "char_accuracy": round(self.char_accuracy, 4),
            "word_accuracy": round(self.word_accuracy, 4),
            "cer_distribution": _dist(self.per_sample_cer),
            "wer_distribution": _dist(self.per_sample_wer),
            "normalization": self.normalization,
        }


def corpus_ocr_metrics(
    pairs: Sequence[tuple[str, str]], *, normalize: bool = True, **norm_kwargs
) -> OCRMetrics:
    """Compute micro-averaged CER/WER over ``(reference, hypothesis)`` pairs.

    Args:
        pairs: sequence of ``(reference, hypothesis)`` transcripts.
        normalize: apply :func:`normalize_text` to both sides first.
        **norm_kwargs: forwarded to :func:`normalize_text`.

    Returns:
        An :class:`OCRMetrics` with micro-averaged rates and per-sample lists.
    """
    total_char_edits = total_chars = 0
    total_word_edits = total_words = 0
    result = OCRMetrics()
    for reference, hypothesis in pairs:
        ref = normalize_text(reference, **norm_kwargs) if normalize else reference
        hyp = normalize_text(hypothesis, **norm_kwargs) if normalize else hypothesis
        ref_chars = list(ref)
        char_edits = levenshtein(ref_chars, list(hyp))
        word_edits = levenshtein(ref.split(), hyp.split())
        n_chars = len(ref_chars) or (0 if not hyp else len(hyp))
        n_words = len(ref.split()) or (0 if not hyp else len(hyp.split()))

        total_char_edits += char_edits
        total_chars += len(ref_chars)
        total_word_edits += word_edits
        total_words += len(ref.split())

        result.per_sample_cer.append(char_edits / n_chars if n_chars else 0.0)
        result.per_sample_wer.append(word_edits / n_words if n_words else 0.0)
        result.samples += 1

    result.cer = total_char_edits / total_chars if total_chars else 0.0
    result.wer = total_word_edits / total_words if total_words else 0.0
    result.char_accuracy = max(0.0, 1.0 - result.cer)
    result.word_accuracy = max(0.0, 1.0 - result.wer)
    result.normalization = {
        "applied": normalize,
        **({"params": norm_kwargs} if norm_kwargs else {}),
    }
    return result
