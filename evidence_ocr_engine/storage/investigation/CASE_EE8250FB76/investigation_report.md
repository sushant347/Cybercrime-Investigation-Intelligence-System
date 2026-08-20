# Forensic Investigation Report - CASE_EE8250FB76

Generated: 2026-08-20T14:37:37.406Z  
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
| 5 | Chronology contains 1 evidence-derived event time (1 inferred), 1 acquisition-only record and 0 unresolved records [timeline_analysis.json]. |
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

2 events; 2 timestamps resolved (0 non-inferred, 2 inferred, including 1 acquisition-time fallback); 0 timestamps unresolved. Keyword-derived stage order: initial_contact -> social_engineering -> financial_transaction -> post_attack.

> Chronology is provisional: acquisition time is an intake timestamp, not proof of when the underlying event occurred. Every fallback and unresolved value must be checked against the source exhibit.

| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 0 | 2 | 1 | 0 |

### Chronological Events

| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-06-15T00:00:00+00:00 | EVID_00005 | 08_complaint_letter.pdf | content_labeled_date_only | medium | True | initial_contact, social_engineering, financial_transaction, post_attack |
| 2026-07-25T16:24:18.091000+00:00 | EVID_00006 | 07_bank_transfer_slip.pdf | upload_time_fallback | low | True | none |

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
  - **evidence id**: EVID_00005
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
  - **evidence id**: EVID_00005
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

- **mean image quality**: 0.0
- **mean evidence confidence**: 100.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.5
- **hash verified count**: 1.0

## Metadata Summary

| Evidence | EXIF | Device | Software | Consistency notes |
| --- | --- | --- | --- | --- |
| EVID_00005 | False | none | none | none |

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
  - **inferred event count**: 2.0
  - **non inferred event count**: 0.0
  - **acquisition fallback count**: 1.0
  - **progression assessable**: 1.0
  - **stage count**: 4.0
  - **critical event count**: 1.0
  - **timeline span hours**: 976.41
  - **event time span hours**: 0.0
  - **acquisition inclusive span hours**: 976.41
- **correlation statistics**:
  - **pair count**: 1.0
  - **related pair count**: 0.0
  - **mean confidence**: 0.0
  - **max confidence**: 0.0

## Confidence Analysis

| Evidence | Score | Level | Computed explanation |
| --- | --- | --- | --- |
| EVID_00005 | 100.0 | VERY_HIGH | Evidence confidence is 100.0/100 (VERY_HIGH), derived from 3 verified dimension(s). Strongest signal: hash_verification (100/100). Weakest signal: metadata (100/100). |

## Statement of Limitations

| # | Review boundary |
| --- | --- |
| 1 | This automated report organises submitted material and computed leads. It does not determine guilt or attribute an offence to a person. |
| 2 | OCR and entity extraction can omit, merge or misclassify text. Identifiers, amounts and names must be verified in the original exhibit before operational use. |
| 3 | Timeline quality: 2 inferred timestamp(s), including 1 acquisition-time fallback(s), and 0 unresolved timestamp(s). Date-only values use 00:00 UTC; fallbacks describe intake time rather than event time. |
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
| 2 | Notify eSewa of suspected brand impersonation and request preservation of any related abuse records. |
| 3 | Request subscriber/KYC ownership and transaction history from eSewa for: sunita.gurung21@gmail.com, esewa.cashback99@gmail.com. |
| 4 | Request subscriber/KYC ownership and transaction history from Khalti for: +9779801122334. |
| 5 | Request account-holder identity and statements from the relevant bank for: 05019012345678. |
| 6 | Verify these extracted payment references against the source exhibits before including them in record requests: 0119.0625.987456,... |
| 7 | Ask the relevant provider to verify registration, ownership and transaction records for 05019012345678, esewa.cashback99@gmail.com; confirm each... |
| 8 | Review the 1 flagged event with the source exhibits; confirm each event's time, participants and any loss with the complainant. |
| 9 | Assign standard queue priority (rated 35 out of 100). |

## Report Provenance & Integrity

- **report id**: RPT-EE8250FB76-79999E09
- **generated at**: 2026-08-20T14:37:37.398Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 0f6afe626b2e5e1c4bb70b2efae2d8aea52ca3d8d38b481532cc8e4ff88c3ff6
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 2992fd26e4f31a525ba1ed0a8ee36360b760fb0b62c184322686e34968db573a
  - **cross case correlation.json**: eb69d4047d8579e0bc5f6954ea3d2fb83b3f633333637e84c7f0eefd53b6e690
  - **campaign analysis.json**: 05bf323ee75d1b82d4d7c144c1a3344c4d9c86e9a1f937a366bd12f96234ac40
  - **suspect assessment.json**: 3325cadf2262580a12a901fd38e41ad8e08324625ed24cf5b8b72d6303a2ad00
  - **timeline analysis.json**: 494c34b2438e269a435c4cba35b4c3611ef0cabe7c48a1c9edcafd24dc13ffd9
  - **analytics.json**: 7e0e538463e6f4f3b0faec53ab089adf5c1977ef82423be462e8616678069169
  - **case priority.json**: ed8109c5c1107cd3ac2b8bb056f09c39bc7ca8f55c5a4439ceab27c996dc5687
  - **graph.json**: 54af2b5455a0fa4dda4e19f4e7bc1fafc6477e03403cd127a5c9c46d4088dae9

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
