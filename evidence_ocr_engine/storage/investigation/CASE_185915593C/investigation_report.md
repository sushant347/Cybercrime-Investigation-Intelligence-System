# Forensic Investigation Report - CASE_185915593C

Generated: 2026-08-20T14:37:36.663Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Status: Automated analytical draft - investigator review required  
Basis: every statement below references stored forensic findings; accuracy depends on the source evidence and upstream extraction.

## Executive Summary

| # | Finding |
| --- | --- |
| 1 | Case CASE_185915593C contains 8 evidence items; 8/8 passed the stored SHA-256 integrity check. |
| 2 | This case was automatically linked to 2 other cases; these are candidate shared-entity associations: CASE_1A1BF573F3, CASE_EE8250FB76 [cross_case_correlation.json]. |
| 3 | The weighted correlation engine found 10 related evidence pairs out of 28 analysed [correlation_analysis.json]. |
| 4 | Clustering produced 1 candidate campaign; the largest (CAMP_CASE_185915593C_01) groups 4 items for investigator review [campaign_analysis.json]. |
| 5 | The highest-scoring identity lead is '+9779801122334' (khalti_ids), supported by 2 evidence items and scored 78/100; this is a lead, not identity attribution [suspect_assessment.json]. |
| 6 | Chronology contains 4 evidence-derived event times (2 inferred), 4 acquisition-only records and 0 unresolved records [timeline_analysis.json]. |
| 7 | Evidence-timed stage order is incomplete because one or more detected stages has acquisition time only [timeline_analysis.json]. |

## Scope & Methodology

| Scope | Recorded basis |
| --- | --- |
| Objective | Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (identity anchors, candidate clusters and cross-case links) from stored artifacts while preserving each item's recorded integrity status. |
| Evidence scope | 8 evidence items acquired through the CIIS intake pipeline with a recorded SHA-256 digest. |
| Reproducibility | Re-running the analysis against the same stored evidence recomputes the canonical artifacts; report control records the evidence-set digest and the stored JSON companion retains the complete source-artifact hash register. |

### Processing stages

| Stage | Method and stored output |
| --- | --- |
| Phase 1 - Acquisition & OCR | PaddleOCR PP-OCRv5 text extraction with per-item confidence scoring; SHA-256 fingerprint recorded at intake and re-verified at read. |
| Phase 1 - Forensics | metadata/EXIF consistency, forgery signals, logo detection and evidence-confidence scoring stored per item under storage/forensics/. |
| Phase 2 - Correlation | weighted entity-overlap engine scoring every evidence pair; results in correlation_analysis.json. |
| Phase 2 - Cross-case | shared-entity matching against every other analysed case (cross_case_correlation.json). |
| Phase 2 - Campaigns / Suspects / Timeline | clustering, anchor derivation and event reconstruction over the correlated evidence set. |
| Threat intelligence | URL/domain indicators scored by the configured provider (static indicator file, or the trained phishing classifier when CIIS_ML_THREAT_INTEL=1); per-indicator results in 'Model Prediction Results'. |
| Reporting | this document is assembled exclusively from the stored outputs above; it contains no free-text generation. |

## Case Overview

| Case field | Recorded value |
| --- | --- |
| Case Id | CASE_185915593C |
| Evidence Count | 8 |
| First Evidence | 2026-07-25T17:16:30.233Z |
| Last Evidence | 2026-07-25T17:26:20.455Z |
| File Types | jpg, pdf, png |

## Evidence Summary

| Evidence | File | Acquired | OCR confidence | Entities | Integrity |
| --- | --- | --- | --- | --- | --- |
| EVID_00007 | 01_sms_screenshot.jpg | 2026-07-25T17:16:30.233Z | 0.6039 | 0 | VERIFIED |
| EVID_00008 | 02_messenger_chat.jpg | 2026-07-25T17:17:07.920Z | 0.9286 | 4 | VERIFIED |
| EVID_00009 | 03_qr_code_flyer.png | 2026-07-25T17:18:32.458Z | 0.9814 | 4 | VERIFIED |
| EVID_00010 | 04_esewa_payment_screenshot.jpg | 2026-07-25T17:18:54.475Z | 0.9116 | 4 | VERIFIED |
| EVID_00011 | 05_khalti_receipt.jpg | 2026-07-25T17:19:57.040Z | 0.986 | 10 | VERIFIED |
| EVID_00012 | 06_phishing_email_screenshot.jpg | 2026-07-25T17:20:21.991Z | 0.8556 | 2 | VERIFIED |
| EVID_00013 | 07_bank_transfer_slip.pdf | 2026-07-25T17:20:51.466Z | 0.9893 | 8 | VERIFIED |
| EVID_00014 | 08_complaint_letter.pdf | 2026-07-25T17:26:20.455Z | 1.0 | 25 | VERIFIED |

## Timeline Analysis

8 events; 8 timestamps resolved (2 non-inferred, 6 inferred, including 4 acquisition-time fallbacks); 0 timestamps unresolved. Content/metadata event times span 85.3 hours. Keyword-derived stage order: initial_contact -> financial_transaction -> social_engineering -> post_attack. This order is incomplete because one or more detected stages have acquisition time only.

> Chronology is provisional: acquisition time is an intake timestamp, not proof of when the underlying event occurred. Every fallback and unresolved value must be checked against the source exhibit.

| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 8 | 2 | 6 | 4 | 0 |

### Chronological Events

| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-06-11T10:42:00+00:00 | EVID_00010 | 04_esewa_payment_screenshot.jpg | content_labeled_date_time | high | False | initial_contact, financial_transaction |
| 2026-06-11T11:15:00+00:00 | EVID_00011 | 05_khalti_receipt.jpg | content_labeled_date_time | high | False | initial_contact, financial_transaction |
| 2026-06-14T00:00:00+00:00 | EVID_00013 | 07_bank_transfer_slip.pdf | content_date_only | medium | True | initial_contact, financial_transaction |
| 2026-06-15T00:00:00+00:00 | EVID_00014 | 08_complaint_letter.pdf | content_labeled_date_only | medium | True | initial_contact, social_engineering, financial_transaction, post_attack |
| 2026-07-25T17:16:30.233000+00:00 | EVID_00007 | 01_sms_screenshot.jpg | upload_time_fallback | low | True | none |
| 2026-07-25T17:17:07.920000+00:00 | EVID_00008 | 02_messenger_chat.jpg | upload_time_fallback | low | True | initial_contact, financial_transaction |
| 2026-07-25T17:18:32.458000+00:00 | EVID_00009 | 03_qr_code_flyer.png | upload_time_fallback | low | True | initial_contact, financial_transaction |
| 2026-07-25T17:20:21.991000+00:00 | EVID_00012 | 06_phishing_email_screenshot.jpg | upload_time_fallback | low | True | social_engineering, financial_transaction |

### Stage Assessment

- **Keyword-derived order:** initial_contact, financial_transaction, social_engineering, post_attack
- **Order assessable:** False
- **Matches configured sequence:** False

### Critical Events

- **EVID_00010** at 2026-06-11T10:42:00+00:00 (content_labeled_date_time, high, inferred=False): contains money entity/entities: NPR 200; contains transaction_ids entity/entities: 0119.0625.987456
- **EVID_00011** at 2026-06-11T11:15:00+00:00 (content_labeled_date_time, high, inferred=False): contains money entity/entities: NPR 1500; contains khalti_ids entity/entities: +9779801122334, +9779847011223; contains transaction_ids entity/entities: 0SN2026, KH-2026-0611-77245
- **EVID_00013** at 2026-06-14T00:00:00+00:00 (content_date_only, medium, inferred=True): contains money entity/entities: NPR 25000; contains bank_accounts entity/entities: 05010198765432, 9847011223; contains transaction_ids entity/entities: DSN2026, MBL-2026-441829
- **EVID_00014** at 2026-06-15T00:00:00+00:00 (content_labeled_date_only, medium, inferred=True): contains money entity/entities: NPR 1500, NPR 200, NPR 25000; contains esewa_ids entity/entities: esewa.cashback99@gmail.com, sunita.gurung21@gmail.com; contains khalti_ids entity/entities: +9779801122334; contains bank_accounts entity/entities: 05019012345678; contains transaction_ids entity/entities: 0119.0625.987456, CASE_2026_0088, KH-2026-0611-77245
- **EVID_00008** at 2026-07-25T17:17:07.920000+00:00 (upload_time_fallback, low, inferred=True): contains money entity/entities: NPR 200; contains esewa_ids entity/entities: sunita.gurung21@gmail.com
- **EVID_00009** at 2026-07-25T17:18:32.458000+00:00 (upload_time_fallback, low, inferred=True): contains money entity/entities: NPR 5000; contains transaction_ids entity/entities: DSN2026
- **EVID_00012** at 2026-07-25T17:20:21.991000+00:00 (upload_time_fallback, low, inferred=True): contains money entity/entities: NPR 5

## Correlation Analysis

10 of 28 analysed pairs met a configured relationship threshold.

| Evidence pair | Strength | Confidence | Computed basis |
| --- | --- | --- | --- |
| EVID_00011 <-> EVID_00014 | VERY_STRONG | 0.9215 | EVID_00011 (05_khalti_receipt.jpg) and EVID_00014 (08_complaint_letter.pdf) show a very strong relationship (confidence 0.92) based on 7 independent factors. Both items reference the same phones: +9779801122334,… |
| EVID_00008 <-> EVID_00014 | STRONG | 0.7059 | EVID_00008 (02_messenger_chat.jpg) and EVID_00014 (08_complaint_letter.pdf) show a strong relationship (confidence 0.71) based on 5 independent factors. Both items reference the same emails: sunita.gurung21@gmail.com… |
| EVID_00013 <-> EVID_00014 | STRONG | 0.591 | EVID_00013 (07_bank_transfer_slip.pdf) and EVID_00014 (08_complaint_letter.pdf) show a strong relationship (confidence 0.59) based on 4 independent factors. Both items reference the same phones: +9779847011223 [weight… |
| EVID_00009 <-> EVID_00014 | MEDIUM | 0.549 | EVID_00009 (03_qr_code_flyer.png) and EVID_00014 (08_complaint_letter.pdf) show a medium relationship (confidence 0.55) based on 4 independent factors. Both items reference the same domains: esewa-cashback-offer.xyz… |
| EVID_00009 <-> EVID_00011 | MEDIUM | 0.5334 | EVID_00009 (03_qr_code_flyer.png) and EVID_00011 (05_khalti_receipt.jpg) show a medium relationship (confidence 0.53) based on 3 independent factors. Both items reference the same domains: esewa-cashback-offer.xyz… |

## Cross-Case Correlation

These are automated shared-entity associations and require independent corroboration.

| Other case | Strength | Confidence | Matched indicators | Basis |
| --- | --- | --- | --- | --- |
| CASE_1A1BF573F3 | VERY_STRONG | 1.0 | bank_accounts:05010198765432, domains:esewa.cashbacko90gmail.com, domains:sunita.gurung216gmail.com, khalti_ids:+9779847011223, urls:https://esewa-cashback-offer.xyz/claim?ref=dsn2026, +24 more | Shares 29 entity(ies) with CASE_1A1BF573F3: bank account 05010198765432, domain esewa.cashbacko90gmail.com, domain sunita.gurung216gmail.com (+26 more). 25 of these are… |
| CASE_EE8250FB76 | VERY_STRONG | 0.9992 | bank_accounts:05019012345678, domains:esewa-verify-kyc.com, emails:esewa.cashback99@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, +16 more | Shares 21 entity(ies) with CASE_EE8250FB76: bank account 05019012345678, domain esewa-verify-kyc.com, email esewa.cashback99@gmail.com (+18 more). 17 of these are distinctive;… |

## Campaign Analysis

Clusters are candidate groupings produced by configured thresholds; they do not by themselves establish coordination.

| Candidate cluster | Evidence | Confidence | Shared signature |
| --- | --- | --- | --- |
| CAMP_CASE_185915593C_01 | EVID_00008, EVID_00011, EVID_00013, EVID_00014 | 0.7395 | phones:+9779847011223, dates:11 june 2026, domains:esewa-cashback-offer.xyz, domains:gmail.com, emails:sunita.gurung21@gmail.com |

**Unclustered evidence:** EVID_00007, EVID_00009, EVID_00010, EVID_00012

## Suspect Assessment

> Identity anchors are investigative leads, not legal attribution. Verify ownership and role using original exhibits and independent records.

| Identity lead | Score | Confidence | Risk | Supporting evidence |
| --- | --- | --- | --- | --- |
| khalti_ids:+9779801122334 | 77.8 | HIGH | HIGH | EVID_00011, EVID_00014 |
| phones:+9779847011223 | 74.8 | HIGH | HIGH | EVID_00011, EVID_00013, EVID_00014 |
| esewa_ids:sunita.gurung21@gmail.com | 74.6 | HIGH | HIGH | EVID_00008, EVID_00014 |
| phones:+9779801122334 | 72.7 | HIGH | HIGH | EVID_00011, EVID_00012, EVID_00014 |
| emails:sunita.gurung21@gmail.com | 68.3 | HIGH | HIGH | EVID_00008, EVID_00014 |
| bank_accounts:05019012345678 | 67.5 | HIGH | HIGH | EVID_00014 |
| esewa_ids:esewa.cashback99@gmail.com | 67.5 | HIGH | HIGH | EVID_00014 |
| khalti_ids:+9779847011223 | 65.4 | HIGH | HIGH | EVID_00011 |
| emails:esewa.cashback99@gmail.com | 61.2 | HIGH | HIGH | EVID_00014 |
| emails:support@esewa-verify-kyc.com | 61.2 | HIGH | HIGH | EVID_00014 |

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

- **mean image quality**: 66.38
- **mean evidence confidence**: 90.19
- **mean forgery score**: 17.18
- **max forgery score**: 25.2
- **mean ocr confidence**: 0.91
- **hash verified count**: 8.0

## Metadata Summary

| Evidence | EXIF | Device | Software | Consistency notes |
| --- | --- | --- | --- | --- |
| EVID_00007 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00008 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00009 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00010 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00011 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00012 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00013 | False | none | none | none |
| EVID_00014 | False | none | none | none |

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
  - **largest campaign size**: 4.0
  - **clustered evidence**: 4.0
  - **unclustered evidence**: 4.0
  - **mean campaign confidence**: 0.7395
- **timeline statistics**:
  - **event count**: 8.0
  - **resolved event count**: 8.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 6.0
  - **non inferred event count**: 2.0
  - **acquisition fallback count**: 4.0
  - **progression assessable**: 0.0
  - **stage count**: 4.0
  - **critical event count**: 7.0
  - **timeline span hours**: 1062.64
  - **event time span hours**: 85.3
  - **acquisition inclusive span hours**: 1062.64
- **correlation statistics**:
  - **pair count**: 28.0
  - **related pair count**: 10.0
  - **mean confidence**: 0.1809
  - **max confidence**: 0.9215

## Confidence Analysis

| Evidence | Score | Level | Computed explanation |
| --- | --- | --- | --- |
| EVID_00007 | 85.6 | VERY_HIGH | Evidence confidence is 85.6/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (62/100). |
| EVID_00008 | 86.7 | VERY_HIGH | Evidence confidence is 86.7/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (66/100). |
| EVID_00009 | 94.1 | VERY_HIGH | Evidence confidence is 94.1/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (80/100). |
| EVID_00010 | 84.4 | VERY_HIGH | Evidence confidence is 84.4/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (56/100). |
| EVID_00011 | 86.3 | VERY_HIGH | Evidence confidence is 86.3/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (68/100). |
| EVID_00012 | 84.4 | VERY_HIGH | Evidence confidence is 84.4/100 (VERY_HIGH), derived from 6 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: image_quality (55/100). |
| EVID_00013 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00014 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |

## Statement of Limitations

| # | Review boundary |
| --- | --- |
| 1 | This automated report organises submitted material and computed leads. It does not determine guilt or attribute an offence to a person. |
| 2 | OCR and entity extraction can omit, merge or misclassify text. Identifiers, amounts and names must be verified in the original exhibit before operational use. |
| 3 | Timeline quality: 6 inferred timestamp(s), including 4 acquisition-time fallback(s), and 0 unresolved timestamp(s). Date-only values use 00:00 UTC; fallbacks describe intake time rather than event time. |
| 4 | Correlation and cross-case scores measure shared features, not causation, common ownership or identity. |
| 5 | Campaign clusters and identity-anchor scores are prioritisation aids that require independent corroboration. |
| 6 | Threat-intelligence verdicts reflect the configured provider and its coverage at analysis time; no match does not prove safety. |
| 7 | New evidence or corrected extraction may change any finding in this report. |

## Investigation Conclusion

| # | Conclusion |
| --- | --- |
| 1 | 8/8 evidence items passed SHA-256 integrity verification; this establishes stored-file integrity, not the truth of its content. |
| 2 | The engine identified 10 weighted associations for manual corroboration; shared features alone do not prove that the items have a common actor or cause. |
| 3 | 1 candidate campaign cluster met the configured clustering criteria and requires investigator review before being treated as coordinated activity. |
| 4 | Validate the ownership and role of identity lead '+9779801122334' (78/100 model score; 2 supporting evidence items) against provider records and the original exhibits. |
| 5 | The keyword-derived stage order is provisional because one or more stage-bearing items lack a reliable event time. |

## Statutory Basis

The findings engage 7 provisions of the Electronic Transactions Act, 2063 (2008): s.52, s.47, s.53, s.54, s.55, s.19, s.56. Each is listed with the finding that engaged it and the evidence behind that finding.

**Statute:** Electronic Transactions Act, 2063 (2008)  
**ऐन:** विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३  
**Jurisdiction:** Nepal

*Cited from the English text of the Act. The Nepali text is authoritative where the two differ; verify any provision against विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३ before relying on it in a filing.*

### Section 52 — To commit computer fraud

*Section 52, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Acquiring a financial benefit by fraud through a computer, including from the payment of any bill, the balance of another person's account, or an ATM card. The amount obtained is recoverable. |
| Penalty | fine not exceeding one hundred thousand Rupees or imprisonment not exceeding two years or both |
| Evidence-based match | 13 payment identifiers (0119.0625.987456, 0501-0198765432 and 0501-9012345678) appear alongside 9 money values (NPR 1,500, NPR 200 and NPR 25,000) in the same case, evidencing a financial benefit moving through a payment rail. |
| Supporting evidence | EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00013, EVID_00014 |

### Section 47 — Publication of illegal materials in electronic form

*Section 47, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Publishing or displaying material in electronic media, including on the internet, which is prohibited by prevailing law or is contrary to public morality or decent behaviour. |
| Penalty | fine not exceeding one hundred thousand Rupees or imprisonment not exceeding five years or both |
| Evidence-based match | threat intelligence flagged 5 indicators in this case; the evidence carries 8 web addresses (eSewa-cashback-offer.xyz and esewa-cashback-offer.xyz), i.e. material published in electronic form. |
| Supporting evidence | EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00014 |

### Section 53 — Punishment to the person who abets to commit computer related offence

*Section 53, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Abetting another to commit an offence under the Act, or attempting or being involved in a conspiracy to commit one. |
| Penalty | fine not exceeding fifty thousand Rupees or imprisonment not exceeding six months or both, depending on the degree of the offence |
| Evidence-based match | campaign CAMP_CASE_185915593C_01 groups 4 evidence items by shared indicators, which evidences coordinated activity rather than a single isolated act. |
| Supporting evidence | EVID_00008, EVID_00011, EVID_00013, EVID_00014 |

### Section 54 — Punishment to the Accomplice

*Section 54, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Assisting another to commit an offence under the Act, or acting as an accomplice by any means. |
| Penalty | one half of the punishment for which the principal is liable |
| Evidence-based match | campaign CAMP_CASE_185915593C_01 evidences coordination across 4 evidence items. Where more than one person acted, anyone who assisted is liable to one half of the principal's punishment. |
| Supporting evidence | EVID_00008, EVID_00011, EVID_00013, EVID_00014 |

### Section 55 — Punishment in an offence committed outside Nepal

*Section 55, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | An offence under the Act involving a computer, computer system or network located in Nepal may be prosecuted even where the act was committed by a person residing outside Nepal. |
| Penalty | as for the underlying offence |
| Evidence-based match | this case shares identifiers with 2 other cases (CASE_1A1BF573F3 and CASE_EE8250FB76). Where any part of the conduct occurred outside Nepal, the Act still applies to systems located in Nepal. |
| Supporting evidence | none |

### Section 19 — Punishment for illegal use of trade-marks

*Section 19, Patent, Design and Trade Mark Act, 2022 (1965)*

| Field | Recorded value |
| --- | --- |
| Conduct | Using a trade-mark that is not registered to the user, using one whose registration has been cancelled, or otherwise using a registered mark without authority (s.18B). |
| Penalty | fine not exceeding one hundred thousand Rupees, and confiscation of articles and goods connected with the offence, as per its gravity |
| Evidence-based match | brand marks were detected in the evidence (Facebook, Gmail, Google and 6 more) across 6 evidence items. Where the material was not published by the mark's owner, its use is unauthorised. Registration and authority are matters of record to be confirmed. |
| Supporting evidence | EVID_00007, EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00012 |

### Section 56 — Confiscation

*Section 56, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Any computer, computer system, disk, software or accessory device used to commit an offence relating to computer under the Act is liable to confiscation. |
| Penalty | confiscation of the computer, computer system, disks, software or other accessory devices used |
| Evidence-based match | the findings engage 5 provisions of the Act (s.47, s.52, s.53 and 2 more). Any computer, device or storage medium used to commit those acts falls within the confiscation power and should be identified for seizure. |
| Supporting evidence | none |

### Evidentiary and regulatory follow-up

These entries are preservation or investigative actions, not findings that an institution violated a rule.

#### Legal recognition and preservation of electronic records

*Sections 4, 6, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Status | evidence_handling_requirement |
| Expectation | Where the law requires a record to be retained, an electronic record is recognised when it remains accessible, can be reproduced in its original format, and retains available origin, destination, date and time information. |
| Why relevant | This report relies on 8 electronic evidence items; preservation and reproducibility therefore remain material to later verification. |
| Recommended action | Retain the original files, acquisition metadata, SHA-256 values and chain-of-custody history. A file hash supports integrity checking but is not by itself a statutory digital signature under ETA sections 3 and 5. |
| Applicability | Applies where an electronic record is retained or relied on under the Electronic Transactions Act and prevailing law. |
| Supporting evidence | EVID_00007, EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00012, EVID_00013, EVID_00014 |

#### Preserve and correlate forensic logs

*Controls 83, 84, 85, 86, Nepal Rastra Bank Cyber Resilience Guidelines 2023*

| Field | Recorded value |
| --- | --- |
| Status | investigative_follow_up |
| Expectation | Detected events should be recorded with information such as event type, time and user or address; audit data should be protected, logs securely backed up, timestamps synchronised, and events centralised and correlated across relevant systems. |
| Why relevant | The case contains 13 payment identifiers across 6 evidence items; the corresponding institution-side records may establish transaction sequence, account activity, source address and timing. |
| Recommended action | Send a preservation request for transaction, authentication, application, system and network logs, including timezone and clock-synchronisation details, before normal retention or rotation removes them. |
| Applicability | Conditional: confirm that the affected organisation is an institution within the Guidelines' scope, including an A, B, C or D class BFI, Payment System Operator or Payment Service Provider licensed by NRB's Payment Systems Department. |
| Supporting evidence | EVID_00008, EVID_00009, EVID_00010, EVID_00011, EVID_00013, EVID_00014 |

### Provisions requiring manual review

The current evidence model does not automatically assess these provisions:

- **Section 44 — To Pirate, Destroy or Alter computer source code:** manual review requires source-code versions, repository history or another technical comparison establishing alteration
- **Section 48 — Breach of confidentiality:** manual review must establish both the person's authorised access and disclosure to an unauthorised recipient
- **Section 57 — Offences committed by a corporate body:** manual review requires attribution to a corporate body and evidence of responsibility, consent, knowledge or negligence

### Primary sources

- **Nepal Law Commission — Electronic Transactions Act, 2063 (2008)**  
  https://lawcommission.gov.np/content/13397/  
  Used for: Statutory offence mapping and electronic-record preservation guidance.
  Note: The Nepali text is authoritative where it differs from the English translation.
- **Nepal Rastra Bank, Payment Systems Department — Nepal Rastra Bank Cyber Resilience Guidelines 2023**  
  https://www.nrb.org.np/contents/uploads/2023/08/Cyber-Resilience-Guidelines-2023.pdf  
  Used for: Conditional investigative follow-up for authentication and forensic logging; never used as an offence finding.
  Note: Repository copy verified byte-for-byte against the official NRB download. Applicability to the affected institution must be confirmed by the investigator.

> This is an automated mapping from technical findings to statutory provisions, provided to assist the investigating officer. It is not legal advice and not a charging decision. A provision is listed because the evidence contains the features described, not because an offence has been proved: intent, authorisation and identity are matters for investigation. Provisions of the Act not listed here were not assessed.


## Recommendations

| # | Investigator action |
| --- | --- |
| 1 | Issue preservation requests to the relevant hosting providers, then seek suspension of the suspected domains: esewa-cashback-offer.xyz,... |
| 2 | Notify eSewa of suspected brand impersonation and request preservation of any related abuse records. |
| 3 | Request subscriber/KYC ownership and transaction history from eSewa for: sunita.gurung21@gmail.com, esewa.cashback99@gmail.com. |
| 4 | Request subscriber/KYC ownership and transaction history from Khalti for: +9779801122334, +9779847011223. |
| 5 | Request account-holder identity and statements from the relevant bank for: 05010198765432, 9847011223 (+1 more). |
| 6 | Verify these extracted payment references against the source exhibits before including them in record requests: DSN2026, 0119.0625.987456,... |
| 7 | Ask the relevant provider to verify registration, ownership and transaction records for +9779801122334, +9779847011223; confirm each party's role. |
| 8 | Review 4 items as a candidate cluster because they share a website; corroborate the link before combining incidents. |
| 9 | Review the 4 flagged events with the source exhibits; confirm each event's time, participants and any loss with the complainant. |
| 10 | Assign high queue priority (rated 73 out of 100). |

## Report Provenance & Integrity

- **report id**: RPT-185915593C-E17EB5B7
- **generated at**: 2026-08-20T14:37:36.660Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 623b9e5e28815e86892679dc56e1ac545ea1fddc4590023db83275c6bf9c8b61
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 9757224a52d4bcafd723b968f9b4eb7ea3087c6114708c6ed8674af0bb6a9046
  - **cross case correlation.json**: c732a2bfe3c5b97e8f15edc5d141b146245e3c2ce435f0ac7d4425c7210854ee
  - **campaign analysis.json**: 05d1be10d72591e4884d31f468f1099e8dde687f781af65a7dbb5dd0a0cfcc4b
  - **suspect assessment.json**: 1a299f2002a5a8b61b35cd54098eff6dee5febb18a96a7c1a70f13514288fa5b
  - **timeline analysis.json**: 9568c6699de1ba663a4c1cd1c1d65345131137a13c2539a97e3d2f3bc2d67df3
  - **analytics.json**: 41da3724d72034e1138d340d4ee1d1d95bce1a06aad56ee1bedf4c7e9c0d2c69
  - **case priority.json**: c8d3a8004ca15e69f0be11b20c4b74aea2f055c9d4c319de4bfda2aa1633c036
  - **graph.json**: 1507f39e6b2ff34789d0d56da888dfb63cdb45ee12476a7a93e2dcfc6af50bf6

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
