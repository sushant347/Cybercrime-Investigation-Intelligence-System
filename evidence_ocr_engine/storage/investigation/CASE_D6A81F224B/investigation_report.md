# Forensic Investigation Report - CASE_D6A81F224B

Generated: 2026-07-25T18:31:35.899Z  
System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_D6A81F224B contains 3 evidence item(s), each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 1 other case(s) through shared entities: CASE_EE8250FB76 [cross_case_correlation.json].
- The weighted correlation engine found 3 related evidence pair(s) out of 3 analysed [correlation_analysis.json].
- 1 coordinated campaign(s) were identified; the largest (CAMP_CASE_D6A81F224B_01) groups 7 item(s) [campaign_analysis.json].
- The strongest suspect anchor is '+9779801122334' (khalti_ids) with confidence 79/100 [suspect_assessment.json].
- Observed attack progression: initial_contact -> financial_transaction -> social_engineering -> post_attack [timeline_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 3 evidence item(s) acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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

- **case id**: CASE_D6A81F224B
- **evidence count**: 3
- **first evidence**: 2026-07-25T17:39:24.493Z
- **last evidence**: 2026-07-25T17:46:09.276Z
- **file types**:
  - jpg
  - pdf

## Evidence Summary

- **evidence id**: EVID_00020
- **file name**: 06_phishing_email_screenshot.jpg
- **upload time**: 2026-07-25T17:39:24.493Z
- **sha256**: b6ec522eddc05475f9ec7671ec46098a129fa8be863cc270c97b42b702e71134
- **hash verified**: True
- **ocr confidence**: 0.8556
- **evidence confidence score**: 84.4
- **entity count**: 2
- **evidence id**: EVID_00021
- **file name**: 07_bank_transfer_slip.pdf
- **upload time**: 2026-07-25T17:39:52.053Z
- **sha256**: 6f1cc10ae55d554c751ee1cbf688924c8962c5faebe87be8c457d077d6bc63c2
- **hash verified**: True
- **ocr confidence**: 0.9918
- **evidence confidence score**: 100.0
- **entity count**: 8
- **evidence id**: EVID_00022
- **file name**: 08_complaint_letter.pdf
- **upload time**: 2026-07-25T17:46:09.276Z
- **sha256**: fe644062bf75e62c8ae13ec24c7e0461491a5610095a50546c4fa757d98e866f
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: 100.0
- **entity count**: 25

## Correlation Analysis

- **pair count**: 3
- **related pair count**: 3
- **strength distribution**:
  - **STRONG**: 2
  - **WEAK**: 1
- **top relationships**:
  - **pair**: EVID_00021 <-> EVID_00022
  - **strength**: STRONG
  - **confidence**: 0.7837
  - **explanation**: EVID_00021 (07_bank_transfer_slip.pdf) and EVID_00022 (08_complaint_letter.pdf) show a strong relationship (confidence 0.78) based on 4 independent factor(s). Both items reference the same phones: +9779847011223 [weight 0.90]. Both items reference the same transaction ids: mbl-2026-441829 [weight 0.95]. Both items reference the same money: npr 25000 [weight 0.20]. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00020 <-> EVID_00022
  - **strength**: STRONG
  - **confidence**: 0.5563
  - **explanation**: EVID_00020 (06_phishing_email_screenshot.jpg) and EVID_00022 (08_complaint_letter.pdf) show a strong relationship (confidence 0.56) based on 2 independent factor(s). Both items reference the same phones: +9779801122334 [weight 0.90]. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00020 <-> EVID_00021
  - **strength**: WEAK
  - **confidence**: 0.2212
  - **explanation**: EVID_00020 (06_phishing_email_screenshot.jpg) and EVID_00021 (07_bank_transfer_slip.pdf) show a weak relationship (confidence 0.22) based on 1 independent factor(s). Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40].

## Cross-Case Correlation

- **related case count**: 1
- **related case ids**:
  - CASE_EE8250FB76
- **links**:
  - **other case id**: CASE_EE8250FB76
  - **relationship strength**: VERY_STRONG
  - **match confidence**: 0.9999
  - **match reason**: Shares 21 entity(ies) with CASE_EE8250FB76: bank account 05019012345678, domain esewa-cashback-offer.xyz, domain esewa-verify-kyc.com (+18 more)
  - **matched entities**:
    - **entity type**: bank_accounts
    - **value**: 05019012345678
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: domains
    - **value**: esewa-cashback-offer.xyz
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: domains
    - **value**: esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: domains
    - **value**: gmail.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: emails
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: emails
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: emails
    - **value**: support@esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: esewa_ids
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: esewa_ids
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: khalti_ids
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 1500
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 200
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 25000
    - **this evidence ids**:
      - EVID_00021
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 5000
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: phones
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00020
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: phones
    - **value**: +9779847011223
    - **this evidence ids**:
      - EVID_00021
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: 0119.0625.987456
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: case_2026_0088
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: kh-2026-0611-77245
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: mbl-2026-441829
    - **this evidence ids**:
      - EVID_00021
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: urls
    - **value**: https://esewa-cashback-offer.xyz/claim
    - **this evidence ids**:
      - EVID_00022
    - **other evidence ids**:
      - EVID_00005

## Campaign Analysis

- **campaign count**: 1
- **unclustered evidence**:
  - EVID_00015
- **campaigns**:
  - **campaign id**: CAMP_CASE_D6A81F224B_01
  - **members**:
    - EVID_00016
    - EVID_00017
    - EVID_00018
    - EVID_00019
    - EVID_00020
    - EVID_00021
    - EVID_00022
  - **confidence**: 0.6856
  - **signature**:
    - domains:esewa-cashback-offer.xyz
    - money:npr 200
    - phones:+9779801122334
    - phones:+9779847011223
    - dates:11 june 2026
  - **summary**: Campaign CAMP_CASE_D6A81F224B_01 groups 7 evidence item(s) with mean link confidence 0.69. Shared indicators: domains:esewa-cashback-offer.xyz, money:npr 200, phones:+9779801122334, phones:+9779847011223, dates:11 june 2026. Impersonated/used brands: esewa, gmail, khalti. Active 2026-07-25T17:35:36.671Z to 2026-07-25T17:46:09.276Z.

## Timeline Analysis

- **summary**: 3 event(s) spanning 1001.8 hour(s); 0 timestamp(s) unresolved. Observed scam progression: initial_contact -> financial_transaction -> social_engineering -> post_attack.
- **stage progression**:
  - initial_contact
  - financial_transaction
  - social_engineering
  - post_attack
- **progression consistent**: False
- **milestones**:
  - **timestamp**: 2026-06-14T00:00:00+00:00
  - **description**: Investigation start - first reconstructed evidence event
  - **timestamp**: 2026-06-14T00:00:00+00:00
  - **description**: First observation of stage 'initial_contact' (EVID_00021)
  - **timestamp**: 2026-06-14T00:00:00+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00021)
  - **timestamp**: 2026-07-25T17:39:24.493000+00:00
  - **description**: First observation of stage 'social_engineering' (EVID_00020)
  - **timestamp**: 2026-07-25T17:46:09.276000+00:00
  - **description**: First observation of stage 'post_attack' (EVID_00022)
- **critical events**:
  - **timestamp**: 2026-06-14T00:00:00+00:00
  - **evidence id**: EVID_00021
  - **reasons**:
    - contains money entity/entities: NPR 25000
    - contains bank_accounts entity/entities: 05010198765432, 9847011223
    - contains transaction_ids entity/entities: DSN2026, MBL-2026-441829
  - **timestamp**: 2026-07-25T17:39:24.493000+00:00
  - **evidence id**: EVID_00020
  - **reasons**:
    - contains money entity/entities: NPR 5
  - **timestamp**: 2026-07-25T17:46:09.276000+00:00
  - **evidence id**: EVID_00022
  - **reasons**:
    - contains money entity/entities: NPR 1500, NPR 200, NPR 25000
    - contains esewa_ids entity/entities: esewa.cashback99@gmail.com, sunita.gurung21@gmail.com
    - contains khalti_ids entity/entities: +9779801122334
    - contains bank_accounts entity/entities: 05019012345678
    - contains transaction_ids entity/entities: 0119.0625.987456, CASE_2026_0088, KH-2026-0611-77245

## Suspect Assessment

- **suspect id**: SUSPECT_CASE_D6A81F224B_09
- **identity**: khalti_ids:+9779801122334
- **confidence score**: 78.6
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00019
  - EVID_00022
- **explanation**: Suspect anchor '+9779801122334' (khalti_ids) scores 78.6/100 (HIGH, risk HIGH) across 2 evidence item(s): EVID_00019, EVID_00022. Identity strength: 100/100 (weight 0.25) - '+9779801122334' is a khalti_id - identity weight 100/100 for this anchor type. Evidence count: 50/100 (weight 0.20) - appears in 2 of 8 evidence item(s). Evidence confidence: 93/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 93/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00019. Correlation strength: 97/100 (weight 0.15) - its 2 evidence items are inter-linked with mean correlation confidence 0.97 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_D6A81F224B_12
- **identity**: phones:+9779847011223
- **confidence score**: 77.1
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00019
  - EVID_00021
  - EVID_00022
- **explanation**: Suspect anchor '+9779847011223' (phones) scores 77.1/100 (HIGH, risk HIGH) across 3 evidence item(s): EVID_00019, EVID_00021, EVID_00022. Identity strength: 85/100 (weight 0.25) - '+9779847011223' is a phone - identity weight 85/100 for this anchor type. Evidence count: 75/100 (weight 0.20) - appears in 3 of 8 evidence item(s). Evidence confidence: 95/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 95/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00019. Correlation strength: 77/100 (weight 0.15) - its 3 evidence items are inter-linked with mean correlation confidence 0.77 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: khalti_ids:+9779801122334, phones:+9779801122334.
- **suspect id**: SUSPECT_CASE_D6A81F224B_08
- **identity**: esewa_ids:sunita.gurung21@gmail.com
- **confidence score**: 76.8
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00016
  - EVID_00022
- **explanation**: Suspect anchor 'sunita.gurung21@gmail.com' (esewa_ids) scores 76.8/100 (HIGH, risk HIGH) across 2 evidence item(s): EVID_00016, EVID_00022. Identity strength: 100/100 (weight 0.25) - 'sunita.gurung21@gmail.com' is a esewa_id - identity weight 100/100 for this anchor type. Evidence count: 50/100 (weight 0.20) - appears in 2 of 8 evidence item(s). Evidence confidence: 93/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 93/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00022. Correlation strength: 85/100 (weight 0.15) - its 2 evidence items are inter-linked with mean correlation confidence 0.85 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: emails:sunita.gurung21@gmail.com.
- **suspect id**: SUSPECT_CASE_D6A81F224B_11
- **identity**: phones:+9779801122334
- **confidence score**: 75.2
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00019
  - EVID_00020
  - EVID_00022
- **explanation**: Suspect anchor '+9779801122334' (phones) scores 75.2/100 (HIGH, risk HIGH) across 3 evidence item(s): EVID_00019, EVID_00020, EVID_00022. Identity strength: 85/100 (weight 0.25) - '+9779801122334' is a phone - identity weight 85/100 for this anchor type. Evidence count: 75/100 (weight 0.20) - appears in 3 of 8 evidence item(s). Evidence confidence: 90/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 90/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00019. Correlation strength: 70/100 (weight 0.15) - its 3 evidence items are inter-linked with mean correlation confidence 0.70 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: khalti_ids:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_D6A81F224B_05
- **identity**: emails:sunita.gurung21@gmail.com
- **confidence score**: 70.5
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00016
  - EVID_00022
- **explanation**: Suspect anchor 'sunita.gurung21@gmail.com' (emails) scores 70.5/100 (HIGH, risk HIGH) across 2 evidence item(s): EVID_00016, EVID_00022. Identity strength: 75/100 (weight 0.25) - 'sunita.gurung21@gmail.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 50/100 (weight 0.20) - appears in 2 of 8 evidence item(s). Evidence confidence: 93/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 93/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00022. Correlation strength: 85/100 (weight 0.15) - its 2 evidence items are inter-linked with mean correlation confidence 0.85 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: esewa_ids:sunita.gurung21@gmail.com.
- **suspect id**: SUSPECT_CASE_D6A81F224B_02
- **identity**: bank_accounts:05019012345678
- **confidence score**: 67.5
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00022
- **explanation**: Suspect anchor '05019012345678' (bank_accounts) scores 67.5/100 (HIGH, risk HIGH) across 1 evidence item(s): EVID_00022. Identity strength: 100/100 (weight 0.25) - '05019012345678' is a bank_account - identity weight 100/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence item(s). Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00022. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: emails:esewa.cashback99@gmail.com, emails:sunita.gurung21@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_D6A81F224B_07
- **identity**: esewa_ids:esewa.cashback99@gmail.com
- **confidence score**: 67.5
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00022
- **explanation**: Suspect anchor 'esewa.cashback99@gmail.com' (esewa_ids) scores 67.5/100 (HIGH, risk HIGH) across 1 evidence item(s): EVID_00022. Identity strength: 100/100 (weight 0.25) - 'esewa.cashback99@gmail.com' is a esewa_id - identity weight 100/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence item(s). Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00022. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: bank_accounts:05019012345678, emails:esewa.cashback99@gmail.com, emails:sunita.gurung21@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_D6A81F224B_10
- **identity**: khalti_ids:+9779847011223
- **confidence score**: 65.4
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00019
- **explanation**: Suspect anchor '+9779847011223' (khalti_ids) scores 65.4/100 (HIGH, risk HIGH) across 1 evidence item(s): EVID_00019. Identity strength: 100/100 (weight 0.25) - '+9779847011223' is a khalti_id - identity weight 100/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence item(s). Evidence confidence: 86/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 86/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00019. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_D6A81F224B_04
- **identity**: emails:esewa.cashback99@gmail.com
- **confidence score**: 61.2
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00022
- **explanation**: Suspect anchor 'esewa.cashback99@gmail.com' (emails) scores 61.2/100 (HIGH, risk HIGH) across 1 evidence item(s): EVID_00022. Identity strength: 75/100 (weight 0.25) - 'esewa.cashback99@gmail.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence item(s). Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00022. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: bank_accounts:05019012345678, emails:sunita.gurung21@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_D6A81F224B_06
- **identity**: emails:support@esewa-verify-kyc.com
- **confidence score**: 61.2
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00022
- **explanation**: Suspect anchor 'support@esewa-verify-kyc.com' (emails) scores 61.2/100 (HIGH, risk HIGH) across 1 evidence item(s): EVID_00022. Identity strength: 75/100 (weight 0.25) - 'support@esewa-verify-kyc.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence item(s). Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - anchor 'support@esewa-verify-kyc.com' is flagged malicious by threat intelligence. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 day(s) across its evidence set. Co-occurring identity entities: bank_accounts:05019012345678, emails:esewa.cashback99@gmail.com, emails:sunita.gurung21@gmail.com, esewa_ids:esewa.cashback99@gmail.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 7.0
- **malicious indicators**: 6.0
- **suspicious indicators**: 0.0
- **benign indicators**: 1.0
- **evidence with threats**: 4.0
- **threat evidence ratio**: 0.5

## Model Prediction Results

- **indicators classified**: 3
- **flagged malicious**: 2
- **predictions**:
  - **indicator**: https://esewa-cashback-offer.xyz/claim
  - **evidence id**: EVID_00022
  - **verdict**: malicious
  - **risk score**: 100
  - **confidence**: 1.0
  - **risk level**: malicious
  - **source**: heuristics
  - **model version**: 
  - **domain**: esewa-cashback-offer.xyz
  - **brand impersonated**: esewa
  - **official domain**: False
  - **reasons**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - registered under '.xyz', a TLD with a high abuse rate
    - reward/prize wording in the link: cashback, claim, offer
  - **threat signals**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - registered under '.xyz', a TLD with a high abuse rate
    - reward/prize wording in the link: cashback, claim, offer
  - **indicator**: esewa-verify-kyc.com
  - **evidence id**: EVID_00022
  - **verdict**: malicious
  - **risk score**: 75
  - **confidence**: 0.75
  - **risk level**: malicious
  - **source**: heuristics
  - **model version**: 
  - **domain**: esewa-verify-kyc.com
  - **brand impersonated**: esewa
  - **official domain**: False
  - **reasons**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - credential/verification wording in the link: kyc, verify
  - **threat signals**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - credential/verification wording in the link: kyc, verify
  - **indicator**: gmail.com
  - **evidence id**: EVID_00022
  - **verdict**: benign
  - **risk score**: 0
  - **confidence**: 0.0
  - **risk level**: benign
  - **source**: heuristics
  - **model version**: 
  - **domain**: gmail.com
  - **official domain**: True
  - **reasons**:
    - gmail.com is an official gmail domain
  - **trust signals**:
    - gmail.com is an official gmail domain

## Evidence Quality Summary

- **mean image quality**: 66.38
- **mean evidence confidence**: 90.19
- **mean forgery score**: 17.18
- **max forgery score**: 25.2
- **mean ocr confidence**: 0.91
- **hash verified count**: 8.0

## Metadata Summary

- **evidence id**: EVID_00020
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00021
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - none
- **evidence id**: EVID_00022
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - none

## Investigation Statistics

- **entity statistics**:
  - **bank accounts**: 3
  - **dates**: 6
  - **domains**: 8
  - **emails**: 4
  - **esewa ids**: 3
  - **khalti ids**: 3
  - **money**: 10
  - **phones**: 7
  - **times**: 1
  - **transaction ids**: 10
  - **urls**: 2
- **campaign statistics**:
  - **campaign count**: 1.0
  - **largest campaign size**: 7.0
  - **clustered evidence**: 7.0
  - **unclustered evidence**: 1.0
  - **mean campaign confidence**: 0.6856
- **timeline statistics**:
  - **event count**: 8.0
  - **resolved event count**: 8.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 8.0
  - **stage count**: 4.0
  - **critical event count**: 7.0
  - **timeline span hours**: 1001.77
- **correlation statistics**:
  - **pair count**: 28.0
  - **related pair count**: 28.0
  - **mean confidence**: 0.3903
  - **max confidence**: 0.9725

## Confidence Analysis

- **evidence id**: EVID_00020
- **score**: 84.4
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 84.4/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (55/100).
- **evidence id**: EVID_00021
- **score**: 100.0
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100).
- **evidence id**: EVID_00022
- **score**: 100.0
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100).

## Investigation Conclusion

- 3/3 evidence item(s) passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (3 weighted relationship(s)), consistent with related activity rather than isolated incidents.
- 1 campaign cluster(s) indicate coordinated operation.
- Investigation should focus on anchor '+9779801122334' (79/100 confidence).
- Observed stage order deviates from the canonical scam sequence; evidence acquisition order should be reviewed.

## Recommendations

- 1. Preserve and take down 'esewa-cashback-offer.xyz' (risk 83/100). Serve the registrar/host with a preservation request before takedown so logs survive. Grounds: The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.; AI model classified this URL as phishing with 100% confidence.. Seen as: https://esewa-cashback-offer.xyz/claim, https://esewa-cashback-offer.xyz/claim?ref=dsn2026. Appears in: EVID_00017, EVID_00019, EVID_00022.
- 2. Preserve and take down 'esewa-verify-kyc.com' (risk 79/100). Serve the registrar/host with a preservation request before takedown so logs survive. Grounds: The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.; AI model classified this URL as phishing with 100% confidence.. Appears in: EVID_00022.
- 3. Preserve and take down 'esewa.cashbacko90gmail.com' (risk 79/100). Serve the registrar/host with a preservation request before takedown so logs survive. Grounds: The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.; AI model classified this URL as phishing with 100% confidence.. Appears in: EVID_00018.
- 4. Preserve and take down 'sunita.gurung216gmail.com' (risk 79/100). Serve the registrar/host with a preservation request before takedown so logs survive. Grounds: The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.; AI model classified this URL as phishing with 100% confidence.. Appears in: EVID_00018.
- 5. Request wallet KYC and transaction history from eSewa Ltd (F1Soft) for esewa ids: 'sunita.gurung21@gmail.com', 'esewa.cashback99@gmail.com'. The receiving account's KYC identity is the most direct route to the perpetrator.
- 6. Request wallet KYC and transaction history from Khalti / Sparrow Pay Pvt Ltd for khalti ids: '+9779801122334', '+9779847011223'. The receiving account's KYC identity is the most direct route to the perpetrator.
- 7. Request account opening documents and statement of the transaction window from the account-holding bank for bank accounts: '05010198765432', '9847011223', '05019012345678'. The receiving account's KYC identity is the most direct route to the perpetrator.
- 8. Cite transaction reference(s) 'dsn2026', '0119.0625.987456', 'kh-2026-0611-77245', 'mbl-2026-441829', '0sn2026' in every records request - providers can locate a transaction by code far faster than by account, and the code binds victim payment to recipient account in one record.
- 9. Pursue subscriber/KYC records for khalti_id '+9779801122334' (suspect confidence 79/100, appears in 2 evidence item(s)).
- 10. Pursue subscriber/KYC records for phone '+9779847011223' (suspect confidence 77/100, appears in 3 evidence item(s)).
- 11. Pursue subscriber/KYC records for esewa_id 'sunita.gurung21@gmail.com' (suspect confidence 77/100, appears in 2 evidence item(s)).
- 12. Treat campaign CAMP_CASE_D6A81F224B_01 as one operation: its 7 evidence items share esewa-cashback-offer.xyz, gmail.com. Request registrar and hosting records once, for the whole cluster.
- 13. Review the 3 critical timeline event(s) (OTP/credential/payment moments) with the complainant: they mark exactly when compromise and loss occurred, and anchor the victim-impact statement.
- 14. Case priority: CRITICAL (76.4/100) - Immediate escalation recommended: assign a lead investigator and initiate legal preservation requests now.

## Report Provenance & Integrity

- **report id**: RPT-D6A81F224B-407B1D13
- **generated at**: 2026-07-25T18:31:35.898Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 0cc172ec43881c9c5985fa48b79d0ea450e9098daab2b6e599cf71e441773243
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 92fafbc890bfb2b79136c4514049f3e91f6eca62e1f95cc087be2cf88dbd5aed
  - **cross case correlation.json**: 9de2227c34ad60468123b093a90b4d8c47ee03d5a7f4a91be15c6bb2d50eeb36
  - **campaign analysis.json**: 531cbe81c3753681894c61f2e19f9d3cbd14914a3e261ab8e4247a6aa18f58a7
  - **suspect assessment.json**: 1b7b229675bed6fff66256fabb75e1f8307217b52c089b6886bbd7976d2150f4
  - **timeline analysis.json**: 180b93487965da0f2d4eca1512d2c7e2b4056a49ebbfc89364b8facd8e35627f
  - **analytics.json**: 40f078233e3bf7e8b16b83a0d63695852491dc22bdb4f7c7893a4f58ab6f3e63
  - **case priority.json**: 182893e205dba75a31110be6246be9712047adb8fe90f7ade8ad23d8f209b619
  - **graph.json**: 53d751b36052a0e9b90c22f077555759903cde84021889834f2fc6d036a53923

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00020
  - **sha256**: b6ec522eddc05475f9ec7671ec46098a129fa8be863cc270c97b42b702e71134
  - **upload time**: 2026-07-25T17:39:24.493Z
  - **status**: processed
  - **evidence id**: EVID_00021
  - **sha256**: 6f1cc10ae55d554c751ee1cbf688924c8962c5faebe87be8c457d077d6bc63c2
  - **upload time**: 2026-07-25T17:39:52.053Z
  - **status**: processed
  - **evidence id**: EVID_00022
  - **sha256**: fe644062bf75e62c8ae13ec24c7e0461491a5610095a50546c4fa757d98e866f
  - **upload time**: 2026-07-25T17:46:09.276Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
