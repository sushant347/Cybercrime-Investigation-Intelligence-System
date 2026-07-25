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
