# Forensic Investigation Report - CASE_2CF24DBA5F

Generated: 2026-08-20T14:46:35.294Z  
Produced by: Cybercrime Investigation Intelligence Engine (CIIS), Phase 2  
Status: Automated analytical draft - investigator review required  
Basis: every statement below references stored forensic findings; accuracy depends on the source evidence and upstream extraction.

## Executive Summary

| # | Finding |
| --- | --- |
| 1 | Case CASE_2CF24DBA5F contains 4 evidence items; 4/4 passed the stored SHA-256 integrity check. |
| 2 | The weighted correlation engine found 0 related evidence pairs out of 6 analysed [correlation_analysis.json]. |
| 3 | Chronology contains 1 evidence-derived event time (0 inferred), 3 acquisition-only records and 0 unresolved records [timeline_analysis.json]. |
| 4 | Attack stages were detected, but no evidence-derived event times were available to order them [timeline_analysis.json]. |

## Scope & Methodology

| Scope | Recorded basis |
| --- | --- |
| Objective | Acquire, verify, correlate and reconstruct the digital evidence for this case, and derive investigative leads (identity anchors, candidate clusters and cross-case links) from stored artifacts while preserving each item's recorded integrity status. |
| Evidence scope | 4 evidence items acquired through the CIIS intake pipeline with a recorded SHA-256 digest. |
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
| Case Id | CASE_2CF24DBA5F |
| Evidence Count | 4 |
| First Evidence | 2026-07-25T12:50:00.695Z |
| Last Evidence | 2026-07-25T12:53:47.011Z |
| File Types | jpg, png, txt |

## Evidence Summary

| Evidence | File | Acquired | OCR confidence | Entities | Integrity |
| --- | --- | --- | --- | --- | --- |
| EVID_00001 | yeti.jpg | 2026-07-25T12:50:00.695Z | 1.0 | 5 | VERIFIED |
| EVID_00002 | whatsapp_chat_export.txt | 2026-07-25T12:53:07.182Z | 1.0 | 2 | VERIFIED |
| EVID_00003 | romanchat.jpg | 2026-07-25T12:53:23.174Z | 0.9859 | 0 | VERIFIED |
| EVID_00004 | phishing_email_screenshot.png | 2026-07-25T12:53:47.011Z | 0.9014 | 0 | VERIFIED |

## Timeline Analysis

4 events; 4 timestamps resolved (1 non-inferred, 3 inferred, including 3 acquisition-time fallbacks); 0 timestamps unresolved. Attack stages were detected, but no evidence-derived event times were available to order them.

> Chronology is provisional: acquisition time is an intake timestamp, not proof of when the underlying event occurred. Every fallback and unresolved value must be checked against the source exhibit.

| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 1 | 3 | 3 | 0 |

### Chronological Events

| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-01-04T09:12:00+00:00 | EVID_00001 | yeti.jpg | content_date_time | high | False | none |
| 2026-07-25T12:53:07.182000+00:00 | EVID_00002 | whatsapp_chat_export.txt | upload_time_fallback | low | True | financial_transaction, post_attack |
| 2026-07-25T12:53:23.174000+00:00 | EVID_00003 | romanchat.jpg | upload_time_fallback | low | True | initial_contact, social_engineering, credential_theft, financial_transaction |
| 2026-07-25T12:53:47.011000+00:00 | EVID_00004 | phishing_email_screenshot.png | upload_time_fallback | low | True | none |

### Stage Assessment

- **Keyword-derived order:** none
- **Order assessable:** False
- **Matches configured sequence:** True

### Critical Events

- **EVID_00001** at 2026-01-04T09:12:00+00:00 (content_date_time, high, inferred=False): contains money entity/entities: NPR 2000
- **EVID_00002** at 2026-07-25T12:53:07.182000+00:00 (upload_time_fallback, low, inferred=True): contains money entity/entities: NPR 2000, NPR 500000

## Correlation Analysis

0 of 6 analysed pairs met a configured relationship threshold.

| Evidence pair | Strength | Confidence | Computed basis |
| --- | --- | --- | --- |
| none | none | none | none |

## Cross-Case Correlation

No cross-case correlations were found for this case.

## Campaign Analysis

Clusters are candidate groupings produced by configured thresholds; they do not by themselves establish coordination.

| Candidate cluster | Evidence | Confidence | Shared signature |
| --- | --- | --- | --- |
| none | none | none | none |

**Unclustered evidence:** EVID_00001, EVID_00002, EVID_00003, EVID_00004

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
- **mean evidence confidence**: 0.0
- **mean forgery score**: 0.0
- **max forgery score**: 0.0
- **mean ocr confidence**: 0.97
- **hash verified count**: 4.0

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
  - **unclustered evidence**: 4.0
  - **mean campaign confidence**: 0.0
- **timeline statistics**:
  - **event count**: 4.0
  - **resolved event count**: 4.0
  - **unresolved event count**: 0.0
  - **inferred event count**: 3.0
  - **non inferred event count**: 1.0
  - **acquisition fallback count**: 3.0
  - **progression assessable**: 0.0
  - **stage count**: 5.0
  - **critical event count**: 2.0
  - **timeline span hours**: 4851.7
  - **event time span hours**: 0.0
  - **acquisition inclusive span hours**: 4851.7
- **correlation statistics**:
  - **pair count**: 6.0
  - **related pair count**: 0.0
  - **mean confidence**: 0.0071
  - **max confidence**: 0.0428

## Confidence Analysis

- **note**: No Phase-1 confidence scores stored for this case.

## Statement of Limitations

| # | Review boundary |
| --- | --- |
| 1 | This automated report organises submitted material and computed leads. It does not determine guilt or attribute an offence to a person. |
| 2 | OCR and entity extraction can omit, merge or misclassify text. Identifiers, amounts and names must be verified in the original exhibit before operational use. |
| 3 | Timeline quality: 3 inferred timestamp(s), including 3 acquisition-time fallback(s), and 0 unresolved timestamp(s). Date-only values use 00:00 UTC; fallbacks describe intake time rather than event time. |
| 4 | Correlation and cross-case scores measure shared features, not causation, common ownership or identity. |
| 5 | Campaign clusters and identity-anchor scores are prioritisation aids that require independent corroboration. |
| 6 | Threat-intelligence verdicts reflect the configured provider and its coverage at analysis time; no match does not prove safety. |
| 7 | New evidence or corrected extraction may change any finding in this report. |

## Investigation Conclusion

| # | Conclusion |
| --- | --- |
| 1 | 4/4 evidence items passed SHA-256 integrity verification; this establishes stored-file integrity, not the truth of its content. |
| 2 | The keyword-derived stage order is provisional because one or more stage-bearing items lack a reliable event time. |

## Statutory Basis

The findings engage 2 provisions of the Electronic Transactions Act, 2063 (2008): s.45, s.56. Each is listed with the finding that engaged it and the evidence behind that finding.

**Statute:** Electronic Transactions Act, 2063 (2008)  
**ऐन:** विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३  
**Jurisdiction:** Nepal

*Cited from the English text of the Act. The Nepali text is authoritative where the two differ; verify any provision against विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३ before relying on it in a filing.*

### Section 45 — Unauthorized Access in Computer Materials

*Section 45, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Accessing any programme, information or data of a computer without the authorisation of its owner, or beyond the scope of an authorisation held. |
| Penalty | fine not exceeding two hundred thousand Rupees or imprisonment not exceeding three years or both |
| Evidence-based match | credential material appears in 1 evidence item (login), indicating access to an account was sought or obtained. |
| Supporting evidence | EVID_00003 |

### Section 56 — Confiscation

*Section 56, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Conduct | Any computer, computer system, disk, software or accessory device used to commit an offence relating to computer under the Act is liable to confiscation. |
| Penalty | confiscation of the computer, computer system, disks, software or other accessory devices used |
| Evidence-based match | the findings engage 1 provision of the Act (s.45). Any computer, device or storage medium used to commit those acts falls within the confiscation power and should be identified for seizure. |
| Supporting evidence | none |

### Evidentiary and regulatory follow-up

These entries are preservation or investigative actions, not findings that an institution violated a rule.

#### Legal recognition and preservation of electronic records

*Sections 4, 6, Electronic Transactions Act, 2063 (2008)*

| Field | Recorded value |
| --- | --- |
| Status | evidence_handling_requirement |
| Expectation | Where the law requires a record to be retained, an electronic record is recognised when it remains accessible, can be reproduced in its original format, and retains available origin, destination, date and time information. |
| Why relevant | This report relies on 4 electronic evidence items; preservation and reproducibility therefore remain material to later verification. |
| Recommended action | Retain the original files, acquisition metadata, SHA-256 values and chain-of-custody history. A file hash supports integrity checking but is not by itself a statutory digital signature under ETA sections 3 and 5. |
| Applicability | Applies where an electronic record is retained or relied on under the Electronic Transactions Act and prevailing law. |
| Supporting evidence | EVID_00001, EVID_00002, EVID_00003, EVID_00004 |

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

> This is an automated mapping from technical findings to statutory provisions, provided to assist the investigating officer. It is not legal advice and not a charging decision. A provision is listed because the evidence contains the features described, not because an offence has been proved: intent, authorisation and identity are matters for investigation. Provisions of the Act not listed here were not assessed.


## Recommendations

| # | Investigator action |
| --- | --- |
| 1 | Review the 1 flagged event with the source exhibits; confirm each event's time, participants and any loss with the complainant. |
| 2 | Assign low queue priority (rated 13 out of 100). |

## Report Provenance & Integrity

- **report id**: RPT-2CF24DBA5F-8B9EB33D
- **generated at**: 2026-08-20T14:46:35.291Z
- **generator**: CIIS Phase-2 reporting module (template-over-data; no free-text generation)
- **evidence set digest**: 845d2580a93c7505d88a3b735dd3a956db233d26f779d05f4a85f60abfe82c3f
- **evidence set digest note**: SHA-256 over the sorted SHA-256 digests of every evidence item; any change to the evidence set changes this value.
- **source artifact hashes**:
  - **correlation analysis.json**: 1228831a1611726fbd5e664ef884147673b9d872321c6659d5ff5df1f9b81288
  - **cross case correlation.json**: 6c4b7e022465546d0555c8cb462748c5b6c81a0b9a0b5bdb505f7587bf91bc63
  - **campaign analysis.json**: 56cdaeb9dc918d3c956f9da9b7a3f6f920d903a5f5d4b684b0e3f6c453209e71
  - **suspect assessment.json**: 8d3e382d3c8de17e9bafae0f9eb52336ac5cdcaf2c402e4af138d39c4f266aef
  - **timeline analysis.json**: 6fe056bdd864349e606328ea6e8f74afdf3fe53e7a6f6cd536111cb3b7b9f5a8
  - **analytics.json**: 907115a71cbdea9527d44df68b5ba22c8379359d7706d969f121a85fdd5824b9
  - **case priority.json**: f6411fad6eac0b4f62523803791f11143ffb11e4af5fa9e796988fb7e740141c
  - **graph.json**: 20a6b700f5d7d2a3e790e65c3a51eb5be164baef6e3510368db288b7dec81610

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
