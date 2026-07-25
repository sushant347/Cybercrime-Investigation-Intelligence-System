# Forensic Investigation Report - CASE_8F43434664

Generated: 2026-07-25T13:02:00.252Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_8F43434664 contains 4 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 1 other case(s) through shared entities: CASE_2CF24DBA5F [cross_case_correlation.json].
- The weighted correlation engine found 6 related evidence pair(s) out of 6 analysed [correlation_analysis.json].
- The strongest suspect anchor is 'security@nabil-bank-alerts.com' (emails) with confidence 39/100 [suspect_assessment.json].
- Observed attack progression: financial_transaction -> initial_contact -> social_engineering -> credential_theft [timeline_analysis.json].

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
- **ocr confidence**: 0.9686
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00006
- **file name**: phishing_email_screenshot.png
- **upload time**: 2026-07-25T12:55:59.642Z
- **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
- **hash verified**: True
- **ocr confidence**: 0.9859
- **evidence confidence score**: not available
- **entity count**: 4
- **evidence id**: EVID_00007
- **file name**: bank_transactions.csv
- **upload time**: 2026-07-25T12:56:12.284Z
- **sha256**: fbc5fcf7403a5aa8c042baed4343d0162e8d3506ff5d1163864662d25602e87e
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 2
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

- **related case count**: 1
- **related case ids**:
  - CASE_2CF24DBA5F
- **links**:
  - **other case id**: CASE_2CF24DBA5F
  - **relationship strength**: VERY_STRONG
  - **match confidence**: 0.8262
  - **match reason**: Shares 4 entity(ies) with CASE_2CF24DBA5F: domain nabil-bank-alerts.com, domain nabil-verify.example-scam.top, email security@nabil-bank-alerts.com (+1 more)
  - **matched entities**:
    - **entity type**: domains
    - **value**: nabil-bank-alerts.com
    - **this evidence ids**:
      - EVID_00006
    - **other evidence ids**:
      - EVID_00004
    - **entity type**: domains
    - **value**: nabil-verify.example-scam.top
    - **this evidence ids**:
      - EVID_00006
    - **other evidence ids**:
      - EVID_00004
    - **entity type**: emails
    - **value**: security@nabil-bank-alerts.com
    - **this evidence ids**:
      - EVID_00006
    - **other evidence ids**:
      - EVID_00004
    - **entity type**: urls
    - **value**: http://nabil-verify.example-scam.top/login
    - **this evidence ids**:
      - EVID_00006
    - **other evidence ids**:
      - EVID_00004

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

- **summary**: 4 event(s) spanning 4860.9 hour(s); 0 timestamp(s) unresolved. Observed scam progression: financial_transaction -> initial_contact -> social_engineering -> credential_theft.
- **stage progression**:
  - financial_transaction
  - initial_contact
  - social_engineering
  - credential_theft
- **progression consistent**: False
- **milestones**:
  - **timestamp**: 2026-01-04T00:00:00+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-01-04T00:00:00+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00007)
  - **timestamp**: 2026-07-25T12:55:59.642000+00:00
  - **description**: First observation of stage 'initial_contact' (EVID_00006)
  - **timestamp**: 2026-07-25T12:55:59.642000+00:00
  - **description**: First observation of stage 'social_engineering' (EVID_00006)
  - **timestamp**: 2026-07-25T12:55:59.642000+00:00
  - **description**: First observation of stage 'credential_theft' (EVID_00006)
- **critical events**:
  - none

## Suspect Assessment

- **suspect id**: SUSPECT_CASE_8F43434664_01
- **identity**: emails:security@nabil-bank-alerts.com
- **confidence score**: 38.8
- **confidence level**: LOW
- **risk level**: LOW
- **evidence ids**:
  - EVID_00006
- **explanation**: Suspect anchor 'security@nabil-bank-alerts.com' (emails) scores 38.8/100 (LOW, risk LOW) across 1 evidence item(s): EVID_00006. Identity strength: 75/100 (weight 0.25) - 'security@nabil-bank-alerts.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 4 evidence item(s). Evidence confidence: 50/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 50/100 (no Phase-1 scores stored; neutral 50 assumed). Threat intelligence: 0/100 (weight 0.15) - no threat-intelligence indicator file available. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set.

## Threat Intelligence Summary

No threat-intelligence indicator file was provided; threat corroboration was skipped (not an absence of threat).

## Model Prediction Results

No threat-intelligence provider was active during this analysis; indicator-level model predictions were not produced (this is a coverage gap, not an absence of threat).

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.74
- **hash verified count**: 3.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **dates**: 2
  - **domains**: 2
  - **emails**: 1
  - **urls**: 1
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
  - **stage count**: 4.0
  - **critical event count**: 0.0
  - **timeline span hours**: 4860.94
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
- Investigation should focus on anchor 'security@nabil-bank-alerts.com' (39/100 confidence).
- Observed stage order deviates from the canonical scam sequence; evidence acquisition order should be reviewed.

## Recommendations

- Case priority: LOW (5.5/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Report Provenance & Integrity

- **report id**: RPT-8F43434664-C68268EA
- **generated at**: 2026-07-25T13:02:00.249Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 979de3cce77008b7cb3832ef8c38159a1119b6bef7b3419c7fce7b4bfa73d1cb
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v4.json**: ef3671eddfa5c1bd32998bda6b9dbf225586f0700a5225404cef8510a53058b1
  - **cross case correlation v2.json**: 53686826421e33ffb0da4f92ca54a11b939fd97c615355f75065812ad8a4667f
  - **campaign analysis.json**: 80fc936883a286bff9b74b80c6b7b8d7a4c11b8679caf8f6ad076c7a4f22cf82
  - **suspect assessment.json**: 13058acf4753f8b9db3ad999f61279b334fd23ea43a4e8198799fe97fb6ef0af
  - **timeline analysis v4.json**: 98b621c111eb2448db9d6442ac6099f792491e9570c5d4bcb4fe73d66de77231
  - **analytics.json**: a0b6645b072c0977d20fa1a971634bb7ac29dd01170327c682967baf3547bdfa
  - **case priority.json**: 74bc79c5cbc8e70a1b7b0e494c5bcf0f3d40d86f809c30855ca917c8a9f86ea8
  - **graph v4.json**: 9d953b90eeca969c3739f39746e67ddecadde85a13f9224fadbaecb6c9a319f2

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
