# Investigation Report

- **Report ID:** RPT-F6299B65C4
- **Generated:** 2026-07-10T20:48:04
- **Investigator:** Unspecified
- **Source file:** timeline.json
- **Source SHA-256:** f655197e2cd852d69270165bc5791dadb1d8b09b695664cae8d54c40d6487528

## Overview

- **Total evidence items:** 7
- **Resolved timestamps:** 7
- **Unresolved timestamps:** 0
- **Timestamp confidence breakdown:** high: 1, medium: 2, low: 4

## Risk Signal Highlights

**Signal frequency:** financial (4), urgency (3), credential (1), threat (1)

- `EVID_00101` (victim1_messenger_chat.jpg) at 2026-07-08T20:15:00+00:00 — flags: urgency, financial, credential
- `EVID_00102` (victim1_esewa_screenshot.jpg) at 2026-07-08T20:58:00+00:00 — flags: financial
- `EVID_00103` (victim1_telegram_followup.jpg) at 2026-07-09T09:40:00+00:00 — flags: urgency, threat
- `EVID_00104` (victim2_whatsapp_chat.jpg) at 2026-07-09T14:15:00+00:00 — flags: urgency, financial
- `EVID_00105` (victim2_bank_transfer.jpg) at 2026-07-09T14:55:00+00:00 — flags: financial

## Correlation Highlights

- `EVID_00106` (unrelated_family_group_chat.jpg) — linked to: EVID_00107 (temporal_proximity, weight 0.8541666666666666)
- `EVID_00107` (unrelated_meeting_reminder.jpg) — linked to: EVID_00106 (temporal_proximity, weight 0.8541666666666666)
- `EVID_00101` (victim1_messenger_chat.jpg) — linked to: EVID_00104 (shared_entity, weight 2.0); EVID_00102 (shared_entity, weight 2.0); EVID_00103 (shared_entity, weight 1.0); EVID_00105 (shared_entity, weight 1.0)
- `EVID_00102` (victim1_esewa_screenshot.jpg) — linked to: EVID_00101 (shared_entity, weight 2.0); EVID_00103 (shared_entity, weight 1.0); EVID_00105 (shared_entity, weight 1.0); EVID_00104 (temporal_proximity, weight 0.28125)
- `EVID_00103` (victim1_telegram_followup.jpg) — linked to: EVID_00101 (shared_entity, weight 1.0); EVID_00102 (shared_entity, weight 1.0); EVID_00104 (temporal_proximity, weight 0.8055555555555556); EVID_00105 (temporal_proximity, weight 0.7777777777777778)
- `EVID_00104` (victim2_whatsapp_chat.jpg) — linked to: EVID_00101 (shared_entity, weight 2.0); EVID_00102 (temporal_proximity, weight 0.28125); EVID_00103 (temporal_proximity, weight 0.8055555555555556); EVID_00105 (temporal_proximity, weight 0.9722222222222222)
- `EVID_00105` (victim2_bank_transfer.jpg) — linked to: EVID_00101 (shared_entity, weight 1.0); EVID_00102 (shared_entity, weight 1.0); EVID_00103 (temporal_proximity, weight 0.7777777777777778); EVID_00104 (temporal_proximity, weight 0.9722222222222222)

## Chronological Narrative

- **[2026-07-06T11:00:00+00:00]** unrelated_family_group_chat.jpg (`EVID_00106`) _(confidence: low, source: upload_time_fallback)_
  > Bibek Karki
dashain ma ghar aaune ho?
ma pani aauxu dai
  — correlated with: EVID_00107
- **[2026-07-06T14:30:00+00:00]** unrelated_meeting_reminder.jpg (`EVID_00107`) _(confidence: low, source: upload_time_fallback)_
  > Office Group
meeting is at 3pm tomorrow, please be on time
  — correlated with: EVID_00106
- **[2026-07-08T20:15:00+00:00]** victim1_messenger_chat.jpg (`EVID_00101`) _(confidence: low, source: upload_time_fallback)_
  > Suraj Bhandari
नमस्ते dai, tapaiko account ma bonus paisa aayeko xa
esewa id: suraj.offers22
phone: 9807766554
yo link m
  — correlated with: EVID_00104, EVID_00102, EVID_00103, EVID_00105
  — ⚠ risk signals: urgency, financial, credential
- **[2026-07-08T20:58:00+00:00]** victim1_esewa_screenshot.jpg (`EVID_00102`) _(confidence: medium, source: content_chat_timestamp)_
  > eSewa
Payment To: suraj.offers22
Amount: Rs. 25,000
07-08, 20:58:np 120
Status: Completed
From: 9807766554
  — correlated with: EVID_00101, EVID_00103, EVID_00105, EVID_00104
  — ⚠ risk signals: financial
- **[2026-07-09T09:40:00+00:00]** victim1_telegram_followup.jpg (`EVID_00103`) _(confidence: low, source: upload_time_fallback)_
  > Suraj Offers
paisa aaena bhane hamiley tapaiko photo ra details sabai lai pathaidine chau
farkera call garnus 9807766554
  — correlated with: EVID_00101, EVID_00102, EVID_00104, EVID_00105
  — ⚠ risk signals: urgency, threat
- **[2026-07-09T14:15:00+00:00]** victim2_whatsapp_chat.jpg (`EVID_00104`) _(confidence: medium, source: content_time_only)_
  > Unknown
तपाईंको eSewa account ma cashback आएको छ
Click here to claim: hxxp://esewa-bonus-verify.xyz/claim
limited time o
  — correlated with: EVID_00101, EVID_00102, EVID_00103, EVID_00105
  — ⚠ risk signals: urgency, financial
- **[2026-07-09T14:55:00+00:00]** victim2_bank_transfer.jpg (`EVID_00105`)
  > Nepal Bank Transfer Confirmation
Date: 2026-07-09 14:55:00
To Account: 0198765432109
Amount: NPR 40,000
Beneficiary: Sur
  — correlated with: EVID_00101, EVID_00102, EVID_00103, EVID_00104
  — ⚠ risk signals: financial

## Confidence & Caveats

Timestamps in this report are resolved with varying confidence. Readers should weigh conclusions accordingly:

- **high** — an explicit date and time were found in the evidence content itself (most forensically reliable).
- **medium** — either a chat-style inline timestamp or a time-only value combined with the upload date as a best guess; the date portion may be inexact.
- **low** — no usable timestamp was found in the content; the system fell back to the file's processing/upload time, which may not reflect when the underlying event occurred.
- **none** — no timestamp could be resolved at all; this item is listed at the end of the timeline, unordered relative to other unresolved items.

**4 of 7 evidence item(s) have low or unresolved timestamp confidence** and should not be treated as precisely dated without further corroboration.
