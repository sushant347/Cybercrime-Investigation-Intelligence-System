# Forensic Investigation Report - CASE_2CF24DBA5F

Generated: 2026-07-25T14:45:18.982Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_2CF24DBA5F contains 5 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- The weighted correlation engine found 10 related evidence pair(s) out of 10 analysed [correlation_analysis.json].
- The strongest suspect anchor is 'security@nabil-bank-alerts.com' (emails) with confidence 54/100 [suspect_assessment.json].
- Observed attack progression: initial_contact -> financial_transaction -> post_attack -> social_engineering -> credential_theft [timeline_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 5 evidence item(s) acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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
- **evidence count**: 5
- **first evidence**: 2026-07-25T14:22:38.355Z
- **last evidence**: 2026-07-25T14:24:07.592Z
- **file types**:
  - jpg
  - pdf
  - png
  - txt
  - url

## Evidence Summary

- **evidence id**: EVID_00001
- **file name**: https_plasticostermoencogibles.pe_scss_css_scss_.url
- **upload time**: 2026-07-25T14:22:38.355Z
- **sha256**: fab44e99bd90f1ffe214d4d2bb6580e4c0d52f5fe930e773d96cf92ee820a2f5
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 2
- **evidence id**: EVID_00002
- **file name**: police_scan_report.pdf
- **upload time**: 2026-07-25T14:23:23.722Z
- **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 1
- **evidence id**: EVID_00003
- **file name**: phishing_email_screenshot.png
- **upload time**: 2026-07-25T14:23:26.295Z
- **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
- **hash verified**: True
- **ocr confidence**: 0.9859
- **evidence confidence score**: not available
- **entity count**: 4
- **evidence id**: EVID_00004
- **file name**: const.jpg
- **upload time**: 2026-07-25T14:23:41.798Z
- **sha256**: d07bcc76b5d280385a06f106c083edc33bff69e82ac63fddf8c433f6b4a5fc02
- **hash verified**: True
- **ocr confidence**: 0.9014
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00005
- **file name**: whatsapp_chat_export.txt
- **upload time**: 2026-07-25T14:24:07.592Z
- **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 5

## Correlation Analysis

- **pair count**: 10
- **related pair count**: 10
- **strength distribution**:
  - **WEAK**: 10
- **top relationships**:
  - **pair**: EVID_00001 <-> EVID_00002
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (https_plasticostermoencogibles.pe_scss_css_scss_.url) and EVID_00002 (police_scan_report.pdf) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00003
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (https_plasticostermoencogibles.pe_scss_css_scss_.url) and EVID_00003 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00004
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (https_plasticostermoencogibles.pe_scss_css_scss_.url) and EVID_00004 (const.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00005
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (https_plasticostermoencogibles.pe_scss_css_scss_.url) and EVID_00005 (whatsapp_chat_export.txt) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00002 <-> EVID_00003
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00002 (police_scan_report.pdf) and EVID_00003 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

No cross-case correlations were found for this case.

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00001
  - EVID_00002
  - EVID_00003
  - EVID_00004
  - EVID_00005
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 5 event(s) spanning 4853.2 hour(s); 0 timestamp(s) unresolved. Observed scam progression: initial_contact -> financial_transaction -> post_attack -> social_engineering -> credential_theft.
- **stage progression**:
  - initial_contact
  - financial_transaction
  - post_attack
  - social_engineering
  - credential_theft
- **progression consistent**: False
- **milestones**:
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: First observation of stage 'initial_contact' (EVID_00005)
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00005)
  - **timestamp**: 2026-07-25T14:23:23.722000+00:00
  - **description**: First observation of stage 'post_attack' (EVID_00002)
  - **timestamp**: 2026-07-25T14:23:26.295000+00:00
  - **description**: First observation of stage 'social_engineering' (EVID_00003)
  - **timestamp**: 2026-07-25T14:23:26.295000+00:00
  - **description**: First observation of stage 'credential_theft' (EVID_00003)
- **critical events**:
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **evidence id**: EVID_00005
  - **reasons**:
    - contains money entity/entities: NPR 2000
  - **timestamp**: 2026-07-25T14:23:23.722000+00:00
  - **evidence id**: EVID_00002
  - **reasons**:
    - contains money entity/entities: NPR 250000

## Suspect Assessment

- **suspect id**: SUSPECT_CASE_2CF24DBA5F_01
- **identity**: emails:security@nabil-bank-alerts.com
- **confidence score**: 53.8
- **confidence level**: MODERATE
- **risk level**: MEDIUM
- **evidence ids**:
  - EVID_00003
- **explanation**: Suspect anchor 'security@nabil-bank-alerts.com' (emails) scores 53.8/100 (MODERATE, risk MEDIUM) across 1 evidence item(s): EVID_00003. Identity strength: 75/100 (weight 0.25) - 'security@nabil-bank-alerts.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 5 evidence item(s). Evidence confidence: 50/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 50/100 (no Phase-1 scores stored; neutral 50 assumed). Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'http://nabil-verify.example-scam.top/login' in EVID_00003. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set.

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 5.0
- **malicious indicators**: 3.0
- **evidence with threats**: 1.0
- **threat evidence ratio**: 0.2

## Model Prediction Results

- **indicators classified**: 3
- **flagged malicious**: 2
- **predictions**:
  - **indicator**: http://nabil-verify.example-scam.top/login
  - **evidence id**: EVID_00003
  - **verdict**: malicious
  - **risk score**: 81
  - **confidence**: 0.81
  - **risk level**: Critical
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: nabil-verify.example-scam.top
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
    - The URL does not use HTTPS, meaning data is transmitted without encryption.
    - The URL contains suspicious keyword(s) associated with phishing.
  - **threat signals**:
    - ✗ Plain HTTP protocol used (unencrypted connections)
    - ✗ Missing SPF record (facilitates email spoofing)
    - ✗ Missing DMARC record (facilitates email spoofing)
    - ✗ High-abuse top-level domain
    - ✗ Phishing-associated keyword(s) in URL
  - **indicator**: nabil-bank-alerts.com
  - **evidence id**: EVID_00003
  - **verdict**: malicious
  - **risk score**: 79
  - **confidence**: 0.79
  - **risk level**: High
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: nabil-bank-alerts.com
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
  - **indicator**: https://plasticostermoencogibles.pe/scss/css/scss/
  - **evidence id**: EVID_00001
  - **verdict**: suspicious
  - **risk score**: 42
  - **confidence**: 0.94
  - **risk level**: Medium
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: plasticostermoencogibles.pe
  - **trust score**: 75
  - **official domain**: False
  - **ssl status**: VALID
  - **registrar**: Yachay Telecomunicaciones
  - **spf present**: True
  - **dmarc present**: False
  - **ssl days left**: 35
  - **hosting**: DEFT.COM, United States
  - **ip address**: 75.102.22.119
  - **reasons**:
    - The hybrid decision engine flagged this URL as suspicious due to mixed signals between the ML model, active rules, and threat intelligence.
    - AI model classified this URL as phishing with 100% confidence.
    - The domain is missing DMARC email-authentication record(s), which legitimate organisations typically configure.
  - **threat signals**:
    - ✗ Missing DMARC record (facilitates email spoofing)
  - **trust signals**:
    - ✓ Valid SSL certificate
    - ✓ Registered with trusted registrar (Yachay Telecomunicaciones)
    - ✓ SPF email authentication configured

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.98
- **hash verified count**: 5.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **dates**: 1
  - **domains**: 3
  - **emails**: 1
  - **money**: 2
  - **times**: 3
  - **urls**: 2
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 5.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 5.0
  - **resolved event count**: 5.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 4.0
  - **stage count**: 5.0
  - **critical event count**: 2.0
  - **timeline span hours**: 4853.19
- **correlation statistics**:
  - **pair count**: 10.0
  - **related pair count**: 10.0
  - **mean confidence**: 0.2212
  - **max confidence**: 0.2212

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 5/5 evidence item(s) passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (10 weighted relationship(s)), consistent with related activity rather than isolated incidents.
- Investigation should focus on anchor 'security@nabil-bank-alerts.com' (54/100 confidence).
- Observed stage order deviates from the canonical scam sequence; evidence acquisition order should be reviewed.

## Recommendations

- Pursue subscriber/KYC records for email 'security@nabil-bank-alerts.com' (suspect confidence 54/100).
- Prioritise the 2 critical event(s) involving OTP/financial entities for victim-impact assessment.
- Case priority: LOW (21.6/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Report Provenance & Integrity

- **report id**: RPT-2CF24DBA5F-C2E2DACB
- **generated at**: 2026-07-25T14:45:18.979Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: f8320f982f3c29e5b76842e5e4ffef335f82140f5388e98ff6a8c8f992f16825
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis v9.json**: ca426761da8574f896a033abc3d929563c4a5c12da58e63302e865bbcb15b9a1
  - **cross case correlation v3.json**: c62e8db800905c481bc8f84d740e477ef15811f557e91e791318f20f69514027
  - **campaign analysis v4.json**: 867165c44b0d22d55f575534b71edba21658de1fc48dfb6006ada9d078798f0b
  - **suspect assessment v4.json**: 6bd8090d54379234f54a025b6669a4471c5fb99ce1da55142ef5664dafd2b6a2
  - **timeline analysis v9.json**: 4d97b7f30799f982f26c58a57ebd602e39b593b7bd1c23fc5090ef2c510a28fd
  - **analytics v4.json**: ee5dfd0f7d535152fc230ace2ecd580341159d5e88371b5eb26f5a2f21f8195d
  - **case priority v4.json**: 33a2d5f473a69565f32cb5e83f86df9c708e1ef79c607e8f806296be6fa39c22
  - **graph v9.json**: 5c8e861eb531efca38b68454631b286867c1796a137f2572de8cd83f0b5265cd

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00001
  - **sha256**: fab44e99bd90f1ffe214d4d2bb6580e4c0d52f5fe930e773d96cf92ee820a2f5
  - **upload time**: 2026-07-25T14:22:38.355Z
  - **status**: processed
  - **evidence id**: EVID_00002
  - **sha256**: 63b677916b711ece64fc71292577dfb70a2385c2de817cd0200f86d777b0b350
  - **upload time**: 2026-07-25T14:23:23.722Z
  - **status**: processed
  - **evidence id**: EVID_00003
  - **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
  - **upload time**: 2026-07-25T14:23:26.295Z
  - **status**: processed
  - **evidence id**: EVID_00004
  - **sha256**: d07bcc76b5d280385a06f106c083edc33bff69e82ac63fddf8c433f6b4a5fc02
  - **upload time**: 2026-07-25T14:23:41.798Z
  - **status**: processed
  - **evidence id**: EVID_00005
  - **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
  - **upload time**: 2026-07-25T14:24:07.592Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
