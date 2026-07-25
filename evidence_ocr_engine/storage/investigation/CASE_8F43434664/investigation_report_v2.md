# Forensic Investigation Report - CASE_8F43434664

Generated: 2026-07-24T16:20:51.736Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_8F43434664 contains 3 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 2 other case(s) through shared entities: CASE_2CF24DBA5F, CASE_F1278DD84F [cross_case_correlation.json].
- The weighted correlation engine found 3 related evidence pair(s) out of 3 analysed [correlation_analysis.json].
- Observed attack progression: initial_contact -> financial_transaction [timeline_analysis.json].

## Case Overview

- **case id**: CASE_8F43434664
- **evidence count**: 3
- **first evidence**: 2026-07-24T16:07:15.486Z
- **last evidence**: 2026-07-24T16:07:39.891Z
- **file types**:
  - jpg
  - png
  - txt

## Evidence Summary

- **evidence id**: EVID_00004
- **file name**: whatsapp_chat_export.txt
- **upload time**: 2026-07-24T16:07:15.486Z
- **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 5
- **evidence id**: EVID_00005
- **file name**: low_quality_scan_demo.png
- **upload time**: 2026-07-24T16:07:27.960Z
- **sha256**: 75b2a30d39404920c875e5ba3c57e951d4ee762153936fbfb408ef8cd7d24fdd
- **hash verified**: True
- **ocr confidence**: 0.5607
- **evidence confidence score**: not available
- **entity count**: 0
- **evidence id**: EVID_00006
- **file name**: romanchat.jpg
- **upload time**: 2026-07-24T16:07:39.891Z
- **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
- **hash verified**: True
- **ocr confidence**: 0.9686
- **evidence confidence score**: not available
- **entity count**: 0

## Correlation Analysis

- **pair count**: 3
- **related pair count**: 3
- **strength distribution**:
  - **WEAK**: 3
- **top relationships**:
  - **pair**: EVID_00004 <-> EVID_00005
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00004 (whatsapp_chat_export.txt) and EVID_00005 (low_quality_scan_demo.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00004 <-> EVID_00006
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00004 (whatsapp_chat_export.txt) and EVID_00006 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00005 <-> EVID_00006
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00005 (low_quality_scan_demo.png) and EVID_00006 (romanchat.jpg) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

- **related case count**: 2
- **related case ids**:
  - CASE_2CF24DBA5F
  - CASE_F1278DD84F
- **links**:
  - **other case id**: CASE_2CF24DBA5F
  - **relationship strength**: WEAK
  - **match confidence**: 0.1175
  - **match reason**: Shares 1 entity(ies) with CASE_2CF24DBA5F: money rs 2000
  - **matched entities**:
    - **entity type**: money
    - **value**: rs 2000
    - **this evidence ids**:
      - EVID_00004
    - **other evidence ids**:
      - EVID_00001
  - **other case id**: CASE_F1278DD84F
  - **relationship strength**: WEAK
  - **match confidence**: 0.1175
  - **match reason**: Shares 1 entity(ies) with CASE_F1278DD84F: money rs 2000
  - **matched entities**:
    - **entity type**: money
    - **value**: rs 2000
    - **this evidence ids**:
      - EVID_00004
    - **other evidence ids**:
      - EVID_00007

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00004
  - EVID_00005
  - EVID_00006
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 3 event(s) spanning 0.0 hour(s). Observed scam progression: initial_contact -> financial_transaction. The progression follows the canonical scam sequence. 1 critical event(s) involve OTP/financial entities.
- **stage progression**:
  - initial_contact
  - financial_transaction
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-07-24T16:07:15.486Z
  - **description**: Investigation start - first evidence acquired
  - **timestamp**: 2026-07-24T16:07:15.486Z
  - **description**: First observation of stage 'initial_contact' (EVID_00004)
  - **timestamp**: 2026-07-24T16:07:15.486Z
  - **description**: First observation of stage 'financial_transaction' (EVID_00004)
- **critical events**:
  - **timestamp**: 2026-07-24T16:07:15.486Z
  - **evidence id**: EVID_00004
  - **reasons**:
    - contains money entity/entities: Rs 2000

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

No threat-intelligence indicator file was provided; threat corroboration was skipped (not an absence of threat).

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.84
- **hash verified count**: 3.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **dates**: 1
  - **money**: 1
  - **times**: 3
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 3.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 3.0
  - **stage count**: 2.0
  - **critical event count**: 1.0
  - **timeline span hours**: 0.01
- **correlation statistics**:
  - **pair count**: 3.0
  - **related pair count**: 3.0
  - **mean confidence**: 0.2212
  - **max confidence**: 0.2212

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Investigation Conclusion

- 3/3 evidence item(s) passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (3 weighted relationship(s)), consistent with related activity rather than isolated incidents.

## Recommendations

- Prioritise the 1 critical event(s) involving OTP/financial entities for victim-impact assessment.
- Case priority: LOW (13.8/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00004
  - **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
  - **upload time**: 2026-07-24T16:07:15.486Z
  - **status**: processed
  - **evidence id**: EVID_00005
  - **sha256**: 75b2a30d39404920c875e5ba3c57e951d4ee762153936fbfb408ef8cd7d24fdd
  - **upload time**: 2026-07-24T16:07:27.960Z
  - **status**: processed
  - **evidence id**: EVID_00006
  - **sha256**: 0340d5863313f4cc0b9b40ed835a77a71b8304d2e08eb32f08a56ed93a6e0b10
  - **upload time**: 2026-07-24T16:07:39.891Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
