# Forensic Investigation Report - CASE_185915593C

Generated: 2026-08-04T08:17:42.096Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Basis: every statement below references stored forensic findings; no content is generated outside computed results.

## Executive Summary

- Case CASE_185915593C contains 8 evidence items, each acquired under SHA-256 chain-of-custody verification.
- This case is linked to 2 other cases through shared entities: CASE_1A1BF573F3, CASE_EE8250FB76 [cross_case_correlation.json].
- The weighted correlation engine found 28 related evidence pairs out of 28 analysed [correlation_analysis.json].
- 1 coordinated campaign were identified; the largest (CAMP_CASE_185915593C_01) groups 5 items [campaign_analysis.json].
- The strongest suspect anchor is '+9779801122334' (khalti_ids) with confidence 78/100 [suspect_assessment.json].
- Observed attack progression: initial_contact -> financial_transaction -> social_engineering -> post_attack [timeline_analysis.json].

## Scope & Methodology

- **objective**: Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (suspect anchors, campaigns, cross-case links) strictly from stored, hash-verified artifacts.
- **evidence scope**: 8 evidence items acquired through the CIIS intake pipeline under SHA-256 chain-of-custody control.
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

- **case id**: CASE_185915593C
- **evidence count**: 8
- **first evidence**: 2026-07-25T17:16:30.233Z
- **last evidence**: 2026-07-25T17:26:20.455Z
- **file types**:
  - jpg
  - pdf
  - png

## Evidence Summary

- **evidence id**: EVID_00007
- **file name**: 01_sms_screenshot.jpg
- **upload time**: 2026-07-25T17:16:30.233Z
- **sha256**: 905b21d603ca0a6f49fd226e46470c85d509dce56f8ab68edce76b6b7ff8cec7
- **hash verified**: True
- **ocr confidence**: 0.6039
- **evidence confidence score**: 85.6
- **entity count**: 0
- **evidence id**: EVID_00008
- **file name**: 02_messenger_chat.jpg
- **upload time**: 2026-07-25T17:17:07.920Z
- **sha256**: bb246839287ca1bcc1f6a38bbdf26489ef6eb74213b7fc2d224597a910bf4ef4
- **hash verified**: True
- **ocr confidence**: 0.9286
- **evidence confidence score**: 86.7
- **entity count**: 4
- **evidence id**: EVID_00009
- **file name**: 03_qr_code_flyer.png
- **upload time**: 2026-07-25T17:18:32.458Z
- **sha256**: 6f712c8b0e4fb6c50d156a1bf002713b4bbd60bf7db0a9cf7fbe3ea04b2cbdf9
- **hash verified**: True
- **ocr confidence**: 0.9814
- **evidence confidence score**: 94.1
- **entity count**: 4
- **evidence id**: EVID_00010
- **file name**: 04_esewa_payment_screenshot.jpg
- **upload time**: 2026-07-25T17:18:54.475Z
- **sha256**: 3a19295ff003a894311ef7efcf80bb94c8feec5a69590c3052f7f8d60ce7217b
- **hash verified**: True
- **ocr confidence**: 0.9116
- **evidence confidence score**: 84.4
- **entity count**: 4
- **evidence id**: EVID_00011
- **file name**: 05_khalti_receipt.jpg
- **upload time**: 2026-07-25T17:19:57.040Z
- **sha256**: 54a62cd3ad10a85b9b060ff73dcab3d5fb2bb3f073f3bcab66f90ae45d7d779b
- **hash verified**: True
- **ocr confidence**: 0.986
- **evidence confidence score**: 86.3
- **entity count**: 10
- **evidence id**: EVID_00012
- **file name**: 06_phishing_email_screenshot.jpg
- **upload time**: 2026-07-25T17:20:21.991Z
- **sha256**: b6ec522eddc05475f9ec7671ec46098a129fa8be863cc270c97b42b702e71134
- **hash verified**: True
- **ocr confidence**: 0.8556
- **evidence confidence score**: 84.4
- **entity count**: 2
- **evidence id**: EVID_00013
- **file name**: 07_bank_transfer_slip.pdf
- **upload time**: 2026-07-25T17:20:51.466Z
- **sha256**: 6f1cc10ae55d554c751ee1cbf688924c8962c5faebe87be8c457d077d6bc63c2
- **hash verified**: True
- **ocr confidence**: 0.9893
- **evidence confidence score**: 100.0
- **entity count**: 8
- **evidence id**: EVID_00014
- **file name**: 08_complaint_letter.pdf
- **upload time**: 2026-07-25T17:26:20.455Z
- **sha256**: fe644062bf75e62c8ae13ec24c7e0461491a5610095a50546c4fa757d98e866f
- **hash verified**: True
- **ocr confidence**: 1.0
- **evidence confidence score**: 100.0
- **entity count**: 25

## Timeline Analysis

- **summary**: 8 events spanning 1001.4 hours; 0 timestamps unresolved. Observed scam progression: initial_contact -> financial_transaction -> social_engineering -> post_attack.
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
  - **description**: First observation of stage 'initial_contact' (EVID_00013)
  - **timestamp**: 2026-06-14T00:00:00+00:00
  - **description**: First observation of stage 'financial_transaction' (EVID_00013)
  - **timestamp**: 2026-07-25T17:20:21.991000+00:00
  - **description**: First observation of stage 'social_engineering' (EVID_00012)
  - **timestamp**: 2026-07-25T17:26:20.455000+00:00
  - **description**: First observation of stage 'post_attack' (EVID_00014)
- **critical events**:
  - **timestamp**: 2026-06-14T00:00:00+00:00
  - **evidence id**: EVID_00013
  - **reasons**:
    - contains money entity/entities: NPR 25000
    - contains bank_accounts entity/entities: 05010198765432, 9847011223
    - contains transaction_ids entity/entities: DSN2026, MBL-2026-441829
  - **timestamp**: 2026-07-25T11:15:00+00:00
  - **evidence id**: EVID_00011
  - **reasons**:
    - contains money entity/entities: NPR 1500
    - contains khalti_ids entity/entities: +9779801122334, +9779847011223
    - contains transaction_ids entity/entities: 0SN2026, KH-2026-0611-77245
  - **timestamp**: 2026-07-25T17:17:07.920000+00:00
  - **evidence id**: EVID_00008
  - **reasons**:
    - contains money entity/entities: NPR 200
    - contains esewa_ids entity/entities: sunita.gurung21@gmail.com
  - **timestamp**: 2026-07-25T17:18:32.458000+00:00
  - **evidence id**: EVID_00009
  - **reasons**:
    - contains money entity/entities: NPR 5000
    - contains transaction_ids entity/entities: DSN2026
  - **timestamp**: 2026-07-25T17:18:54.475000+00:00
  - **evidence id**: EVID_00010
  - **reasons**:
    - contains money entity/entities: NPR 200
    - contains transaction_ids entity/entities: 0119.0625.987456
  - **timestamp**: 2026-07-25T17:20:21.991000+00:00
  - **evidence id**: EVID_00012
  - **reasons**:
    - contains money entity/entities: NPR 5
  - **timestamp**: 2026-07-25T17:26:20.455000+00:00
  - **evidence id**: EVID_00014
  - **reasons**:
    - contains money entity/entities: NPR 1500, NPR 200, NPR 25000
    - contains esewa_ids entity/entities: esewa.cashback99@gmail.com, sunita.gurung21@gmail.com
    - contains khalti_ids entity/entities: +9779801122334
    - contains bank_accounts entity/entities: 05019012345678
    - contains transaction_ids entity/entities: 0119.0625.987456, CASE_2026_0088, KH-2026-0611-77245

## Correlation Analysis

- **pair count**: 28
- **related pair count**: 28
- **strength distribution**:
  - **VERY STRONG**: 1
  - **STRONG**: 4
  - **MEDIUM**: 5
  - **WEAK**: 18
- **top relationships**:
  - **pair**: EVID_00011 <-> EVID_00014
  - **strength**: VERY_STRONG
  - **confidence**: 0.9389
  - **explanation**: EVID_00011 (05_khalti_receipt.jpg) and EVID_00014 (08_complaint_letter.pdf) show a very strong relationship (confidence 0.94) based on 7 independent factors. Both items reference the same phones: +9779801122334, +9779847011223 [weight 1.26]. Both items reference the same khalti ids: +9779801122334 [weight 0.78]. Both items reference the same transaction ids: kh-2026-0611-77245 [weight 0.74]. Both items reference the same domains: esewa-cashback-offer.xyz [weight 0.42]. Both items reference the same money: npr 1500 [weight 0.07]. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40]. Threat intelligence flags the same malicious indicator in both items: esewa-cashback-offer.xyz [weight 0.80].
  - **pair**: EVID_00008 <-> EVID_00014
  - **strength**: STRONG
  - **confidence**: 0.7709
  - **explanation**: EVID_00008 (02_messenger_chat.jpg) and EVID_00014 (08_complaint_letter.pdf) show a strong relationship (confidence 0.77) based on 5 independent factors. Both items reference the same emails: sunita.gurung21@gmail.com [weight 0.66]. Both items reference the same esewa ids: sunita.gurung21@gmail.com [weight 0.78]. Both items reference the same domains: gmail.com [weight 0.46]. Both items reference the same money: npr 200 [weight 0.06]. Acquired 0.2 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00013 <-> EVID_00014
  - **strength**: STRONG
  - **confidence**: 0.6815
  - **explanation**: EVID_00013 (07_bank_transfer_slip.pdf) and EVID_00014 (08_complaint_letter.pdf) show a strong relationship (confidence 0.68) based on 4 independent factors. Both items reference the same phones: +9779847011223 [weight 0.63]. Both items reference the same transaction ids: mbl-2026-441829 [weight 0.74]. Both items reference the same money: npr 25000 [weight 0.06]. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40].
  - **pair**: EVID_00009 <-> EVID_00014
  - **strength**: STRONG
  - **confidence**: 0.6488
  - **explanation**: EVID_00009 (03_qr_code_flyer.png) and EVID_00014 (08_complaint_letter.pdf) show a strong relationship (confidence 0.65) based on 4 independent factors. Both items reference the same domains: esewa-cashback-offer.xyz [weight 0.42]. Both items reference the same money: npr 5000 [weight 0.05]. Acquired 0.1 hours apart (within the 48h proximity window) [weight 0.40]. Threat intelligence flags the same malicious indicator in both items: esewa-cashback-offer.xyz [weight 0.80].
  - **pair**: EVID_00009 <-> EVID_00011
  - **strength**: STRONG
  - **confidence**: 0.6366
  - **explanation**: EVID_00009 (03_qr_code_flyer.png) and EVID_00011 (05_khalti_receipt.jpg) show a strong relationship (confidence 0.64) based on 3 independent factors. Both items reference the same domains: esewa-cashback-offer.xyz [weight 0.42]. Acquired 0.0 hours apart (within the 48h proximity window) [weight 0.40]. Threat intelligence flags the same malicious indicator in both items: esewa-cashback-offer.xyz [weight 0.80].

## Cross-Case Correlation

- **related case count**: 2
- **related case ids**:
  - CASE_1A1BF573F3
  - CASE_EE8250FB76
- **links**:
  - **other case id**: CASE_1A1BF573F3
  - **relationship strength**: VERY_STRONG
  - **match confidence**: 1.0
  - **match reason**: Shares 29 entity(ies) with CASE_1A1BF573F3: bank account 05010198765432, domain esewa.cashbacko90gmail.com, domain sunita.gurung216gmail.com (+26 more). 25 of these are distinctive; the other 4 are common across the corpus and were discounted
  - **matched entities**:
    - **entity type**: bank_accounts
    - **value**: 05010198765432
    - **this evidence ids**:
      - EVID_00013
    - **other evidence ids**:
      - EVID_00021
    - **entity type**: domains
    - **value**: esewa.cashbacko90gmail.com
    - **this evidence ids**:
      - EVID_00010
    - **other evidence ids**:
      - EVID_00018
    - **entity type**: domains
    - **value**: sunita.gurung216gmail.com
    - **this evidence ids**:
      - EVID_00010
    - **other evidence ids**:
      - EVID_00018
    - **entity type**: khalti_ids
    - **value**: +9779847011223
    - **this evidence ids**:
      - EVID_00011
    - **other evidence ids**:
      - EVID_00019
    - **entity type**: urls
    - **value**: https://esewa-cashback-offer.xyz/claim?ref=dsn2026
    - **this evidence ids**:
      - EVID_00009
    - **other evidence ids**:
      - EVID_00017
    - **entity type**: bank_accounts
    - **value**: 9847011223
    - **this evidence ids**:
      - EVID_00013
    - **other evidence ids**:
      - EVID_00021
    - **entity type**: phones
    - **value**: 0198765432
    - **this evidence ids**:
      - EVID_00013
    - **other evidence ids**:
      - EVID_00021
    - **entity type**: bank_accounts
    - **value**: 05019012345678
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: domains
    - **value**: esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: emails
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: emails
    - **value**: support@esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: esewa_ids
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: transaction_ids
    - **value**: case_2026_0088
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: urls
    - **value**: https://esewa-cashback-offer.xyz/claim
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00022
    - **entity type**: emails
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00008
      - EVID_00014
    - **other evidence ids**:
      - EVID_00016
      - EVID_00022
    - **entity type**: esewa_ids
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00008
      - EVID_00014
    - **other evidence ids**:
      - EVID_00016
      - EVID_00022
    - **entity type**: khalti_ids
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00019
      - EVID_00022
    - **entity type**: transaction_ids
    - **value**: 0119.0625.987456
    - **this evidence ids**:
      - EVID_00010
      - EVID_00014
    - **other evidence ids**:
      - EVID_00018
      - EVID_00022
    - **entity type**: transaction_ids
    - **value**: kh-2026-0611-77245
    - **this evidence ids**:
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00019
      - EVID_00022
    - **entity type**: transaction_ids
    - **value**: mbl-2026-441829
    - **this evidence ids**:
      - EVID_00013
      - EVID_00014
    - **other evidence ids**:
      - EVID_00021
      - EVID_00022
    - **entity type**: domains
    - **value**: gmail.com
    - **this evidence ids**:
      - EVID_00008
      - EVID_00014
    - **other evidence ids**:
      - EVID_00016
      - EVID_00022
    - **entity type**: transaction_ids
    - **value**: dsn2026
    - **this evidence ids**:
      - EVID_00009
      - EVID_00013
    - **other evidence ids**:
      - EVID_00017
      - EVID_00019
      - EVID_00021
    - **entity type**: domains
    - **value**: esewa-cashback-offer.xyz
    - **this evidence ids**:
      - EVID_00009
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00017
      - EVID_00019
      - EVID_00022
    - **entity type**: phones
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00011
      - EVID_00012
      - EVID_00014
    - **other evidence ids**:
      - EVID_00019
      - EVID_00020
      - EVID_00022
    - **entity type**: phones
    - **value**: +9779847011223
    - **this evidence ids**:
      - EVID_00011
      - EVID_00013
      - EVID_00014
    - **other evidence ids**:
      - EVID_00019
      - EVID_00021
      - EVID_00022
    - **entity type**: money
    - **value**: npr 1500
    - **this evidence ids**:
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00019
      - EVID_00022
    - **entity type**: money
    - **value**: npr 25000
    - **this evidence ids**:
      - EVID_00013
      - EVID_00014
    - **other evidence ids**:
      - EVID_00021
      - EVID_00022
    - **entity type**: money
    - **value**: npr 200
    - **this evidence ids**:
      - EVID_00008
      - EVID_00010
      - EVID_00014
    - **other evidence ids**:
      - EVID_00016
      - EVID_00018
      - EVID_00022
    - **entity type**: money
    - **value**: npr 5000
    - **this evidence ids**:
      - EVID_00009
      - EVID_00014
    - **other evidence ids**:
      - EVID_00017
      - EVID_00022
  - **other case id**: CASE_EE8250FB76
  - **relationship strength**: VERY_STRONG
  - **match confidence**: 0.9992
  - **match reason**: Shares 21 entity(ies) with CASE_EE8250FB76: bank account 05019012345678, domain esewa-verify-kyc.com, email esewa.cashback99@gmail.com (+18 more). 17 of these are distinctive; the other 4 are common across the corpus and were discounted
  - **matched entities**:
    - **entity type**: bank_accounts
    - **value**: 05019012345678
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: domains
    - **value**: esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: emails
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: emails
    - **value**: support@esewa-verify-kyc.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: esewa_ids
    - **value**: esewa.cashback99@gmail.com
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: case_2026_0088
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: urls
    - **value**: https://esewa-cashback-offer.xyz/claim
    - **this evidence ids**:
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: emails
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00008
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: esewa_ids
    - **value**: sunita.gurung21@gmail.com
    - **this evidence ids**:
      - EVID_00008
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: khalti_ids
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: 0119.0625.987456
    - **this evidence ids**:
      - EVID_00010
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: kh-2026-0611-77245
    - **this evidence ids**:
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: transaction_ids
    - **value**: mbl-2026-441829
    - **this evidence ids**:
      - EVID_00013
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: domains
    - **value**: gmail.com
    - **this evidence ids**:
      - EVID_00008
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: domains
    - **value**: esewa-cashback-offer.xyz
    - **this evidence ids**:
      - EVID_00009
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: phones
    - **value**: +9779801122334
    - **this evidence ids**:
      - EVID_00011
      - EVID_00012
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: phones
    - **value**: +9779847011223
    - **this evidence ids**:
      - EVID_00011
      - EVID_00013
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 1500
    - **this evidence ids**:
      - EVID_00011
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 25000
    - **this evidence ids**:
      - EVID_00013
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 200
    - **this evidence ids**:
      - EVID_00008
      - EVID_00010
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005
    - **entity type**: money
    - **value**: npr 5000
    - **this evidence ids**:
      - EVID_00009
      - EVID_00014
    - **other evidence ids**:
      - EVID_00005

## Campaign Analysis

- **campaign count**: 1
- **unclustered evidence**:
  - EVID_00007
  - EVID_00010
  - EVID_00012
- **campaigns**:
  - **campaign id**: CAMP_CASE_185915593C_01
  - **members**:
    - EVID_00008
    - EVID_00009
    - EVID_00011
    - EVID_00013
    - EVID_00014
  - **confidence**: 0.7353
  - **signature**:
    - domains:esewa-cashback-offer.xyz
    - phones:+9779847011223
    - dates:11 june 2026
    - domains:gmail.com
    - emails:sunita.gurung21@gmail.com
  - **summary**: Campaign CAMP_CASE_185915593C_01 groups 5 evidence items with mean link confidence 0.74. Shared indicators: domains:esewa-cashback-offer.xyz, phones:+9779847011223, dates:11 june 2026, domains:gmail.com, emails:sunita.gurung21@gmail.com. Impersonated/used brands: esewa, khalti. Active 2026-07-25T17:17:07.920Z to 2026-07-25T17:26:20.455Z.

## Suspect Assessment

- **suspect id**: SUSPECT_CASE_185915593C_09
- **identity**: khalti_ids:+9779801122334
- **confidence score**: 78.1
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00011
  - EVID_00014
- **explanation**: Suspect anchor '+9779801122334' (khalti_ids) scores 78.1/100 (HIGH, risk HIGH) across 2 evidence items: EVID_00011, EVID_00014. Identity strength: 100/100 (weight 0.25) - '+9779801122334' is a khalti_id - identity weight 100/100 for this anchor type. Evidence count: 50/100 (weight 0.20) - appears in 2 of 8 evidence items. Evidence confidence: 93/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 93/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00011. Correlation strength: 94/100 (weight 0.15) - its 2 evidence items are inter-linked with mean correlation confidence 0.94 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_185915593C_12
- **identity**: phones:+9779847011223
- **confidence score**: 76.0
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00011
  - EVID_00013
  - EVID_00014
- **explanation**: Suspect anchor '+9779847011223' (phones) scores 76.0/100 (HIGH, risk HIGH) across 3 evidence items: EVID_00011, EVID_00013, EVID_00014. Identity strength: 85/100 (weight 0.25) - '+9779847011223' is a phone - identity weight 85/100 for this anchor type. Evidence count: 75/100 (weight 0.20) - appears in 3 of 8 evidence items. Evidence confidence: 95/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 95/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00011. Correlation strength: 70/100 (weight 0.15) - its 3 evidence items are inter-linked with mean correlation confidence 0.70 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: khalti_ids:+9779801122334, phones:+9779801122334.
- **suspect id**: SUSPECT_CASE_185915593C_08
- **identity**: esewa_ids:sunita.gurung21@gmail.com
- **confidence score**: 75.6
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00008
  - EVID_00014
- **explanation**: Suspect anchor 'sunita.gurung21@gmail.com' (esewa_ids) scores 75.6/100 (HIGH, risk HIGH) across 2 evidence items: EVID_00008, EVID_00014. Identity strength: 100/100 (weight 0.25) - 'sunita.gurung21@gmail.com' is a esewa_id - identity weight 100/100 for this anchor type. Evidence count: 50/100 (weight 0.20) - appears in 2 of 8 evidence items. Evidence confidence: 93/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 93/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00014. Correlation strength: 77/100 (weight 0.15) - its 2 evidence items are inter-linked with mean correlation confidence 0.77 (strongest: STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: emails:sunita.gurung21@gmail.com.
- **suspect id**: SUSPECT_CASE_185915593C_11
- **identity**: phones:+9779801122334
- **confidence score**: 74.2
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00011
  - EVID_00012
  - EVID_00014
- **explanation**: Suspect anchor '+9779801122334' (phones) scores 74.2/100 (HIGH, risk HIGH) across 3 evidence items: EVID_00011, EVID_00012, EVID_00014. Identity strength: 85/100 (weight 0.25) - '+9779801122334' is a phone - identity weight 85/100 for this anchor type. Evidence count: 75/100 (weight 0.20) - appears in 3 of 8 evidence items. Evidence confidence: 90/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 90/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00011. Correlation strength: 63/100 (weight 0.15) - its 3 evidence items are inter-linked with mean correlation confidence 0.63 (strongest: VERY_STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: khalti_ids:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_185915593C_05
- **identity**: emails:sunita.gurung21@gmail.com
- **confidence score**: 69.3
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00008
  - EVID_00014
- **explanation**: Suspect anchor 'sunita.gurung21@gmail.com' (emails) scores 69.3/100 (HIGH, risk HIGH) across 2 evidence items: EVID_00008, EVID_00014. Identity strength: 75/100 (weight 0.25) - 'sunita.gurung21@gmail.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 50/100 (weight 0.20) - appears in 2 of 8 evidence items. Evidence confidence: 93/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 93/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00014. Correlation strength: 77/100 (weight 0.15) - its 2 evidence items are inter-linked with mean correlation confidence 0.77 (strongest: STRONG). Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: esewa_ids:sunita.gurung21@gmail.com.
- **suspect id**: SUSPECT_CASE_185915593C_02
- **identity**: bank_accounts:05019012345678
- **confidence score**: 67.5
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00014
- **explanation**: Suspect anchor '05019012345678' (bank_accounts) scores 67.5/100 (HIGH, risk HIGH) across 1 evidence item: EVID_00014. Identity strength: 100/100 (weight 0.25) - '05019012345678' is a bank_account - identity weight 100/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence items. Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00014. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: emails:esewa.cashback99@gmail.com, emails:sunita.gurung21@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_185915593C_07
- **identity**: esewa_ids:esewa.cashback99@gmail.com
- **confidence score**: 67.5
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00014
- **explanation**: Suspect anchor 'esewa.cashback99@gmail.com' (esewa_ids) scores 67.5/100 (HIGH, risk HIGH) across 1 evidence item: EVID_00014. Identity strength: 100/100 (weight 0.25) - 'esewa.cashback99@gmail.com' is a esewa_id - identity weight 100/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence items. Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00014. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: bank_accounts:05019012345678, emails:esewa.cashback99@gmail.com, emails:sunita.gurung21@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_185915593C_10
- **identity**: khalti_ids:+9779847011223
- **confidence score**: 65.4
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00011
- **explanation**: Suspect anchor '+9779847011223' (khalti_ids) scores 65.4/100 (HIGH, risk HIGH) across 1 evidence item: EVID_00011. Identity strength: 100/100 (weight 0.25) - '+9779847011223' is a khalti_id - identity weight 100/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence items. Evidence confidence: 86/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 86/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'esewa-cashback-offer.xyz' in EVID_00011. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_185915593C_04
- **identity**: emails:esewa.cashback99@gmail.com
- **confidence score**: 61.2
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00014
- **explanation**: Suspect anchor 'esewa.cashback99@gmail.com' (emails) scores 61.2/100 (HIGH, risk HIGH) across 1 evidence item: EVID_00014. Identity strength: 75/100 (weight 0.25) - 'esewa.cashback99@gmail.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence items. Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - co-occurs with threat-flagged indicator 'https://esewa-cashback-offer.xyz/claim' in EVID_00014. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: bank_accounts:05019012345678, emails:sunita.gurung21@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.
- **suspect id**: SUSPECT_CASE_185915593C_06
- **identity**: emails:support@esewa-verify-kyc.com
- **confidence score**: 61.2
- **confidence level**: HIGH
- **risk level**: HIGH
- **evidence ids**:
  - EVID_00014
- **explanation**: Suspect anchor 'support@esewa-verify-kyc.com' (emails) scores 61.2/100 (HIGH, risk HIGH) across 1 evidence item: EVID_00014. Identity strength: 75/100 (weight 0.25) - 'support@esewa-verify-kyc.com' is a email - identity weight 75/100 for this anchor type. Evidence count: 25/100 (weight 0.20) - appears in 1 of 8 evidence items. Evidence confidence: 100/100 (weight 0.15) - mean Phase-1 evidence confidence of its evidence set is 100/100. Threat intelligence: 100/100 (weight 0.15) - anchor 'support@esewa-verify-kyc.com' is flagged malicious by threat intelligence. Correlation strength: 50/100 (weight 0.15) - fewer than two evidence items (or no correlation input); neutral 50. Timeline span: 0/100 (weight 0.10) - activity spans 0.0 days across its evidence set. Co-occurring identity entities: bank_accounts:05019012345678, emails:esewa.cashback99@gmail.com, emails:sunita.gurung21@gmail.com, esewa_ids:esewa.cashback99@gmail.com, esewa_ids:sunita.gurung21@gmail.com, khalti_ids:+9779801122334, phones:+9779801122334, phones:+9779847011223.

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 7.0
- **malicious indicators**: 5.0
- **suspicious indicators**: 0.0
- **benign indicators**: 2.0
- **evidence with threats**: 4.0
- **threat evidence ratio**: 0.5

## Model Prediction Results

- **indicators classified**: 5
- **flagged malicious**: 3
- **predictions**:
  - **indicator**: https://esewa-cashback-offer.xyz/claim?ref=DsN2026
  - **evidence id**: EVID_00009
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
  - **indicator**: esewa.cashbacko90gmail.com
  - **evidence id**: EVID_00010
  - **verdict**: malicious
  - **risk score**: 75
  - **confidence**: 0.75
  - **risk level**: malicious
  - **source**: heuristics
  - **model version**: 
  - **domain**: esewa.cashbacko90gmail.com
  - **brand impersonated**: esewa
  - **official domain**: False
  - **reasons**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - reward/prize wording in the link: cashback
  - **threat signals**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - reward/prize wording in the link: cashback
  - **indicator**: esewa-verify-kyc.com
  - **evidence id**: EVID_00014
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
  - **evidence id**: EVID_00008
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
  - **indicator**: sunita.gurung216gmail.com
  - **evidence id**: EVID_00010
  - **verdict**: benign
  - **risk score**: 0
  - **confidence**: 0.0
  - **risk level**: benign
  - **source**: heuristics
  - **model version**: 
  - **domain**: sunita.gurung216gmail.com
  - **official domain**: False
  - **reasons**:
    - no risk signal matched
  - **trust signals**:
    - no risk signal matched

## Evidence Quality Summary

- **mean image quality**: 65.17
- **mean evidence confidence**: 90.19
- **mean forgery score**: 18.31
- **max forgery score**: 25.2
- **mean ocr confidence**: 0.91
- **hash verified count**: 8.0

## Metadata Summary

- **evidence id**: EVID_00007
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00008
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00009
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00010
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00011
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00012
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal).
- **evidence id**: EVID_00013
- **has exif**: False
- **device**: 
- **software**: 
- **consistency notes**:
  - none
- **evidence id**: EVID_00014
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
  - **largest campaign size**: 5.0
  - **clustered evidence**: 5.0
  - **unclustered evidence**: 3.0
  - **mean campaign confidence**: 0.7353
- **timeline statistics**:
  - **event count**: 8.0
  - **resolved event count**: 8.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 8.0
  - **stage count**: 4.0
  - **critical event count**: 7.0
  - **timeline span hours**: 1001.44
- **correlation statistics**:
  - **pair count**: 28.0
  - **related pair count**: 28.0
  - **mean confidence**: 0.3621
  - **max confidence**: 0.9389

## Confidence Analysis

- **evidence id**: EVID_00007
- **score**: 85.6
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 85.6/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (62/100).
- **evidence id**: EVID_00008
- **score**: 86.7
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 86.7/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (66/100).
- **evidence id**: EVID_00009
- **score**: 94.1
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 94.1/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (80/100).
- **evidence id**: EVID_00010
- **score**: 84.4
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 84.4/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (56/100).
- **evidence id**: EVID_00011
- **score**: 86.3
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 86.3/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (68/100).
- **evidence id**: EVID_00012
- **score**: 84.4
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 84.4/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (55/100).
- **evidence id**: EVID_00013
- **score**: 100.0
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100).
- **evidence id**: EVID_00014
- **score**: 100.0
- **level**: VERY_HIGH
- **explanation**: Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100).

## Investigation Conclusion

- 8/8 evidence items passed SHA-256 chain-of-custody verification.
- The evidence set is internally connected (28 weighted relationships), consistent with related activity rather than isolated incidents.
- 1 campaign cluster indicate coordinated operation.
- Investigation should focus on anchor '+9779801122334' (78/100 confidence).
- Observed stage order deviates from the canonical scam sequence; evidence acquisition order should be reviewed.

## Statutory Basis

The findings engage 6 provisions of the Electronic Transactions Act, 2063 (2008): s.52, s.47, s.53, s.54, s.19, s.56. Each is listed with the finding that engaged it and the evidence behind that finding.

**Statute:** Electronic Transactions Act, 2063 (2008)  
**ऐन:** विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३  
**Jurisdiction:** Nepal

*Cited from the English text of the Act. The Nepali text is authoritative where the two differ; verify any provision against विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३ before relying on it in a filing.*

### Section 52 — To commit computer fraud

*Section 52, Electronic Transactions Act, 2063 (2008)*

**Conduct.** Acquiring a financial benefit by fraud through a computer, including from the payment of any bill, the balance of another person's account, or an ATM card. The amount obtained is recoverable.

**Penalty.** fine not exceeding one hundred thousand Rupees or imprisonment not exceeding two years or both

**Why this is engaged.** 13 payment identifiers (0119.0625.987456, 0501-0198765432 and 0501-9012345678) appear alongside 9 money values (NPR 1,500, NPR 200 and NPR 25,000) in the same case, evidencing a financial benefit moving through a payment rail.

**Evidence.** EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00013, EVID_00014

### Section 47 — Publication of illegal materials in electronic form

*Section 47, Electronic Transactions Act, 2063 (2008)*

**Conduct.** Publishing or displaying material in electronic media, including on the internet, which is prohibited by prevailing law or is contrary to public morality or decent behaviour.

**Penalty.** fine not exceeding one hundred thousand Rupees or imprisonment not exceeding five years or both

**Why this is engaged.** threat intelligence flagged 5 indicators in this case; the evidence carries 8 web addresses (eSewa-cashback-offer.xyz and esewa-cashback-offer.xyz), i.e. material published in electronic form.

**Evidence.** EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00014

### Section 53 — Punishment to the person who abets to commit computer related offence

*Section 53, Electronic Transactions Act, 2063 (2008)*

**Conduct.** Abetting another to commit an offence under the Act, or attempting or being involved in a conspiracy to commit one.

**Penalty.** fine not exceeding fifty thousand Rupees or imprisonment not exceeding six months or both, depending on the degree of the offence

**Why this is engaged.** campaign CAMP_CASE_185915593C_01 groups 5 evidence items by shared indicators, which evidences coordinated activity rather than a single isolated act.

**Evidence.** EVID_00008, EVID_00009, EVID_00011, EVID_00013, EVID_00014

### Section 54 — Punishment to the Accomplice

*Section 54, Electronic Transactions Act, 2063 (2008)*

**Conduct.** Assisting another to commit an offence under the Act, or acting as an accomplice by any means.

**Penalty.** one half of the punishment for which the principal is liable

**Why this is engaged.** campaign CAMP_CASE_185915593C_01 evidences coordination across 5 evidence items. Where more than one person acted, anyone who assisted is liable to one half of the principal's punishment.

**Evidence.** EVID_00008, EVID_00009, EVID_00011, EVID_00013, EVID_00014

### Section 19 — Punishment for illegal use of trade-marks

*Section 19, Patent, Design and Trade Mark Act, 2022 (1965)*

**Conduct.** Using a trade-mark that is not registered to the user, using one whose registration has been cancelled, or otherwise using a registered mark without authority (s.18B).

**Penalty.** fine not exceeding one hundred thousand Rupees, and confiscation of articles and goods connected with the offence, as per its gravity

**Why this is engaged.** brand marks were detected in the evidence (Facebook, Gmail, Google and 6 more) across 8 evidence items. Where the material was not published by the mark's owner, its use is unauthorised. Registration and authority are matters of record to be confirmed.

**Evidence.** EVID_00007, EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00012, EVID_00013, EVID_00014

### Section 56 — Confiscation

*Section 56, Electronic Transactions Act, 2063 (2008)*

**Conduct.** Any computer, computer system, disk, software or accessory device used to commit an offence relating to computer under the Act is liable to confiscation.

**Penalty.** confiscation of the computer, computer system, disks, software or other accessory devices used

**Why this is engaged.** the findings engage 4 provisions of the Act (s.47, s.52, s.53 and 1 more). Any computer, device or storage medium used to commit those acts falls within the confiscation power and should be identified for seizure.

> This is an automated mapping from technical findings to statutory provisions, provided to assist the investigating officer. It is not legal advice and not a charging decision. A provision is listed because the evidence contains the features described, not because an offence has been proved: intent, authorisation and identity are matters for investigation. Provisions of the Act not listed here were not assessed.


## Recommendations

- Get the fake websites shut down: esewa-cashback-offer.xyz, esewa-verify-kyc.com (+1 more). Ask the hosting company to save its records first.
- Tell eSewa their name is being used in this scam, so they can warn other customers.
- Ask eSewa who owns these wallets (KYC) and their payment history: sunita.gurung21@gmail.com, esewa.cashback99@gmail.com.
- Ask Khalti who owns these wallets (KYC) and their payment history: +9779801122334, +9779847011223.
- Ask the bank who owns these accounts and their statements: 05010198765432, 9847011223 (+1 more).
- Include these payment reference numbers in those requests so the transfers are easy to find: DSN2026, 0119.0625.987456, KH-2026-0611-77245.
- Ask the phone/wallet company who is registered to +9779801122334, +9779847011223 - it appears again and again across this evidence.
- Treat 5 of the items as one scam operation rather than 5 separate incidents - they share the same website.
- Go through the 7 key moments - when money moved and codes were shared - with the victim, and record what they lost.
- Act on this case first (rated 76 out of 100).

## Report Provenance & Integrity

- **report id**: RPT-185915593C-FC9E6AA7
- **generated at**: 2026-08-04T08:17:41.962Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 623b9e5e28815e86892679dc56e1ac545ea1fddc4590023db83275c6bf9c8b61
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: e54500d4afbe2e08798c6bcc637caed97286563b37cd8a4418623282d9bc4671
  - **cross case correlation.json**: c732a2bfe3c5b97e8f15edc5d141b146245e3c2ce435f0ac7d4425c7210854ee
  - **campaign analysis.json**: fca63a5948fc0e9c595f1738255307d7de7e3b2ceea30ddceff94fdb5d72915f
  - **suspect assessment.json**: 56cdf6330e8e6b7962f906899b675186adedc4284ba98518f7973ee58a850402
  - **timeline analysis.json**: 50adb56dc3dd1ad0212e4eda4bf9e4b8d7eb19b44d8f9b9cd30c5cc90a56e788
  - **analytics.json**: 52fbf770752a094dcb85c2ced4172a39a49042a6951becd410c67cc2bd7a88d8
  - **case priority.json**: 4ffdd96e4aeab1d81d5f69c1dad4ef0958e330231bd42e78d0caed4b0cc60362
  - **graph.json**: b597eac3c3b052dfd18d22027136927a1d26e27124a0ea58cd371e0fa2c72c96

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00007
  - **sha256**: 905b21d603ca0a6f49fd226e46470c85d509dce56f8ab68edce76b6b7ff8cec7
  - **upload time**: 2026-07-25T17:16:30.233Z
  - **status**: processed
  - **evidence id**: EVID_00008
  - **sha256**: bb246839287ca1bcc1f6a38bbdf26489ef6eb74213b7fc2d224597a910bf4ef4
  - **upload time**: 2026-07-25T17:17:07.920Z
  - **status**: processed
  - **evidence id**: EVID_00009
  - **sha256**: 6f712c8b0e4fb6c50d156a1bf002713b4bbd60bf7db0a9cf7fbe3ea04b2cbdf9
  - **upload time**: 2026-07-25T17:18:32.458Z
  - **status**: processed
  - **evidence id**: EVID_00010
  - **sha256**: 3a19295ff003a894311ef7efcf80bb94c8feec5a69590c3052f7f8d60ce7217b
  - **upload time**: 2026-07-25T17:18:54.475Z
  - **status**: processed
  - **evidence id**: EVID_00011
  - **sha256**: 54a62cd3ad10a85b9b060ff73dcab3d5fb2bb3f073f3bcab66f90ae45d7d779b
  - **upload time**: 2026-07-25T17:19:57.040Z
  - **status**: processed
  - **evidence id**: EVID_00012
  - **sha256**: b6ec522eddc05475f9ec7671ec46098a129fa8be863cc270c97b42b702e71134
  - **upload time**: 2026-07-25T17:20:21.991Z
  - **status**: processed
  - **evidence id**: EVID_00013
  - **sha256**: 6f1cc10ae55d554c751ee1cbf688924c8962c5faebe87be8c457d077d6bc63c2
  - **upload time**: 2026-07-25T17:20:51.466Z
  - **status**: processed
  - **evidence id**: EVID_00014
  - **sha256**: fe644062bf75e62c8ae13ec24c7e0461491a5610095a50546c4fa757d98e866f
  - **upload time**: 2026-07-25T17:26:20.455Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
