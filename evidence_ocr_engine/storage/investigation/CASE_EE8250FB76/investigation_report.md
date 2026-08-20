# Forensic Investigation Report - CASE_EE8250FB76

Generated: 2026-08-20T18:18:43.931Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Status: Automated analytical draft - investigator review required  
Basis: every statement below references stored forensic findings; accuracy depends on the source evidence and upstream extraction.

## Executive Summary

| # | Finding |
| --- | --- |
| 1 | Case CASE_EE8250FB76 contains 2 evidence items; 1/2 passed the stored SHA-256 integrity check. |
| 2 | This case was automatically linked to 2 other cases; these are candidate shared-entity associations: CASE_185915593C, CASE_1A1BF573F3 [cross_case_correlation.json]. |
| 3 | The weighted correlation engine found 0 related evidence pairs out of 1 analysed [correlation_analysis.json]. |
| 4 | The highest-scoring identity lead is '05019012345678' (bank_accounts), supported by 1 evidence item and scored 68/100; this is a lead, not identity attribution [suspect_assessment.json]. |
| 5 | Chronology contains 2 evidence-derived event times (1 inferred), 0 acquisition-only records and 0 unresolved records [timeline_analysis.json]. |
| 6 | Evidence-timed stage order: initial_contact -> social_engineering -> financial_transaction -> post_attack [timeline_analysis.json]. |

## Scope & Methodology

| Scope | Recorded basis |
| --- | --- |
| Objective | Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (identity anchors, candidate clusters and cross-case links) from stored artifacts while preserving each item's recorded integrity status. |
| Evidence scope | 2 evidence items acquired through the CIIS intake pipeline with a recorded SHA-256 digest. |
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
| Case Id | CASE_EE8250FB76 |
| Evidence Count | 2 |
| First Evidence | 2026-07-25T16:24:17.560Z |
| Last Evidence | 2026-07-25T16:24:18.091Z |
| File Types | pdf |

## Evidence Summary

| Evidence | File | Acquired | OCR confidence | Entities | Integrity |
| --- | --- | --- | --- | --- | --- |
| EVID_00005 | 08_complaint_letter.pdf | 2026-07-25T16:24:17.560Z | 1.0 | 25 | VERIFIED |
| EVID_00006 | 07_bank_transfer_slip.pdf | 2026-07-25T16:24:18.091Z | 0.0 | 0 | FAILED |

## Timeline Analysis

2 events; 2 timestamps resolved (1 non-inferred, 1 inferred, including 0 acquisition-time fallbacks); 0 timestamps unresolved. Content/metadata event times span 972.1 hours. Keyword-derived stage order: initial_contact -> social_engineering -> financial_transaction -> post_attack.

> Chronology includes inferred values. Date-only values are normalised to 00:00 UTC and do not establish an exact time.

| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 1 | 1 | 0 | 0 |

### Chronological Events

| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-06-15T00:00:00+00:00 | EVID_00005 | 08_complaint_letter.pdf | content_labeled_date_only | medium | True | initial_contact, social_engineering, financial_transaction, post_attack |
| 2026-07-25T12:06:25+00:00 | EVID_00006 | 07_bank_transfer_slip.pdf | metadata_pdf_created | medium | False | none |

### Stage Assessment

- **Keyword-derived order:** initial_contact, social_engineering, financial_transaction, post_attack
- **Order assessable:** True
- **Matches configured sequence:** True

### Critical Events

- **EVID_00005** at 2026-06-15T00:00:00+00:00 (content_labeled_date_only, medium, inferred=True): contains money entity/entities: NPR 1500, NPR 200, NPR 25000; contains esewa_ids entity/entities: esewa.cashback99@gmail.com, sunita.gurung21@gmail.com; contains khalti_ids entity/entities: +9779801122334; contains bank_accounts entity/entities: 05019012345678; contains transaction_ids entity/entities: 0119.0625.987456, CASE_2026_0088, KH-2026-0611-77245

## Correlation Analysis

0 of 1 analysed pairs met a configured relationship threshold.

| Evidence pair | Strength | Confidence | Computed basis |
| --- | --- | --- | --- |
| none | none | none | none |

## Cross-Case Correlation

These are automated shared-entity associations and require independent corroboration.

| Other case | Strength | Confidence | Matched indicators | Basis |
| --- | --- | --- | --- | --- |
| CASE_185915593C | VERY_STRONG | 0.9992 | bank_accounts:05019012345678, domains:esewa-verify-kyc.com, emails:esewa.cashback99@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, +16 more | Shares 21 entity(ies) with CASE_185915593C: bank account 05019012345678, domain esewa-verify-kyc.com, email esewa.cashback99@gmail.com (+18 more). 17 of these are distinctive;… |
| CASE_1A1BF573F3 | VERY_STRONG | 0.9992 | bank_accounts:05019012345678, domains:esewa-verify-kyc.com, emails:esewa.cashback99@gmail.com, emails:support@esewa-verify-kyc.com, esewa_ids:esewa.cashback99@gmail.com, +16 more | Shares 21 entity(ies) with CASE_1A1BF573F3: bank account 05019012345678, domain esewa-verify-kyc.com, email esewa.cashback99@gmail.com (+18 more). 17 of these are distinctive;… |

## Campaign Analysis

Clusters are candidate groupings produced by configured thresholds; they do not by themselves establish coordination.

| Candidate cluster | Evidence | Confidence | Shared signature |
| --- | --- | --- | --- |
| none | none | none | none |

**Unclustered evidence:** EVID_00005, EVID_00006

## Suspect Assessment

> Identity anchors are investigative leads, not legal attribution. Verify ownership and role using original exhibits and independent records.

| Identity lead | Score | Confidence | Risk | Supporting evidence |
| --- | --- | --- | --- | --- |
| bank_accounts:05019012345678 | 67.5 | HIGH | HIGH | EVID_00005 |
| esewa_ids:esewa.cashback99@gmail.com | 67.5 | HIGH | HIGH | EVID_00005 |
| esewa_ids:sunita.gurung21@gmail.com | 67.5 | HIGH | HIGH | EVID_00005 |
| khalti_ids:+9779801122334 | 67.5 | HIGH | HIGH | EVID_00005 |
| phones:+9779801122334 | 63.8 | HIGH | HIGH | EVID_00005 |
| phones:+9779847011223 | 63.8 | HIGH | HIGH | EVID_00005 |
| emails:esewa.cashback99@gmail.com | 61.2 | HIGH | HIGH | EVID_00005 |
| emails:sunita.gurung21@gmail.com | 61.2 | HIGH | HIGH | EVID_00005 |
| emails:support@esewa-verify-kyc.com | 61.2 | HIGH | HIGH | EVID_00005 |

## Threat Intelligence Summary

- **intel available**: 1.0
- **indicators checked**: 4.0
- **malicious indicators**: 3.0
- **suspicious indicators**: 0.0
- **benign indicators**: 1.0
- **evidence with threats**: 1.0
- **threat evidence ratio**: 0.5

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
  - **domain age days**: 11330
  - **registrar**: MarkMonitor, Inc.
  - **spf present**: True
  - **dmarc present**: True
  - **ssl days left**: 69
  - **hosting**: Google LLC, India
  - **ip address**: 142.250.182.101
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

- **mean image quality**: 0.0
- **mean evidence confidence**: 75.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.5
- **hash verified count**: 1.0

## Metadata Summary

| Evidence | EXIF | Device | Software | Consistency notes |
| --- | --- | --- | --- | --- |
| EVID_00005 | False | none | none | none |
| EVID_00006 | False | none | none | none |

## Investigation Statistics

- **entity statistics**:
  - **bank accounts**: 1
  - **dates**: 4
  - **domains**: 3
  - **emails**: 3
  - **esewa ids**: 2
  - **khalti ids**: 1
  - **money**: 4
  - **phones**: 2
  - **transaction ids**: 4
  - **urls**: 1
- **campaign statistics**:
  - **campaign count**: 0.0
  - **largest campaign size**: 0.0
  - **clustered evidence**: 0.0
  - **unclustered evidence**: 2.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 2.0
  - **resolved event count**: 2.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 1.0
  - **non inferred event count**: 1.0
  - **acquisition fallback count**: 0.0
  - **progression assessable**: 1.0
  - **stage count**: 4.0
  - **critical event count**: 1.0
  - **timeline span hours**: 972.11
  - **event time span hours**: 972.11
  - **acquisition inclusive span hours**: 972.11
- **correlation statistics**:
  - **pair count**: 1.0
  - **related pair count**: 0.0
  - **mean confidence**: 0.0
  - **max confidence**: 0.0

## Confidence Analysis

| Evidence | Score | Level | Computed explanation |
| --- | --- | --- | --- |
| EVID_00005 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |
| EVID_00006 | 50.0 | MODERATE | Evidence confidence is 50.0/100 (MODERATE), derived from 3 verified dimensions. Strongest signal: metadata (100/100). Weakest signal: hash_verification (0/100). |

## Statement of Limitations

| # | Review boundary |
| --- | --- |
| 1 | This automated report organises submitted material and computed leads. It does not determine guilt or attribute an offence to a person. |
| 2 | OCR and entity extraction can omit, merge or misclassify text. Identifiers, amounts and names must be verified in the original exhibit before operational use. |
| 3 | Timeline quality: 1 inferred timestamp(s), including 0 acquisition-time fallback(s), and 0 unresolved timestamp(s). Date-only values use 00:00 UTC; fallbacks describe intake time rather than event time. |
| 4 | Correlation and cross-case scores measure shared features, not causation, common ownership or identity. |
| 5 | Campaign clusters and identity-anchor scores are prioritisation aids that require independent corroboration. |
| 6 | Threat-intelligence verdicts reflect the configured provider and its coverage at analysis time; no match does not prove safety. |
| 7 | New evidence or corrected extraction may change any finding in this report. |

## Investigation Conclusion

| # | Conclusion |
| --- | --- |
| 1 | 1/2 evidence items passed SHA-256 integrity verification; this establishes stored-file integrity, not the truth of its content. |
| 2 | Validate the ownership and role of identity lead '05019012345678' (68/100 model score; 1 supporting evidence item) against provider records and the original exhibits. |

## Statutory Basis

The findings engage 4 provisions of the Electronic Transactions Act, 2063 (2008): s.52, s.47, s.55, s.56. Each is listed with the finding that engaged it and the evidence behind that finding.

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
| Evidence-based match | 8 payment identifiers (0119.0625.987456, 0501-9012345678 and 9801122334) appear alongside 4 money values (NPR 1,500, NPR 200 and NPR 25,000) in the same case, evidencing a financial benefit moving through a payment rail. |
| Supporting evidence | EVID_00005 |

### Section 47 — Publication of illegal materials in electronic form

*Section 47, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Publishing or displaying material in electronic media, including on the internet, which is prohibited by prevailing law or is contrary to public morality or decent behaviour. |
| Penalty | fine not exceeding one hundred thousand Rupees or imprisonment not exceeding five years or both |
| Evidence-based match | threat intelligence flagged 3 indicators in this case; the evidence carries 4 web addresses (esewa-cashback-offer.xyz and esewa-verify-kyc.com), i.e. material published in electronic form. |
| Supporting evidence | EVID_00005 |

### Section 55 — Punishment in an offence committed outside Nepal

*Section 55, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | An offence under the Act involving a computer, computer system or network located in Nepal may be prosecuted even where the act was committed by a person residing outside Nepal. |
| Penalty | as for the underlying offence |
| Evidence-based match | this case shares identifiers with 2 other cases (CASE_185915593C and CASE_1A1BF573F3). Where any part of the conduct occurred outside Nepal, the Act still applies to systems located in Nepal. |
| Supporting evidence | none |

### Section 56 — Confiscation

*Section 56, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Any computer, computer system, disk, software or accessory device used to commit an offence relating to computer under the Act is liable to confiscation. |
| Penalty | confiscation of the computer, computer system, disks, software or other accessory devices used |
| Evidence-based match | the findings engage 3 provisions of the Act (s.47, s.52 and s.55). Any computer, device or storage medium used to commit those acts falls within the confiscation power and should be identified for seizure. |
| Supporting evidence | none |

### Evidentiary and regulatory follow-up

These entries are preservation or investigative actions, not findings that an institution violated a rule.

#### Legal recognition and preservation of electronic records

*Sections 4, 6, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Status | evidence_handling_requirement |
| Expectation | Where the law requires a record to be retained, an electronic record is recognised when it remains accessible, can be reproduced in its original format, and retains available origin, destination, date and time information. |
| Why relevant | This report relies on 2 electronic evidence items; preservation and reproducibility therefore remain material to later verification. |
| Recommended action | Retain the original files, acquisition metadata, SHA-256 values and chain-of-custody history. A file hash supports integrity checking but is not by itself a statutory digital signature under ETA sections 3 and 5. |
| Applicability | Applies where an electronic record is retained or relied on under the Electronic Transactions Act and prevailing law. |
| Supporting evidence | EVID_00005, EVID_00006 |

#### Preserve and correlate forensic logs

*Controls 83, 84, 85, 86, Nepal Rastra Bank Cyber Resilience Guidelines 2023*

| Field | Recorded value |
| --- | --- |
| Status | investigative_follow_up |
| Expectation | Detected events should be recorded with information such as event type, time and user or address; audit data should be protected, logs securely backed up, timestamps synchronised, and events centralised and correlated across relevant systems. |
| Why relevant | The case contains 8 payment identifiers across 1 evidence item; the corresponding institution-side records may establish transaction sequence, account activity, source address and timing. |
| Recommended action | Send a preservation request for transaction, authentication, application, system and network logs, including timezone and clock-synchronisation details, before normal retention or rotation removes them. |
| Applicability | Conditional: confirm that the affected organisation is an institution within the Guidelines' scope, including an A, B, C or D class BFI, Payment System Operator or Payment Service Provider licensed by NRB's Payment Systems Department. |
| Supporting evidence | EVID_00005 |

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
| 2 | Request subscriber/KYC ownership and transaction history from eSewa for: sunita.gurung21@gmail.com, esewa.cashback99@gmail.com. |
| 3 | Request subscriber/KYC ownership and transaction history from Khalti for: +9779801122334. |
| 4 | Request account-holder identity and statements from the relevant bank for: 05019012345678. |
| 5 | Verify these extracted payment references against the source exhibits before including them in record requests: 0119.0625.987456,... |
| 6 | Ask the relevant provider to verify registration, ownership and transaction records for 05019012345678, esewa.cashback99@gmail.com; confirm each... |
| 7 | Review the 1 flagged event with the source exhibits; confirm each event's time, participants and any loss with the complainant. |
| 8 | Assign standard queue priority (rated 30 out of 100). |

## Report Provenance & Integrity

- **report id**: RPT-EE8250FB76-A2A93F5D
- **generated at**: 2026-08-20T18:18:43.924Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 0f6afe626b2e5e1c4bb70b2efae2d8aea52ca3d8d38b481532cc8e4ff88c3ff6
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 36a1e8076239dadc5dccf24f9c288b6ef790ab74a4adf4ae8bab86b8bfca0769
  - **cross case correlation.json**: eb69d4047d8579e0bc5f6954ea3d2fb83b3f633333637e84c7f0eefd53b6e690
  - **campaign analysis.json**: 5b7123b106467ea7d40b19ae8f109c6797d62e8b0a156add5b88690ad4fd08a9
  - **suspect assessment.json**: e5b46de171df226df405aad4692db8e8b6509895fdc3894b499aa0318d095e79
  - **timeline analysis.json**: 12ed6415569cbb4f900bc3187491af56d12f843ccbd3d653db36bc934d14d2b7
  - **analytics.json**: ad3b6fd16e8f0e16613f0b79bb74ec9102194cdc60de6ec1127fd781ae6653ea
  - **case priority.json**: c78ccb54ba2adb1ac4743dfe1837c2ffaa45e109968a869bf3dcb49b7e165dca
  - **graph.json**: 062155fdc06d92349b8ed39219e93fa5497076cd5330a0466d6d743633835a91

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
