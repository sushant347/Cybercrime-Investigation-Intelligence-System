# Forensic Investigation Report - CASE_8F43434664

Generated: 2026-07-25T13:53:49.315Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_8F43434664 contains 4 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- The weighted correlation engine found 6 related evidence pair(s) out of 6 analysed [correlation_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 4 evidence item(s) acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
- **methodology**:
  - Phase 1 - Acquisition & OCR: PaddleOCR PP-OCRv5 text extraction with per-item confidence scoring; SHA-256 fingerprint recorded at intake and re-verified at read.
  - Phase 1 - Forensics: metadata/EXIF consistency, forgery signals, logo detection and evidence-confidence scoring stored per item under storage/forensics/.
  - Phase 2 - Correlation: weighted entity-overlap engine scoring every evidence pair; results in correlation_analysis.json.
  - Phase 2 - Cross-case: shared-entity matching against every other analysed case (cross_case_correlation.json).
  - Phase 2 - Campaigns / Suspects / Timeline: clustering, anchor derivation and event reconstruction over the correlated evidence set.
  - Threat intelligence: URL/domain indicators scored by the configured provider (static indicator file, or the trained phishing classifier when CIIS_ML_THREAT_INTEL=1); per-indicator results in 'Model Prediction Results'.
  - Reporting: this document is assembled exclusively from the stored outputs above; it contains no free-text generation.
- **reproducibility**: Re-running the analysis against the same stored evidence reproduces every figure herein; artifacts are versioned and never overwritten.

## Case Overview

- **case id**: CASE_8F43434664
- **evidence count**: 4
- **first evidence**: 2026-07-25T12:55:29.488Z
- **last evidence**: 2026-07-25T12:56:24.334Z
- **file types**:
  - csv
  - jpg
  - pdf
  - png

## Evidence Summary

- **evidence id**: EVID_00005
- **file name**: romanchat.jpg
- **upload time**: 2026-07-25T12:55:29.488Z
- **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
- **hash verified**: True
- **ocr confidence**: 0.5607
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00006
- **file name**: phishing_email_screenshot.png
- **upload time**: 2026-07-25T12:55:59.642Z
- **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
- **hash verified**: True
- **ocr confidence**: 0.9686
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00007
- **file name**: bank_transactions.csv
- **upload time**: 2026-07-25T12:56:12.284Z
- **sha256**: fbc5fcf7403a5aa8c042baed4343d0162e8d3506ff5d1163864662d25602e87e
- **hash verified**: True
- **ocr confidence**: 0.0
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00008
- **file name**: police_scan_report.pdf
- **upload time**: 2026-07-25T12:56:24.334Z
- **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
- **hash verified**: False
- **ocr confidence**: 0.0
- **evidence confidence score**: not available
- **entity count**: 0

## Correlation Analysis

- **pair count**: 6
- **related pair count**: 6
- **strength distribution**:
  - **WEAK**: 6
- **top relationships**:
  - **pair**: EVID_00005 <-> EVID_00006
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00005 (romanchat.jpg) and EVID_00006 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00005 <-> EVID_00007
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00005 (romanchat.jpg) and EVID_00007 (bank_transactions.csv) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00005 <-> EVID_00008
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00005 (romanchat.jpg) and EVID_00008 (police_scan_report.pdf) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00006 <-> EVID_00007
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00006 (phishing_email_screenshot.png) and EVID_00007 (bank_transactions.csv) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00006 <-> EVID_00008
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00006 (phishing_email_screenshot.png) and EVID_00008 (police_scan_report.pdf) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

No cross-case correlations were found for this case.

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00005
  - EVID_00006
  - EVID_00007
  - EVID_00008
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 4 event(s) spanning 0.0 hour(s); 0 timestamp(s) unresolved.
- **stage progression**:
  - none
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-07-25T12:55:29.488000+00:00
  - **description**: Investigation start - first reconstructed evidence event
- **critical events**:
  - none

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

No threat-intelligence indicator file was provided; threat corroboration was skipped (not an absence of threat).

## Model Prediction Results

No threat-intelligence provider was active during this analysis; indicator-level model predictions were not produced (this is a coverage gap, not an absence of threat).

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.38
- **hash verified count**: 3.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 4.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 4.0
  - **resolved event count**: 4.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 4.0
  - **stage count**: 0.0
  - **critical event count**: 0.0
  - **timeline span hours**: 0.02
- **correlation statistics**:
  - **pair count**: 6.0
  - **related pair count**: 6.0
  - **mean confidence**: 0.2212
  - **max confidence**: 0.2212

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 3/4 evidence item(s) passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (6 weighted relationship(s)), consistent with related activity rather than isolated incidents.

## Recommendations

- Case priority: LOW (5.5/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Report Provenance & Integrity

- **report id**: RPT-8F43434664-56BD50B1
- **generated at**: 2026-07-25T13:53:49.311Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 979de3cce77008b7cb3832ef8c38159a1119b6bef7b3419c7fce7b4bfa73d1cb
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v5.json**: 8ec9eb7780473d1cb012a9ff4fa146f4c9cabc9c0f97626731c7a9af418821c5
  - **cross case correlation v3.json**: b4d93a4ca7c1d914f93c4b94c5891b4d257d2ed235099647f2bd334bceac8f89
  - **campaign analysis v2.json**: 20a9e5be85410fe4d42be848d5f8d4652e42aa57bf130f54141eaf212d55bb63
  - **suspect assessment v2.json**: dfdf3c01e563258cd07b21a64ee8a827ad941aacecddf40c103d9b219d55337b
  - **timeline analysis v5.json**: dc90f6005b5bb6759463f76dea01cec4387956446106c80a876cee2b6ae2a34e
  - **analytics v2.json**: 9ac06bc650dcb8616df207d12215b0ec93f484a63f60689873a6b7bac22a8471
  - **case priority v2.json**: 14e52bb3cd02cad03170444afaadf4e67e36389b31797926ce499e01df8a10ca
  - **graph v5.json**: 66b261e6c58129d4c9cd87ae90c5c9357b5cabac18b1b3f5f6d4182d967e1ea1

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00005
  - **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
  - **upload time**: 2026-07-25T12:55:29.488Z
  - **status**: processed
  - **evidence id**: EVID_00006
  - **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
  - **upload time**: 2026-07-25T12:55:59.642Z
  - **status**: processed
  - **evidence id**: EVID_00007
  - **sha256**: fbc5fcf7403a5aa8c042baed4343d0162e8d3506ff5d1163864662d25602e87e
  - **upload time**: 2026-07-25T12:56:12.284Z
  - **status**: processed
  - **evidence id**: EVID_00008
  - **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
  - **upload time**: 2026-07-25T12:56:24.334Z
  - **status**: uploaded
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
