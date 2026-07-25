# Forensic Investigation Report - CASE_85B2471DFB

Generated: 2026-07-25T14:24:15.533Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_85B2471DFB contains 0 evidence item(s), each acquired under SHA-256 chain-of-custody verification.

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 0 evidence item(s) acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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

- **case id**: CASE_85B2471DFB
- **evidence count**: 0
- **first evidence**: not available
- **last evidence**: not available
- **file types**:
  - none

## Evidence Summary

- none

## Correlation Analysis

Correlation analysis not available for this case.

## Cross-Case Correlation

No cross-case correlations were found for this case.

## Campaign Analysis

Campaign analysis not available for this case.

## Timeline Analysis

Timeline analysis not available for this case.

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

Threat statistics not available.

## Model Prediction Results

The active threat-intelligence provider returned no classification for any URL/domain indicator in this case's evidence.

## Evidence Quality Summary

- **hash verified count**: 0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

Analytics not available.

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 0/0 evidence item(s) passed SHA-256 chain-of-custody verification.

## Recommendations

- No specific action items derived; continue standard processing.

## Report Provenance & Integrity

- **report id**: RPT-85B2471DFB-640A81CB
- **generated at**: 2026-07-25T14:24:15.532Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **cross case correlation.json**: fd38da6a9e84c64799e571e0514d2eeb7c492b3451f98da7a3aaf2b50c438f51

## Appendix

- **chain of custody**:
  - none
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
