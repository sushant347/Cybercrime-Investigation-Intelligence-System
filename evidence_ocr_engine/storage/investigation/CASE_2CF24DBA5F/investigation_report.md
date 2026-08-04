# Forensic Investigation Report - CASE_2CF24DBA5F

Generated: 2026-08-04T05:29:50.850Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_2CF24DBA5F contains 4 evidence items, each acquired under SHA-256 chain-of-custody verification.
- The weighted correlation engine found 6 related evidence pairs out of 6 analysed [correlation_analysis.json].
- Observed attack progression: financial_transaction -> post_attack -> initial_contact -> social_engineering -> credential_theft [timeline_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 4 evidence items acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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
- **ocr confidence**: 1.0
- **evidence confidence score**: 77.5
- **entity count**: 5
- **evidence id**: EVID_00002
- **file name**: whatsapp_chat_export.txt
- **upload time**: 2026-07-25T12:53:07.182Z
- **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: 82.5
- **entity count**: 2
- **evidence id**: EVID_00003
- **file name**: romanchat.jpg
- **upload time**: 2026-07-25T12:53:23.174Z
- **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
- **hash verified**: True
- **ocr confidence**: 0.9859
- **evidence confidence score**: 77.5
- **entity count**: 0
- **evidence id**: EVID_00004
- **file name**: phishing_email_screenshot.png
- **upload time**: 2026-07-25T12:53:47.011Z
- **sha256**: 8ef0f27a84960b656d9051892e36096ce56fe9f30eb9a935d4d4330a002b9b7f
- **hash verified**: True
- **ocr confidence**: 0.9014
- **evidence confidence score**: 77.5
- **entity count**: 0

## Timeline Analysis

- **summary**: 4 events spanning 4851.7 hours; 0 timestamps unresolved. Observed scam progression: financial_transaction -> post_attack -> initial_contact -> social_engineering -> credential_theft.
- **stage progression**:
  - financial_transaction
  - post_attack
  - initial_contact
  - social_engineering
  - credential_theft
- **progression consistent**: False
- **milestones**:
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-07-25T12:53:07.182000+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00002)
  - **timestamp**: 2026-07-25T12:53:07.182000+00:00
  - **description**: First observation of stage 'post_attack' (EVID_00002)
  - **timestamp**: 2026-07-25T12:53:23.174000+00:00
  - **description**: First observation of stage 'initial_contact' (EVID_00003)
  - **timestamp**: 2026-07-25T12:53:23.174000+00:00
  - **description**: First observation of stage 'social_engineering' (EVID_00003)
  - **timestamp**: 2026-07-25T12:53:23.174000+00:00
  - **description**: First observation of stage 'credential_theft' (EVID_00003)
- **critical events**:
  - **timestamp**: 2026-01-04T09:12:00+00:00
  - **evidence id**: EVID_00001
  - **reasons**:
    - contains money entity/entities: NPR 2000
  - **timestamp**: 2026-07-25T12:53:07.182000+00:00
  - **evidence id**: EVID_00002
  - **reasons**:
    - contains money entity/entities: NPR 2000, NPR 500000

## Correlation Analysis

- **pair count**: 6
- **related pair count**: 6
- **strength distribution**:
  - **WEAK**: 6
- **top relationships**:
  - **pair**: EVID_00001 <-> EVID_00002
  - **strength**: WEAK
  - **confidence**: 0.2545
  - **explanation**: EVID_00001 (yeti.jpg) and EVID_00002 (whatsapp_chat_export.txt) show a weak relationship (confidence 0.25) based on 2 independent factors. Both items reference the same money: npr 2000 [weight 0.07]. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00003
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (yeti.jpg) and EVID_00003 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00001 <-> EVID_00004
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00001 (yeti.jpg) and EVID_00004 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00002 <-> EVID_00003
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00002 (whatsapp_chat_export.txt) and EVID_00003 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor. Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00002 <-> EVID_00004
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00002 (whatsapp_chat_export.txt) and EVID_00004 (phishing_email_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor. Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

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

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 0.0
- **malicious indicators**: 0.0
- **suspicious indicators**: 0.0
- **benign indicators**: 0.0
- **evidence with threats**: 0.0
- **threat evidence ratio**: 0.0

## Model Prediction Results

The active threat-intelligence provider returned no classification for any URL/domain indicator in this case's evidence.

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 78.75
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.97
- **hash verified count**: 4.0

## Metadata Summary

- **evidence id**: EVID_00001
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00002
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - none
- **evidence id**: EVID_00003
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00004
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).

## Investigation Statistics

- **entity statistics**:
  - **dates**: 1
  - **money**: 3
  - **times**: 3
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
  - **stage count**: 5.0
  - **critical event count**: 2.0
  - **timeline span hours**: 4851.7
- **correlation statistics**:
  - **pair count**: 6.0
  - **related pair count**: 6.0
  - **mean confidence**: 0.2268
  - **max confidence**: 0.2545

## Confidence Analysis

- **evidence id**: EVID_00001
- **score**: 77.5
- **level**: HIGH
- **explanation**: Evidence confidence is 77.5/100 (HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: processing (30/100).
- **evidence id**: EVID_00002
- **score**: 82.5
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 82.5/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: processing (30/100).
- **evidence id**: EVID_00003
- **score**: 77.5
- **level**: HIGH
- **explanation**: Evidence confidence is 77.5/100 (HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: processing (30/100).
- **evidence id**: EVID_00004
- **score**: 77.5
- **level**: HIGH
- **explanation**: Evidence confidence is 77.5/100 (HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: processing (30/100).

## Investigation Conclusion

- 4/4 evidence items passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (6 weighted relationships), consistent with related activity rather than isolated incidents.
- Observed stage order deviates from the canonical scam sequence; evidence acquisition order should be reviewed.

## Recommendations

- Go through the 2 key moments - when money moved and codes were shared - with the victim, and record what they lost.
- Low urgency - handle after the others (rated 30 out of 100).

## Report Provenance & Integrity

- **report id**: RPT-2CF24DBA5F-12CFF9FC
- **generated at**: 2026-08-04T05:29:50.726Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 845d2580a93c7505d88a3b735dd3a956db233d26f779d05f4a85f60abfe82c3f
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 3b4dfea120ca21d01e15888ab11f16d98a992574e7e70f2f83700f3133e34d8e
  - **cross case correlation.json**: 6c4b7e022465546d0555c8cb462748c5b6c81a0b9a0b5bdb505f7587bf91bc63
  - **campaign analysis.json**: 9de713497ccdbdfa2b534f69b0f7da170c0e7bf285cc89f0b917f1f0bb0c5288
  - **suspect assessment.json**: 752497ea636208cb1e52fbd5eb3207e5fe83f6f05123bf4a23525a67fcbb2704
  - **timeline analysis.json**: d4189177894610f13490b7e0a6946df2e6d9546e1c4b86af855ba02679eeec1d
  - **analytics.json**: c27afb6394098d874f9fb7e6c758574bc0111ac66747bc37f8a1adf62e59054d
  - **case priority.json**: d9776374b6775e023cfeb282e4e71ec308ea387cf71a5b828cccae79b7e13ab5
  - **graph.json**: 063b55866d7bb07325f3101d13c1be188a04c1e42cfb2c0a41168f17898b107e

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
