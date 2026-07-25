# Forensic Investigation Report - CASE_4106C94201

Generated: 2026-07-25T14:12:54.695Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_4106C94201 contains 1 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
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

- **case id**: CASE_4106C94201
- **evidence count**: 1
- **first evidence**: 2026-07-25T14:11:41.914Z
- **last evidence**: 2026-07-25T14:11:41.914Z
- **file types**:
  - url

## Evidence Summary

- **evidence id**: EVID_00014
- **file name**: https_www.telegrammessage.com_.url
- **upload time**: 2026-07-25T14:11:41.914Z
- **sha256**: 14625a373e9fcbc09d3047faae956eb1d23d38ed22deb9f816daff0136353200
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
  - EVID_00014
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 1 event(s) spanning 0.0 hour(s); 0 timestamp(s) unresolved.
- **stage progression**:
  - none
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-07-25T14:11:41.914000+00:00
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

- **indicators classified**: 1
- **flagged malicious**: 1
- **predictions**:
  - **indicator**: https://www.telegrammessage.com/
  - **evidence id**: EVID_00014
  - **verdict**: malicious
  - **risk score**: 81
  - **confidence**: 0.81
  - **risk level**: Critical
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: www.telegrammessage.com
  - **trust score**: 10
  - **brand impersonated**: telegram
  - **official domain**: False
  - **ssl status**: VALID
  - **domain age days**: 42
  - **registrar**: Spaceship, Inc.
  - **spf present**: False
  - **dmarc present**: False
  - **ssl days left**: 51
  - **hosting**: Cloudflare, Inc., Canada
  - **ip address**: 104.21.88.199
  - **reasons**:
    - The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.
    - AI model classified this URL as phishing with 97% confidence.
    - The domain contains the brand name 'telegram' but is not the official domain -- possible brand impersonation.
    - The domain is missing SPF and DMARC email-authentication record(s), which legitimate organisations typically configure.
    - The domain contains 'telegram' but is not the official telegram.com domain — a common brand impersonation technique.
    - Brand 'Telegram' referenced in hostname, but registrable domain 'telegrammessage.com' does not belong to the official Telegram infrastructure.
  - **threat signals**:
    - ✗ Impersonates known brand: telegram (found in domain)
    - ✗ Recently registered domain (age 42 days)
    - ✗ Missing SPF record (facilitates email spoofing)
    - ✗ Missing DMARC record (facilitates email spoofing)
  - **trust signals**:
    - ✓ Valid SSL certificate
    - ✓ Registered with trusted registrar (Spaceship, Inc.)
    - ✓ Hosted on a trusted enterprise network (Cloudflare, Inc.)

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

- **report id**: RPT-4106C94201-9078601B
- **generated at**: 2026-07-25T14:12:54.685Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 3bebac03c4a83c85e101c7e264d7e5ad4517ed7bc5c3fdff5820dd343991c5ad
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v3.json**: 3c8bc986fe669b71997ec8ebcb49077f2d23bb3d4a1eda51dcfb38f1f6150406
  - **cross case correlation.json**: 037204937a4cff74d5de9ef621a3435c7db1332c1c518a22a5bd9f894fc3e680
  - **campaign analysis v2.json**: e0aabe435bc128dfaa671ed1d6cd4304889473fa0e5c79caa9d78480b30f4ead
  - **suspect assessment v2.json**: ec1da792d58230213aa88fa419aa161fb68d460aecb13e986ae224316f91e0ad
  - **timeline analysis v3.json**: 2320d3ad682bccab730ac3b6ee43cdff3e7a5c14cc9d71cf455fda1bac4302e1
  - **analytics v2.json**: 06c68cf61e6c392d1055a96328f5dbfd6c37c03b6a1e1bc8d889625b42117199
  - **case priority v2.json**: 28e1ad0105e7797569cf2a88edcdd6c892246f01d8db27e73284c046b061cd83
  - **graph v3.json**: aee02f951b904f56057328a50e898cc79c2086b90e4c938ea0e98faa9f64d190

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00014
  - **sha256**: 14625a373e9fcbc09d3047faae956eb1d23d38ed22deb9f816daff0136353200
  - **upload time**: 2026-07-25T14:11:41.914Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
