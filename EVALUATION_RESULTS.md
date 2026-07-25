# CIIS Evaluation Results (Chapter 6)

_Generated 2026-07-25 07:42 UTC from real repo artifacts. No value is hand-typed or fabricated; blocked tables show placeholders, not invented numbers._

| Table | Status |
|---|---|
| 6.1 OCR | 🔴 Blocked — needs annotated corpus |
| 6.2 Entity extraction | 🔴 Blocked — needs corpus + spaCy |
| 6.3 URL classification | 🟢 Real (verified test set) |
| 6.4 Correlation | 🟡 Harness ready — needs gold pairs |
| 6.5 Timeline | 🟡 Harness ready — needs gold order/timestamps |
| 6.6 RAG | ⚪ Not implemented (future work) |
| 6.7 End-to-end | 🟢 System real / 🟡 baseline = estimate |
| 6.8 Security | 🟢 Test-backed |

## Table 6.3 — URL / Phishing Classification

Source: `full_retraining_report_20260712T090000Z.json` · held-out test set **n = 87,756** · deployed model: **xgboost**

| Model | Precision | Recall | F1 | Accuracy | ROC-AUC | PR-AUC | FNR |
|---|---|---|---|---|---|---|---|
| **xgboost** ⭐ | 0.9762 | 0.9838 | 0.9800 | 0.9790 | 0.9973 | 0.9977 | 0.0162 |
| lightgbm | 0.9748 | 0.9820 | 0.9784 | 0.9773 | 0.9968 | 0.9973 | 0.0180 |
| decision_tree | 0.9729 | 0.9725 | 0.9727 | 0.9715 | 0.9824 | 0.9779 | 0.0275 |
| random_forest | 0.9707 | 0.9806 | 0.9756 | 0.9744 | 0.9959 | 0.9965 | 0.0194 |
| extra_trees | 0.9686 | 0.9818 | 0.9752 | 0.9739 | 0.9958 | 0.9963 | 0.0182 |
| logistic_regression | 0.8841 | 0.9099 | 0.8968 | 0.8906 | 0.9475 | 0.9426 | 0.0901 |
| svm | 0.8839 | 0.9102 | 0.8968 | 0.8906 | 0.9479 | 0.9436 | 0.0898 |
| naive_bayes | 0.8540 | 0.7573 | 0.8027 | 0.8056 | 0.8935 | 0.8716 | 0.2427 |

Deployed **xgboost** confusion matrix (n=87,756): TN=40,819 FP=1,101 FN=743 TP=45,093 · MCC=0.9579 · log-loss=0.0684

## Table 6.7 — End-to-End Processing Time

Implemented system, real case `CASE_2CF24DBA5F` (from per-stage `duration_ms` logs; umbrella rows are authoritative, sub-stages are inside them):

| Phase | Time |
|---|---|
| Phase-1 (acquire + OCR) | 7.945 s |
| Phase-2 (analysis, 8 modules) | 0.057 s |
| **End-to-end total** | **8.001 s** |
| Manual workflow (baseline) | _pending — cited estimate/SME, not measured in code_ |
| Report correctness | _pending — human review via `report_review.py`_ |

Phase-1 sub-stages (ms, inside the Phase-1 total): {'hashing': 0.8, 'ocr': 7641.8, 'preprocessing': 241.1, 'upload': 16.5}

## Table 6.8 — Security

| # | Threat | Result | Backed by (test) |
|---|---|---|---|
| 1 | Unauthorized API access | **Open by design** (not blocked) | `api/tests/test_security_posture.py` |
| 2 | Evidence-file tampering | **Detected** (SHA-256) | `tests/test_hash_service.py::test_verify_detects_tampering` |
| 3 | Homoglyph phishing URL | **Detected — component-level** (not e2e) | `tests/test_brand_intelligence.py` |
| 4 | Oversized upload (>50 MB) | **Rejected** (HTTP 400) | `api/tests/test_evidence.py::test_upload_rejects_oversized` |

## Tables 6.1 / 6.2 / 6.4 / 6.5 — harnesses ready, awaiting human data

Columns are defined and the runners work; cells stay blank (—) until gold data is supplied (see `EVALUATION.md`).

**Table 6.1 — OCR (3 pipeline stages)**

| Stage | CER | WER | Char-Acc | Entity-Preservation % |
|---|---|---|---|---|
| Raw | — | — | — | — |
| + Preprocessing | — | — | — | — |
| + Correction | — | — | — | — |

**Table 6.2 — Entity extraction**

| Method | Precision | Recall | F1 (micro) | F1 (macro) |
|---|---|---|---|---|
| Regex-only | — | — | — | — |
| spaCy baseline | — | — | — | — |
| Full pipeline | — | — | — | — |

**Table 6.4 — Correlation**

| Method | Precision | Recall | F1 |
|---|---|---|---|
| Live weighted engine | — | — | — |
| Exact-match baseline | — | — | — |
| Unweighted baseline | — | — | — |

**Table 6.5 — Timeline**

| Method | Order accuracy | Timestamp MAE | % ≤ 60 s | Unresolved rate |
|---|---|---|---|---|
| Live four-tier engine | — | — | — | — |
| Upload-time baseline | — | — | — | — |

## Reusable metric validation

The dependency-free `classification_metrics.py` ROC-AUC / PR-AUC match scikit-learn to **0.0e+00** on 2,000 random samples (cross-checked, sklearn not a dependency).

_Regenerate this file anytime: `python run_all_evaluations.py` shows the same data live._
