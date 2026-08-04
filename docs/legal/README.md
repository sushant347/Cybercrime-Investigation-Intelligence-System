# Legal and regulatory corpus

Source material for the statutory-basis module
(`timeline_report_engine/ciis_timeline_report/legal/`). These are public
instruments of Nepali law and policy, kept in the repository so that every
provision the engine cites can be checked against the text it was transcribed
from, rather than taken on trust.

## What the engine actually uses

Only one document is transcribed into code today:

| Document | Used for |
|---|---|
| `2.1 The Electronic Transactions Act, 2063 (2008).pdf` | Sections 45, 47, 52, 53, 55 — the offences the engine maps findings to |

`provisions.py` holds the section number, the heading as enacted, and the
penalty as written. Nothing is paraphrased into a different figure. The
*trigger* — when the engine considers a finding to engage a provision — is
recorded separately and is editorial, not statutory.

## The rest

Held as reference for work not yet done. Listing them is not a claim that the
engine implements them:

- `2.1 Electronic Transactions Rules 2064 (2007)` and the Nepali originals of
  the Act and Rules — the subordinate legislation and authoritative language
  texts.
- `4.1 National Cyber Security Policy, 2023`, `4.3 Cyber Security Byelaw, 2077`,
  `4.5 NRB Cyber-Resilience-Guidelines-2023`, `4.6 CSIRTs` — policy and
  incident-response framework. Relevant to reporting obligations and to who a
  case should be escalated to; not currently modelled.
- `7.2 Copyright Act, 2059`, `7.3 Patent, Design and Trade Mark Act, 2022` —
  relevant to brand-impersonation cases, which the engine detects but does not
  yet map to intellectual-property provisions.
- `8.6 Nepal Broadband Policy`, `ADGM electronic records and digital
  signatures` — background.
- `investigation-report-Esewa Scam (1).pdf` — a report produced by this system,
  kept as a worked example.

## Provenance note

The Nepali-language texts are authoritative where they differ from the English
translations. The engine transcribes from the English text of the Act, so any
citation should be checked against the Nepali original before it is relied on
in a filing.
