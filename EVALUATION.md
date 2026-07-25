# CIIS Evaluation — Chapter 6 tables: status, commands, results

One command runs everything computable and prints the status matrix:

```bash
python run_all_evaluations.py
```

No number here is fabricated. Where an artifact exists, the table is computed
from it; where human gold data or review is required, the harness is built and
the output is **blocked honestly** until that data is supplied.

## Status at a glance

| Table | Status | Where the number comes from |
|---|---|---|
| 6.1 OCR (CER/WER/entity-preservation) | 🔴 Blocked | needs a 30–100 sample annotated bilingual corpus |
| 6.2 Entity extraction (P/R/F1) | 🔴 Blocked | same corpus + spaCy (new optional dep) |
| 6.3 URL classification | 🟢 Implemented (real) | `results/full_retraining_report_*.json`, test set n=87,756 |
| 6.4 Correlation (P/R/F1) | 🟡 Harness ready | needs human gold related-pairs |
| 6.5 Timeline (order/timestamp/unresolved) | 🟡 Harness ready | needs human gold order + timestamps |
| 6.6 RAG | ⚪ Not implemented | correctly future work |
| 6.7 End-to-end | 🟢 Impl. (system) / 🟡 (baseline) | `storage/*` timing logs; manual baseline = cited estimate |
| 6.8 Security | 🟢 Implemented (test-backed) | passing tests (row 3 component-level) |

## Per-table commands

**6.3 — URL/phishing classification** (real; does *not* retrain):
```bash
cd threat_intelligence_system && ../.venv-threat/bin/python scripts/run_table_6_3.py
```
Deployed XGBoost: P=0.9762 R=0.9838 F1=0.9800 ROC-AUC=0.9973 PR-AUC=0.9977 FNR=0.0162.
Provenance + confusion-matrix consistency verified by `tests/test_table_6_3_source.py`.

**6.7 — end-to-end processing time** (real):
```bash
cd evidence_ocr_engine && ../.venv-platform/bin/python scripts/aggregate_processing_time.py --case <CASE_ID>
```
Uses the per-stage `duration_ms` logs; the `pipeline`/`phase2_pipeline` umbrella
rows are the authoritative totals (sub-stages are *inside* them — never summed on
top). Manual-workflow cell must be an explicitly-cited estimate. Report-correctness:
```bash
python evidence_ocr_engine/scripts/report_review.py --case <CASE_ID> --out review.json
# a human fills each 'verdict', then:
python evidence_ocr_engine/scripts/report_review.py --score review.json
```

**6.8 — security** (proven by tests):
- Row 1 open-access-by-design → `ciis_api/api/tests/test_security_posture.py`
- Row 2 tampering → `evidence_ocr_engine/tests/test_hash_service.py::test_verify_detects_tampering`
- Row 3 homoglyph (component-level, not e2e) → `threat_intelligence_system/tests/test_brand_intelligence.py`
- Row 4 oversized upload → `ciis_api/api/tests/test_evidence.py::test_upload_rejects_oversized`

**6.4 / 6.5 — correlation & timeline** (live services, not the deprecated prototypes):
```bash
# 1. fill the gold templates in samples/ground_truth/
cp samples/ground_truth/correlation_gold_template.json samples/ground_truth/correlation_gold.json  # then edit
cd evidence_ocr_engine && ../.venv-platform/bin/python scripts/run_table_6_4.py --gold samples/ground_truth/correlation_gold.json
../.venv-platform/bin/python scripts/run_table_6_5.py --gold samples/ground_truth/timeline_gold.json
```
Baselines included: correlation exact-match + unweighted; timeline upload-time
ordering. Timestamp accuracy = MAE / median AE / % within {60 s, 1 h, 24 h} /
unresolved-rate (unresolved items excluded from MAE).

**6.1 / 6.2 — OCR & entities** (blocked on corpus):
```bash
cd evidence_ocr_engine && ../.venv-platform/bin/python scripts/run_table_6_1.py --manifest <corpus>.json --gold-entities <ents>.json
../.venv-platform/bin/python scripts/run_table_6_2.py --gold <gold>.json --texts <texts>.json
```

## Where the confusion matrix comes from

Two different places, for two different purposes:

1. **Table 6.3 (URL classifier) — already computed, do not recompute.**
   scikit-learn computes it during training/evaluation at
   `threat_intelligence_system/src/evaluation/evaluator.py:152`
   (`confusion_matrix(y_true, y_pred).tolist()`, sklearn imported line 19)
   inside `ModelEvaluator`. `src/training/full_retraining.py` runs it and stores
   one per model at `test_evaluations.<model>.confusion_matrix` in
   `results/full_retraining_report_*.json`, in `[[TN, FP], [FN, TP]]` form. The
   deployed XGBoost matrix (TN=40,819 FP=1,101 FN=743 TP=45,093) is read out by
   `scripts/run_table_6_3.py` — nothing is recomputed.
2. **Reusable, dependency-free — for every other binary evaluation.**
   `evidence_ocr_engine/backend/modules/investigation/evaluation/classification_metrics.py:80`
   → `confusion_matrix(y_true, y_pred)` returns a `ConfusionMatrix` whose
   `.matrix()` is `[[TN,FP],[FN,TP]]`, plus `.accuracy / .precision / .recall /
   .f1 / .false_negative_rate` and rank-based `roc_auc()` / `pr_auc()` (matched
   to sklearn at 0.0e+00). The Table 6.3 provenance test
   (`threat_intelligence_system/tests/test_table_6_3_source.py`) uses this to
   prove the *stored* matrix reproduces the *reported* P/R/F1/FNR.

## What "ground truth" means, and the evaluation workflow

**Ground truth** is the *correct answer, decided by a human*, that a metric
compares the system's output against. Precision, recall, CER, MAE — none of them
mean anything without it: you can only call the engine "right" if you already
know what "right" is. Per table:

| Table | Ground truth = the human-decided correct… |
|---|---|
| 6.1 OCR | exact text a human reads off each image |
| 6.2 Entities | true list of phones/URLs/wallets/… visible in the evidence |
| 6.3 Classification | true phishing/legitimate label of each URL (already labelled, 585k rows) |
| 6.4 Correlation | pairs of evidence a human judges truly related |
| 6.5 Timeline | true chronological order + true timestamps of the events |

**Every evaluated table follows the same three steps:**

1. **Predict** — run the live engine on real evidence → OCR text / entities /
   related-pairs / an ordering.
2. **Ground truth** — a human writes the correct answer for the *same* evidence
   (the "gold" file).
3. **Score** — a metric compares (1) vs (2). Baselines (exact-match,
   upload-time ordering, spaCy) are scored the same way, so the engine's value is
   measured *relative* to something simpler — e.g. in the demo below the weighted
   engine scores F1 = 1.0 within-case while the exact-match baseline scores 0.0.

6.1/6.2/6.4/6.5 are "blocked" only at **step 2** (human labels). Steps 1 and 3 —
the engine and the metric code — are finished and tested. 6.3 is the one table
whose ground truth already exists at scale, which is why it has real numbers now.

### Try it now with zero labelling (illustrative demo)

A demo runs out of the box on the **real cases already in storage**:

```bash
python run_all_evaluations.py          # 6.4 / 6.5 auto-run on the example gold
```

It uses `samples/ground_truth/correlation_gold_example.json` and
`timeline_gold_example.json` — real cases (`CASE_2CF24DBA5F`, …) with **plausible,
clearly-labelled DEMO** relationships (e.g. the three screenshots in one fraud
case are "related"; cases sharing the same scam amount are "one campaign"). This
lets you watch the full predict→score pipeline work — **but the numbers are not
thesis-grade** (a human didn't verify them). For real table values, replace the
example with genuine gold as described next.

## Step-by-step: producing the blocked tables (6.1, 6.2, 6.4, 6.5)

These need **human-provided ground truth**. All code — loaders, validators,
baselines, runners — is finished. You provide the labels in the exact JSON
shapes below, run one command, and real numbers print. Every runner refuses to
emit a number from an empty template. (The `*_gold_example.json` files above are
a filled-in reference you can copy from.)

> **Shared prerequisite (6.4, 6.5):** the cases you label must already exist in
> engine storage — upload evidence and run the analysis first, so
> `storage/evidence.csv` and `storage/entities.csv` are populated. The gold
> evidence IDs (`EVID_xxxxx`) must match those files.

### Table 6.4 — Correlation (Precision / Recall / F1)

**Measures:** does the engine link the *right* evidence pairs? Scores the live
weighted engine plus an exact-match and an unweighted baseline against human
gold pairs.

**Input — `correlation_gold.json`** (a human marks which pairs are truly related):
```bash
cp evidence_ocr_engine/samples/ground_truth/correlation_gold_template.json \
   evidence_ocr_engine/samples/ground_truth/correlation_gold.json
```
```json
{
  "within_case": {
    "CASE_0021": { "related_pairs": [ ["EVID_00001","EVID_00002"], ["EVID_00001","EVID_00005"] ] },
    "CASE_0042": { "related_pairs": [] }
  },
  "cross_case": { "related_pairs": [ ["EVID_00001","EVID_00099"] ] }
}
```
- Each item is a **pair of evidence IDs** `[a, b]` an analyst judges to belong
  to the same activity. Order is ignored (`[a,b] == [b,a]`).
- `within_case` → both IDs in the **same** case (keyed by case id);
  `cross_case` → the two IDs live in **different** cases.
- `[]` means "genuinely no related pairs". Delete the `_README` key.

**Run:**
```bash
cd evidence_ocr_engine
../.venv-platform/bin/python scripts/run_table_6_4.py --gold samples/ground_truth/correlation_gold.json
```
**Output:** per case, three rows — `live_weighted`, `exact_match`,
`unweighted_shared` — each with Precision / Recall / F1 and TP/FP/FN.

### Table 6.5 — Timeline (order accuracy, timestamp accuracy, unresolved rate)

**Measures:** does the engine order events correctly, and how close are its
resolved timestamps to the truth? Live four-tier engine vs. an upload-time
baseline.

**Input — `timeline_gold.json`:**
```bash
cp evidence_ocr_engine/samples/ground_truth/timeline_gold_template.json \
   evidence_ocr_engine/samples/ground_truth/timeline_gold.json
```
```json
{
  "CASE_0021": {
    "order": ["EVID_00001", "EVID_00003", "EVID_00002"],
    "timestamps": {
      "EVID_00001": "2026-01-04T09:12:00Z",
      "EVID_00003": "2026-01-04T09:14:00Z"
    }
  }
}
```
- `order` = the **true chronological order** of that case's evidence IDs (human-sorted).
- `timestamps` = the **true ISO-8601 timestamp** per evidence ID a human can date
  from the content. You may timestamp only a subset — un-timestamped items aren't
  scored; items the engine can't resolve count toward the **unresolved rate** and
  are excluded from MAE.

**Run:**
```bash
../.venv-platform/bin/python scripts/run_table_6_5.py --gold samples/ground_truth/timeline_gold.json
```
**Output:** per case — order accuracy (live vs. baseline), and timestamp MAE /
median AE / % within 60 s / unresolved rate.

### Table 6.1 — OCR (CER / WER / entity-preservation), 3 stages

**Measures:** recognition accuracy at each pipeline stage
(Raw → + Preprocessing → + Correction).

**Input 1 — an OCR manifest `ocr_corpus.json`** (a human transcribes each image's
**exact visible text**, verbatim, no correction/translation):
```json
[
  { "id": "img_001", "reference": "…exact human transcript…", "image": "samples/img_001.png" },
  { "id": "img_002", "reference": "…", "image": "samples/img_002.png" }
]
```
- `reference` = ground-truth text. `image` = path to the evidence image (relative
  to the manifest, or to the engine root). Items with an `image` and no
  `hypothesis` run **live PaddleOCR**; items that instead carry a `"hypothesis"`
  string are scored directly (lets you run without PaddleOCR installed).
- Target: **30–100 images, English + Nepali/Devanagari**.

**Input 2 (optional) — `preservation_entities.json`** `{id: ["entity string", …]}`
to add the entity-preservation column (fraction of true entity strings that
survive OCR verbatim).

**Run:**
```bash
../.venv-platform/bin/python scripts/run_table_6_1.py \
    --manifest samples/ground_truth/ocr_corpus.json \
    --gold-entities samples/ground_truth/preservation_entities.json
```
(The bundled `*_example.json` manifest is refused as a real result; add
`--allow-example` only to smoke-test the harness.)

### Table 6.2 — Entity extraction (Precision / Recall / F1): regex vs spaCy vs full

**Measures:** entity extraction quality for three prediction sources against the
same gold.

**Input 1 — gold entities `entities_gold.json`** `{evidence_id: {type: [values]}}`:
```json
{
  "EVID_00001": {
    "urls": ["http://nabil-verify.scam.top/login"],
    "emails": ["support@fake-bank.com"],
    "phones": ["+9779812345678"],
    "esewa_ids": ["9812345678"]
  }
}
```
- Keyed by **evidence ID**; each list is the human-verified true entities of that
  type. Use the extractor's type names (`urls, emails, phones, domains,
  esewa_ids, khalti_ids, imepay_ids, bank_accounts, otp, money, …` — the full
  28-type vocabulary).

**Input 2 — texts `texts.json`** `{evidence_id: "the OCR/source text"}` (the raw
text the regex and spaCy passes read).

**Optional dependency — spaCy** (not installed; a *new optional* dependency). The
spaCy row is skipped with a clear note unless you install it **into the platform
venv** (the runner runs there):
```bash
.venv-platform/bin/python -m pip install spacy && .venv-platform/bin/python -m spacy download en_core_web_sm
```
Expect spaCy to score poorly on domain types (eSewa/wallet/OTP) — a legitimate,
reportable finding, not a bug.

**Run:**
```bash
../.venv-platform/bin/python scripts/run_table_6_2.py \
    --gold samples/ground_truth/entities_gold.json \
    --texts samples/ground_truth/texts.json
```
**Output:** micro P/R/F1 and macro-F1 for `regex_only`, `spacy` (or SKIPPED), and
`full` pipeline.

## Reusable metric modules (all unit-tested)

| Metric | Module |
|---|---|
| confusion matrix, accuracy, precision, recall, F1, FNR, FPR, ROC-AUC, PR-AUC | `investigation/evaluation/classification_metrics.py` |
| CER, WER, char/word accuracy, entity-preservation | `evidence/evaluation/ocr_metrics.py` |
| entity P/R/F1, micro/macro | `evidence/evaluation/entity_metrics.py` |
| correlation P/R/F1 (+ baselines) | `investigation/evaluation/correlation_eval.py`, `correlation_baselines.py` |
| timeline order accuracy, timestamp accuracy, unresolved rate | `investigation/evaluation/timeline_eval.py` |
| end-to-end timing aggregation | `evidence_ocr_engine/scripts/aggregate_processing_time.py` |
| gold-label loaders + templates | `investigation/evaluation/gold_labels.py`, `samples/ground_truth/*_template.json` |

The dependency-free ROC-AUC / PR-AUC match scikit-learn to 0.0e+00 on 2,000
random samples (cross-checked, not committed as a dependency).

## Still blocked (human-only, by design)
1. **6.1 / 6.2** — annotated 30–100 sample bilingual corpus (true text + true entities).
2. **6.4 / 6.5** — gold related-pairs and gold order/timestamps (fill the templates).
3. **6.7** — manual-workflow time (cited estimate/SME) + report-correctness grading (harness ready).
4. **6.8 row 1** — policy decision already taken: open access by design.
