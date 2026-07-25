# Forensic Investigation Report - CASE_EE8250FB76

Generated: 2026-07-25T17:26:36.787Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_EE8250FB76 contains 2 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 1 other case(s) through shared entities: CASE_185915593C [cross_case_correlation.json].

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

- **case id**: CASE_EE8250FB76
- **evidence count**: 2
- **first evidence**: 2026-07-25T16:24:17.560Z
- **last evidence**: 2026-07-25T16:24:18.091Z
- **file types**:
  - pdf

## Evidence Summary

- **evidence id**: EVID_00005
- **file name**: 08_complaint_letter.pdf
- **upload time**: 2026-07-25T16:24:17.560Z
- **sha256**: fe644062bf75e62c8ae13ec24c7e0461491a5610095a50546c4fa757d98e866f
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: 100.0
- **entity count**: 25
- **evidence id**: EVID_00006
- **file name**: 07_bank_transfer_slip.pdf
- **upload time**: 2026-07-25T16:24:18.091Z
- **sha256**: 6f1cc10ae55d554c751ee1cbf688924c8962c5faebe87be8c457d077d6bc63c2
- **hash verified**: False
- **ocr confidence**: 0.0
- **evidence confidence score**: not available
- **entity count**: 0

## Correlation Analysis

Correlation analysis not available for this case.

## Cross-Case Correlation

- **related case count**: 1
- **related case ids**:
  - CASE_185915593C
- **links**:
  - **other case id**: CASE_185915593C
  - **relationship strength**: VERY_STRONG
  - **match confidence**: 0.9999
  - **match reason**: Shares 21 entity(ies) with CASE_185915593C: bank account 05019012345678, domain esewa-cashback-offer.xyz, domain esewa-verify-kyc.com (+18 more)
  - **matched entities**:
    - **entity type**: bank_accounts
    - **value**: 05019012345678
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014
    - **entity type**: domains
    - **value**: esewa-cashback-offer.xyz
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00009
      - EVID_00011
      - EVID_00014
    - **entity type**: domains
    - **value**: esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014
    - **entity type**: domains
    - **value**: gmail.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00008
      - EVID_00014
    - **entity type**: emails
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014
    - **entity type**: emails
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00008
      - EVID_00014
    - **entity type**: emails
    - **value**: support@esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014
    - **entity type**: esewa_ids
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014
    - **entity type**: esewa_ids
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00008
      - EVID_00014
    - **entity type**: khalti_ids
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00011
      - EVID_00014
    - **entity type**: money
    - **value**: npr 1500
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00011
      - EVID_00014
    - **entity type**: money
    - **value**: npr 200
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00008
      - EVID_00010
      - EVID_00014
    - **entity type**: money
    - **value**: npr 25000
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00013
      - EVID_00014
    - **entity type**: money
    - **value**: npr 5000
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00009
      - EVID_00014
    - **entity type**: phones
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00011
      - EVID_00012
      - EVID_00014
    - **entity type**: phones
    - **value**: +9779847011223
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00011
      - EVID_00013
      - EVID_00014
    - **entity type**: transaction_ids
    - **value**: 0119.0625.987456
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00010
      - EVID_00014
    - **entity type**: transaction_ids
    - **value**: case_2026_0088
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014
    - **entity type**: transaction_ids
    - **value**: kh-2026-0611-77245
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00011
      - EVID_00014
    - **entity type**: transaction_ids
    - **value**: mbl-2026-441829
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00013
      - EVID_00014
    - **entity type**: urls
    - **value**: https://esewa-cashback-offer.xyz/claim
    - **this evidence ids**:
      - EVID_00005
    - **other evidence ids**:
      - EVID_00014

## Campaign Analysis

Campaign analysis not available for this case.

## Timeline Analysis

Timeline analysis not available for this case.

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

Threat statistics not available.

## Model Prediction Results

- **indicators classified**: 3
- **flagged malicious**: 2
- **predictions**:
  - **indicator**: https://esewa-cashback-offer.xyz/claim
  - **evidence id**: EVID_00005
  - **verdict**: malicious
  - **risk score**: 81
  - **confidence**: 0.81
  - **risk level**: Critical
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: esewa-cashback-offer.xyz
  - **trust score**: 35
  - **official domain**: False
  - **ssl status**: UNKNOWN
  - **spf present**: False
  - **dmarc present**: False
  - **reasons**:
    - The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.
    - AI model classified this URL as phishing with 100% confidence.
    - The top-level domain is frequently associated with phishing and spam campaigns (risk score: 0.7).
    - SSL status could not be verified.
    - The URL contains suspicious keyword(s) associated with phishing.
    - The domain is missing SPF and DMARC email-authentication record(s), which legitimate organisations typically configure.
  - **threat signals**:
    - ✗ Missing SPF record (facilitates email spoofing)
    - ✗ Missing DMARC record (facilitates email spoofing)
    - ✗ High-abuse top-level domain
    - ✗ Phishing-associated keyword(s) in URL
  - **indicator**: esewa-verify-kyc.com
  - **evidence id**: EVID_00005
  - **verdict**: malicious
  - **risk score**: 79
  - **confidence**: 0.79
  - **risk level**: High
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: esewa-verify-kyc.com
  - **trust score**: 50
  - **official domain**: False
  - **ssl status**: UNKNOWN
  - **spf present**: False
  - **dmarc present**: False
  - **reasons**:
    - The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.
    - AI model classified this URL as phishing with 100% confidence.
    - SSL status could not be verified.
    - The URL does not use HTTPS, meaning data is transmitted without encryption.
    - The URL contains suspicious keyword(s) associated with phishing.
    - The domain is missing SPF and DMARC email-authentication record(s), which legitimate organisations typically configure.
  - **threat signals**:
    - ✗ Plain HTTP protocol used (unencrypted connections)
    - ✗ Missing SPF record (facilitates email spoofing)
    - ✗ Missing DMARC record (facilitates email spoofing)
    - ✗ Phishing-associated keyword(s) in URL
  - **indicator**: gmail.com
  - **evidence id**: EVID_00005
  - **verdict**: benign
  - **risk score**: 20
  - **confidence**: 0.8
  - **risk level**: Low
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: gmail.com
  - **trust score**: 100
  - **brand impersonated**: google
  - **official domain**: True
  - **ssl status**: VALID
  - **domain age days**: 11304
  - **registrar**: MarkMonitor, Inc.
  - **spf present**: True
  - **dmarc present**: True
  - **ssl days left**: 57
  - **hosting**: Google LLC, United States
  - **ip address**: 192.178.174.83
  - **reasons**:
    - The hybrid decision engine confirmed this URL is legitimate based on trusted signals and ML model agreement.
    - The URL does not use HTTPS, meaning data is transmitted without encryption.
  - **threat signals**:
    - ✗ Plain HTTP protocol used (unencrypted connections)
  - **trust signals**:
    - ✓ Official registered domain of trusted brand: google
    - ✓ Valid SSL certificate
    - ✓ HTTPS Strict-Transport-Security (HSTS) active
    - ✓ Established domain age (30.9 years old)
    - ✓ Registered with trusted registrar (MarkMonitor, Inc.)
    - ✓ SPF email authentication configured

## Evidence Quality Summary

- **hash verified count**: 1

## Metadata Summary

- **evidence id**: EVID_00005
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - none

## Investigation Statistics

Analytics not available.

## Confidence Analysis

- **evidence id**: EVID_00005
- **score**: 100.0
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100).

## Investigation Conclusion

- 1/2 evidence item(s) passed SHA-256 chain-of-custody verification.

## Recommendations

- No specific action items derived; continue standard processing.

## Report Provenance & Integrity

- **report id**: RPT-EE8250FB76-7BBFA0D7
- **generated at**: 2026-07-25T17:26:36.786Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 0f6afe626b2e5e1c4bb70b2efae2d8aea52ca3d8d38b481532cc8e4ff88c3ff6
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **cross case correlation.json**: 01ce932a6ed2e65406f905490d9a7897c203f208268411261779ad758f304b91

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00005
  - **sha256**: fe644062bf75e62c8ae13ec24c7e0461491a5610095a50546c4fa757d98e866f
  - **upload time**: 2026-07-25T16:24:17.560Z
  - **status**: processed
  - **evidence id**: EVID_00006
  - **sha256**: 6f1cc10ae55d554c751ee1cbf688924c8962c5faebe87be8c457d077d6bc63c2
  - **upload time**: 2026-07-25T16:24:18.091Z
  - **status**: uploaded
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
