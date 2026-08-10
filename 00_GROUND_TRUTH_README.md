# Synthetic Test Case: CASE_2026_0088 — "Dashain Cashback" eSewa Phishing Scam

This is a **fictional, synthetically generated** test case for validating the CIIE pipeline
(OCR, entity extraction, URL classification, correlation, timeline reconstruction, report
generation). All names, numbers, and accounts are made up.

## Case narrative
Victim Sunita Gurung (Pokhara) is contacted via SMS, then Facebook Messenger, then email,
by a scammer impersonating "eSewa Support," claiming she won a NPR 5,000 Dashain cashback.
She is asked to pay small "verification/processing fees" via eSewa and Khalti, then a larger
NPR 25,000 "release fee" via direct bank transfer, before all contact stops.

## Evidence items (8 files)
| # | File | Type | Blur level |
|---|------|------|-----------|
| 1 | 01_sms_screenshot.jpg | Phishing SMS screenshot | Blurred (light-medium) |
| 2 | 02_messenger_chat.jpg | Messenger chat log (mixed EN/Nepali/Roman Nepali) | Blurred (light) |
| 3 | 03_qr_code_flyer.png | QR code flyer distributing phishing link | Clean (must stay scannable) |
| 4 | 04_esewa_payment_screenshot.jpg | eSewa payment confirmation | Blurred (heavy) |
| 5 | 05_khalti_receipt.jpg | Khalti payment receipt | Blurred (light) |
| 6 | 06_phishing_email_screenshot.jpg | Phishing email (English) | Blurred (medium) |
| 7 | 07_bank_transfer_slip.pdf | Scanned bank transfer voucher | Simulated scan noise/rotation |
| 8 | 08_complaint_letter.pdf | Victim's typed complaint to Cyber Bureau | Clean/typed |

## Ground-truth entities (for evaluating extraction precision/recall)

**Phishing URL:** `https://esewa-cashback-offer.xyz/claim` (also with `?ref=DSN2026`)
— appears in: SMS, Messenger chat, QR code, phishing email

**Scammer phone / Khalti ID:** `9801122334` (`+977-9801122334`)
— appears in: Messenger chat, phishing email, Khalti receipt

**Scammer eSewa ID:** `esewa.cashback99@gmail.com`
— appears in: Messenger chat, eSewa payment screenshot

**Victim eSewa ID:** `sunita.gurung21@gmail.com`
— appears in: Messenger chat, eSewa payment screenshot, complaint letter

**Victim phone:** `9847011223`
— appears in: Messenger chat, Khalti receipt, bank slip, complaint letter

**Bank account (recipient):** `0501-9012345678`, Machhapuchhre Bank Limited, name "Rabin Thapa"
— appears in: bank transfer slip, complaint letter

**Victim bank account:** `0501-0198765432`
— appears in: bank slip

**Transaction IDs:** `0119.0625.987456` (eSewa), `KH-2026-0611-77245` (Khalti), `MBL-2026-441829` (bank voucher)

**Case/complaint reference:** `CASE_2026_0088`

**Brand names referenced:** eSewa, Khalti, Machhapuchhre Bank Limited

**Dates (for timeline reconstruction testing):**
- 10 June 2026 — SMS received
- 11 June 2026, ~10:00–11:15 AM — Messenger chat, eSewa fee paid, Khalti fee paid
- Email received (undated in-message, but same window)
- 14 June 2026 — Bank transfer made
- 15 June 2026 — Complaint filed

## Expected correlation links your engine should find
- SMS ↔ Messenger chat ↔ QR flyer ↔ Phishing email — via shared URL `esewa-cashback-offer.xyz`
- Messenger chat ↔ Khalti receipt ↔ Phishing email — via shared number `9801122334`
- Messenger chat ↔ eSewa payment screenshot — via shared ID `esewa.cashback99@gmail.com`
- Bank slip ↔ Complaint letter — via shared account `0501-9012345678` and phone `9847011223`
- All items ↔ Complaint letter — via case reference `CASE_2026_0088`

## Notes on the blur
Each "screenshot" evidence item was rendered cleanly first, then run through a Gaussian blur
+ heavy JPEG re-compression pass to simulate a real low-quality forwarded phone screenshot —
useful for stress-testing PaddleOCR confidence scoring and your confidence-gated correction
rule. The QR code and typed complaint letter were deliberately left clean/sharp, since QR
codes need to remain scannable and a "typed complaint" wouldn't realistically be blurry.
