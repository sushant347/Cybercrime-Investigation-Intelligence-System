# OCR & Entity Ground-Truth Corpus

This folder holds the **labelled ground-truth** used to compute the project's
headline research metrics:

* **OCR accuracy** — Character Error Rate (CER) and Word Error Rate (WER),
  via `scripts/benchmark_ocr.py` → `backend/modules/evidence/evaluation/ocr_metrics.py`.
* **Entity extraction** — Precision / Recall / F1 per entity type,
  via `scripts/benchmark_entities.py` → `evaluation/entity_metrics.py`.

> **Important — these are methodology harnesses, not pre-baked results.**
> The two `*_example.*` files below are a small *worked example* so the scripts
> run and are unit-tested end to end. The numbers they produce are illustrative
> only. **Defensible research numbers require a real, human-annotated corpus**
> (target: 30–100 representative samples, English + Nepali/Devanagari). Build it
> as described below, then point the scripts at your real manifest.

## Files

| File | Purpose |
|---|---|
| `ocr_manifest_example.json` | Worked example for the CER/WER harness (reference + hypothesis pairs). |
| `entities_gold_example.json` | Worked example for the entity P/R/F1 harness. |

## Building the real corpus

### OCR (CER/WER)

1. Collect representative evidence images (screenshots, scans, photos) covering
   the languages and quality levels you claim to support.
2. For each image, a human transcribes the **exact** visible text verbatim — no
   correction, translation, or reordering. Save one manifest entry:
   ```json
   {"id": "img_001", "reference": "…exact transcript…", "image": "samples/img_001.png"}
   ```
3. Run: `python scripts/benchmark_ocr.py --manifest <your_manifest>.json --out results/ocr_benchmark.json`
   (items with an `image` and no `hypothesis` run live OCR; items with a
   `hypothesis` are scored directly — useful for CI without a PaddleOCR install).

### Entity extraction (P/R/F1)

1. From the same corpus, a human lists the **true** entities per evidence item,
   keyed by `evidence_id`:
   ```json
   {"EVID_00001": {"urls": ["http://…"], "emails": ["a@b.com"], "phones": ["+977…"]}}
   ```
2. Run the pipeline so predictions land in `storage/entities.csv`.
3. Run: `python scripts/benchmark_entities.py --gold <gold>.json --out results/entity_benchmark.json`

## Reproducibility rules (record these next to any reported number)

* **Normalization (OCR):** Unicode NFC, lowercase, whitespace collapsed
  (defaults in `normalize_text`). Report if you deviate.
* **Matching (entities):** set-based per `(type, value)` with per-type
  normalization (URLs ignore a trailing slash; phone/eSewa ids compared on
  `+`/digits only). See `default_normalizer`.
* **Averaging:** report the full per-sample distribution (min/mean/median/max),
  not just the best case; report entity F1 both **micro** and **macro**.
* **Annotation quality:** for a subset, have a second annotator label
  independently and report agreement.
