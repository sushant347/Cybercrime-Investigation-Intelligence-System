# Forensic Investigation Report - CASE_4B2A51A300

Generated: 2026-08-21T17:57:23.083Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Status: Automated analytical draft - investigator review required  
Basis: every statement below references stored forensic findings; accuracy depends on the source evidence and upstream extraction.

## Executive Summary

| # | Finding |
| --- | --- |
| 1 | Case CASE_4B2A51A300 contains 9 evidence items; 9/9 passed the stored SHA-256 integrity check. |
| 2 | This case was automatically linked to 4 other cases; these are candidate shared-entity associations: CASE_0CD406813C, CASE_EE8250FB76, CASE_185915593C, CASE_1A1BF573F3 [cross_case_correlation.json]. |
| 3 | The weighted correlation engine found 20 related evidence pairs out of 36 analysed [correlation_analysis.json]. |
| 4 | Clustering produced 1 candidate campaign; the largest (CAMP_CASE_4B2A51A300_01) groups 8 items for investigator review [campaign_analysis.json]. |
| 5 | The highest-scoring identity lead is '+9779812345678' (khalti_ids), supported by 5 evidence items and scored 85/100; this is a lead, not identity attribution [suspect_assessment.json]. |
| 6 | Chronology contains 4 evidence-derived event times (2 inferred), 5 acquisition-only records and 0 unresolved records [timeline_analysis.json]. |
| 7 | Evidence-timed stage order is incomplete because one or more detected stages has acquisition time only [timeline_analysis.json]. |

## Scope & Methodology

| Scope | Recorded basis |
| --- | --- |
| Objective | Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (identity anchors, candidate clusters and cross-case links) from stored artifacts while preserving each item's recorded integrity status. |
| Evidence scope | 9 evidence items acquired through the CIIS intake pipeline with a recorded SHA-256 digest. |
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
| Case Id | CASE_4B2A51A300 |
| Evidence Count | 9 |
| First Evidence | 2026-08-21T06:42:54.755Z |
| Last Evidence | 2026-08-21T06:43:15.097Z |
| File Types | csv, jpg, pdf, txt, url |

## Evidence Summary

| Evidence | File | Acquired | OCR confidence | Entities | Integrity |
| --- | --- | --- | --- | --- | --- |
| EVID_00034 | 07_fake_support_profile.jpg | 2026-08-21T06:42:54.755Z | 0.9934 | 5 | VERIFIED |
| EVID_00035 | 06_police_complaint.pdf | 2026-08-21T06:43:01.064Z | 1.0 | 15 | VERIFIED |
| EVID_00036 | 05_transactions.csv | 2026-08-21T06:43:01.325Z | 1.0 | 5 | VERIFIED |
| EVID_00037 | 04_kyc_phishing_email.txt | 2026-08-21T06:43:01.370Z | 1.0 | 13 | VERIFIED |
| EVID_00038 | 03_khalti_receipt.jpg | 2026-08-21T06:43:01.434Z | 0.9962 | 6 | VERIFIED |
| EVID_00039 | 02_whatsapp_chat.jpg | 2026-08-21T06:43:07.959Z | 0.9872 | 5 | VERIFIED |
| EVID_00040 | 01_khalti_kyc_sms.jpg | 2026-08-21T06:43:11.546Z | 0.7512 | 0 | VERIFIED |
| EVID_00041 | http_khalti-kyc-verify.top_login.url | 2026-08-21T06:43:15.002Z | 1.0 | 2 | VERIFIED |
| EVID_00042 | https_esewa-bonus-claim.xyz_verify_ref_KYC2026.url | 2026-08-21T06:43:15.097Z | 1.0 | 2 | VERIFIED |

## Timeline Analysis

9 events; 9 timestamps resolved (2 non-inferred, 7 inferred, including 5 acquisition-time fallbacks); 0 timestamps unresolved. Content/metadata event times span 15.3 hours. Keyword-derived stage order: social_engineering -> credential_theft -> financial_transaction -> post_attack -> initial_contact. This order is incomplete because one or more detected stages have acquisition time only.

> Chronology is provisional: acquisition time is an intake timestamp, not proof of when the underlying event occurred. Every fallback and unresolved value must be checked against the source exhibit.

| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 9 | 2 | 7 | 5 | 0 |

### Chronological Events

| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-08-02T00:00:00+00:00 | EVID_00035 | 06_police_complaint.pdf | content_date_only | medium | True | social_engineering, credential_theft, financial_transaction, post_attack |
| 2026-08-02T00:00:00+00:00 | EVID_00036 | 05_transactions.csv | content_date_only | medium | True | financial_transaction |
| 2026-08-02T08:55:31+00:00 | EVID_00037 | 04_kyc_phishing_email.txt | content_labeled_date_time | high | False | initial_contact, social_engineering, credential_theft, financial_transaction |
| 2026-08-02T15:18:00+00:00 | EVID_00038 | 03_khalti_receipt.jpg | content_date_time | high | False | financial_transaction |
| 2026-08-21T06:42:54.755000+00:00 | EVID_00034 | 07_fake_support_profile.jpg | upload_time_fallback | low | True | social_engineering, financial_transaction |
| 2026-08-21T06:43:07.959000+00:00 | EVID_00039 | 02_whatsapp_chat.jpg | upload_time_fallback | low | True | initial_contact, financial_transaction |
| 2026-08-21T06:43:11.546000+00:00 | EVID_00040 | 01_khalti_kyc_sms.jpg | upload_time_fallback | low | True | none |
| 2026-08-21T06:43:15.002000+00:00 | EVID_00041 | http_khalti-kyc-verify.top_login.url | upload_time_fallback | low | True | social_engineering, credential_theft, financial_transaction |
| 2026-08-21T06:43:15.097000+00:00 | EVID_00042 | https_esewa-bonus-claim.xyz_verify_ref_KYC2026.url | upload_time_fallback | low | True | social_engineering, financial_transaction |

### Stage Assessment

- **Keyword-derived order:** social_engineering, credential_theft, financial_transaction, post_attack, initial_contact
- **Order assessable:** False
- **Matches configured sequence:** False

### Critical Events

- **EVID_00035** at 2026-08-02T00:00:00+00:00 (content_date_only, medium, inferred=True): contains money entity/entities: NPR 10250, NPR 750, NPR 9500; contains khalti_ids entity/entities: +9779812345678; contains bank_accounts entity/entities: 01903015472901; contains transaction_ids entity/entities: KHL-2026-0802-44190
- **EVID_00036** at 2026-08-02T00:00:00+00:00 (content_date_only, medium, inferred=True): contains khalti_ids entity/entities: +9779812345678
- **EVID_00037** at 2026-08-02T08:55:31+00:00 (content_labeled_date_time, high, inferred=False): contains money entity/entities: NPR 750; contains khalti_ids entity/entities: +9779812345678; contains bank_accounts entity/entities: 01903015472901
- **EVID_00038** at 2026-08-02T15:18:00+00:00 (content_date_time, high, inferred=False): contains money entity/entities: NPR 750; contains transaction_ids entity/entities: KHL-2026-0802-44190
- **EVID_00034** at 2026-08-21T06:42:54.755000+00:00 (upload_time_fallback, low, inferred=True): contains khalti_ids entity/entities: +9779812345678
- **EVID_00039** at 2026-08-21T06:43:07.959000+00:00 (upload_time_fallback, low, inferred=True): contains money entity/entities: NPR 750; contains khalti_ids entity/entities: +9779812345678

## Correlation Analysis

20 of 36 analysed pairs met a configured relationship threshold.

Each factor below contributes points. The points sum to the pair's total weight, and the confidence is that total put through a saturating curve - so more corroborating factors raise confidence, but no single factor can carry a pair to certainty on its own.

| Evidence pair | Strength | Weight | Confidence | Contributing factors |
| --- | --- | --- | --- | --- |
| EVID_00035 <-> EVID_00037 | VERY_STRONG | 7.91 | 0.9929 | **Phones** (+0.51): +9779812345678 - but 1 of these are common across the corpus and were discounted<br>**Emails** (+0.59): reward.center2026@gmail.com<br>**Khalti Ids** (+0.78): +9779812345678<br>**Bank Accounts** (+0.90): 01903015472901<br>**Urls** (+1.35): http://khalti-kyc-verify.top/login, https://esewa-bonus-claim.xyz/verify?ref=kyc2026<br>**Domains** (+1.27): khalti-kyc-verify.top, esewa-bonus-claim.xyz, gmail.com - but 1 of these are common…<br>**Money** (+0.11): npr 750<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+2.40): Threat intelligence flags the same malicious indicators in both items:… |
| EVID_00034 <-> EVID_00035 | VERY_STRONG | 3.51 | 0.8887 | **Phones** (+0.51): +9779812345678 - but 1 of these are common across the corpus and were discounted<br>**Emails** (+0.59): reward.center2026@gmail.com<br>**Khalti Ids** (+0.78): +9779812345678<br>**Domains** (+0.83): khalti-kyc-verify.top, gmail.com - but 1 of these are common across the corpus and were…<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+0.80): Threat intelligence flags the same malicious indicator in both items:… |
| EVID_00034 <-> EVID_00037 | VERY_STRONG | 3.51 | 0.8887 | **Phones** (+0.51): +9779812345678 - but 1 of these are common across the corpus and were discounted<br>**Emails** (+0.59): reward.center2026@gmail.com<br>**Khalti Ids** (+0.78): +9779812345678<br>**Domains** (+0.83): khalti-kyc-verify.top, gmail.com - but 1 of these are common across the corpus and were…<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+0.80): Threat intelligence flags the same malicious indicator in both items:… |
| EVID_00035 <-> EVID_00041 | VERY_STRONG | 2.77 | 0.8235 | **Urls** (+0.68): http://khalti-kyc-verify.top/login<br>**Domains** (+0.50): khalti-kyc-verify.top<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+1.60): Threat intelligence flags the same malicious indicators in both items:… |
| EVID_00037 <-> EVID_00041 | VERY_STRONG | 2.77 | 0.8235 | **Urls** (+0.68): http://khalti-kyc-verify.top/login<br>**Domains** (+0.50): khalti-kyc-verify.top<br>**Timeline Proximity** (+0.00): Acquired 0.0 hours apart (within the 48h proximity window)<br>**Threat Intelligence** (+1.60): Threat intelligence flags the same malicious indicators in both items:… |

## Cross-Case Correlation

These are automated shared-entity associations and require independent corroboration.

| Other case | Strength | Confidence | Matched indicators | Basis |
| --- | --- | --- | --- | --- |
| CASE_0CD406813C | VERY_STRONG | 0.8238 | bank_accounts:01903015472901, domains:esewa-bonus-claim.xyz, emails:reward.center2026@gmail.com, phones:+9779812345678, domains:gmail.com | Shares 5 entity(ies) with CASE_0CD406813C: bank account 01903015472901, domain esewa-bonus-claim.xyz, email reward.center2026@gmail.com (+2 more) |
| CASE_EE8250FB76 | WEAK | 0.189 | domains:gmail.com | Shares 1 entity(ies) with CASE_EE8250FB76: domain gmail.com |
| CASE_185915593C | WEAK | 0.189 | domains:gmail.com | Shares 1 entity(ies) with CASE_185915593C: domain gmail.com |
| CASE_1A1BF573F3 | WEAK | 0.189 | domains:gmail.com | Shares 1 entity(ies) with CASE_1A1BF573F3: domain gmail.com |

## Campaign Analysis

Clusters are candidate groupings produced by configured thresholds; they do not by themselves establish coordination.

| Candidate cluster | Evidence | Confidence | Shared signature |
| --- | --- | --- | --- |
| CAMP_CASE_4B2A51A300_01 | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039, EVID_00041, EVID_00042 | 0.7428 | phones:+9779812345678, khalti_ids:+9779812345678, domains:gmail.com, domains:khalti-kyc-verify.top, emails:reward.center2026@gmail.com |

**Unclustered evidence:** EVID_00040

## Suspect Assessment

> Identity anchors are investigative leads, not legal attribution. Verify ownership and role using original exhibits and independent records.

| Identity lead | Score | Confidence | Risk | Supporting evidence |
| --- | --- | --- | --- | --- |
| khalti_ids:+9779812345678 | 84.9 | VERY_HIGH | CRITICAL | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00039 |
| emails:reward.center2026@gmail.com | 80.2 | VERY_HIGH | CRITICAL | EVID_00034, EVID_00035, EVID_00037, EVID_00039 |
| bank_accounts:01903015472901 | 79.9 | HIGH | HIGH | EVID_00035, EVID_00037 |
| phones:+9779812345678 | 79.3 | HIGH | HIGH | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039 |
| phones:+9779856770011 | 72.0 | HIGH | HIGH | EVID_00035, EVID_00038 |
| emails:bikash.thapa14@gmail.com | 61.2 | HIGH | HIGH | EVID_00037 |

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 5.0
- **malicious indicators**: 4.0
- **suspicious indicators**: 0.0
- **benign indicators**: 1.0
- **evidence with threats**: 5.0
- **threat evidence ratio**: 0.5556

## Model Prediction Results

- **indicators classified**: 3
- **flagged malicious**: 2
- **predictions**:
  - **indicator**: https://esewa-bonus-claim.xyz/verify?ref=KYC2026
  - **evidence id**: EVID_00035
  - **verdict**: malicious
  - **risk score**: 83
  - **confidence**: 0.83
  - **risk level**: Critical
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: esewa-bonus-claim.xyz
  - **trust score**: 20
  - **official domain**: False
  - **ssl status**: UNKNOWN
  - **spf present**: False
  - **dmarc present**: False
  - **reasons**:
    - The hybrid decision engine confirmed this URL is phishing based on agreement between the ML model and threat indicators.
    - AI model classified this URL as phishing with 100% confidence.
    - The top-level domain is frequently associated with phishing and spam campaigns (risk score: 0.7).
    - SSL status could not be verified.
    - The domain or URL has high character entropy, suggesting a randomly-generated string often used in phishing.
    - The URL contains suspicious keyword(s) associated with phishing.
  - **threat signals**:
    - ✗ Missing SPF record (facilitates email spoofing)
    - ✗ Missing DMARC record (facilitates email spoofing)
    - ✗ High-abuse top-level domain
    - ✗ High character entropy (suspicious random string)
    - ✗ Phishing-associated keyword(s) in URL
  - **indicator**: khalti-kyc-verify.top
  - **evidence id**: EVID_00034
  - **verdict**: malicious
  - **risk score**: 81
  - **confidence**: 0.81
  - **risk level**: Critical
  - **source**: ml:xgboost
  - **model version**: 4.0.0
  - **domain**: khalti-kyc-verify.top
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
  - **indicator**: gmail.com
  - **evidence id**: EVID_00034
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
  - **domain age days**: 11331
  - **registrar**: MarkMonitor, Inc.
  - **spf present**: True
  - **dmarc present**: True
  - **ssl days left**: 68
  - **hosting**: Google LLC, United States
  - **ip address**: 142.250.29.17
  - **reasons**:
    - The hybrid decision engine confirmed this URL is legitimate based on trusted signals and ML model agreement.
    - The URL does not use HTTPS, meaning data is transmitted without encryption.
  - **threat signals**:
    - ✗ Plain HTTP protocol used (unencrypted connections)
  - **trust signals**:
    - ✓ Official registered domain of trusted brand: google
    - ✓ Valid SSL certificate
    - ✓ HTTPS Strict-Transport-Security (HSTS) active
    - ✓ Established domain age (31.0 years old)
    - ✓ Registered with trusted registrar (MarkMonitor, Inc.)
    - ✓ SPF email authentication configured

## Evidence Quality Summary

- **mean image quality**: 65.2
- **mean evidence confidence**: 92.77
- **mean forgery score**: 20.23
- **max forgery score**: 26.0
- **mean ocr confidence**: 0.97
- **hash verified count**: 9.0
- **evidence with ocr result**: 9.0

## Metadata Summary

| Evidence | EXIF | Device | Software | Consistency notes |
| --- | --- | --- | --- | --- |
| EVID_00034 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00035 | False | none | none | none |
| EVID_00036 | False | none | none | none |
| EVID_00037 | False | none | none | none |
| EVID_00038 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00039 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00040 | False | none | none | Image carries no EXIF metadata (typical for screenshots and messaging-app exports; one less authenticity signal). |
| EVID_00041 | False | none | none | none |
| EVID_00042 | False | none | none | none |

## Investigation Statistics

- **entity statistics**:
  - **bank accounts**: 2
  - **dates**: 6
  - **domains**: 11
  - **emails**: 5
  - **khalti ids**: 5
  - **money**: 6
  - **phones**: 8
  - **times**: 2
  - **transaction ids**: 2
  - **urls**: 6
- **campaign statistics**:
  - **campaign count**: 1.0
  - **largest campaign size**: 8.0
  - **clustered evidence**: 8.0
  - **unclustered evidence**: 1.0
  - **mean campaign confidence**: 0.7428
- **timeline statistics**:
  - **event count**: 9.0
  - **resolved event count**: 9.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 7.0
  - **non inferred event count**: 2.0
  - **acquisition fallback count**: 5.0
  - **progression assessable**: 0.0
  - **stage count**: 5.0
  - **critical event count**: 6.0
  - **timeline span hours**: 462.72
  - **event time span hours**: 15.3
  - **acquisition inclusive span hours**: 462.72
- **correlation statistics**:
  - **pair count**: 36.0
  - **related pair count**: 20.0
  - **mean confidence**: 0.3631
  - **max confidence**: 0.9929

## Confidence Analysis

| Evidence | Score | Level | Computed explanation |
| --- | --- | --- | --- |
| EVID_00034 | 81.3 | VERY_HIGH | Evidence confidence is 81.3/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: image_quality (61/100). |
| EVID_00035 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00036 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00037 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00038 | 86.5 | VERY_HIGH | Evidence confidence is 86.5/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: image_quality (76/100). |
| EVID_00039 | 86.6 | VERY_HIGH | Evidence confidence is 86.6/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: forgery (78/100). |
| EVID_00040 | 80.5 | VERY_HIGH | Evidence confidence is 80.5/100 (VERY_HIGH), derived from 5 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: image_quality (45/100). |
| EVID_00041 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00042 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimensions. Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |

## Statement of Limitations

| # | Review boundary |
| --- | --- |
| 1 | This automated report organises submitted material and computed leads. It does not determine guilt or attribute an offence to a person. |
| 2 | OCR and entity extraction can omit, merge or misclassify text. Identifiers, amounts and names must be verified in the original exhibit before operational use. |
| 3 | Timeline quality: 7 inferred timestamp(s), including 5 acquisition-time fallback(s), and 0 unresolved timestamp(s). Date-only values use 00:00 UTC; fallbacks describe intake time rather than event time. |
| 4 | Correlation and cross-case scores measure shared features, not causation, common ownership or identity. |
| 5 | Campaign clusters and identity-anchor scores are prioritisation aids that require independent corroboration. |
| 6 | Threat-intelligence verdicts reflect the configured provider and its coverage at analysis time; no match does not prove safety. |
| 7 | New evidence or corrected extraction may change any finding in this report. |

## Investigation Conclusion

| # | Conclusion |
| --- | --- |
| 1 | 9/9 evidence items passed SHA-256 integrity verification; this establishes stored-file integrity, not the truth of its content. |
| 2 | The engine identified 20 weighted associations for manual corroboration; shared features alone do not prove that the items have a common actor or cause. |
| 3 | 1 candidate campaign cluster met the configured clustering criteria and requires investigator review before being treated as coordinated activity. |
| 4 | Validate the ownership and role of identity lead '+9779812345678' (85/100 model score; 5 supporting evidence items) against provider records and the original exhibits. |
| 5 | The keyword-derived stage order is provisional because one or more stage-bearing items lack a reliable event time. |

## Statutory Basis

The findings engage 7 provisions of the Electronic Transactions Act, 2063 (2008): s.52, s.47, s.45, s.53, s.54, s.55, s.56. Each is listed with the finding that engaged it and the evidence behind that finding.

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
| Evidence-based match | 3 payment identifiers (01903015472901, 9812345678 and KHL-2026-0802-44190) appear alongside 5 money values (NPR 10,250, NPR 750 and NPR 9,500) in the same case, evidencing a financial benefit moving through a payment rail. |
| Supporting evidence | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039 |

### Section 47 — Publication of illegal materials in electronic form

*Section 47, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Publishing or displaying material in electronic media, including on the internet, which is prohibited by prevailing law or is contrary to public morality or decent behaviour. |
| Penalty | fine not exceeding one hundred thousand Rupees or imprisonment not exceeding five years or both |
| Evidence-based match | threat intelligence flagged 4 indicators in this case; the evidence carries 5 web addresses (esewa-bonus-claim.xyz and gmail.com), i.e. material published in electronic form. |
| Supporting evidence | EVID_00034, EVID_00035, EVID_00037, EVID_00039, EVID_00041, EVID_00042 |

### Section 45 — Unauthorized Access in Computer Materials

*Section 45, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Accessing any programme, information or data of a computer without the authorisation of its owner, or beyond the scope of an authorisation held. |
| Penalty | fine not exceeding two hundred thousand Rupees or imprisonment not exceeding three years or both |
| Evidence-based match | credential material appears in 3 evidence items (login), indicating access to an account was sought or obtained. |
| Supporting evidence | EVID_00035, EVID_00037, EVID_00041 |

### Section 53 — Punishment to the person who abets to commit computer related offence

*Section 53, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Abetting another to commit an offence under the Act, or attempting or being involved in a conspiracy to commit one. |
| Penalty | fine not exceeding fifty thousand Rupees or imprisonment not exceeding six months or both, depending on the degree of the offence |
| Evidence-based match | campaign CAMP_CASE_4B2A51A300_01 groups 8 evidence items by shared indicators, which evidences coordinated activity rather than a single isolated act. |
| Supporting evidence | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039, EVID_00041, EVID_00042 |

### Section 54 — Punishment to the Accomplice

*Section 54, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Assisting another to commit an offence under the Act, or acting as an accomplice by any means. |
| Penalty | one half of the punishment for which the principal is liable |
| Evidence-based match | campaign CAMP_CASE_4B2A51A300_01 evidences coordination across 8 evidence items. Where more than one person acted, anyone who assisted is liable to one half of the principal's punishment. |
| Supporting evidence | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039, EVID_00041, EVID_00042 |

### Section 55 — Punishment in an offence committed outside Nepal

*Section 55, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | An offence under the Act involving a computer, computer system or network located in Nepal may be prosecuted even where the act was committed by a person residing outside Nepal. |
| Penalty | as for the underlying offence |
| Evidence-based match | this case shares identifiers with 4 other cases (CASE_0CD406813C, CASE_EE8250FB76 and CASE_185915593C). Where any part of the conduct occurred outside Nepal, the Act still applies to systems located in Nepal. |
| Supporting evidence | none |

### Section 56 — Confiscation

*Section 56, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Any computer, computer system, disk, software or accessory device used to commit an offence relating to computer under the Act is liable to confiscation. |
| Penalty | confiscation of the computer, computer system, disks, software or other accessory devices used |
| Evidence-based match | the findings engage 6 provisions of the Act (s.45, s.47, s.52 and 3 more). Any computer, device or storage medium used to commit those acts falls within the confiscation power and should be identified for seizure. |
| Supporting evidence | none |

### Evidentiary and regulatory follow-up

These entries are preservation or investigative actions, not findings that an institution violated a rule.

#### Legal recognition and preservation of electronic records

*Sections 4, 6, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Status | evidence_handling_requirement |
| Expectation | Where the law requires a record to be retained, an electronic record is recognised when it remains accessible, can be reproduced in its original format, and retains available origin, destination, date and time information. |
| Why relevant | This report relies on 9 electronic evidence items; preservation and reproducibility therefore remain material to later verification. |
| Recommended action | Retain the original files, acquisition metadata, SHA-256 values and chain-of-custody history. A file hash supports integrity checking but is not by itself a statutory digital signature under ETA sections 3 and 5. |
| Applicability | Applies where an electronic record is retained or relied on under the Electronic Transactions Act and prevailing law. |
| Supporting evidence | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039, EVID_00040, EVID_00041, EVID_00042 |

#### Preserve and correlate forensic logs

*Controls 83, 84, 85, 86, Nepal Rastra Bank Cyber Resilience Guidelines 2023*

| Field | Recorded value |
| --- | --- |
| Status | investigative_follow_up |
| Expectation | Detected events should be recorded with information such as event type, time and user or address; audit data should be protected, logs securely backed up, timestamps synchronised, and events centralised and correlated across relevant systems. |
| Why relevant | The case contains 3 payment identifiers across 6 evidence items; the corresponding institution-side records may establish transaction sequence, account activity, source address and timing. |
| Recommended action | Send a preservation request for transaction, authentication, application, system and network logs, including timezone and clock-synchronisation details, before normal retention or rotation removes them. |
| Applicability | Conditional: confirm that the affected organisation is an institution within the Guidelines' scope, including an A, B, C or D class BFI, Payment System Operator or Payment Service Provider licensed by NRB's Payment Systems Department. |
| Supporting evidence | EVID_00034, EVID_00035, EVID_00036, EVID_00037, EVID_00038, EVID_00039 |

#### Preserve authentication and MFA records

*Controls 71(d), Nepal Rastra Bank Cyber Resilience Guidelines 2023*

| Field | Recorded value |
| --- | --- |
| Status | investigative_follow_up |
| Expectation | Critical systems, processes and roles should require multi-factor authentication wherever supported, with enforced password-complexity requirements. |
| Why relevant | Credential or OTP material appears in 3 evidence items; authentication and account-change records are therefore relevant corroboration. |
| Recommended action | Request the relevant login, MFA challenge, OTP delivery, account-change and access-control records from the institution for the incident window. |
| Applicability | Conditional: confirm that the affected organisation is an institution within the Guidelines' scope, including an A, B, C or D class BFI, Payment System Operator or Payment Service Provider licensed by NRB's Payment Systems Department. |
| Supporting evidence | EVID_00035, EVID_00037, EVID_00041 |

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
| 1 | Issue preservation requests to the relevant hosting providers, then seek suspension of the suspected domains: esewa-bonus-claim.xyz,... |
| 2 | Request subscriber/KYC ownership and transaction history from Khalti for: +9779812345678. |
| 3 | Request account-holder identity and statements from the relevant bank for: 01903015472901. |
| 4 | Verify these extracted payment references against the source exhibits before including them in record requests: KHL-2026-0802-44190. |
| 5 | Ask the relevant provider to verify registration, ownership and transaction records for +9779812345678, reward.center2026@gmail.com; confirm each... |
| 6 | Review 8 items as a candidate cluster because they share a website; corroborate the link before combining incidents. |
| 7 | Review the 4 flagged events with the source exhibits; confirm each event's time, participants and any loss with the complainant. |
| 8 | Assign immediate queue priority (rated 78 out of 100). |

## Report Provenance & Integrity

- **report id**: RPT-4B2A51A300-D9B54C93
- **generated at**: 2026-08-21T17:57:23.075Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: d8dec30a40023fad96d3b9600c94b3fd9b02a80d2ecc9338b8e419b31060dc0e
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 16007a681f9a507e5c61edc5a0825d8954c988e009b91990abb9fe22513adabf
  - **cross case correlation.json**: 54d97936a476377e7bc4266be8a62e0fd8322e0a30ecaf0cd67e804b2d9ff35d
  - **campaign analysis.json**: ed06a4e2bceff33a1a9a7dcb8e43a6e613f66ecfd5c45a7e06fe78c4aaed02ce
  - **suspect assessment.json**: 8ef37f8c7d05c3e1439a15ade1e7e7346f7f801b273deb0735ba50dd0e418afd
  - **timeline analysis.json**: d2debe9e9fba2d63b6b34c0b0aa48f4123d4e8c81e95895e99ed3ec951984520
  - **analytics.json**: 7f0fb25289dad013b219457b6714023bf4af6fe286c19aac0d907b25645fc490
  - **case priority.json**: 68660c1a5cc81dec52ac6eb1e0db097ffa34184fcf9e2639e6d5d45400b05eb6
  - **graph.json**: 97184b7741ed19d39bfa7f14330eb1c85c2e9232883bc48979bb616d072ccfc9

## Appendix

- **chain of custody**:
  - **evidence id**: EVID_00034
  - **sha256**: 6d92c801ed6d05fa286c12f47ae02d132bead9fbdb9bff677ee09c9d75b9182f
  - **upload time**: 2026-08-21T06:42:54.755Z
  - **status**: processed
  - **evidence id**: EVID_00035
  - **sha256**: 1faf503b6bb893fe3af90c59467475a200c619c14640adef12710a7417cb1fca
  - **upload time**: 2026-08-21T06:43:01.064Z
  - **status**: processed
  - **evidence id**: EVID_00036
  - **sha256**: 6a007523d9087637c918cd46126302cc8a5173087004379c560c56299d68ddd0
  - **upload time**: 2026-08-21T06:43:01.325Z
  - **status**: processed
  - **evidence id**: EVID_00037
  - **sha256**: c7e51499cd6ed8d389ba79bb4c8f8cf2dc9b70d569f950826478969dd685ff8d
  - **upload time**: 2026-08-21T06:43:01.370Z
  - **status**: processed
  - **evidence id**: EVID_00038
  - **sha256**: 1257b4d56141a312458e7cb6d0150962bdd14c1c2a78fe36de7a8b58d0e472d1
  - **upload time**: 2026-08-21T06:43:01.434Z
  - **status**: processed
  - **evidence id**: EVID_00039
  - **sha256**: 4418cd74971cd5335563109352c019c8ddf261179ecac874392fe1474f74cc31
  - **upload time**: 2026-08-21T06:43:07.959Z
  - **status**: processed
  - **evidence id**: EVID_00040
  - **sha256**: 92e987df1a332874a7e5e78eee6b199d33a2cf9c68e657335adc33529cc7faae
  - **upload time**: 2026-08-21T06:43:11.546Z
  - **status**: processed
  - **evidence id**: EVID_00041
  - **sha256**: 2576cee0748325bb6eb525dcda7ed95b0115cac7336260f31149f15dd3e6e56a
  - **upload time**: 2026-08-21T06:43:15.002Z
  - **status**: processed
  - **evidence id**: EVID_00042
  - **sha256**: e419582edacddd1546d5d02c7f831ac5deacb68e5936be289619a9f2f4839f33
  - **upload time**: 2026-08-21T06:43:15.097Z
  - **status**: processed
- **stored artifacts root**: storage/investigation/<CASE_ID>/
- **phase1 artifacts root**: storage/forensics/<EVIDENCE_ID>/
