# Forensic Investigation Report - CASE_F1278DD84F

Generated: 2026-07-24T16:20:56.682Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_F1278DD84F contains 2 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 3 other case(s) through shared entities: CASE_2CF24DBA5F, CASE_85B2471DFB, CASE_8F43434664 [cross_case_correlation.json].
- The weighted correlation engine found 1 related evidence pair(s) out of 1 analysed [correlation_analysis.json].
- Observed attack progression: initial_contact -> financial_transaction [timeline_analysis.json].

## Case Overview

- **case id**: CASE_F1278DD84F
- **evidence count**: 2
- **first evidence**: 2026-07-24T16:19:58.868Z
- **last evidence**: 2026-07-24T16:19:58.952Z
- **file types**:
  - png
  - txt

## Evidence Summary

- **evidence id**: EVID_00007
- **file name**: whatsapp_chat_export.txt
- **upload time**: 2026-07-24T16:19:58.868Z
- **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: not available
- **entity count**: 5
- **evidence id**: EVID_00008
- **file name**: scam_sms_screenshot.png
- **upload time**: 2026-07-24T16:19:58.952Z
- **sha256**: b566c34426563417a8b355e67d17daee57765586450e2c18bb8c160b5b716d7b
- **hash verified**: True
- **ocr confidence**: 0.9766
- **evidence confidence score**: not available
- **entity count**: 2

## Correlation Analysis

- **pair count**: 1
- **related pair count**: 1
- **strength distribution**:
  - **WEAK**: 1
- **top relationships**:
  - **pair**: EVID_00007 <-> EVID_00008
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00007 (whatsapp_chat_export.txt) and EVID_00008 (scam_sms_screenshot.png) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

- **related case count**: 3
- **related case ids**:
  - CASE_2CF24DBA5F
  - CASE_85B2471DFB
  - CASE_8F43434664
- **links**:
  - **other case id**: CASE_2CF24DBA5F
  - **relationship strength**: MEDIUM
  - **match confidence**: 0.3127
  - **match reason**: Shares 3 entity(ies) with CASE_2CF24DBA5F: money rs 2,000, money rs 2000, money rs 5,00,000
  - **matched entities**:
    - **entity type**: money
    - **value**: rs 2,000
    - **this evidence ids**:
      - EVID_00008
    - **other evidence ids**:
      - EVID_00002
    - **entity type**: money
    - **value**: rs 2000
    - **this evidence ids**:
      - EVID_00007
    - **other evidence ids**:
      - EVID_00001
    - **entity type**: money
    - **value**: rs 5,00,000
    - **this evidence ids**:
      - EVID_00008
    - **other evidence ids**:
      - EVID_00002
  - **other case id**: CASE_85B2471DFB
  - **relationship strength**: MEDIUM
  - **match confidence**: 0.3127
  - **match reason**: Shares 3 entity(ies) with CASE_85B2471DFB: money rs 2,000, money rs 2000, money rs 5,00,000
  - **matched entities**:
    - **entity type**: money
    - **value**: rs 2,000
    - **this evidence ids**:
      - EVID_00008
    - **other evidence ids**:
      - EVID_00010
    - **entity type**: money
    - **value**: rs 2000
    - **this evidence ids**:
      - EVID_00007
    - **other evidence ids**:
      - EVID_00009
    - **entity type**: money
    - **value**: rs 5,00,000
    - **this evidence ids**:
      - EVID_00008
    - **other evidence ids**:
      - EVID_00010
  - **other case id**: CASE_8F43434664
  - **relationship strength**: WEAK
  - **match confidence**: 0.1175
  - **match reason**: Shares 1 entity(ies) with CASE_8F43434664: money rs 2000
  - **matched entities**:
    - **entity type**: money
    - **value**: rs 2000
    - **this evidence ids**:
      - EVID_00007
    - **other evidence ids**:
      - EVID_00004

## Campaign Analysis

- **campaign count**: 0
- **unclustered evidence**:
  - EVID_00007
  - EVID_00008
- **campaigns**:
  - none

## Timeline Analysis

- **summary**: 2 event(s) spanning 0.0 hour(s). Observed scam progression: initial_contact -> financial_transaction. The progression follows the canonical scam sequence. 2 critical event(s) involve OTP/financial entities.
- **stage progression**:
  - initial_contact
  - financial_transaction
- **progression consistent**: True
- **milestones**:
  - **timestamp**: 2026-07-24T16:19:58.868Z
  - **description**: Investigation start - first evidence acquired
  - **timestamp**: 2026-07-24T16:19:58.868Z
  - **description**: First observation of stage 'initial_contact' (EVID_00007)
  - **timestamp**: 2026-07-24T16:19:58.868Z
  - **description**: First observation of stage 'financial_transaction' (EVID_00007)
- **critical events**:
  - **timestamp**: 2026-07-24T16:19:58.868Z
  - **evidence id**: EVID_00007
  - **reasons**:
    - contains money entity/entities: Rs 2000
  - **timestamp**: 2026-07-24T16:19:58.952Z
  - **evidence id**: EVID_00008
  - **reasons**:
    - contains money entity/entities: Rs 2,000, Rs 5,00,000

## Suspect Assessment

No suspect anchors were derived from the evidence.

## Threat Intelligence Summary

No threat-intelligence indicator file was provided; threat corroboration was skipped (not an absence of threat).

## Evidence Quality Summary

- **mean image quality**: 0.0
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.99
- **hash verified count**: 2.0

## Metadata Summary

- **note**: No Phase-1 metadata reports stored for this case.

## Investigation Statistics

- **entity statistics**:
  - **dates**: 1
  - **money**: 3
  - **times**: 3
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 2.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 2.0
  - **stage count**: 2.0
  - **critical event count**: 2.0
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

- Prioritise the 2 critical event(s) involving OTP/financial entities for victim-impact assessment.
- Case priority: LOW (22.2/100) - Low urgency: archive-ready unless new evidence raises the correlation or threat picture.

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00007
  - **sha256**: c7ab347cfbd2b80c944c85b3442f3b2c400da1d3b92962f9ded8598e1e06cfb2
  - **upload time**: 2026-07-24T16:19:58.868Z
  - **status**: processed
  - **evidence id**: EVID_00008
  - **sha256**: b566c34426563417a8b355e67d17daee57765586450e2c18bb8c160b5b716d7b
  - **upload time**: 2026-07-24T16:19:58.952Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
