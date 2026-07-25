# Forensic Investigation Report - CASE_36BBE50ED9

Generated: 2026-07-25T13:52:24.397Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_36BBE50ED9 contains 2 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 1 other case(s) through shared entities: CASE_9350872D71 [cross_case_correlation.json].
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

- **case id**: CASE_36BBE50ED9
- **evidence count**: 2
- **first evidence**: 2026-07-25T13:49:37.749Z
- **last evidence**: 2026-07-25T13:49:40.306Z
- **file types**:
  - csv
  - pdf

## Evidence Summary

- **evidence id**: EVID_00009
- **file name**: police_scan_report.pdf
- **upload time**: 2026-07-25T13:49:37.749Z
- **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 1
- **evidence id**: EVID_00010
- **file name**: bank_transactions.csv
- **upload time**: 2026-07-25T13:49:40.306Z
- **sha256**: fbc5fcf7403a5aa8c042baed4343d0162e8d3506ff5d1163864662d25602e87e
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 2

## Correlation Analysis

- **pair count**: 1
- **related pair count**: 1
- **strength distribution**:
  - **WEAK**: 1
- **top relationships**:
  - **pair**: EVID_00009 <-> EVID_00010
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00009 (police_scan_report.pdf) and EVID_00010 (bank_transactions.csv) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

- **related case count**: 1
- **related case ids**:
  - CASE_9350872D71
- **links**:
  - **other case id**: CASE_9350872D71
  - **relationship strength**: WEAK
  - **match confidence**: 0.1175
  - **match reason**: Shares 1 entity(ies) with CASE_9350872D71: money npr 250000
  - **matched entities**:
    - **entity type**: money
    - **value**: npr 250000
    - **this evidence ids**:
      - EVID_00009
    - **other evidence ids**:
      - EVID_00011

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00009
  - EVID_00010
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 2 event(s) spanning 4861.8 hour(s); 0 timestamp(s) unresolved. Observed scam progression: financial_transaction -> post_attack.
- **stage progression**:
  - financial_transaction
  - post_attack
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-01-04T00:00:00+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-01-04T00:00:00+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00010)
  - **timestamp**: 2026-07-25T13:49:37.749000+00:00
  - **description**: First observation of stage 'post_attack' (EVID_00009)
- **critical events**:
  - **timestamp**: 2026-07-25T13:49:37.749000+00:00
  - **evidence id**: EVID_00009
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
- **mean ocr confidence**: 1.0
- **hash verified count**: 2.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **dates**: 2
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
  - **timeline span hours**: 4861.83
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

- **report id**: RPT-36BBE50ED9-868B9B4C
- **generated at**: 2026-07-25T13:52:24.394Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 4ae6ecf18ac754c27899be758225d730e56c272281c639e9a7f5d0dccda2600c
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v3.json**: 07f2d6b71782322ce24dc77d2f2c949651eacfd80ed416e62c02fcf6237166eb
  - **cross case correlation v2.json**: 821221364299d80f47081fb4b375fe2271df2c48654383a6b550b935524e899d
  - **campaign analysis.json**: a741c38d16a6e83430586bce53349dd129389edcde638455fb97b0b1b8491cd3
  - **suspect assessment.json**: f1196001c8590f39790a43cb042ac15ce2375a43279f79491bd75d498aca62de
  - **timeline analysis v3.json**: 2556f16ce8463a51351be7d87f50c6763fe5f4fe4c681cd7551d7ae6efccfca9
  - **analytics.json**: 6640d027b929e7b194f6d8ef6554e591f9662cefed46e339f5e68f140ce1d7d4
  - **case priority.json**: 725a3e367b1afdda774e11082e192e116e83da09a7dfca0c36a75e0fca904c7b
  - **graph v3.json**: 0af834eac3b0fbe2ffa0b4d09c76c67d6364204e8d72604c93158fe70dc23a9a

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00009
  - **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
  - **upload time**: 2026-07-25T13:49:37.749Z
  - **status**: processed
  - **evidence id**: EVID_00010
  - **sha256**: fbc5fcf7403a5aa8c042baed4343d0162e8d3506ff5d1163864662d25602e87e
  - **upload time**: 2026-07-25T13:49:40.306Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
