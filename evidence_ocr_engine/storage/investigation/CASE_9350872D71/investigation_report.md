# Forensic Investigation Report - CASE_9350872D71

Generated: 2026-07-25T13:52:24.247Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_9350872D71 contains 2 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 1 other case(s) through shared entities: CASE_36BBE50ED9 [cross_case_correlation.json].
- The weighted correlation engine found 1 related evidence pair(s) out of 1 analysed [correlation_analysis.json].
- Observed attack progression: financial_transaction -> post_attack [timeline_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 2 evidence item(s) acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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

- **case id**: CASE_9350872D71
- **evidence count**: 2
- **first evidence**: 2026-07-25T13:51:58.581Z
- **last evidence**: 2026-07-25T13:52:01.149Z
- **file types**:
  - jpg
  - pdf

## Evidence Summary

- **evidence id**: EVID_00011
- **file name**: police_scan_report.pdf
- **upload time**: 2026-07-25T13:51:58.581Z
- **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 1
- **evidence id**: EVID_00012
- **file name**: romanchat.jpg
- **upload time**: 2026-07-25T13:52:01.149Z
- **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
- **hash verified**: True
- **ocr confidence**: 0.9686
- **evidence confidence score**: not available
- **entity count**: 0

## Correlation Analysis

- **pair count**: 1
- **related pair count**: 1
- **strength distribution**:
  - **WEAK**: 1
- **top relationships**:
  - **pair**: EVID_00011 <-> EVID_00012
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00011 (police_scan_report.pdf) and EVID_00012 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

- **related case count**: 1
- **related case ids**:
  - CASE_36BBE50ED9
- **links**:
  - **other case id**: CASE_36BBE50ED9
  - **relationship strength**: WEAK
  - **match confidence**: 0.1175
  - **match reason**: Shares 1 entity(ies) with CASE_36BBE50ED9: money npr 250000
  - **matched entities**:
    - **entity type**: money
    - **value**: npr 250000
    - **this evidence ids**:
      - EVID_00011
    - **other evidence ids**:
      - EVID_00009

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00011
  - EVID_00012
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 2 event(s) spanning 0.0 hour(s); 0 timestamp(s) unresolved. Observed scam progression: financial_transaction -> post_attack.
- **stage progression**:
  - financial_transaction
  - post_attack
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-07-25T13:51:58.581000+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-07-25T13:51:58.581000+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00011)
  - **timestamp**: 2026-07-25T13:51:58.581000+00:00
  - **description**: First observation of stage 'post_attack' (EVID_00011)
- **critical events**:
  - **timestamp**: 2026-07-25T13:51:58.581000+00:00
  - **evidence id**: EVID_00011
  - **reasons**:
    - contains money entity/entities: NPR 250000

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
- **mean ocr confidence**: 0.98
- **hash verified count**: 2.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **money**: 1
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 2.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 2.0
  - **resolved event count**: 2.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 2.0
  - **stage count**: 2.0
  - **critical event count**: 1.0
  - **timeline span hours**: 0.0
- **correlation statistics**:
  - **pair count**: 1.0
  - **related pair count**: 1.0
  - **mean confidence**: 0.2212
  - **max confidence**: 0.2212

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 2/2 evidence item(s) passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (1 weighted relationship(s)), consistent with related activity rather than isolated incidents.

## Recommendations

- Prioritise the 1 critical event(s) involving OTP/financial entities for victim-impact assessment.
- Case priority: LOW (13.8/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Report Provenance & Integrity

- **report id**: RPT-9350872D71-AA6EDB3A
- **generated at**: 2026-07-25T13:52:24.242Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: d3cb154946a6e9a9f5402a1562adebe09a30db0c86156993cb20913b3f8f33b7
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v3.json**: 9f71c2ac2aaa377ae7467a39404d7ff158ead7a43c420aca148d2bf11c0acd0b
  - **cross case correlation.json**: 4ce52bade5f8d6b4c6f6f75272414bf2d2544ec2ca13a20ad3391e3536423405
  - **campaign analysis.json**: d4133aeda587132df2bf9f2522530d186cfc673bad20c3ac43f024beef62d811
  - **suspect assessment.json**: cfdee972884dad660645bcec78ceb40a7eb0c91d9d495e930d713234a2923a42
  - **timeline analysis v3.json**: 2df24804ea13fa3d9c75cef3264c5fc0ffd59ee58333d2bc6f0ef04928564a24
  - **analytics.json**: f6ae8834f8d4fc80e957d93c216e96cc2b709089025fe9a9c43674c2de38b8a0
  - **case priority.json**: 13b4dbf750bb87c3867d77acc8b771cab83ddecc400ebc9f57f7fbe0a840a932
  - **graph v3.json**: a372e621d1243bace481fce762f83442d60de7f2d5bc7751e3b056ee7f6d7000

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00011
  - **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
  - **upload time**: 2026-07-25T13:51:58.581Z
  - **status**: processed
  - **evidence id**: EVID_00012
  - **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
  - **upload time**: 2026-07-25T13:52:01.149Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
