# Evaluation — command runbook

Copy-paste commands to produce each Chapter-6 table. Run from the **repo root**.
Two virtualenvs are used: `.venv-platform` (engine + API) and `.venv-threat` (ML).

Legend: 🟢 works now · 🟡 demo runs now, real numbers need your gold · 🔴 needs data first.

**Quick start — just want to see everything?**
1. Run every computable table at once → `.venv-platform/bin/python run_all_evaluations.py`
2. Read the already-generated results with sources → open **`EVALUATION_RESULTS.md`**
3. Understand what "gold / ground truth" means → open **`EVALUATION.md`**

**How each table works** (same 3 steps everywhere):
`predict` (run the engine on evidence) → `ground truth` (a human writes the correct answer =
the "gold" file) → `score` (a metric compares them). 6.3/6.7/6.8 already have their ground
truth, so they give real numbers. 6.1/6.2/6.4/6.5 ship with a small **demo gold** so they run
out of the box; swap in real gold for thesis numbers (each section shows both).

---

## Everything at once

```bash
.venv-platform/bin/python run_all_evaluations.py
```

Runs every computable table (real 6.3 + 6.7, demo 6.4 + 6.5) and prints a status matrix.

---

## 🟢 Table 6.3 — URL / phishing classification

```bash
cd threat_intelligence_system
../.venv-threat/bin/python scripts/run_table_6_3.py
cd ..
```

Real numbers from the stored retraining report. Does **not** retrain.

---

## 🟢 Table 6.7 — End-to-end processing time

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/aggregate_processing_time.py --case CASE_2CF24DBA5F
cd ..
```

Replace `CASE_2CF24DBA5F` with any analyzed case id. Report-correctness (manual grading):

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/report_review.py --case CASE_2CF24DBA5F --out review.json
# a human fills each "verdict" in review.json, then:
../.venv-platform/bin/python scripts/report_review.py --score review.json
cd ..
```

---

## 🟡 Table 6.4 — Correlation

Demo (runs now on real cases, illustrative labels):

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_4.py --gold samples/ground_truth/correlation_gold_example.json
cd ..
```

Real numbers — first fill the gold, then run:

```bash
cp evidence_ocr_engine/samples/ground_truth/correlation_gold_template.json \
   evidence_ocr_engine/samples/ground_truth/correlation_gold.json
# edit correlation_gold.json: list evidence-id pairs a human judges related
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_4.py --gold samples/ground_truth/correlation_gold.json
cd ..
```

---

## 🟡 Table 6.5 — Timeline

Demo (runs now):

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_5.py --gold samples/ground_truth/timeline_gold_example.json
cd ..
```

Real numbers:

```bash
cp evidence_ocr_engine/samples/ground_truth/timeline_gold_template.json \
   evidence_ocr_engine/samples/ground_truth/timeline_gold.json
# edit timeline_gold.json: per case, true "order" + true "timestamps"
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_5.py --gold samples/ground_truth/timeline_gold.json
cd ..
```

---

## 🟡 Table 6.1 — OCR (demo runs now on real sample images)

Demo (live OCR on 2 real sample images, illustrative labels):

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_1.py \
    --manifest samples/ground_truth/ocr_corpus_example.json --allow-example
cd ..
```

Real numbers — first build a 30–100 sample corpus (auto-scaffold the skeleton,
then a human fills each `reference`):

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/scaffold_gold.py ocr --images-dir samples --out samples/ground_truth/ocr_corpus.json
# edit ocr_corpus.json: type the exact visible text into each "reference"
../.venv-platform/bin/python scripts/run_table_6_1.py --manifest samples/ground_truth/ocr_corpus.json
cd ..
```

---

## 🟡 Table 6.2 — Entity extraction (demo runs now)

Demo (regex vs full pipeline on the sample-image texts):

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_2.py \
    --gold  samples/ground_truth/entities_gold_example.json \
    --texts samples/ground_truth/texts_example.json
cd ..
```

Real numbers — scaffold from your corpus, a human fills the entity lists:

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/scaffold_gold.py entities \
    --from-manifest samples/ground_truth/ocr_corpus.json \
    --out-gold samples/ground_truth/entities_gold.json \
    --out-texts samples/ground_truth/texts.json
# edit entities_gold.json: list the true entities per type
../.venv-platform/bin/python scripts/run_table_6_2.py \
    --gold samples/ground_truth/entities_gold.json --texts samples/ground_truth/texts.json
cd ..
```

Optional spaCy baseline (a new optional dependency — install into `.venv-platform`):

```bash
.venv-platform/bin/python -m pip install spacy
.venv-platform/bin/python -m spacy download en_core_web_sm
```

---

## 🟢 Table 6.8 — Security (each row proven by a test)

```bash
# Row 1 — open access by design
cd ciis_api && ../.venv-platform/bin/python -m pytest api/tests/test_security_posture.py -q && cd ..

# Row 2 — evidence tampering detected
cd evidence_ocr_engine && ../.venv-platform/bin/python -m pytest tests/test_hash_service.py::test_verify_detects_tampering -q && cd ..

# Row 3 — homoglyph phishing (component-level)
cd threat_intelligence_system && ../.venv-threat/bin/python -m pytest tests/test_brand_intelligence.py -q && cd ..

# Row 4 — oversized upload rejected
cd ciis_api && ../.venv-platform/bin/python -m pytest api/tests/test_evidence.py::test_upload_rejects_oversized -q && cd ..
```

---

## Table 6.6 — RAG

Not implemented (future work) — no command.

---

## Do I have to write these JSON files by hand?

**The structure — no. The values — yes (that's the whole point).** Ground truth
is the *human-decided correct answer*; auto-deriving it from the engine would be
circular. So `scaffold_gold.py` auto-writes the JSON *skeleton* (all ids / image
paths pre-filled) from the images and cases you already have — you only type the
transcripts / entities / pairs:

```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/scaffold_gold.py ocr         --images-dir samples --out samples/ground_truth/ocr_corpus.json
../.venv-platform/bin/python scripts/scaffold_gold.py entities    --from-manifest samples/ground_truth/ocr_corpus.json --out-gold samples/ground_truth/entities_gold.json --out-texts samples/ground_truth/texts.json
../.venv-platform/bin/python scripts/scaffold_gold.py correlation --out samples/ground_truth/correlation_gold.json
../.venv-platform/bin/python scripts/scaffold_gold.py timeline    --out samples/ground_truth/timeline_gold.json
cd ..
```

The `*_example.json` demo files are already-filled references you can copy from.

## Input formats (what each gold file needs)

- `correlation_gold.json` → `{"within_case": {"<CASE>": {"related_pairs": [["EVID_a","EVID_b"], …]}}, "cross_case": {"related_pairs": [["EVID_x","EVID_y"], …]}}`
- `timeline_gold.json` → `{"<CASE>": {"order": ["EVID_a","EVID_b", …], "timestamps": {"EVID_a": "2026-01-04T09:12:00Z", …}}}`
- `ocr_corpus.json` → `[{"id": "img_001", "reference": "…exact transcript…", "image": "samples/img_001.png"}, …]`
- `entities_gold.json` → `{"EVID_a": {"urls": ["…"], "phones": ["…"], "esewa_ids": ["…"]}}`
- `texts.json` → `{"EVID_a": "the OCR/source text …"}`

See `EVALUATION.md` for the meaning of each field and what "ground truth" is.
