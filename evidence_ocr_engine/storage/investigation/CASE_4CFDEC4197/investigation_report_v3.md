# Forensic Investigation Report - CASE_4CFDEC4197

Generated: 2026-07-25T14:41:38.444Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_4CFDEC4197 contains 1 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- The weighted correlation engine found 0 related evidence pair(s) out of 0 analysed [correlation_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 1 evidence item(s) acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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

- **case id**: CASE_4CFDEC4197
- **evidence count**: 1
- **first evidence**: 2026-07-25T14:41:19.994Z
- **last evidence**: 2026-07-25T14:41:19.994Z
- **file types**:
  - url

## Evidence Summary

- **evidence id**: EVID_00006
- **file name**: http_shared-scam-domain.test_pay.url
- **upload time**: 2026-07-25T14:41:19.994Z
- **sha256**: 08dcf69e8c1888d919ce088901076b95b3badf8d840a871a461d622d679ac619
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 2

## Correlation Analysis

- **pair count**: 0
- **related pair count**: 0
- **strength distribution**:
- **top relationships**:
  - none

## Cross-Case Correlation

No cross-case correlations were found for this case.

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00006
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 1 event(s) spanning 0.0 hour(s); 0 timestamp(s) unresolved.
- **stage progression**:
  - none
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-07-25T14:41:19.994000+00:00
  - **description**: Investigation start - first reconstructed evidence event
- **critical events**:
  - none

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 2.0
- **malicious indicators**: 2.0
- **evidence with threats**: 1.0
- **threat evidence ratio**: 1.0

## Model Prediction Results

No threat-intelligence provider was active during this analysis; indicator-level model predictions were not produced (this is a coverage gap, not an absence of threat).

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 1.0
- **hash verified count**: 1.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **domains**: 1
  - **urls**: 1
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 1.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 1.0
  - **resolved event count**: 1.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 1.0
  - **stage count**: 0.0
  - **critical event count**: 0.0
  - **timeline span hours**: 0.0
- **correlation statistics**:
  - **pair count**: 0.0
  - **related pair count**: 0.0
  - **mean confidence**: 0.0
  - **max confidence**: 0.0

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 1/1 evidence item(s) passed SHA-256 chain-of-custody verification.

## Recommendations

- Case priority: MEDIUM (30.8/100) - Standard queue: process in normal rotation while monitoring for new linked evidence.

## Report Provenance & Integrity

- **report id**: RPT-4CFDEC4197-B60A615A
- **generated at**: 2026-07-25T14:41:38.443Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 30154e0b4fa8b29d8178ef0a1ee9384b677bea00bd4af2b601145b7d9c29305a
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v3.json**: e2d689981a35276db7a3f669cfff67f88e5b0e7396792cfaf2c24ace312e9304
  - **cross case correlation v3.json**: 763f5ae0a738850661553a892a9085bdc655974bbed57bb7678369e0e3639f00
  - **campaign analysis.json**: 2c705fa0165570207686e21707dbbb05836bb1da772caff43f7da15f10a10620
  - **suspect assessment.json**: 5962fe553a6028fd0d6e48e154417ba6d599d0d5ae431da5e4980ca4f60c49da
  - **timeline analysis v3.json**: a560ed6e986059551185b9ce62aa0e6652bd2cd4f8217cf4e8564ff586abcfe5
  - **analytics.json**: 76205ca606995dfd9bddb30c8ef91c9b23a0da3bbad04e28453a16a5b1bc4e5e
  - **case priority.json**: e54606fce7c9bbb5854abc30155b8c372eee7f2b78f036e1fe8b07e7d54a10cb
  - **graph v3.json**: 19212aecdb0021ef087b0d4b2dcc2418c843c66aaa1a3db50acbb07bb4726a53

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00006
  - **sha256**: 08dcf69e8c1888d919ce088901076b95b3badf8d840a871a461d622d679ac619
  - **upload time**: 2026-07-25T14:41:19.994Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
