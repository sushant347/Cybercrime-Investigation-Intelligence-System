# Forensic Investigation Report - CASE_2CF24DBA5F

Generated: 2026-07-25T12:53:55.993Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_2CF24DBA5F contains 4 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- The weighted correlation engine found 6 related evidence pair(s) out of 6 analysed [correlation_analysis.json].
- The strongest suspect anchor is 'security@nabil-bank-alerts.com' (emails) with confidence 39/100 [suspect_assessment.json].
- Observed attack progression: initial_contact -> financial_transaction -> social_engineering -> credential_theft [timeline_analysis.json].

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

- **case id**: CASE_2CF24DBA5F
- **evidence count**: 4
- **first evidence**: 2026-07-25T12:50:00.695Z
- **last evidence**: 2026-07-25T12:53:47.011Z
- **file types**:
  - jpg
  - png
  - txt

## Evidence Summary

- **evidence id**: EVID_00001
- **file name**: yeti.jpg
- **upload time**: 2026-07-25T12:50:00.695Z
- **sha256**: 8f2e60ea6fc0eeffd209e28eb29228797104b60a2505934fc3d42642c100ea79
- **hash verified**: True
- **ocr confidence**: 0.9152
- **evidence confidence score**: not available
- **entity count**: 4
- **evidence id**: EVID_00002
- **file name**: whatsapp_chat_export.txt
- **upload time**: 2026-07-25T12:53:07.182Z
- **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 5
- **evidence id**: EVID_00003
- **file name**: romanchat.jpg
- **upload time**: 2026-07-25T12:53:23.174Z
- **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
- **hash verified**: True
- **ocr confidence**: 0.9686
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00004
- **file name**: phishing_email_screenshot.png
- **upload time**: 2026-07-25T12:53:47.011Z
- **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
- **hash verified**: True
- **ocr confidence**: 0.9859
- **evidence confidence score**: not available
- **entity count**: 4

## Correlation Analysis

- **pair count**: 6
- **related pair count**: 6
- **strength distribution**:
  - **WEAK**: 6
- **top relationships**:
  - **pair**: EVID_00001 <-> EVID_00002
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (yeti.jpg) and EVID_00002 (whatsapp_chat_export.txt) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00003
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (yeti.jpg) and EVID_00003 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00004
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (yeti.jpg) and EVID_00004 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00002 <-> EVID_00003
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00002 (whatsapp_chat_export.txt) and EVID_00003 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00002 <-> EVID_00004
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00002 (whatsapp_chat_export.txt) and EVID_00004 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

No cross-case correlations were found for this case.

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00001
  - EVID_00002
  - EVID_00003
  - EVID_00004
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 4 event(s) spanning 4851.7 hour(s); 0 timestamp(s) unresolved. Observed scam progression: initial_contact -> financial_transaction -> social_engineering -> credential_theft.
- **stage progression**:
  - initial_contact
  - financial_transaction
  - social_engineering
  - credential_theft
- **progression consistent**: False
- **milestones**:
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: First observation of stage 'initial_contact' (EVID_00002)
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00002)
  - **timestamp**: 2026-07-25T12:53:47.011000+00:00
  - **description**: First observation of stage 'social_engineering' (EVID_00004)
  - **timestamp**: 2026-07-25T12:53:47.011000+00:00
  - **description**: First observation of stage 'credential_theft' (EVID_00004)
- **critical events**:
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **evidence id**: EVID_00002
  - **reasons**:
    - contains money entity/entities: Rs 2000

## Suspect Assessment

- **suspect id**: SUSPECT_CASE_2CF24DBA5F_01
- **identity**: emails:security@nabil-bank-alerts.com
- **confidence score**: 38.8
- **confidence level**: LOW
- **risk level**: LOW
- **evidence ids**:
  - EVID_00004
- **explanation**: Suspect anchor 'security@nabil-bank-alerts.com' (emails) scores 38.8/100 (LOW, risk LOW) across 1 evidence item(s): EVID_00004. Identity strength: 75/100 (weight 0.25) - 'security@nabil-bank-alerts.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 4 evidence item(s). Evidence confidence: 50/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 50/100 (no Phase-1 scores stored; neutral 50 assumed). Threat intelligence: 0/100 (weight 0.15) - no threat-intelligence indicator file available. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set.

## Threat Intelligence Summary

No threat-intelligence indicator file was provided; threat corroboration was skipped (not an absence of threat).

## Model Prediction Results

No threat-intelligence provider was active during this analysis; indicator-level model predictions were not produced (this is a coverage gap, not an absence of threat).

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.97
- **hash verified count**: 4.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **dates**: 1
  - **domains**: 2
  - **emails**: 1
  - **money**: 1
  - **ports**: 2
  - **times**: 5
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
  - **inferred event count**: 3.0
  - **stage count**: 4.0
  - **critical event count**: 1.0
  - **timeline span hours**: 4851.7
- **correlation statistics**:
  - **pair count**: 6.0
  - **related pair count**: 6.0
  - **mean confidence**: 0.2212
  - **max confidence**: 0.2212

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 4/4 evidence item(s) passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (6 weighted relationship(s)), consistent with related activity rather than isolated incidents.
- Investigation should focus on anchor 'security@nabil-bank-alerts.com' (39/100 confidence).
- Observed stage order deviates from the canonical scam sequence; evidence acquisition order should be reviewed.

## Recommendations

- Prioritise the 1 critical event(s) involving OTP/financial entities for victim-impact assessment.
- Case priority: LOW (13.8/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Report Provenance & Integrity

- **report id**: RPT-2CF24DBA5F-010216D0
- **generated at**: 2026-07-25T12:53:55.992Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 845d2580a93c7505d88a3b735dd3a956db233d26f779d05f4a85f60abfe82c3f
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v5.json**: 606cd3e9ddfb9ea51edae3fd4809b28c145ded3c31c71a77552d3134012b22d5
  - **cross case correlation.json**: ec5d454817713980deeaaa23fe58adf8ffef30b91488d6aac04b194addcc7b17
  - **campaign analysis.json**: 69e9ef6d9e9ed939484307d8d50cb975803a505a9aeb0a7926fde19b38bb344e
  - **suspect assessment.json**: 2eb4374c1f785a610e6d940e9cf2d9e038cc6e33a958bca933ba2e0ddb89da88
  - **timeline analysis v5.json**: d79e22ff86d5f7eb147dcc7d438e8e13adeedea98c801ae754f82f67ddb2dfd5
  - **analytics.json**: 22df3eb99a31dff38b24892ee9adfdb7fe951595e96e99232962fc231313ee4d
  - **case priority.json**: 186dbbf2d52b4faa5c8d137af1e04e7d5c86110faa5c4a680f482ff16d93b2b5
  - **graph v5.json**: dc41844c51c4135f888e6339c7f06cfc362878b86373ddedbcff39f112f94327

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00001
  - **sha256**: 8f2e60ea6fc0eeffd209e28eb29228797104b60a2505934fc3d42642c100ea79
  - **upload time**: 2026-07-25T12:50:00.695Z
  - **status**: processed
  - **evidence id**: EVID_00002
  - **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
  - **upload time**: 2026-07-25T12:53:07.182Z
  - **status**: processed
  - **evidence id**: EVID_00003
  - **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
  - **upload time**: 2026-07-25T12:53:23.174Z
  - **status**: processed
  - **evidence id**: EVID_00004
  - **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
  - **upload time**: 2026-07-25T12:53:47.011Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
