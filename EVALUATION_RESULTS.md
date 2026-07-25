# CIIS Evaluation Results (Chapter 6)

_Generated 2026-07-25 08:55 UTC from real repo artifacts + demo gold._

**Read this first.** Tables 6.3, 6.7, 6.8 are **real**. Tables 6.1/6.2/6.4/6.5 below are
run on **ILLUSTRATIVE DEMO gold** — real cases/images already in storage, with plausible
human-style labels — so you can see the pipeline work end-to-end. They are **not
thesis-grade** (a real corpus / human-verified labels are still needed). Every table names
the exact case(s)/image(s) its numbers came from. Reproduce any row via `EVAL_COMMANDS.md`.

| Table | Status | Source of the numbers |
|---|---|---|
| 6.1 OCR | 🟡 demo (real OCR) | 3 sample images (incl. 1 low-quality) |
| 6.2 Entities | 🟡 demo | same 2 sample images |
| 6.3 URL classification | 🟢 real | 87,756-row held-out test set |
| 6.4 Correlation | 🟡 demo | 4 real storage cases |
| 6.5 Timeline | 🟡 demo | 1 real storage case |
| 6.6 RAG | ⚪ not implemented | — |
| 6.7 End-to-end | 🟢 real (system) | 1 real storage case |
| 6.8 Security | 🟢 real (tests) | passing tests |

## Table 6.1 — OCR (CER / WER / entity preservation)

**Source:** `samples/ground_truth/ocr_corpus_example.json` — 3 sample images, hand-transcribed:
`scam_sms_screenshot.png` + `phishing_email_screenshot.png` (clean) and
`low_quality_scan_demo.png` (low-quality / rotated). Live PaddleOCR (PP-OCRv5).

| Stage | CER | WER | Char-Acc | Entity-Preservation % | n |
|---|---|---|---|---|---|
| Raw | 0.3444 | 0.4058 | 0.6556 | 100.0 | 3 |
| + Preprocessing | 0.3444 | 0.4058 | 0.6556 | 100.0 | 3 |
| + Correction | **0.3370** | 0.4058 | **0.6630** | 100.0 | 3 |

_The low-quality image dominates the average: PaddleOCR reads it **upside-down**
(confidence **0.56** vs 0.98 for the clean images), pushing CER to 0.34. The
**+ Correction** stage measurably improves it (CER 0.3444 → **0.3370**, char-accuracy
0.6556 → 0.6630) by fixing some OCR errors — a difference that only appears once a
degraded image is in the mix (on the two clean images all three stages are identical,
because there is nothing to correct). Entity preservation stays 100% because the gold
entities come from the two clean images. Demo only (n=3, mostly English); a real
Table 6.1 needs a 30–100 sample bilingual corpus._

**For comparison, the two clean images alone (n=2):** all three stages = CER 0.0154,
char-accuracy 0.9846 — i.e. correction only helps when OCR actually made errors.

## Table 6.2 — Entity extraction (Precision / Recall / F1)

**Source:** `entities_gold_example.json` + `texts_example.json` — same 2 images
(`scam_sms`, `phishing_email`); gold = the money/email/URL/domain entities a human read from them.

| Method | Precision | Recall | F1 (micro) | F1 (macro) | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| Regex-only (live extractor) | 0.8333 | 1.0000 | 0.9091 | 0.9167 | 5 | 1 | 0 |
| spaCy baseline | — | — | — | — | | | _not installed (optional dep)_ |
| Full pipeline | — | — | — | — | | | _not produced by the demo runner_ |

_The extractor found all 5 true entities (recall 1.0) plus 1 extra (a domain it derived
beyond the small gold list) → precision 0.83._

## Table 6.3 — URL / Phishing Classification (real)

**Source:** `results/full_retraining_report_20260712T090000Z.json` → `test_evaluations` ·
held-out test set **n = 87,756** · deployed model **xgboost**. Not recomputed.

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

Deployed **xgboost** confusion matrix (n=87,756): TN=40,819 · FP=1,101 · FN=743 · TP=45,093 · MCC=0.9579

## Table 6.4 — Correlation (Precision / Recall / F1)

**Source:** `correlation_gold_example.json` — real cases `CASE_2CF24DBA5F`, `CASE_8F43434664`,
`CASE_F1278DD84F`, `CASE_85B2471DFB`. Gold = same-case screenshots are 'related'; cases sharing
scam amounts are 'one campaign'.

**Within-case** (each case scored separately; shown here as the average pattern — all 4 cases identical):

| Method | Precision | Recall | F1 |
|---|---|---|---|
| Live weighted engine | 1.00 | 1.00 | 1.00 |
| Exact-match baseline | 0.00 | 0.00 | 0.00 |
| Unweighted baseline | 0.00 | 0.00 | 0.00 |

**Cross-case** (all cases pooled):

| Method | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| Live cross-case engine | 0.3333 | 1.0000 | 0.5000 | 3 | 6 | 0 |

_Reading: the weighted engine links the same-case screenshots (F1 = 1.0) via timeline +
weak signals, while the exact-match and unweighted baselines find no shared **exact** entity
within a case (F1 = 0.0) — that gap is the engine's value. Cross-case recall = 1.0 (found all
3 gold pairs) with 6 extra money-based links → precision 0.33._

## Table 6.5 — Timeline (order / timestamp accuracy / unresolved rate)

**Source:** `timeline_gold_example.json` — real case `CASE_2CF24DBA5F` (3 evidence items).

| Method | Order accuracy | Timestamp MAE | Median AE | % ≤ 60 s | Unresolved rate |
|---|---|---|---|---|---|
| Live four-tier engine | 1.00 | 11,594,075 s | 17,391,090 s | 0.33 | 0.00 |
| Upload-time baseline | 1.00 | — | — | — | — |

_Reading: ordering is correct (1.0), but the timestamp MAE is ~134 days because the engine
resolves each item's **upload_time** (July 2026) rather than the **content date** (Jan 2026
in the WhatsApp/SMS text). That is a real, reportable finding — the timestamp-resolution gap._

## Table 6.7 — End-to-End Processing Time (real)

**Source:** per-stage `duration_ms` logs for real case `CASE_2CF24DBA5F` (3 evidence items).

| Phase | Time |
|---|---|
| Phase-1 (acquire + OCR) | 7.945 s |
| Phase-2 (analysis, 8 modules) | 0.057 s |
| **End-to-end total** | **8.001 s** |
| Manual workflow (baseline) | _pending — cited estimate/SME, not measured in code_ |
| Report correctness | _pending — human review via `report_review.py`_ |

## Table 6.8 — Security (real, test-backed)

| # | Threat | Result | Backing test |
|---|---|---|---|
| 1 | Unauthorized API access | Open by design (not blocked) | `api/tests/test_security_posture.py` |
| 2 | Evidence-file tampering | Detected (SHA-256) | `tests/test_hash_service.py::test_verify_detects_tampering` |
| 3 | Homoglyph phishing URL | Detected — component-level | `tests/test_brand_intelligence.py` |
| 4 | Oversized upload (>50 MB) | Rejected (HTTP 400) | `api/tests/test_evidence.py::test_upload_rejects_oversized` |

## Appendix — the cases & files these demo numbers came from

These cases are committed under `evidence_ocr_engine/storage/` for testing (remove before launch).

| Case | Evidence | Source file |
|---|---|---|
| CASE_2CF24DBA5F | EVID_00001 | `samples/whatsapp_chat_export.txt` |
| CASE_2CF24DBA5F | EVID_00002 | `samples/scam_sms_screenshot.png` |
| CASE_2CF24DBA5F | EVID_00003 | `samples/low_quality_scan_demo.png` |
| CASE_8F43434664 | EVID_00004 | `samples/whatsapp_chat_export.txt` |
| CASE_8F43434664 | EVID_00005 | `samples/low_quality_scan_demo.png` |
| CASE_8F43434664 | EVID_00006 | `samples/romanchat.jpg` |
| CASE_F1278DD84F | EVID_00007 | `samples/whatsapp_chat_export.txt` |
| CASE_F1278DD84F | EVID_00008 | `samples/scam_sms_screenshot.png` |
| CASE_85B2471DFB | EVID_00009 | `samples/whatsapp_chat_export.txt` |
| CASE_85B2471DFB | EVID_00010 | `samples/scam_sms_screenshot.png` |

_6.3 uses none of these — it is the URL classifier's own 585k-row dataset. 6.2 uses
`scam_sms_screenshot.png` + `phishing_email_screenshot.png`; 6.1 uses those two plus
`low_quality_scan_demo.png` (the degraded image that makes the correction stage's value visible)._

Reproduce every table: see **`EVAL_COMMANDS.md`**.
