# Forensic Investigation Report - CASE_0CD406813C

Generated: 2026-08-21T17:13:56.142Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Status: Automated analytical draft - investigator review required  
Basis: every statement below references stored forensic findings; accuracy depends on the source evidence and upstream extraction.

## Executive Summary

| # | Finding |
| --- | --- |
| 1 | Case CASE_0CD406813C contains 8 evidence items; 8/8 passed the stored SHA-256 integrity check. |
| 2 | This case was automatically linked to 4 other cases; these are candidate shared-entity associations: CASE_4B2A51A300, CASE_EE8250FB76, CASE_185915593C, CASE_1A1BF573F3 [cross_case_correlation.json]. |
| 3 | The weighted correlation engine found 17 related evidence pairs out of 28 analysed [correlation_analysis.json]. |
| 4 | Clustering produced 1 candidate campaign; the largest (CAMP_CASE_0CD406813C_01) groups 6 items for investigator review [campaign_analysis.json]. |
| 5 | The highest-scoring identity lead is '+9779812345678' (esewa_ids), supported by 4 evidence items and scored 85/100; this is a lead, not identity attribution [suspect_assessment.json]. |
| 6 | Chronology contains 5 evidence-derived event times (3 inferred), 3 acquisition-only records and 0 unresolved records [timeline_analysis.json]. |
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
| Case Id | CASE_0CD406813C |
| Evidence Count | 8 |
| First Evidence | 2026-08-21T06:37:22.707Z |
| Last Evidence | 2026-08-21T06:38:44.588Z |
| File Types | csv, jpg, pdf, txt, url |

## Evidence Summary

| Evidence | File | Acquired | OCR confidence | Entities | Integrity |
| --- | --- | --- | --- | --- | --- |
| EVID_00026 | 07_qr_flyer_poor_capture.jpg | 2026-08-21T06:37:22.707Z | 0.9819 | 0 | VERIFIED |
| EVID_00027 | 06_complaint_letter.pdf | 2026-08-21T06:37:35.208Z | 1.0 | 14 | VERIFIED |
| EVID_00028 | 05_bank_statement.csv | 2026-08-21T06:37:35.597Z | 1.0 | 5 | VERIFIED |
| EVID_00029 | 04_phishing_email.txt | 2026-08-21T06:37:35.716Z | 1.0 | 11 | VERIFIED |
| EVID_00030 | 03_esewa_payment_receipt.jpg | 2026-08-21T06:37:35.842Z | 0.9956 | 6 | VERIFIED |
| EVID_00031 | 02_messenger_chat.jpg | 2026-08-21T06:37:39.863Z | 0.9871 | 6 | VERIFIED |
| EVID_00032 | 01_sms_cashback_offer.jpg | 2026-08-21T06:37:43.588Z | 0.8675 | 3 | VERIFIED |
| EVID_00033 | https_esewa-bonus-claim.xyz_verify_ref_DSN2026.url | 2026-08-21T06:38:44.588Z | 1.0 | 2 | VERIFIED |

## Timeline Analysis

8 events; 8 timestamps resolved (2 non-inferred, 6 inferred, including 3 acquisition-time fallbacks); 0 timestamps unresolved. Content/metadata event times span 11.7 hours. Keyword-derived stage order: social_engineering -> financial_transaction -> post_attack. This order is incomplete because one or more detected stages have acquisition time only.

> Chronology is provisional: acquisition time is an intake timestamp, not proof of when the underlying event occurred. Every fallback and unresolved value must be checked against the source exhibit.

| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 8 | 2 | 6 | 3 | 0 |

### Chronological Events

| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07-14T00:00:00+00:00 | EVID_00027 | 06_complaint_letter.pdf | content_date_only | medium | True | social_engineering, financial_transaction, post_attack |
| 2026-07-14T00:00:00+00:00 | EVID_00028 | 05_bank_statement.csv | content_date_only | medium | True | financial_transaction |
| 2026-07-14T00:00:00+00:00 | EVID_00031 | 02_messenger_chat.jpg | content_date_only | medium | True | financial_transaction |
| 2026-07-14T09:12:04+00:00 | EVID_00029 | 04_phishing_email.txt | content_labeled_date_time | high | False | social_engineering, financial_transaction |
| 2026-07-14T11:42:00+00:00 | EVID_00030 | 03_esewa_payment_receipt.jpg | content_date_time | high | False | financial_transaction |
| 2026-08-21T06:37:22.707000+00:00 | EVID_00026 | 07_qr_flyer_poor_capture.jpg | upload_time_fallback | low | True | initial_contact |
| 2026-08-21T06:37:43.588000+00:00 | EVID_00032 | 01_sms_cashback_offer.jpg | upload_time_fallback | low | True | social_engineering, financial_transaction |
| 2026-08-21T06:38:44.588000+00:00 | EVID_00033 | https_esewa-bonus-claim.xyz_verify_ref_DSN2026.url | upload_time_fallback | low | True | social_engineering, financial_transaction |

### Stage Assessment

- **Keyword-derived order:** social_engineering, financial_transaction, post_attack
- **Order assessable:** False
- **Matches configured sequence:** True

### Critical Events

- **EVID_00027** at 2026-07-14T00:00:00+00:00 (content_date_only, medium, inferred=True): contains money entity/entities: NPR 12000, NPR 12500, NPR 15000; contains esewa_ids entity/entities: +9779812345678; contains bank_accounts entity/entities: 01903015472901; contains transaction_ids entity/entities: ESW-2026-0714-88231
- **EVID_00028** at 2026-07-14T00:00:00+00:00 (content_date_only, medium, inferred=True): contains esewa_ids entity/entities: +9779812345678
- **EVID_00031** at 2026-07-14T00:00:00+00:00 (content_date_only, medium, inferred=True): contains money entity/entities: NPR 500; contains esewa_ids entity/entities: +9779812345678
- **EVID_00029** at 2026-07-14T09:12:04+00:00 (content_labeled_date_time, high, inferred=False): contains money entity/entities: NPR 15000, NPR 500; contains esewa_ids entity/entities: +9779812345678
- **EVID_00030** at 2026-07-14T11:42:00+00:00 (content_date_time, high, inferred=False): contains money entity/entities: NPR 500; contains transaction_ids entity/entities: ESW-2026-0714-88231
- **EVID_00032** at 2026-08-21T06:37:43.588000+00:00 (upload_time_fallback, low, inferred=True): contains money entity/entities: NPR 15, NPR 500

## Correlation Analysis

17 of 28 analysed pairs met a configured relationship threshold.

Each factor below contributes points. The points sum to the pair's total weight, and the confidence is that total put through a saturating curve - so more corroborating factors raise confidence, but no single factor can carry a pair to certainty on its own.

| Evidence pair | Strength | Weight | Confidence | Contributing factors |
| --- | --- | --- | --- | --- |
| EVID_00027 <-> EVID_00029 | VERY_STRONG | 5.17 | 0.9606 | **Phones** (+0.51): +9779812345678 - but 1 of these are common across the corpus and were discounted<br>**Emails** (+0.59): reward.center2026@gmail.com<br>**Esewa Ids** (+0.83): +9779812345678<br>**Urls** (+0.68): https://esewa-bonus-claim.xyz/verify?ref=dsn2026<br>**Domains** (+0.77): esewa-bonus-claim.xyz, gmail.com - but 1 of these are common across the corpus and were…<br>**Money** (+0.19): npr 15000, npr 500<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+1.60): Threat intelligence flags the same malicious indicators in both items:… |
| EVID_00027 <-> EVID_00033 | VERY_STRONG | 2.72 | 0.8168 | **Urls** (+0.68): https://esewa-bonus-claim.xyz/verify?ref=dsn2026<br>**Domains** (+0.44): esewa-bonus-claim.xyz<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+1.60): Threat intelligence flags the same malicious indicators in both items:… |
| EVID_00029 <-> EVID_00033 | VERY_STRONG | 2.72 | 0.8168 | **Urls** (+0.68): https://esewa-bonus-claim.xyz/verify?ref=dsn2026<br>**Domains** (+0.44): esewa-bonus-claim.xyz<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+1.60): Threat intelligence flags the same malicious indicators in both items:… |
| EVID_00027 <-> EVID_00030 | STRONG | 2.45 | 0.7832 | **Phones** (+1.41): +9779841002233, +9779812345678 - but 1 of these are common across the corpus and were…<br>**Transaction Ids** (+0.95): esw-2026-0714-88231<br>**Money** (+0.09): npr 500<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window) |
| EVID_00027 <-> EVID_00031 | STRONG | 2.35 | 0.7703 | **Phones** (+0.51): +9779812345678 - but 1 of these are common across the corpus and were discounted<br>**Emails** (+0.59): reward.center2026@gmail.com<br>**Esewa Ids** (+0.83): +9779812345678<br>**Domains** (+0.34): gmail.com - but 1 of these are common across the corpus and were discounted<br>**Money** (+0.09): npr 500<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window) |

## Cross-Case Correlation

These are automated shared-entity associations and require independent corroboration.

| Other case | Strength | Confidence | Matched indicators | Basis |
| --- | --- | --- | --- | --- |
| CASE_4B2A51A300 | VERY_STRONG | 0.8238 | bank_accounts:01903015472901, domains:esewa-bonus-claim.xyz, emails:reward.center2026@gmail.com, phones:+9779812345678, domains:gmail.com | Shares 5 entity(ies) with CASE_4B2A51A300: bank account 01903015472901, domain esewa-bonus-claim.xyz, email reward.center2026@gmail.com (+2 more) |
| CASE_EE8250FB76 | WEAK | 0.189 | domains:gmail.com | Shares 1 entity(ies) with CASE_EE8250FB76: domain gmail.com |
| CASE_185915593C | WEAK | 0.189 | domains:gmail.com | Shares 1 entity(ies) with CASE_185915593C: domain gmail.com |
| CASE_1A1BF573F3 | WEAK | 0.189 | domains:gmail.com | Shares 1 entity(ies) with CASE_1A1BF573F3: domain gmail.com |

## Campaign Analysis

Clusters are candidate groupings produced by configured thresholds; they do not by themselves establish coordination.

| Candidate cluster | Evidence | Confidence | Shared signature |
| --- | --- | --- | --- |
| CAMP_CASE_0CD406813C_01 | EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031, EVID_00033 | 0.7357 | phones:+9779812345678, dates:2026-07-14, esewa_ids:+9779812345678, money:npr 500, domains:esewa-bonus-claim.xyz |

**Unclustered evidence:** EVID_00026, EVID_00032

## Suspect Assessment

> Identity anchors are investigative leads, not legal attribution. Verify ownership and role using original exhibits and independent records.

| Identity lead | Score | Confidence | Risk | Supporting evidence |
| --- | --- | --- | --- | --- |
| esewa_ids:+9779812345678 | 85.0 | VERY_HIGH | CRITICAL | EVID_00027, EVID_00028, EVID_00029, EVID_00031 |
| phones:+9779812345678 | 77.5 | HIGH | HIGH | EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031, EVID_00032 |
| emails:reward.center2026@gmail.com | 75.6 | HIGH | HIGH | EVID_00027, EVID_00029, EVID_00031 |
| phones:+9779841002233 | 72.0 | HIGH | HIGH | EVID_00027, EVID_00030 |
| bank_accounts:01903015472901 | 67.5 | HIGH | HIGH | EVID_00027 |
| emails:sunita.rai88@gmail.com | 61.2 | HIGH | HIGH | EVID_00029 |

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 3.0
- **malicious indicators**: 2.0
- **suspicious indicators**: 0.0
- **benign indicators**: 1.0
- **evidence with threats**: 3.0
- **threat evidence ratio**: 0.375

## Model Prediction Results

- **indicators classified**: 2
- **flagged malicious**: 1
- **predictions**:
  - **indicator**: https://esewa-bonus-claim.xyz/verify?ref=DSN2026
  - **evidence id**: EVID_00027
  - **verdict**: malicious
  - **risk score**: 100
  - **confidence**: 1.0
  - **risk level**: malicious
  - **source**: heuristics
  - **model version**: 
  - **domain**: esewa-bonus-claim.xyz
  - **brand impersonated**: esewa
  - **official domain**: False
  - **reasons**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - registered under '.xyz', a TLD with a high abuse rate
    - credential/verification wording in the link: verify
    - reward/prize wording in the link: bonus, claim
    - combines a reward offer with a verification request
  - **threat signals**:
    - hostname contains the brand 'esewa' but is not an official esewa domain
    - registered under '.xyz', a TLD with a high abuse rate
    - credential/verification wording in the link: verify
    - reward/prize wording in the link: bonus, claim
    - combines a reward offer with a verification request
  - **indicator**: gmail.com
  - **evidence id**: EVID_00027
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

- **mean image quality**: 61.12
- **mean evidence confidence**: 91.88
- **mean forgery score**: 16.25
- **max forgery score**: 23.7
- **mean ocr confidence**: 0.98
- **hash verified count**: 8.0
- **evidence with ocr result**: 8.0

## Metadata Summary

| Evidence | EXIF | Device | Software | Consistency notes |
| --- | --- | --- | --- | --- |
| EVID_00026 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00027 | False | none | none | none |
| EVID_00028 | False | none | none | none |
| EVID_00029 | False | none | none | none |
| EVID_00030 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00031 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00032 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00033 | False | none | none | none |

## Investigation Statistics

- **entity statistics**:
  - **bank accounts**: 1
  - **dates**: 7
  - **domains**: 6
  - **emails**: 4
  - **esewa ids**: 4
  - **money**: 10
  - **phones**: 8
  - **times**: 2
  - **transaction ids**: 2
  - **urls**: 3
- **campaign statistics**:
  - **campaign count**: 1.0
  - **largest campaign size**: 6.0
  - **clustered evidence**: 6.0
  - **unclustered evidence**: 2.0
  - **mean campaign confidence**: 0.7357
- **timeline statistics**:
  - **event count**: 8.0
  - **resolved event count**: 8.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 6.0
  - **non inferred event count**: 2.0
  - **acquisition fallback count**: 3.0
  - **progression assessable**: 0.0
  - **stage count**: 4.0
  - **critical event count**: 6.0
  - **timeline span hours**: 918.65
  - **event time span hours**: 11.7
  - **acquisition inclusive span hours**: 918.65
- **correlation statistics**:
  - **pair count**: 28.0
  - **related pair count**: 17.0
  - **mean confidence**: 0.3226
  - **max confidence**: 0.9606

## Confidence Analysis

| Evidence | Score | Level | Computed explanation |
| --- | --- | --- | --- |
| EVID_00026 | 82.0 | VERY_HIGH | Evidence confidence is 82.0/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: image_quality (38/100). |
| EVID_00027 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00028 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00029 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00030 | 86.7 | VERY_HIGH | Evidence confidence is 86.7/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: image_quality (77/100). |
| EVID_00031 | 87.0 | VERY_HIGH | Evidence confidence is 87.0/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: forgery (79/100). |
| EVID_00032 | 79.3 | HIGH | Evidence confidence is 79.3/100 (HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: image_quality (51/100). |
| EVID_00033 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |

## Statement of Limitations

| # | Review boundary |
| --- | --- |
| 1 | This automated report organises submitted material and computed leads. It does not determine guilt or attribute an offence to a person. |
| 2 | OCR and entity extraction can omit, merge or misclassify text. Identifiers, amounts and names must be verified in the original exhibit before operational use. |
| 3 | Timeline quality: 6 inferred timestamp(s), including 3 acquisition-time fallback(s), and 0 unresolved timestamp(s). Date-only values use 00:00 UTC; fallbacks describe intake time rather than event time. |
| 4 | Correlation and cross-case scores measure shared features, not causation, common ownership or identity. |
| 5 | Campaign clusters and identity-anchor scores are prioritisation aids that require independent corroboration. |
| 6 | Threat-intelligence verdicts reflect the configured provider and its coverage at analysis time; no match does not prove safety. |
| 7 | New evidence or corrected extraction may change any finding in this report. |

## Investigation Conclusion

| # | Conclusion |
| --- | --- |
| 1 | 8/8 evidence items passed SHA-256 integrity verification; this establishes stored-file integrity, not the truth of its content. |
| 2 | The engine identified 17 weighted associations for manual corroboration; shared features alone do not prove that the items have a common actor or cause. |
| 3 | 1 candidate campaign cluster met the configured clustering criteria and requires investigator review before being treated as coordinated activity. |
| 4 | Validate the ownership and role of identity lead '+9779812345678' (85/100 model score; 4 supporting evidence items) against provider records and the original exhibits. |
| 5 | The keyword-derived stage order is provisional because one or more stage-bearing items lack a reliable event time. |

## Statutory Basis

The findings engage 6 provisions of the Electronic Transactions Act, 2063 (2008): s.52, s.47, s.53, s.54, s.55, s.56. Each is listed with the finding that engaged it and the evidence behind that finding.

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
| Evidence-based match | 3 payment identifiers (01903015472901, 9812345678 and ESW-2026-0714-88231) appear alongside 7 money values (NPR 12,000, NPR 12,500 and NPR 15,000) in the same case, evidencing a financial benefit moving through a payment rail. |
| Supporting evidence | EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031 |

### Section 47 — Publication of illegal materials in electronic form

*Section 47, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Publishing or displaying material in electronic media, including on the internet, which is prohibited by prevailing law or is contrary to public morality or decent behaviour. |
| Penalty | fine not exceeding one hundred thousand Rupees or imprisonment not exceeding five years or both |
| Evidence-based match | threat intelligence flagged 2 indicators in this case; the evidence carries 3 web addresses (esewa-bonus-claim.xyz and gmail.com), i.e. material published in electronic form. |
| Supporting evidence | EVID_00027, EVID_00029, EVID_00031, EVID_00033 |

### Section 53 — Punishment to the person who abets to commit computer related offence

*Section 53, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Abetting another to commit an offence under the Act, or attempting or being involved in a conspiracy to commit one. |
| Penalty | fine not exceeding fifty thousand Rupees or imprisonment not exceeding six months or both, depending on the degree of the offence |
| Evidence-based match | campaign CAMP_CASE_0CD406813C_01 groups 6 evidence items by shared indicators, which evidences coordinated activity rather than a single isolated act. |
| Supporting evidence | EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031, EVID_00033 |

### Section 54 — Punishment to the Accomplice

*Section 54, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Assisting another to commit an offence under the Act, or acting as an accomplice by any means. |
| Penalty | one half of the punishment for which the principal is liable |
| Evidence-based match | campaign CAMP_CASE_0CD406813C_01 evidences coordination across 6 evidence items. Where more than one person acted, anyone who assisted is liable to one half of the principal's punishment. |
| Supporting evidence | EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031, EVID_00033 |

### Section 55 — Punishment in an offence committed outside Nepal

*Section 55, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | An offence under the Act involving a computer, computer system or network located in Nepal may be prosecuted even where the act was committed by a person residing outside Nepal. |
| Penalty | as for the underlying offence |
| Evidence-based match | this case shares identifiers with 4 other cases (CASE_4B2A51A300, CASE_EE8250FB76 and CASE_185915593C). Where any part of the conduct occurred outside Nepal, the Act still applies to systems located in Nepal. |
| Supporting evidence | none |

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
| Supporting evidence | EVID_00026, EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031, EVID_00032, EVID_00033 |

#### Preserve and correlate forensic logs

*Controls 83, 84, 85, 86, Nepal Rastra Bank Cyber Resilience Guidelines 2023*

| Field | Recorded value |
| --- | --- |
| Status | investigative_follow_up |
| Expectation | Detected events should be recorded with information such as event type, time and user or address; audit data should be protected, logs securely backed up, timestamps synchronised, and events centralised and correlated across relevant systems. |
| Why relevant | The case contains 3 payment identifiers across 5 evidence items; the corresponding institution-side records may establish transaction sequence, account activity, source address and timing. |
| Recommended action | Send a preservation request for transaction, authentication, application, system and network logs, including timezone and clock-synchronisation details, before normal retention or rotation removes them. |
| Applicability | Conditional: confirm that the affected organisation is an institution within the Guidelines' scope, including an A, B, C or D class BFI, Payment System Operator or Payment Service Provider licensed by NRB's Payment Systems Department. |
| Supporting evidence | EVID_00027, EVID_00028, EVID_00029, EVID_00030, EVID_00031 |

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
| 1 | Issue preservation requests to the relevant hosting providers, then seek suspension of the suspected domains: esewa-bonus-claim.xyz. |
| 2 | Notify eSewa of suspected brand impersonation and request preservation of any related abuse records. |
| 3 | Request subscriber/KYC ownership and transaction history from eSewa for: +9779812345678. |
| 4 | Request account-holder identity and statements from the relevant bank for: 01903015472901. |
| 5 | Verify these extracted payment references against the source exhibits before including them in record requests: ESW-2026-0714-88231. |
| 6 | Ask the relevant provider to verify registration, ownership and transaction records for +9779812345678, +9779812345678; confirm each party's role. |
| 7 | Review 6 items as a candidate cluster because they share a website; corroborate the link before combining incidents. |
| 8 | Review the 5 flagged events with the source exhibits; confirm each event's time, participants and any loss with the complainant. |
| 9 | Assign high queue priority (rated 74 out of 100). |

## Report Provenance & Integrity

- **report id**: RPT-0CD406813C-59BB87FA
- **generated at**: 2026-08-21T17:13:56.132Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 6a093b28d16b75f95430e52d41f6850d0a52dbd244181ec168371088f9894ae5
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 60cb69ce986428118efda9932df1555e848b9fef21a5b0b981133115243c10ed
  - **cross case correlation.json**: b0223c3d86976fc8d5af7e8ed6659d0ca3de2999cfbcef22448311c7ad611925
  - **campaign analysis.json**: 192cb8fd4882249a42a6f17a87a671725be3dd0169c9377ebe29b045134319ca
  - **suspect assessment.json**: 94a14a0b6f8ccc03c9e45180858692de3b7ff14824c7867677e7c1aaf803dd95
  - **timeline analysis.json**: 5106588ec44d97934fe7c5ee081b45fa862c7683a240b3c3ec17d52d15617e7f
  - **analytics.json**: 65cb03d90c52ebb743ae95f11e8d4eec81b9118da83c06b7030151feda7c599d
  - **case priority.json**: 1f07c289d3d90e68f92e970b5627cc690ff4dced50f135c6f99f789cc9a4124c
  - **graph.json**: daaa9bb618295e2a357baa72fc120c6eb2bd7cf4752937a326c006416d68bfd8

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00026
  - **sha256**: 54ecd6f0726dc06df8a4080f5377ce550949435850008b0cb18beeb199da5cdc
  - **upload time**: 2026-08-21T06:37:22.707Z
  - **status**: processed
  - **evidence id**: EVID_00027
  - **sha256**: 92af393efbe4f1c68816dd41fe4f22a3c92fb51aabd653c9a733e51f432579d1
  - **upload time**: 2026-08-21T06:37:35.208Z
  - **status**: processed
  - **evidence id**: EVID_00028
  - **sha256**: 4bf76c0070966e3953399f40b5e7e857385972901f7f0ec90d1f62a8883a1b2d
  - **upload time**: 2026-08-21T06:37:35.597Z
  - **status**: processed
  - **evidence id**: EVID_00029
  - **sha256**: e094c54741fc7f917edb2ed1de466f4b06e7db8a51ef1414d85eb77fa4bda9f8
  - **upload time**: 2026-08-21T06:37:35.716Z
  - **status**: processed
  - **evidence id**: EVID_00030
  - **sha256**: 82cca081731e572e0951071a23a00ca1ae6d34c40af85a267239d6972f35a028
  - **upload time**: 2026-08-21T06:37:35.842Z
  - **status**: processed
  - **evidence id**: EVID_00031
  - **sha256**: 7624533fbd367356fab83feb47c09adcfd469d85541e4304f4cd6b9871c4a1c3
  - **upload time**: 2026-08-21T06:37:39.863Z
  - **status**: processed
  - **evidence id**: EVID_00032
  - **sha256**: 24fbac36402807e454b2f69df2a9b2a6c5379acd13b062ed1a98f54b0205947e
  - **upload time**: 2026-08-21T06:37:43.588Z
  - **status**: processed
  - **evidence id**: EVID_00033
  - **sha256**: 4a23480101586a51f81577723dcedd0f27a7d5f6c08e32db61363ce95792b2a5
  - **upload time**: 2026-08-21T06:38:44.588Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
