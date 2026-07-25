# Cybercrime Investigation Intelligence System (CIIS)
## Complete System Flow + Methodology Walkthrough + Viva Question Bank

**Project:** Cybercrime Investigation Intelligence Engine Using Digital Evidence Correlation
**Subject Code:** ENCT 354 · Himalaya College of Engineering, IOE, Tribhuvan University
**Team:** Sachyam Dahal (HCE080BCT030), Sujal Shrestha (HCE080BCT042), Suraj Khatri (HCE080BCT043), Sushant Gautam (HCE080BCT045)
**Document generated from:** the actual source tree in this repository (not from the report text), cross-checked against the mid-defence progress report PDF.

---

## 0. How to read this document

This is written the way you would *speak* it in front of an examiner — plain sentences, one idea at a time, with the exact file that implements each idea named next to it so that any claim can be opened and verified live.

It has three parts:

1. **Part A — The system in plain words** (what it is, who uses it, how it is put together).
2. **Part B — The system flow diagram, explained box by box** — this is the main methodology section. Every box of the flowchart gets its own subsection: what enters the box, what happens inside, what leaves, which file does it, and *why we designed it that way*.
3. **Part C — Question bank** — every question you asked, answered properly and defensibly, plus ~20 extra questions an examiner is likely to ask after seeing this flow.

A short honesty note, because examiners reward it: the mid-defence report was written at a point in time, and the code has moved since. Wherever the report and the code differ, this document says so explicitly in a **"Report vs. code"** note. There are five such places, all listed in §12.

---

# PART A — THE SYSTEM IN PLAIN WORDS

## 1. The problem we are solving

A cybercrime complaint in Nepal does not arrive as a database. It arrives as a pile of *screenshots*: a WhatsApp chat where a scammer demands money, an SMS with a shortened link, a fake bank email, an eSewa payment receipt, a scanned police statement. Some of it is in English, some in Nepali Devanagari, and a great deal of it is in **Roman Nepali** ("tapai ko account verify garnus, esewa ma paisa pathaunus"), which no off-the-shelf tool handles.

An investigator today does four things by hand:

1. Reads each screenshot and re-types what it says.
2. Highlights the phone numbers, wallet IDs, links and account numbers.
3. Tries to remember whether that same phone number appeared in a *different* case last month.
4. Assembles the whole thing into a chronological story and writes a report.

Steps 1–3 are mechanical, slow, and error-prone; step 4 is where the human expertise actually is. Our system automates 1–3 and hands the investigator a prepared, evidence-linked draft for step 4 — **without ever modifying the original evidence**, because in a courtroom an altered exhibit is a lost case.

## 2. The two panels (this is the access model)

There are exactly **two panels** in the deployed product. There are no other user types.

### 2.1 Investigator panel — the working surface

The Investigator does not "log in" to a user account. The engine is **case-reference based**: the investigator types a case reference (for example a complaint number like `MCC/2082/0147`), and the system hashes that reference with SHA-256 to derive a stable, non-guessable case id (`CASE_2CF24DBA5F`). Typing the same reference again reopens the same case with all of its evidence, artifacts and reports.

*Implementation:* `evidence_ocr_engine/backend/modules/evidence/case_registry.py` → `make_case_id()` = `"CASE_" + sha256(normalized_reference)[:10].upper()`; front door at `ciis_api/api/views/intake.py`.

The design consequence is deliberate and worth stating in the defence: **there is no case-list endpoint anywhere in the API**. `ciis_api/api/urls.py` carries a comment saying exactly this. Nothing enumerates cases, so one investigator's case can never be discovered by browsing. A case is reachable only by knowing its reference — the same principle as an unlisted document link, applied to evidence.

Inside a case, the Investigator panel is a seven-tab workspace (`ciis_frontend/src/features/cases/CaseDetailPage.tsx`):

| Tab | What it shows | Backed by |
|---|---|---|
| Overview | Case header, evidence count, analysis state | `views/cases.py` |
| Evidence | Upload, per-item OCR text, confidence, hashes, preview | `views/evidence.py` |
| Investigation | Correlation pairs, campaigns, suspects, priority | Phase-2 artifacts |
| Graph | Interactive Cytoscape.js relationship graph | `graph.json` |
| Timeline | Chronological reconstruction with confidence labels | `timeline.json` |
| Analytics | Charts: entity mix, threat levels, quality metrics | `analytics` artifact |
| Reports | Generated Markdown/PDF forensic report, downloadable | `views/reports.py` |

### 2.2 Administrator panel — the custodial surface

The Administrator panel lives at `/admin` (`ciis_frontend/src/features/admin/AdminPage.tsx`) and is gated by a **shared administrator password**, not a user account.

*Implementation:* `ciis_api/api/admin_auth.py`. The password comes from the `CIIS_ADMIN_PASSWORD` environment variable. On success the server returns a **stateless signed token** produced with `django.core.signing` (8-hour expiry) which the frontend then sends as an `X-Admin-Token` header. Because the token is *signed rather than stored*, admin sessions need no user table and no database — which is what let us delete the database entirely (see §9).

The Administrator can do exactly two things that an Investigator cannot:

1. **See every case in the system** (`GET /api/admin/cases/`) — reference, evidence count, whether it has been analysed, and which other cases it is linked to. This is the only enumerating endpoint in the whole product, and it is the reason it is password-gated.
2. **Delete a case, with a full cascade** (`DELETE /api/admin/cases/<id>/`).

The deletion cascade is worth explaining in detail because it is a genuinely non-trivial piece of engineering (`investigation/maintenance.py` + `api/engine.py::delete_case_cascade`). Deleting a case purges: the case registry row, every row belonging to it in the evidence/entity/OCR/processing/audit CSVs, its OCR case JSON, the stored original files, all Phase-1 forensic reports, all Phase-2 artifacts, and its rows in the cross-case entity index — and then **re-analyses every case that was linked to the deleted one**, so their cross-case correlations, graphs, timelines and reports stop referencing evidence that no longer exists. Without that final re-analysis step you would get "ghost links" — a report citing a case that has been erased, which is a data-integrity failure an examiner will ask about.

> **Report vs. code (1).** Appendix E of the progress report lists JWT endpoints (`/api/auth/login/`, `/api/auth/refresh/`) and role-filtered case lists. That RBAC layer was **removed** on 2026-07-23/25 (recorded in `AUDIT.md`) and replaced by the two-panel model above: an open, reference-addressed Investigator engine plus a password-gated Administrator panel. `api/permissions.py` keeps `require("...")` as a *documented no-op* so every view still declares which capability it represents — meaning access control can be restored later by changing one function rather than fifty views. Say this out loud in the defence; it reads as a considered decision, not an omission.

## 3. Architecture at a glance

Seven implemented processing modules, sitting under one web platform, all writing to plain files.

```
┌──────────────────────── ciis_frontend (React 19 + TypeScript + MUI) ─────────────────────────┐
│  Investigator panel: intake → case workspace (7 tabs)      Administrator panel: /admin       │
│  Cytoscape.js graph · Recharts analytics · TanStack Query · Axios (X-Admin-Token)            │
└──────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                           │ REST/JSON
┌──────────────────────────────────────────┴───────────────────────────────────────────────────┐
│  ciis_api (Django 5 + Django REST Framework)                                                  │
│  views/{intake,cases,evidence,investigation,reports,dashboard,audit,notifications,admin}      │
│  api/engine.py = the ONLY bridge into the engine (read-only + background job execution)       │
│  api/store.py  = file-backed platform state (jobs, notifications, activity log) — no DB       │
└──────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                           │ direct Python import
┌──────────────────────────────────────────┴───────────────────────────────────────────────────┐
│  evidence_ocr_engine/backend/modules/                                                         │
│   evidence/      Phase 1  – acquisition, SHA-256, preprocessing, PaddleOCR, storage           │
│   evidence/forensics/     Phase 1.5 – 8 forensic analyses on the pristine original            │
│   evidence/cleaning/      multilingual cleaning + 30-type regex entity extraction             │
│   evidence/enhancement/   confidence-gated OCR correction                                     │
│   evidence/semantic/      XLM-RoBERTa context validation (inference only)                     │
│   investigation/          Phase 2  – 8 analysis modules (M1…M8) + report generation           │
└──────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                           │ lazy, optional adapter
┌──────────────────────────────────────────┴───────────────────────────────────────────────────┐
│  threat_intelligence_system/  – URL parsing → 71 features → 8 ML models (XGBoost deployed)    │
│                                 → rule engine → live intel (VT/WHOIS/SSL/DNS/GeoIP) → 0-100   │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                          storage/  ← CSV + JSON files only. No database server.
```

Three folders in the repository — `evidence_correlation_engine/`, `report generation/`, and partly `timeline_reconstruction/` — are **early standalone prototypes**. Each carries a `DEPRECATED.md` naming its integrated replacement. Nothing in the running product imports the first two. (`timeline_reconstruction/timeline_reconstruction.py` is the exception: it was *un-deprecated* and is now loaded as the canonical engine by the integrated `TimelineService` — see §5.14.)

---

# PART B — THE SYSTEM FLOW, BOX BY BOX

This part follows the flowchart exactly, top to bottom. For each box: **In → What happens → Out → Where in the code → Why**.

## 4. The one rule that governs the whole flow

Before the first box, state the invariant, because every design decision downstream follows from it:

> **The forensic invariant: never modify, always add.**

The uploaded file is copied, never moved and never edited. The OCR output (`raw_text`) is written once and never rewritten. Cleaning does not overwrite `raw_text`; it *adds* `cleaned_text`. Correction does not overwrite `cleaned_text`; it *adds* `enhanced_text`. Semantic validation adds `semantic_text`. So one evidence item ends up carrying **four parallel text layers**, plus the untouched original bytes on disk:

```
original file bytes  (storage/originals/, SHA-256 verified 3×)
   └─ raw_text       verbatim OCR, per line: text + confidence + bounding box
        └─ cleaned_text     normalised, entity-shielded
             └─ enhanced_text    confidence-gated dictionary corrections
                  └─ semantic_text    XLM-R context-validated corrections
```

Why this matters in one sentence: **if defence counsel challenges any automatic change, we can show the exact earlier layer, the rule that fired, the OCR confidence that permitted it, and the timestamp** — and if the challenge succeeds, the original layer is still there, unaltered. There are unit tests that assert this byte-for-byte (`tests/test_ocr.py`, `tests/cleaning/`, `tests/enhancement/`).

## 5. The flow

### 5.1 START → "Authenticate User or Patch or Create Case"

**In:** a case reference typed by the Investigator (or the Administrator password, for the admin panel).
**What happens:** `POST /api/intake/` receives the reference. `normalize_reference()` trims and case-folds it, `make_case_id()` hashes it with SHA-256 and takes the first 10 hex characters, upper-cased, prefixed `CASE_`. `CaseRegistry.resolve_or_create()` then either returns the existing registry row or appends a new one to `storage/case_registry.csv`.
**Out:** `{case_id, case_reference, title, created, ...}` and an activity-log row.
**Code:** `api/views/intake.py`, `evidence/case_registry.py`.
**Why hash the reference instead of using a counter?** Three reasons. (a) It is **deterministic** — the same complaint number always reopens the same case, from any machine, with no lookup table needed. (b) It is **non-enumerable** — you cannot guess `CASE_0002` from `CASE_0001`, so with no listing endpoint, cases are effectively private. (c) It is **stable across re-imports** — you can wipe and rebuild storage and the ids still match the references.

### 5.2 "Upload Digital Evidence"

**In:** a file — PNG / JPG / JPEG / PDF / TXT / CSV (DOCX optional). Or a URL submitted directly as evidence (`POST /cases/<id>/evidence/url/`).
**What happens:** DRF receives the multipart upload, validates size and extension at the API boundary, writes it to a temp path, and enqueues a **background job** (a `ThreadPoolExecutor` in `api/engine.py`, max 2 workers, guarded by a pipeline lock). The job id is returned immediately so the UI can poll `GET /api/jobs/<id>/` and show progress instead of blocking on OCR for eight seconds.
**Out:** a job record in `storage/platform/jobs.json`; a notification when it completes.
**Code:** `api/views/evidence.py`, `api/engine.py`, `api/store.py`.
**Why a background job?** Because OCR of a screenshot takes ~2.6 s and a PDF takes longer; an HTTP request that blocks that long times out behind most proxies and gives the investigator no feedback. The worker thread writes progress into a JSON file, which the UI polls.

### 5.3 "Validate, Hash and Preserve Evidence" — the chain of custody

This is the forensic heart of Phase 1 (`evidence/upload.py` + `evidence/hash_service.py`).

The sequence, in the exact order the code runs it:

1. **Validate.** Extension in the allow-list? Size ≤ 50 MB? File non-empty and readable? Any failure → `EvidenceError`, HTTP 400, audited, nothing stored. (Test: `test_upload_rejects_oversized`.)
2. **Hash the source (hash #1).** `HashService.sha256_file()` streams the file in 1 MB chunks and returns the 64-hex-character digest. Streaming matters: a 50 MB video frame dump must not be loaded into RAM to be hashed.
3. **Copy, never move.** The file is copied into `storage/originals/` under a collision-proof name: `EVID_00001__a1b2c3d4__screenshot.png` (evidence id + hash prefix + original name). The investigator's own file is never touched.
4. **Hash the copy (hash #2) and compare.** If hash #1 ≠ hash #2, the copy is corrupt — the pipeline refuses to continue rather than analysing a damaged exhibit.
5. **Process.** Preprocessing, OCR, everything downstream — all of it works on an **in-memory** image or a separate derived file. The stored original is opened read-only.
6. **Hash again after processing (hash #3) and verify.** This proves the pipeline itself did not modify the exhibit. `hash_verified: true` appears in the case JSON and `storage/evidence.csv`.

**Out:** a row in `storage/evidence.csv` carrying `evidence_id, case_id, original_file_name, stored_path, sha256_before, sha256_after, hash_verified, uploaded_at, status` — this CSV *is* the chain-of-custody register — plus timestamped rows in `storage/processing_log.csv` for every stage with its duration in milliseconds.

**Why three hashes and not one?** One hash proves nothing about *when* corruption happened. Three hashes partition the timeline into answerable segments: hash1 vs hash2 answers "did acquisition damage it?", hash2 vs hash3 answers "did our own analysis damage it?", and hash3 vs a re-hash tomorrow answers "has storage or an operator damaged it since?" That is what a chain of custody is for.

### 5.4 Side box: "File-Based Forensic Storage"

Everything from here on writes to plain CSV and JSON under `evidence_ocr_engine/storage/`. **There is no PostgreSQL, MongoDB, Neo4j or Redis anywhere in this project.** Django is configured with `DATABASES = {}` and `django.contrib.{admin,auth,contenttypes,sessions,messages}` removed from `INSTALLED_APPS` (`ciis_api/config/settings.py`). See §9 for the full storage map and the justification.

### 5.5 Decision: "Does the evidence require OCR?"

A three-way branch on file type (`EvidencePipeline._extract_pages`):

* **Image** (PNG/JPG/JPEG) → preprocessing → PaddleOCR. *Requires OCR.*
* **PDF** → PyMuPDF opens it. A **natively digital PDF** (one with an embedded text layer) is read **directly** — no OCR at all, which preserves the exact characters and the page/line structure the author typed. A **scanned PDF** (image-only pages) is rasterised page by page and each page goes through the image path, keeping page numbers and order.
* **TXT / CSV** (e.g. a WhatsApp chat export) → text is already text. It bypasses OCR entirely and is stored with `confidence = 1.0`.

**Why branch instead of OCR-ing everything?** OCR is lossy. Running OCR over a PDF that already contains perfect text would *introduce* errors into evidence, which is exactly what the forensic invariant exists to prevent. Choosing the lossless path whenever one exists is a forensic decision, not a performance one — though it is also about 40× faster.

### 5.6 "Preprocess Image Adaptively"

**Code:** `evidence/preprocessing.py` — two methods, `assess_quality()` then `preprocess()`.

First we *measure*, then we act. `assess_quality()` computes:

| Measure | How | Threshold in code |
|---|---|---|
| Blur | Variance of the Laplacian: `cv2.Laplacian(gray, CV_64F).var()`. A sharp image has strong second derivatives at edges → high variance. | `< 120.0` ⇒ blurry |
| Brightness | Mean grey value | `< 70` ⇒ dark |
| Contrast | Standard deviation of grey values | `< 45` ⇒ low contrast |
| Noise | Residual after median filtering | `> 9.0` ⇒ noisy |
| Skew | Otsu threshold → `minAreaRect` over the text mask → tilt angle | `≥ deskew_min_angle` ⇒ deskew |

Then `preprocess()` applies **only the corrections the measurements indicate**, in a fixed order: RGB conversion → EXIF-orientation correction (fixes sideways phone photos) → downscale-if-huge / upscale-if-tiny → deskew → perspective correction (flattens a photographed page) → denoise (median, then Gaussian if very noisy) → CLAHE contrast enhancement (`clipLimit=2.5`, `tileGridSize=(8,8)`) → sharpening → border trimming → adaptive thresholding.

Two details examiners like:

* **Adaptive thresholding is gated by `_looks_like_document_scan()`.** Binarising a colourful chat screenshot destroys it — bubble backgrounds turn into solid black. So thresholding runs only on document-like scans. This is one of the clearest examples of "adaptive" meaning *conditional*, not *always-on*.
* **Every step applied is recorded** in the result as a list of strings (`["deskew(2.31deg)", "clahe", "sharpen"]`), so the report can state exactly what was done to the image that produced the text. And all of it happens on an **in-memory copy**; the stored original is byte-identical afterwards (that is what hash #3 proves).

### 5.7 "Extract Text with PaddleOCR 3.x"

**Code:** `evidence/paddle_service.py`, behind the `BaseOCR` interface (`evidence/ocr_interface.py`).

Configuration, precisely: **PaddleOCR ≥ 3.0, pinned to the PP-OCRv5 pipeline**, with `lang="ne"`. The service *rejects* any other model generation at construction time (`_resolve_version` raises). `lang="ne"` loads `PP-OCRv5_server_det` for detection and `devanagari_PP-OCRv5_mobile_rec` for recognition — a multilingual recogniser whose character dictionary contains **both Devanagari and Latin**, so English, Nepali and mixed-script text in one screenshot are read in a single pass. Aliases (`"devanagari"`, `"nepali"`, `"np"`) are mapped to `"ne"` because PaddleOCR 3.x rejects script-group names.

For every detected line the engine returns three things, all stored:

1. **text** — verbatim. Never translated, never autocorrected, never spell-checked at this stage.
2. **confidence** ∈ [0, 1] — the recogniser's own certainty. This single number is the gate for everything in §5.9; without it that module could not exist.
3. **bounding box** — the four-corner polygon locating the line on the image, which is what lets the UI highlight a phone number on the screenshot itself.

Engineering guards: the model is imported **lazily** (so hashing/storage/tests run on machines with no Paddle installed), recognition runs inside a `ThreadPoolExecutor` with a **hard timeout** (a hung OCR call can never freeze the worker), and any line below the low-confidence threshold is logged as a warning.

*(How OCR works internally — detection, rectification, recognition, CTC decoding — is answered in full in Q1, §13.1.)*

### 5.8 "Record Raw Text, Confidence and Metadata"

**Out:** two destinations, deliberately.

* **CSV summaries** for anything a human might want to open in Excel: `cases.csv`, `evidence.csv`, `ocr_results.csv`, `processing_log.csv`.
* **One complete JSON per case**: `storage/json/CASE_XXXX.json` — `raw_text`, per-page text, **per-line confidence**, **per-line bounding boxes**, both hashes, per-stage timings.

`raw_text` is written exactly once here and is never written again by any later module. Everything downstream reads it and writes elsewhere.

### 5.9 Interlude: Phase 1.5 — the eight forensic analyses

Not a separate flowchart box, but it runs here, on the **pristine stored original**, and it is a strong thing to mention in a defence because it is what makes this "forensic" rather than merely "OCR + ML".

`evidence/forensics/pipeline.py` wraps the Phase-1 pipeline and runs, in order: **integrity → metadata → quality → forgery → advanced preprocessing → multi-OCR fusion → logo detection → confidence scoring.**

* **Integrity** — re-verifies hashes independently.
* **Metadata** — EXIF/device/software extraction: which phone took the screenshot, was it edited in Photoshop, what timestamp does the file carry.
* **Quality** — a graded quality report used later as a caveat in the report ("this finding rests on a low-quality image").
* **Forgery** — copy-move / resave / inconsistency indicators.
* **Advanced preprocessing** — a planner that proposes a stronger enhancement chain for hard images.
* **Multi-OCR fusion** — runs more than one OCR engine (PaddleOCR adapter, EasyOCR adapter) and *fuses* results, using agreement between engines as extra evidence for a line.
* **Logo detection** — is the "Nabil Bank" logo in this phishing screenshot the real one? (`forensics/logos/registry.py`)
* **Confidence scoring** — rolls the above into one interpretable score for the item.

Each analysis is **failure-isolated**: an exception writes an audited ERROR row and the run continues. A crash in logo detection must never destroy an evidence trail.

### 5.10 "Clean and Normalize Multilingual Text"

**Code:** `evidence/cleaning/` (`cleaning_pipeline.py` and its collaborators).

**Step 1 — per-line language detection** (`language_detector.py`). Every line is classified as `english`, `nepali_unicode`, `roman_nepali`, `mixed`, or `unknown`, using explainable rules rather than a model: which Unicode block do the characters fall in, and for Latin-only lines, how many words appear in a hand-built list of Roman-Nepali markers (`garnus`, `paisa`, `pathaunus`, `tapai`, `rakhnus`, …). Nothing is ever translated.

**Step 2 — entity preservation, the clever trick** (`entity_preserver.py`). *Before any cleaning rule runs*, every candidate URL, email, phone, hash, wallet ID and money amount is located and swapped for an invisible placeholder built from Unicode **private-use** characters — characters no cleaning rule can match. Cleaning then runs on the placeholder version. Afterwards the original substrings are restored **byte-for-byte**.

The consequence is the single most important sentence in this module: **no cleaning rule can ever damage a piece of evidence.** `supp0rt@fake-bank.com` survives with its zero intact, because that zero may be the scammer's actual address — it is evidence, not a typo. A naïve "fix OCR errors" pass would silently rewrite it to `support@fake-bank.com` and destroy the link to the suspect.

**Step 3 — the cleaning chain, in this fixed order:**

1. **Unicode normalisation** — NFC, curly quotes → straight, non-breaking spaces → spaces, zero-width characters removed. Meaning-preserving by definition.
2. **Structural OCR fixes** — `http//` → `http://`, and similar punctuation-level repairs.
3. *(entity shield goes up)*
4. **Conservative word fixes from a closed list** — `acc0unt`→`account`, `1ogin`→`login`. Unknown words are **never guessed**.
5. **Noise removal** — decorative rules `------`, `!!!!!` → `!`.
6. **Whitespace normalisation** — collapse runs of spaces and blank lines; keep paragraph boundaries.
7. **Sentence reconstruction** — `"Verify your\naccount now"` → `"Verify your account now"`, but **never** merging across an entity line or across a script boundary (Devanagari line + Latin line stay separate).
8. **Roman-Nepali normalisation** — lowercase, collapse elongations (`garnusss` → `garnus`). Words are never rewritten into different words.
9. *(entity shield comes down — originals restored)*

**Out:** a `cleaning` section per evidence item inside the case JSON; `raw_text` untouched.

### 5.11 "Extract and Normalize Entity Types"

**Code:** `evidence/cleaning/entity_extractor.py` + `regex_patterns.py`.

The extractor declares a **stable schema of 30 entity types** in six groups, and returns a key for *every* type on *every* call — empty list included. That last detail matters: downstream consumers can distinguish "we looked and found none" from "we never looked", which is a meaningful distinction in an evidence report.

| Group | Types |
|---|---|
| network (7) | urls, domains, ipv4, ipv6, mac_addresses, ports, cve_ids |
| contact (2) | emails, phones |
| temporal (2) | dates, times |
| financial (8) | money, bank_accounts, card_numbers, transaction_ids, **esewa_ids, khalti_ids, imepay_ids**, otp |
| crypto (6) | eth_wallets, btc_wallets, hashes_md5, hashes_sha1, hashes_sha256, hashes_sha512 |
| social (5) | social_media_urls, telegram_usernames, whatsapp_numbers, facebook_usernames, instagram_usernames |

Of these, **24 are used as correlation keys** (`investigation/config.py::correlation_entity_types`). `dates` and `times` are deliberately excluded because the *timeline* module owns temporal reasoning; `ports`, `cve_ids` and raw hash values are excluded because they do not identify an actor (file identity is handled by the separate `file_hash` correlation factor).

Each extraction is then **validated, normalised and de-duplicated**:

* **Validated** — IPv4 octets must be 0–255 (`ipaddress` module, not just regex); wallet and hash formats are structurally checked; trailing punctuation is stripped.
* **Normalised** — emails and URLs case-folded, whitespace trimmed, and **Nepali mobile numbers canonicalised to `+977…` form**, so `9841234567`, `+977-9841234567` and `977 9841 234 567` all become one value.
* **De-duplicated** on the normalised form, within an evidence item.

**The normalised form is the field the correlation engine matches on.** This is the whole reason normalisation exists: without it, the same scammer's phone number written three ways would look like three different people.

The extractor also counts scam vocabulary in three languages (English "verify/OTP/lottery", Roman Nepali "paisa/pathaunus", Devanagari "पैसा/चिठ्ठा") and rolls the counts into four **risk signals**: urgency, financial, credential-theft, threat. This is *counting only* — deciding "this is phishing" belongs to the threat module.

**Out:** one row per entity in `storage/entities.csv`; counts in `storage/keyword_statistics.csv`.

> **Report vs. code (2).** Section 4.5 of the report says "22 correlatable entity types". The code's schema is **30 types**, of which **24** are correlation keys. The count grew during implementation (eSewa/Khalti/IME Pay were split out, transaction ids and card numbers added). Quote 30/24 and cite `ENTITY_TYPE_GROUPS`; an examiner who checks will find the code, not the report.

### 5.12 "Correct and Semantically Validate Text"

Two layers stacked, both additive.

**Layer 1 — confidence-gated dictionary correction** (`evidence/enhancement/`, writes `enhanced_text`).

Recall that PaddleOCR gave us a confidence for every line. Each cleaned line is traced back to its OCR line, and the confidence decides what is *permitted*:

| OCR confidence | Tier | What is allowed |
|---|---|---|
| ≥ 0.90 | HIGH | **Nothing.** The OCR was confident; we trust it completely. |
| 0.30 – 0.90 | MEDIUM | Exact dictionary lookups only — the word must already be in the known-errors lexicon. |
| < 0.30 | LOW | Dictionary **plus** fuzzy/OCR-rule matching — the word may merely be *close* to a known valid word. |

(`enhancement/confidence_analyzer.py`: `HIGH_CONFIDENCE_THRESHOLD = 0.90`, `LOW_CONFIDENCE_THRESHOLD = 0.30`.)

Even when the tier permits a correction, the **triple-agreement rule** applies: the change is written only if (1) a **dictionary** produced the candidate, (2) the **confidence tier** permits that class of candidate, and (3) a **context check** passes — same script (Devanagari is never replaced by Latin), similar visual shape, with bonus evidence if the corrected word already occurs elsewhere in the document. If any one signal disagrees, the word is left alone. *In forensics, not correcting is always safer than guessing.*

The lexicons are **data, not code**: `enhancement/data/nepali_ocr_lexicon.json` (Devanagari misrecognitions such as `"बोड" → "बोर्ड"`, plus a valid-word list for fuzzy matching) and `english_ocr_lexicon.json` (homoglyph fixes `0↔o`, `1↔l`, `5↔s`, applied only when exactly one real word can result). Adding a newly-observed OCR error is one line of JSON — no programming.

A **Unicode validator** additionally repairs *structurally invalid* Devanagari that OCR sometimes emits: a doubled vowel sign, a double halant (`््`), a vowel sign with no consonant to attach to, stray zero-width joiners. These sequences are illegal under Unicode rules, so repairing them cannot change meaning.

Every correction is logged to `storage/ocr_corrections.csv` with: original word, corrected word, the OCR confidence that permitted it, the rule that produced it, and a timestamp.

**Layer 2 — semantic validation with XLM-RoBERTa** (`evidence/semantic/`, writes `semantic_text`).

The pipeline is: entity protection → sentence reconstruction → mixed-script detection → **rule** candidate generation → **XLM-R** context validation → language + dictionary + confidence gates → accept/reject → entity restoration.

The critical design constraint, stated in the module docstring and enforced by the code: **the language model never generates text.** `XLMRobertaValidator.validate()` (`semantic/validator.py`) takes the sentence with the candidate word replaced by a mask token, runs `xlm-roberta-base` as a **fill-mask** pipeline, reads the top-k predicted tokens, and returns *only a verdict*: it accepts the candidate if `score(candidate) ≥ 0.15` **and** `score(candidate) ≥ score(original)`. The candidate itself was proposed by a deterministic rule; the model is a judge, never an author. There is no path in this code by which a model-invented word can enter evidence.

If `transformers`/`torch` cannot be imported or the model cannot be downloaded (offline lab, weak hardware), the pipeline falls back to `HeuristicSemanticValidator` — dictionary agreement plus character-level edit distance — and **records in the audit log which validator was used**, so the provenance of every correction stays traceable. `python cli.py process CASE_X --no-xlmr` forces the offline path deliberately.

### 5.13 Decision: "Are URL or domain indicators present?" → URL classification + threat enrichment

If the entity extractor found no URL or domain, the flow skips straight to correlation. If it did, the value goes to the threat subsystem via `investigation/ml_threat_intel.py`, an adapter that imports the heavy ML stack **lazily** — if xgboost/sklearn or the model artifact is missing, the adapter reports `available == False`, every lookup returns `None`, and the engine falls back to a static indicator file. The Django process is never bloated by an import it may not need.

**Stage 1 — Parse and canonicalise** (`threat_intelligence_system/src/parser/`). Split into scheme, host, domain, subdomain, path, query, fragment; detect Punycode/IDN homograph tricks (a Cyrillic «а» that renders identically to Latin "a"); resolve and validate.

**Stage 2 — Compute 71 engineered features** (`src/feature_engineering/`, schema pinned in `checkpoints/feature_metadata.json`, `feature_version 2.0.0`, `feature_count: 71`), across eight families:

| Family | Examples from `feature_order` |
|---|---|
| Length (12) | `url_length`, `hostname_length`, `domain_length`, `path_length`, `max_path_segment_length` |
| Entropy (7) | `url_entropy`, `domain_entropy`, `path_entropy`, `digit_entropy_ratio` — Shannon entropy detects machine-generated gibberish like `xk7qz9v2` |
| Character (15) | `digit_count`, `dot_count`, `hyphen_count`, `at_symbol_count`, `percent_sign_count` |
| Structural (9) | `subdomain_count`, `directory_depth`, `has_port`, `has_at_symbol`, `has_double_slash` |
| Lexical (6) | `suspicious_keyword_count` (login/verify/secure/update), token statistics |
| Brand (n) | Levenshtein/Damerau distance to known brands, brand-in-subdomain, typosquatting flags |
| Security | HTTPS usage, certificate flags, redirect count, homoglyph flags |
| TLD | cheap/abused TLD flags (`.xyz`, `.top`, `.icu`, `.gq`…), ccTLD flags |

**Stage 3 — Classify.** The deployed model is **XGBoost** (`checkpoints/xgboost.pkl` / `.ubj`, `production_model.json` `run_id 20260712T090000Z`). Seven other models were trained on identical splits for comparison (LightGBM, Random Forest, Extra Trees, Decision Tree, Logistic Regression, Naive Bayes, SVM). Full numbers and the reason XGBoost was chosen: Q10 (§13.10).

**Stage 4 — "Enrich Threat Intelligence".** A URL can look innocent and still be dangerous, so optional live connectors run (`src/intelligence/`): **VirusTotal** (how many engines flag it), **WHOIS** (domain age — a domain registered three days ago is a strong signal), **SSL** (valid certificate?), **DNS** (SPF/DMARC records present?), **GeoIP** (hosting location), plus a **rule engine** (`src/rules/rule_engine.py`) and a **brand-intelligence engine** that detects homoglyph and typosquat imitation of known brands.

**Stage 5 — Fuse into one 0–100 score.** Weights from `config/settings.yaml`:

```yaml
decision_weights:  ml_probability 0.35 · rule_engine 0.30 · threat_intelligence 0.20 · domain_trust 0.15
classification_thresholds:  legitimate ≤ 30 · suspicious ≤ 60 · phishing ≤ 100
```
mapped to risk bands Safe / Low / Medium / High / Critical.

**Stage 6 — Explain.** `src/explainability/` (SHAP + a reason generator) turns the decision into investigator-readable sentences: *"Domain imitates the brand 'nabilbank'"*, *"Domain registered 3 days ago"*, *"No valid SSL certificate"*. A model that says "phishing, trust me" is useless as evidence; a model that shows its reasoning can go in a report.

Every connector **degrades gracefully**: missing API key or no network ⇒ that signal's weight is redistributed, and the system keeps working with the remaining evidence rather than crashing.

### 5.14 "Assemble the Evidence Intelligence Record" → Phase 2 begins

At this point one evidence item is fully processed. When the Investigator presses **Analyze** (`POST /cases/<id>/analyze/`), the Phase-2 orchestrator runs **eight modules** over the whole case (`investigation/pipeline.py`):

```
load evidence (read-only)
  → M1 correlation
  → M5 timeline                (canonical standalone reconstruction)
       → M2 graph              (uses correlation + reconstructed events)
       → M3 campaigns          (clusters over strong correlations)
       → M4 suspects           (uses correlation for relationship strength)
  → M6 analytics               (uses correlation, campaigns, timeline)
  → M8 prioritization          (uses analytics, correlation, campaigns, timeline)
  → M7 report                  (references every stored finding, incl. priority)
```

Two properties of this orchestrator are worth naming: **failure isolation** (each module runs inside a `safe()` wrapper; a broken module logs an audited ERROR and the case still completes with the other seven results) and **cross-case indexing before correlation** (this case's entities are written to the cross-case index *first*, so a case analysed later can match against them).

### 5.15 "Correlate Evidence and Entities" (M1)

**Code:** `investigation/correlation/service.py` + `investigation/config.py`.

For **every pair** of evidence items in the case (`itertools.combinations`), the engine evaluates **twelve factor types** and produces a weight, a bounded confidence, a relationship band, and a **narrative explanation containing the concrete matching values**. There is no machine learning here — deterministic weighted scoring only, precisely so that every link can be explained to a court.

The weights (`correlation_weights`) encode forensic judgement about how *identifying* each signal is:

| Weight | Factors | Reasoning |
|---|---|---|
| 1.00 | eSewa / Khalti / IME Pay ids, bank accounts, card numbers, BTC/ETH wallets, file hash | A wallet or account identifies one financial identity |
| 0.95 | transaction_ids | A shared transaction code is the same payment seen from both sides |
| 0.90 | phones, whatsapp_numbers | Strong personal identifier |
| 0.85 | emails, mac_addresses | |
| 0.80 | telegram/facebook/instagram usernames, threat_intelligence corroboration | |
| 0.75 / 0.70 | urls, social_media_urls, device_metadata | |
| 0.60 | domains, ipv4, ipv6 | Thousands of unrelated people share a domain |
| 0.50 / 0.40 | image_metadata, timeline_proximity | Weak, contextual |
| 0.25 / 0.20 | otp, money | Two people paying "Rs 5000" prove almost nothing |

Three guards keep the scoring honest:

* **Factor cap = 3** (`correlation_factor_cap`) — one spammy entity repeated twenty times cannot dominate a pair's score.
* **Bounded confidence** — `confidence = 1 − exp(−Σweights / 1.6)`. Weights add, but confidence saturates towards 1 and never exceeds it, so ten weak signals can never masquerade as one strong one.
* **Relationship bands** — confidence is then labelled `NO_RELATIONSHIP (<0.05) · WEAK (<0.30) · MEDIUM (<0.55) · STRONG (<0.80) · VERY_STRONG`. The investigator sees a word, not a raw float.

**Two scopes:**

* **Within-case** — pairs inside one case. A weaker `temporal_proximity` fallback edge is added for pairs with *no* shared entity but upload times within the proximity window (`timeline_proximity_hours = 48.0`), weighted 0.40 so a temporal-only link can never outrank a genuine entity match. *(Minor report-vs-code note: report §4.8 says a 24-hour window; the code's configured value is 48 hours — quote 48 and cite `investigation/config.py`.)*
* **Cross-case** — the same matching logic against the cross-case entity index (`investigation/crosscase.py`), so a phone number or wallet reappearing in an unrelated case produces a link. This is how a *reused scam infrastructure* is discovered — the feature with the most real investigative value in the whole system. Cross-case links expose **only** the matched normalised value plus the linked case/evidence ids; reading the other case's content still requires opening that case by its reference.

### 5.16 Loop: "Add more evidence?"

The Investigator can upload more items and re-run analysis. Re-analysis is **idempotent and versioned** — artifacts are rewritten with an incremented version (`v4 → v5`), so you can see that a case's cross-case picture changed after a new upload (or after an Administrator deleted a linked case).

### 5.17 "Reconstruct the Incident Timeline" (M5)

**Code:** `investigation/timeline/service.py`, which loads `timeline_reconstruction/timeline_reconstruction.py` as the canonical engine.

For each evidence item, a **four-tier timestamp resolution** strategy picks the best-supported event time:

| Tier | Source | Confidence | Meaning |
|---|---|---|---|
| 1 | Explicit date **and** time extracted from the evidence content | High | When the message was actually sent |
| 2 | Time-only value + a date from the same item/context | Medium | Best-supported reconstruction |
| 3 | Inline chat timestamp matched by a dedicated regex (`(\d{1,2})-(\d{1,2}), (\d{1,2}):(\d{2})`) | Medium | Chat-app header lines |
| 4 | System **upload time** | Low, and explicitly labelled *acquisition time* | Not an event time |

Items with **no** resolvable timestamp are marked `unresolved` and placed at the **end** of the timeline — never guessed into a position. Resolved events are sorted, annotated with risk signals, attack-stage classification, milestones, and the items they correlate with, then written to `timeline.json` plus a flat narrative text consumed by the report generator.

**Be ready to defend the honest weakness here.** Our own evaluation (Table 6.5 in `EVALUATION_RESULTS.md`) found: order accuracy **1.00**, but timestamp MAE ≈ 134 days on the demo case — because the engine resolved *upload time* (July 2026) rather than the *content date* (January 2026) written inside the WhatsApp text. That is a real, reportable finding about the tier-1 extractor's coverage on that evidence, and we report it rather than hiding it. The fix is better in-content date extraction, not a change to the tier logic.

### 5.18 M2 Graph · M3 Campaigns · M4 Suspects · M6 Analytics · M8 Priority

* **M2 Graph** (`graph/service.py`) converts case data + M1 correlations + M5 events into a **typed graph**: nodes for the case, each evidence item, each promoted entity and each timeline event; edges typed `contains` (structural), `shared_entity`, `temporal_relationship`, `behavioral_relationship`, `threat_relationship`, `cross_case`. Outputs `graph.json`, `graph_statistics.json`, `graph_summary.json`. It is **visualisation-independent** — pure data, no rendering assumptions.
* **M3 Campaigns** clusters evidence over strong correlations: is this one scam operation or three unrelated ones?
* **M4 Suspects** builds actor profiles around identity anchors (wallet > phone > social handle > email), weighted by `suspect_weights`.
* **M6 Analytics** aggregates entity mix, threat levels, payment rails, quality metrics for the charts.
* **M8 Prioritization** produces a case priority score from analytics + correlation + campaigns + timeline, so a unit with fifty open cases knows which to work first.

### 5.19 "Generate Graph-Theoretic Investigation Report" (M7)

**Code:** `investigation/reporting/service.py` (+ `pdf_renderer.py`).

The report is assembled **exclusively from stored findings**, and every sentence is a **template over concrete values** — evidence ids, hashes, scores, entity values, timestamps. The docstring states the design goal directly: *the generator has no free-text capability, so it cannot hallucinate.* A missing input produces an explicit "not available" statement rather than invented prose.

Outputs `investigation_report.md` + `investigation_report.json` (and PDF), downloadable from the Reports tab. Every finding is traceable to an evidence id and its SHA-256.

**This is the answer to "can an LLM be trusted in forensics?"** — in this system, no LLM writes any report text. The only model that touches text is XLM-R, and it is restricted to yes/no verdicts on rule-proposed words (§5.12).

### 5.20 "Review Graph, Timeline and Investigation Insights"

The Investigator works through the seven tabs. The Graph tab renders `graph.json` with **Cytoscape.js** + the **fCoSE** layout extension (`ciis_frontend/src/features/graph/GraphCanvas.tsx`): three layout modes (structure / force / circle), node size scaled by degree so hub entities read as important (capped so one busy node never dwarfs the rest), and a colour/線-style legend per edge type. Analytics renders with Recharts, behind a `SmartChart` wrapper that detects empty-or-all-zero data and prints a plain-language reason instead of a blank plot.

### 5.21 Decision: "Do investigators need more analysis?" → planned RAG (dashed boxes)

The dashed boxes — **Planned RAG Investigation Assistant** and **ChromaDB Vector Store** — are **future work and are not implemented**. Nothing in the current pipeline depends on them. The intended design is LangChain orchestration over a ChromaDB index of case evidence/entities/correlations/timeline events, with every assertion required to carry a citation to a stored artifact, and its output **explicitly barred from the forensic report**. Say "planned, not implemented" plainly; the report says the same in §4.10.

### 5.22 END

The case now holds: original evidence bytes with a verified hash chain, four text layers per item, a validated entity set, threat verdicts on every URL, a weighted correlation analysis (within *and* across cases), a graph, a timeline, analytics, a priority score, and a hash-traceable report — from a pile of screenshots, in about **8 seconds per 3-item case** (measured: 7.945 s Phase-1 + 0.057 s Phase-2 for `CASE_2CF24DBA5F`).

---

## 6. End-to-end timing (measured, real)

From `scripts/aggregate_processing_time.py` summing `duration_ms` rows for real case `CASE_2CF24DBA5F` (3 evidence items):

| Phase | Time |
|---|---|
| Phase-1 (acquire + hash + preprocess + OCR + store) | 7.945 s |
| Phase-2 (all 8 analysis modules) | 0.057 s |
| **End-to-end** | **8.001 s** |

Note the ratio: **99.3% of the time is OCR**, and all eight analysis modules together cost 57 milliseconds. If asked "how would you make it faster", the answer is GPU inference or batched OCR — not algorithmic changes to correlation. The script deliberately **avoids double-counting** the `pipeline` / `phase2_pipeline` umbrella rows; a naïve sum gives 15.9 s, which would be wrong.

---

## 7. Testing

| Suite | Test functions in the tree today | Run with |
|---|---|---|
| Evidence / OCR engine | **424** (58 core + 63 cleaning + 61 enhancement + 24 evaluation + 50 forensics + 114 investigation + 17 ocr-forensics + 37 semantic) | `cd evidence_ocr_engine && pytest` |
| Threat intelligence system | **310** | `cd threat_intelligence_system && pytest` |
| Django API | **48** | `cd ciis_api && pytest` |
| Frontend (Vitest) | 12 | `cd ciis_frontend && npm test` |
| Prototype suites (deprecated dirs) | 17 | — |

The mid-defence report's Appendix D cites **~308** (evidence/OCR) and **303** (threat intelligence); those were the counts when the report was written, and the suites have grown since. See Q8 (§13.8) for exactly how the two suites are run and what they assert.

---

## 8. Engineering practices (the part examiners award marks for)

* **Clean architecture / SOLID.** One job per file: `hash_service.py` only hashes, `pdf_processor.py` only renders PDFs, `paddle_service.py` only OCRs. Collaborators arrive through constructors (**dependency injection**), which is why the test suite can inject a fake OCR engine and run 424 tests in seconds without PaddleOCR installed. Storage uses the **repository pattern** (one class per CSV), OCR/language-detection/semantic-validation use the **strategy pattern** (abstract base + interchangeable implementations — `BaseOCR`, `BaseLanguageDetector`, `BaseSemanticValidator`).
* **Composition roots.** `build_default_pipeline()` in each phase is the single place where the real object graph is wired, so production wiring and test wiring never diverge silently.
* **Failure isolation.** Phase-1 forensics and Phase-2 analysis both wrap each module; one failure is audited and the run continues.
* **Type hints + Pydantic** on every public output, so the JSON contract is validated automatically and documented in one place (`schemas.py`, `cleaning_schemas.py`, `enhancement_schemas.py`, `semantic_schemas.py`).
* **Deterministic and local.** No Google Translate, no cloud OCR, no LLM in the pipeline. Same input → same output, every time — which is what makes the results reproducible for a reviewer.
* **Atomic file writes** (temp file + rename) and per-file locks in `api/store.py`, because the upload worker writes from a background thread.
* **Graceful degradation everywhere.** Missing VirusTotal key, no network, no `torch`, no PaddleOCR — each is handled with a fallback and an audit entry, never a crash.

---

## 9. Where every piece of data lives (no database)

| What | Where |
|---|---|
| Untouched evidence copies | `storage/originals/` |
| Chain of custody (hashes, status) | `storage/evidence.csv` |
| Case registry (reference → hashed id) | `storage/case_registry.csv`, `storage/cases.csv` |
| Per-stage audit trail with timings | `storage/processing_log.csv` |
| OCR summaries + cleaning preview | `storage/ocr_results.csv` |
| Full per-case results (4 text layers, confidences, boxes, hashes) | `storage/json/CASE_XXXX.json` |
| All extracted entities | `storage/entities.csv` |
| Keyword & risk-signal counts | `storage/keyword_statistics.csv` |
| Every OCR correction with confidence + rule | `storage/ocr_corrections.csv` |
| Phase-1 forensic reports | `storage/forensics/` |
| Phase-2 artifacts (correlation, graph, timeline, analytics, report) | `storage/investigation/<CASE_ID>/*.json` |
| Cross-case entity index | `storage/investigation/cross_case_index*` |
| Platform state: jobs, notifications, activity log | `storage/platform/{jobs.json, notifications.json, activity_log.csv, case_meta.csv, case_history.csv}` |
| Runtime logs | `logs/evidence_engine.log` |

**Why no database at all?** Four defensible reasons: **(a) Reproducibility** — a reviewer clones the repo, runs it on any laptop, and gets identical results with no server to install or migrate. **(b) Inspectability** — a forensic exhibit register you can open in Excel and read is easier to defend than an opaque binary table. **(c) Deployment reality** — a Nepali police unit deploying this offline should not need a DBA. **(d) Honesty about scale** — this is a research prototype at case scale, not a national system; CSV is genuinely sufficient for it, and we say so rather than adding PostgreSQL for appearances. The cost is real and we name it: no transactions, no concurrent multi-writer safety beyond our own file locks, and linear scans instead of indexed queries. We mitigate with atomic writes, per-file locks and an mtime-keyed read cache in `api/engine.py`. Migrating to a database later means replacing the repository classes only — that is exactly what the repository pattern is for.

---

## 10. Datasets used

**URL / phishing classification** (`sample/`, and the merged product in `data/processed/`):

| File | Rows | Notes |
|---|---|---|
| `StealthPhisher2025.csv` | 336,750 | Pre-featurised phishing corpus |
| `dataset2.csv` | 149,728 | Auxiliary phishing-URL dataset (URL, Label) |
| `PhishBD_2026.csv` | 131,168 | URL + label + precomputed lexical columns |
| `PhishTank_2026.csv` | 64,281 | Community-verified phishing URLs |
| `phishing_email_detection_2026_dataset.csv` | 1,501 | Email-level features (sender, urgency, links) |

After discovery → cleaning → validation → **cross-dataset conflict removal** (URLs labelled differently in two sources are dropped) → deduplication → balancing → stratified split, the merged training corpus was **585,040 URLs** (305,573 phishing / 279,467 legitimate) with a **70/15/15** train/validation/test split. Held-out test set = **87,756 rows**. Recorded in `checkpoints/production_model.json` (`dataset_version ds-20260712T090000Z`).

**OCR / entity extraction:** collected and synthesised Nepali cybercrime evidence — chat screenshots (WhatsApp/Messenger/Telegram style), scam SMS, phishing-email screenshots, eSewa/Khalti/IME Pay payment screenshots, scanned PDFs — in English, Devanagari and Roman Nepali (`evidence_ocr_engine/samples/`). Ground truth is **manual transcription** compared against pipeline output (`samples/ground_truth/`). This corpus is currently small (**n = 3** images for the demo OCR table), which we report honestly as a limitation, not a result.

---

## 11. Evaluation status — what is real and what is not

Straight from `EVALUATION_RESULTS.md`. Knowing this table cold is the single best defence preparation, because it lets you answer "are these numbers real?" before it is asked.

| Table | Status | Source |
|---|---|---|
| 6.1 OCR (CER/WER) | 🟡 demo, real OCR | 3 sample images (n=3) |
| 6.2 Entity extraction | 🟡 demo | 2 sample images; regex-only P 0.833 / R 1.000 / F1 0.909 |
| **6.3 URL classification** | 🟢 **real** | 87,756-row held-out test set |
| 6.4 Correlation | 🟡 demo | 4 real storage cases; within-case F1 = 1.00 vs 0.00 for both baselines |
| 6.5 Timeline | 🟡 demo | 1 real case; order accuracy 1.00, timestamp MAE ≈ 134 days (the resolution gap) |
| 6.6 RAG | ⚪ not implemented | — |
| **6.7 End-to-end** | 🟢 **real** | 8.001 s measured |
| **6.8 Security** | 🟢 **real (test-backed)** | 4 threats, 4 passing tests |

The evaluation harnesses **refuse to emit numbers from a template** — `run_table_6_1.py` and `run_table_6_4.py` error out rather than score an ungraded gold file. That refusal is deliberate: it makes fabricating a result impossible by accident.

Table 6.8 in full:

| # | Threat | Result | Backing test |
|---|---|---|---|
| 1 | Unauthorized API access | **Open by design** (not blocked) | `api/tests/test_security_posture.py` |
| 2 | Evidence-file tampering | **Detected** (SHA-256) | `tests/test_hash_service.py::test_verify_detects_tampering` |
| 3 | Homoglyph phishing URL | **Detected** (component-level) | `tests/test_brand_intelligence.py` |
| 4 | Oversized upload (>50 MB) | **Rejected** (HTTP 400) | `api/tests/test_evidence.py::test_upload_rejects_oversized` |

Row 1 is stated honestly rather than dressed up: the Investigator engine is open by design, and there is a passing test proving that unauthenticated requests are *permitted* (never 401/403), so the claim matches the behaviour.

---

## 12. Report vs. code — the five differences, in one place

Read these before the viva. An examiner comparing the PDF with the repository will find them, and having the answer ready converts a weakness into a strength.

| # | The report says | The code does | What to say |
|---|---|---|---|
| 1 | JWT auth, roles, `/api/auth/login/`, role-filtered case lists | Open reference-addressed engine + password-gated Administrator panel; `require()` is a documented no-op | Deliberate change recorded in `AUDIT.md` (2026-07-23/25); restoring RBAC means changing one function, not fifty views |
| 2 | 22 correlatable entity types | 30-type schema, 24 used as correlation keys | The extractor grew during implementation; cite `ENTITY_TYPE_GROUPS` |
| 3 | "NetworkX constructs correlation graphs" | Live `graph/service.py` uses **pure-Python** graph algorithms; NetworkX is in `ciis_api/requirements.txt` and in the **deprecated** prototype `evidence_correlation_engine/graph_builder.py` (a `MultiDiGraph` with centrality + greedy-modularity communities) | See Q3 (§13.3) — answer honestly: NetworkX shaped the design and remains the analytics path; the integrated engine dropped the dependency deliberately |
| 4 | `timeline_reconstruction/` is a superseded prototype (per its own `DEPRECATED.md`) | It was **un-deprecated**: the integrated `TimelineService` loads it as the canonical engine | The `DEPRECATED.md` in that folder is stale; the live import in `timeline/service.py` is the truth |
| 5 | ~308 / 303 tests | 424 / 310 test functions today | Counts at report time; the suites grew |

---

# PART C — QUESTION BANK

## 13. The questions you asked

### 13.1 How does OCR perform processing?

Answer it in two levels: what our *system* does around OCR, and what happens *inside* PaddleOCR.

**Level 1 — the system's OCR stage** (`evidence/pipeline.py::_extract_pages`): route by file type → load image → `assess_quality()` → conditional `preprocess()` on an in-memory copy → `PaddleOCRService.recognize()` under a hard timeout → collect `OCRLine(text, confidence, bounding_box)` per line → assemble `raw_text` in reading order → persist to case JSON + CSV → re-hash the original to prove it is unchanged.

**Level 2 — inside PaddleOCR PP-OCRv5**, three neural stages in sequence:

1. **Text detection** — a segmentation-based detector (the DB / Differentiable Binarization family) runs a lightweight CNN backbone with an FPN neck over the whole image and predicts, per pixel, a probability map of "is this text?" plus a threshold map. Differentiable binarisation makes the thresholding step trainable rather than a fixed post-processing cutoff. Connected components in the binarised map are expanded (Vatti clipping) into **quadrilateral boxes**, one per text line. This is the stage that suits chat screenshots: it finds *short, irregularly placed* regions, whereas layout-analysis approaches assume page-like blocks.

2. **Rectification / cropping** — each quadrilateral is cropped and perspective-warped to a fixed-height horizontal strip (typically 48 px tall). A tilted bubble or an angled photo becomes a straight line of text before recognition. An orientation classifier can rotate a box 180° when needed.

3. **Text recognition** — each strip goes through a CRNN-style recogniser: a CNN backbone (PP-LCNet in v5) produces a feature sequence along the strip's width; a sequence head (BiLSTM / lightweight attention) models context; and a **CTC (Connectionist Temporal Classification)** head emits, at each of T horizontal timesteps, a probability distribution over the character dictionary plus a special *blank* symbol.

   CTC decoding is the key idea worth explaining: the model never has to know *where* each character starts. It emits a per-timestep distribution, then the decoder collapses repeats and removes blanks — so `h-h-e-∅-l-l-∅-l-o` decodes to `hello`. Greedy decoding takes the argmax per timestep. The line's **confidence** is derived from those per-timestep probabilities (in practice the mean of the selected characters' probabilities), which is why confidence is a *per-line* number and why it is a meaningful proxy for "how readable was this line".

   Our `lang="ne"` selects `devanagari_PP-OCRv5_mobile_rec`, whose character dictionary contains Devanagari **and** Latin characters. This is exactly why one pass reads a screenshot containing "पैसा pathaunus 9841234567".

4. **Post-processing (ours, not Paddle's)** — lines are sorted into reading order, stored verbatim with confidence and box, and *nothing else*. Correction is a separate, later, gated stage (§5.12).

### 13.2 Why PaddleOCR instead of Tesseract?

The proposal specified Tesseract, following Hutchins et al.'s dashcam-video comparison. We changed it during implementation for **four evidence-driven reasons**, and the report documents the change openly in §4.4.2 rather than quietly swapping it.

1. **Mixed-script recognition in a single pass.** Our evidence routinely mixes Devanagari, Latin and Roman Nepali *inside one screenshot*. Tesseract handles this by running with `-l nep+eng`, which in practice means reconciling two engine passes and produces unstable results at script boundaries. PaddleOCR's `ne` model has one dictionary spanning both scripts, so one pass reads the whole line. Fewer passes = fewer reconciliation heuristics = fewer places to corrupt evidence.

2. **Per-line confidence is a hard requirement, not a nice-to-have.** Our entire correction architecture (§5.12) is *gated on OCR confidence*: ≥ 0.90 forbids all correction, < 0.30 unlocks fuzzy matching. PaddleOCR returns a clean per-line confidence in [0,1] natively. Tesseract exposes per-word confidences through TSV/hOCR output, but they are heuristics of a different character and are awkward to map onto lines. **Without reliable per-line confidence, our confidence-gated correction module could not exist.** This is the strongest single reason and the one to lead with.

3. **Detection quality on screenshot layouts.** Tesseract's page-segmentation modes were designed for scanned documents — columns, paragraphs, page structure. A WhatsApp screenshot is short bursts of text at irregular positions on coloured bubbles, and we observed Tesseract's segmentation struggling with it. PaddleOCR's DB detector makes no page-layout assumption; it finds text regions wherever they are.

4. **Modern architecture and Devanagari quality.** PP-OCRv5 is a current deep-learning pipeline (DB detector + CRNN/CTC recogniser) whose multilingual models are actively maintained. Tesseract 5's LSTM engine is capable but its Nepali traineddata is weaker on the noisy, low-resolution, colour-background images that make up most of our corpus.

**The honest caveats to volunteer** (examiners respect this): Tesseract is lighter, installs anywhere, and needs no model download; PaddleOCR pulls ~100 MB of models on first run and a heavier Python stack. And we did *not* run a head-to-head CER benchmark on our own corpus — the choice was made on the four architectural grounds above plus observation during implementation. A Tesseract-vs-PaddleOCR CER/WER comparison on a proper 30–100 image bilingual corpus is named future work. Note also that we already have the infrastructure for such a comparison: `forensics/multi_ocr/` runs multiple engines and fuses their output.

### 13.3 Why NetworkX and Cytoscape.js?

Answer this one carefully and honestly, because it is the place where the report and the code differ most (difference #3 in §12).

**The division of labour is: NetworkX computes, Cytoscape.js draws.** They are not alternatives — one is a Python graph-analysis library with no rendering, the other is a browser rendering library with limited analysis. You need both, on opposite sides of the HTTP boundary.

**Why NetworkX (Python side).** Correlation output is naturally a graph: evidence items and entities are nodes, shared identifiers are edges. Once it is a graph, the questions an investigator asks are classical graph questions — *which entity connects the most evidence* (degree/betweenness centrality), *which items form one operation* (community detection), *how is this suspect connected to that wallet* (shortest path). NetworkX gives all of that as one-line calls on a `MultiDiGraph`, and it is the de-facto standard so the code is readable to any reviewer. Our prototype `evidence_correlation_engine/graph_builder.py` uses exactly this: `networkx.MultiDiGraph`, `nx.NetworkXNoPath` handling for path queries, and `greedy_modularity_communities` for campaign clustering. `networkx>=3.0,<4.0` is a declared dependency in `ciis_api/requirements.txt`.

**What changed in the integrated engine — say this plainly.** When the graph builder was integrated into the product (`investigation/graph/service.py`), it was rewritten with **pure-Python graph algorithms and no NetworkX dependency**. The docstring says so: *"Pure-Python graph algorithms (no networkx needed)."* Three reasons: (a) the live graph service only needs typed node/edge construction and simple statistics, not centrality or community detection — those live in the analytics path; (b) dropping a dependency from the request path keeps the Django worker light and import-time small; (c) failure isolation is simpler with no third-party graph state. So the correct statement in a viva is: **"NetworkX shaped the graph design and remains the dependency for graph-theoretic analysis; the integrated per-request graph builder is dependency-free by deliberate choice."** Do not claim the live product builds its graph with NetworkX — an examiner reading `graph/service.py` will find otherwise.

**Why Cytoscape.js (browser side).** It is purpose-built for interactive *network* visualisation, unlike D3 (a general drawing toolkit where you would implement node dragging, zoom and layout yourself). Concretely we use: the **fCoSE** layout extension for force-directed placement of a compound graph; three switchable layout modes (`structure`, `force`, `circle`); a per-edge-type visual language with a rendered legend (`contains` grey solid, `shared_entity` teal solid, `temporal_relationship` amber dashed, `behavioral_relationship` blue dotted, `threat_relationship` red solid, `cross_case` purple dashed); node sizing by degree, capped so a hub cannot dwarf its neighbours; and click-to-select wired to a details panel. It handles a few thousand elements in a browser without hand-written canvas code, and it has first-class TypeScript types.

**And the clean-architecture point:** `graph/service.py` emits `graph.json` that is *visualisation-independent* — pure data, no colours, no coordinates. The engine does not know Cytoscape exists. Swap the frontend for D3, Sigma.js or a desktop viewer and no Python changes.

### 13.4 Is your system autonomous? (short)

**No — it is autonomous in execution, but not in judgement. It is a decision-support system, not a decision-maker.**

Once evidence is uploaded the entire pipeline runs unattended — OCR, cleaning, entity extraction, correction, classification, correlation, timeline, report — with no human step in between. But every output is an *assisted finding, not a verdict*: URLs get a probability and a 0–100 score with reasons, correlations get an explainable confidence band, timestamps carry an explicit confidence tier, unresolved items are flagged rather than guessed, and the report generator cannot write a sentence that is not a template over a stored value. Nothing is filed, charged or concluded without an investigator. And the two human control points are deliberate: the investigator triggers analysis, and the Administrator alone can delete.

### 13.5 What is the mathematical formula of SHA-256 hashing?

SHA-256 is not one formula but a specified sequence. Here is the whole thing, compactly, in the form you can write on a board.

**Setup.** Message `M`, output 256 bits, block size 512 bits, word size 32 bits. All arithmetic is **mod 2³²**.

**(1) Padding.** Append a single `1` bit, then `k` zero bits, then the 64-bit big-endian length `l` of the original message, where `k` is the smallest non-negative solution of

$$l + 1 + k \equiv 448 \pmod{512}$$

The padded message is an exact multiple of 512 bits, split into blocks `M⁽¹⁾…M⁽ᴺ⁾`.

**(2) Initial hash value** `H⁽⁰⁾` = eight 32-bit words = the fractional parts of the square roots of the first 8 primes (2,3,5,7,11,13,17,19):

```
6a09e667  bb67ae85  3c6ef372  a54ff53a  510e527f  9b05688c  1f83d9ab  5be0cd19
```

**(3) Constants** `K₀…K₆₃` = fractional parts of the **cube** roots of the first 64 primes (`428a2f98`, `71374491`, … , `c67178f2`).

**(4) Logical functions** (⊕ = XOR, ¬ = NOT, ∧ = AND, `ROTR` = right rotate, `SHR` = right shift):

$$Ch(x,y,z) = (x \wedge y) \oplus (\neg x \wedge z)$$
$$Maj(x,y,z) = (x \wedge y) \oplus (x \wedge z) \oplus (y \wedge z)$$
$$\Sigma_0(x) = ROTR^{2}(x) \oplus ROTR^{13}(x) \oplus ROTR^{22}(x)$$
$$\Sigma_1(x) = ROTR^{6}(x) \oplus ROTR^{11}(x) \oplus ROTR^{25}(x)$$
$$\sigma_0(x) = ROTR^{7}(x) \oplus ROTR^{18}(x) \oplus SHR^{3}(x)$$
$$\sigma_1(x) = ROTR^{17}(x) \oplus ROTR^{19}(x) \oplus SHR^{10}(x)$$

**(5) Message schedule.** For each 512-bit block, expand its sixteen 32-bit words into 64:

$$W_t = \begin{cases} M_t^{(i)} & 0 \le t \le 15 \\[4pt] \sigma_1(W_{t-2}) + W_{t-7} + \sigma_0(W_{t-15}) + W_{t-16} & 16 \le t \le 63 \end{cases}$$

**(6) Compression.** Initialise `a,b,c,d,e,f,g,h := H⁽ⁱ⁻¹⁾`, then for `t = 0 … 63`:

$$T_1 = h + \Sigma_1(e) + Ch(e,f,g) + K_t + W_t$$
$$T_2 = \Sigma_0(a) + Maj(a,b,c)$$
$$h{=}g,\; g{=}f,\; f{=}e,\; e = d + T_1,\; d{=}c,\; c{=}b,\; b{=}a,\; a = T_1 + T_2$$

**(7) Block update (Davies–Meyer feed-forward).**

$$H_j^{(i)} = a_j^{(64)} + H_j^{(i-1)} \pmod{2^{32}}, \quad j = 0..7$$

**(8) Output.** The digest is the concatenation `H₀⁽ᴺ⁾ ‖ H₁⁽ᴺ⁾ ‖ … ‖ H₇⁽ᴺ⁾` = 256 bits = **64 hexadecimal characters**.

If asked for one line: *SHA-256 is a Merkle–Damgård construction whose compression function is a 64-round block cipher used in Davies–Meyer mode, with the previous chaining value fed forward by modular addition.*

### 13.6 How is data stored in your system?

Two record families, both plain files, deliberately kept apart. Full table in §9.

1. **The forensic source of truth** (`evidence_ocr_engine/storage/`): original evidence bytes in `originals/`; the chain-of-custody register `evidence.csv`; the case registry; the per-stage audit `processing_log.csv`; the complete per-case JSON with all four text layers, per-line confidences and bounding boxes; `entities.csv`; `ocr_corrections.csv`; Phase-1 forensic reports; Phase-2 artifacts under `storage/investigation/<CASE_ID>/`.
2. **Platform state** (`storage/platform/`): background jobs, notifications, activity log, case metadata — written by `api/store.py` with **atomic writes (temp file + rename)**, **per-file locks** (the upload worker writes from a background thread) and auto-increment ids for JSON records.

**No database server anywhere.** `DATABASES = {}` in `ciis_api/config/settings.py`; the SQLite file, the five Django models, all migrations and the whole `accounts/` app were deleted on 2026-07-25 (recorded in `AUDIT.md`). Justification — and the honest costs — in §9. One consequence worth knowing: because admin sessions use a **signed** token rather than a stored one, removing the database did not cost us the Administrator panel.

### 13.7 On which dataset did you perform training?

Only the **URL/phishing classifier** was trained. Full table in §10. Headline numbers to memorise:

* Five source CSVs: StealthPhisher2025 (336,750), dataset2 (149,728), PhishBD_2026 (131,168), PhishTank_2026 (64,281), phishing-email dataset (1,501).
* After discovery → cleaning → validation → **cross-dataset label-conflict removal** → dedup → balancing → stratified split: **585,040 URLs** (305,573 phishing / 279,467 legitimate), **70/15/15**, held-out test **n = 87,756**.
* Labels are inherited from the source datasets (validated by their original publishers), not annotated by us.
* Provenance is pinned: `run_id 20260712T090000Z`, `dataset_version ds-20260712T090000Z`, `feature_version 2.0.0`, training duration 1,652 s. Six of eight checkpoints were byte-verified against that run id.

No other model was trained. OCR uses pretrained PP-OCRv5 weights; XLM-R uses pretrained `xlm-roberta-base` at inference only; cleaning, entity extraction, correlation and timeline contain **no learned parameters at all** — they are deterministic rules.

### 13.8 How are the 303 and 308 tests run (threat intelligence and OCR)?

**Where the numbers come from.** Appendix D, Table D.1 of the mid-defence report: "Evidence / OCR engine ≈ 308" and "Threat intelligence system 303". Both are **pytest** suites, each self-contained in its own folder with its own `pytest.ini` and its own virtual environment.

**Running them:**

```bash
# Evidence / OCR engine  (report: ~308; tree today: 424 test functions)
cd evidence_ocr_engine
.venv\Scripts\activate            # Windows
pytest                            # pytest.ini: testpaths = tests, addopts = -q, pythonpath = .

# Threat intelligence system  (report: 303; tree today: 310)
cd threat_intelligence_system
pytest                            # pytest.ini: testpaths = tests, pythonpath = .

# Django API (48) and frontend (12), for completeness
cd ciis_api && pytest             # pytest-django, DJANGO_SETTINGS_MODULE = config.settings
cd ciis_frontend && npm test      # Vitest
```

**Why they run in seconds instead of hours** — this is the interesting engineering answer. The OCR suite does **not** call PaddleOCR. Because `EvidencePipeline` takes its OCR engine through **dependency injection** (`BaseOCR`), `tests/conftest.py` injects a deterministic fake engine that returns fixed lines and confidences. So all 424 tests exercise hashing, upload validation, PDF handling, storage, cleaning, entity extraction, keyword counting, confidence tiers, correction logging, semantic gating, correlation, graph, timeline and reporting **without a single model download**. The same discipline applies elsewhere: the semantic tests never download XLM-R, and the Table 6.3 provenance test *reads* the stored training report rather than retraining. That is the practical payoff of the strategy pattern, and it is a good thing to point at when asked "why does architecture matter?"

**Composition of the OCR-engine suite (424):** core 58 (hashing, upload, OCR contract, PDF, JSON/CSV storage, pipeline errors) · cleaning 63 · enhancement 61 · evaluation 24 · forensics 50 · investigation 114 · ocr-forensics 17 · semantic 37.

**What the suites actually assert** (report's own wording, verified in code):

* *Evidence/OCR:* original bytes and SHA-256 unchanged; `raw_text` immutable after creation; derived layers stored separately. Concretely `test_hash_service.py::test_verify_detects_tampering` flips a byte and asserts verification fails, and cleaning/enhancement tests assert `result.raw_text == original` byte-for-byte.
* *Threat intelligence:* feature-extraction shape stability (the pipeline always emits exactly 71 features in the pinned order), prediction-schema conformance, and **graceful degradation with missing API keys** — remove the VirusTotal key and the engine must still return a scored verdict from the remaining signals.

**Be precise in the viva:** say "the report cites ~308 and 303 at the time of writing; the suites have since grown to 424 and 310, and here is the command that prints the current number." Precision about your own numbers reads much better than defending a stale figure.

### 13.9 Did you train or fine-tune any model?

**Trained from scratch: yes, one — the URL/phishing classifier.** Eight classical models on 585,040 URLs × 71 features, with Optuna hyperparameter search (25 trials per tunable model), stratified 5-fold cross-validation, held-out test evaluation, calibration analysis and error analysis. XGBoost's tuned parameters: `max_depth 11, learning_rate 0.0862, n_estimators 186, subsample 0.693, colsample_bytree 0.918, reg_alpha 0.016, reg_lambda 0.450, gamma 0.055, min_child_weight 5`. Total training time 1,652 s. Pipeline: `src/training/full_retraining.py` (15 documented stages).

**Fine-tuned: no — deliberately, and we defend the choice.**

* **PaddleOCR PP-OCRv5** — pretrained weights, used as-is.
* **XLM-RoBERTa** — pretrained `xlm-roberta-base`, **inference only**, explicitly "training-free" (report §4.7). It is used as a fill-mask judge, not a generator.
* **No transformer URL classifier** — the proposal mentioned mBERT/RoBERTa; that path was not implemented. `config/settings.yaml` keeps a `transformer: 0.20` ensemble slot, and the report states plainly that no transformer is deployed. Do not claim otherwise.

**Why not fine-tune?** Three honest reasons: (a) **no labelled data** — fine-tuning an OCR recogniser or XLM-R needs thousands of annotated Nepali forensic lines, and our ground truth is a handful of hand-transcribed images; (b) **reproducibility** — a pretrained, pinned model gives identical output on any machine, which is what a forensic pipeline and a research evaluation both require; (c) **the architecture already anticipates it** — `BaseSemanticValidator` is a strategy interface, so a future fine-tuned validator drops in by changing one constructor argument, with no other code touched. Building the seam before you need it is the point.

### 13.10 Why XGBoost, and why is it better than the other 7 baselines?

Two parts: what the numbers say, and why the algorithm suits this problem.

**Part 1 — the measured comparison.** All eight models, identical features, identical splits, held-out test set **n = 87,756** (`results/full_retraining_report_20260712T090000Z.json`, Table 6.3 — one of the three *real* tables):

| Model | Precision | Recall | F1 | Accuracy | ROC-AUC | PR-AUC | FNR |
|---|---|---|---|---|---|---|---|
| **XGBoost** ⭐ | 0.9762 | 0.9838 | **0.9800** | 0.9790 | **0.9973** | **0.9977** | **0.0162** |
| LightGBM | 0.9748 | 0.9820 | 0.9784 | 0.9773 | 0.9968 | 0.9973 | 0.0180 |
| Random Forest | 0.9707 | 0.9806 | 0.9756 | 0.9744 | 0.9959 | 0.9965 | 0.0194 |
| Extra Trees | 0.9686 | 0.9818 | 0.9752 | 0.9739 | 0.9958 | 0.9963 | 0.0182 |
| Decision Tree | 0.9729 | 0.9725 | 0.9727 | 0.9715 | 0.9824 | 0.9779 | 0.0275 |
| Logistic Regression | 0.8841 | 0.9099 | 0.8968 | 0.8906 | 0.9475 | 0.9426 | 0.0901 |
| SVM | 0.8839 | 0.9102 | 0.8968 | 0.8906 | 0.9479 | 0.9436 | 0.0898 |
| Naive Bayes | 0.8540 | 0.7573 | 0.8027 | 0.8056 | 0.8935 | 0.8716 | 0.2427 |

XGBoost confusion matrix: TN 40,819 · FP 1,101 · FN 743 · TP 45,093 → MCC 0.9579.

**Selection was by a stated priority, recorded in the artifact**: `F1 → ROC-AUC → Recall → Precision`, and **accuracy is never used alone**. The stored justification string reads: *"Selected 'xgboost' using the priority F1 > ROC-AUC > Recall > Precision … Runner-up: 'lightgbm'."* Fixing the rule *before* looking at results is what stops post-hoc rationalisation.

**Read the table like an investigator, not a leaderboard.** The metric that matters operationally is **FNR — a missed phishing URL is a scam that proceeds**. On 45,836 phishing URLs: XGBoost misses 743, Naive Bayes misses 11,125 (15× worse), Logistic Regression and SVM miss ~4,120 (5.5× worse). Against LightGBM the margin is genuinely small (F1 0.9800 vs 0.9784, 80 fewer false negatives) and we should say so honestly rather than overclaiming; the decisive comparison is against the linear and probabilistic families, not against the runner-up gradient booster.

**Part 2 — why the algorithm fits this problem.**

1. **The data is tabular, heterogeneous and unscaled.** 71 engineered features mixing counts (`dot_count`), lengths, ratios, booleans and continuous entropies. Gradient-boosted trees split on thresholds, so they need **no feature scaling and no distributional assumptions**. Logistic Regression and SVM need scaling and assume a (near-)linear separating structure — which is precisely why they sit 9 points of F1 behind.
2. **The decision boundary is interaction-heavy.** "Long URL" alone is not phishing; "long URL **and** many subdomains **and** cheap TLD **and** brand-like token **and** domain 3 days old" is. Boosted trees compose these conjunctions natively, one split at a time. Naive Bayes assumes features are conditionally **independent** — catastrophically false here (`url_length`, `path_length` and `token_count` are strongly correlated), which is why its recall collapses to 0.757.
3. **Boosting corrects its own errors.** Each tree is fitted to the residuals of the ensemble so far, so successive trees specialise on the hard cases — the near-miss typosquats that matter most. A single Decision Tree has no such mechanism (F1 0.9727, and much weaker ROC-AUC 0.9824 because its probability estimates are coarse). Random Forest averages independent trees, reducing variance but never targeting residual bias.
4. **Regularisation and imbalance handling.** XGBoost has explicit L1/L2 (`reg_alpha`, `reg_lambda`), `gamma` minimum-split-loss, `min_child_weight`, plus row/column subsampling and `scale_pos_weight` — a fuller toolkit than Random Forest's depth limit, and it is what lets `max_depth 11` be safe.
5. **SHAP explainability is exact and fast for trees.** TreeSHAP gives exact Shapley values in polynomial time, so the report can say *"flagged because: brand distance 1 from 'nabilbank' (+0.31), TLD .top (+0.22), domain age 3 days (+0.18)"*. For an SVM with an RBF kernel you would fall back to slow, approximate KernelSHAP. **In a forensic system, explainability is not a bonus feature — an unexplainable verdict is not evidence.**
6. **Deployment fit.** CPU-only inference in milliseconds, a ~MB-scale `.ubj`/`.pkl` artifact, no GPU. SVM with 585k training rows is painfully slow to train and its prediction cost scales with support vectors.
7. **Runner-up honesty.** LightGBM was within 0.0016 F1. XGBoost was preferred on the stated priority order plus maturity of the SHAP/serialisation tooling. If asked "would LightGBM have been fine?" — yes, and saying so is the right answer.

### 13.11 How does SHA-256 work? (explain properly)

The formulas are in Q5; this is the conceptual explanation.

**What it is.** A cryptographic hash function: an arbitrary-length input mapped to a fixed 256-bit output, designed so that the output behaves like a random fingerprint of the input.

**The four properties we actually rely on:**

1. **Deterministic** — the same bytes always give the same digest, on any machine, in any year. This is what makes a hash a *fingerprint* rather than a checksum of convenience.
2. **Avalanche effect** — flip one bit of a 50 MB file and roughly *half* the output bits change. There is no "close" digest; a match is a match and a mismatch is total.
3. **Pre-image resistance** — given a digest, you cannot construct an input producing it (≈ 2²⁵⁶ work).
4. **Collision resistance** — you cannot find two different files with the same digest (≈ 2¹²⁸ work by the birthday bound). This is the property that matters for evidence: nobody can substitute a doctored screenshot that hashes identically to the original.

**How it achieves that, structurally.**

* **Merkle–Damgård construction.** The padded message is cut into 512-bit blocks and absorbed one at a time into a 256-bit *chaining value*, starting from the fixed IV. Each block's output is the next block's input, so the final digest depends on every bit of every block in order. Change byte 3 of a 50 MB file and every subsequent block's input changes.
* **The compression function is a block cipher in Davies–Meyer mode.** Each 512-bit block drives 64 rounds of mixing over eight 32-bit working registers. Every round applies `Ch` (a bitwise multiplexer: `e` chooses between `f` and `g`), `Maj` (bitwise majority vote), and the four Σ/σ functions built from **rotations and shifts at co-prime-ish distances** (2/13/22, 6/11/25, 7/18/3, 17/19/10). Rotations spread a change *across* the word; XOR and modular addition mix *non-linearly* — addition carries interact with XOR in ways that resist linear and differential cryptanalysis. After the 64 rounds, the *input* chaining value is added back to the output (the Davies–Meyer feed-forward), which makes the compression function one-way even though the underlying cipher is invertible.
* **Nothing-up-my-sleeve constants.** The IV and the 64 round constants are the fractional parts of the square and cube roots of the first primes. They are arbitrary-looking but publicly derived, so no one can claim a backdoor was hidden in them. This is a nice detail to drop in a viva — it shows you understand *why* the constants are what they are.
* **Message schedule expansion.** The 16 words of a block are expanded to 64 via `σ₀`/`σ₁`, so each block's bits influence many rounds rather than one — this is what prevents simple message-modification attacks.

**Why 256 bits and why SHA-2, not MD5/SHA-1?** MD5 (collisions since 2004) and SHA-1 (SHAttered, 2017) are broken for collision resistance, so a defence lawyer could argue a substituted exhibit is theoretically possible. SHA-256 has no practical collision attack and is what NIST, ACPO/UK digital-evidence guidance and standard forensic tooling use. Our system *extracts* MD5/SHA-1/SHA-512 as entity types when they appear in evidence, but the integrity chain itself is SHA-256 only.

### 13.12 How did you implement hashing, and how do you preserve evidence?

**The implementation** is `evidence/hash_service.py` — 60 lines, one job:

```python
def sha256_file(self, path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):   # 1 MB chunks
            digest.update(chunk)
    return digest.hexdigest()          # 64 lowercase hex characters
```

Three deliberate details: **streaming** in 1 MB chunks (a 50 MB exhibit never loads into RAM, and the API is unchanged for a 5 GB one); **binary mode** (`"rb"` — text mode would apply newline translation and change the digest across platforms); **case-insensitive comparison** in `verify()`. There are two verification entry points: `verify()` returns a bool and logs, `verify_or_raise()` throws `HashVerificationError` — so a caller must consciously choose whether a mismatch is recoverable.

Hashing is also used in a **second, unrelated role**: `case_registry.make_case_id()` hashes the *case reference* to derive a stable, non-enumerable case id (§5.1). Same primitive, different purpose — worth distinguishing if asked.

**Evidence preservation is seven mechanisms working together**, and this is the answer to give in full, because it is the project's strongest claim:

1. **Copy, never move.** The investigator's file is untouched. A copy goes to `storage/originals/` with a collision-proof name.
2. **Triple hash chain.** Hash before copy → hash after copy (must match, else abort) → hash after all processing (must match). `hash_verified: true` is recorded. Failure aborts loudly and is audited; it never proceeds silently.
3. **The append-only text layers.** `raw_text` → `cleaned_text` → `enhanced_text` → `semantic_text`. No stage overwrites an earlier one. Unit tests assert byte equality of the earlier layers after later stages run.
4. **In-memory processing only.** Preprocessing, OCR and every forensic analysis operate on copies in memory; the stored file is opened read-only. Hash #3 is the proof.
5. **The entity shield.** Private-use Unicode placeholders make it *structurally impossible* for a cleaning or correction rule to alter a URL, email, wallet or hash — the string is not present in the text while the rules run.
6. **The chain-of-custody register + audit trail.** `evidence.csv` records both hashes, timestamps and status per item; `processing_log.csv` records every stage, its outcome and its duration; the investigation audit records every analysis and every cross-case query. You can reconstruct exactly what the system did, when, and how long it took.
7. **Correction provenance.** `ocr_corrections.csv` logs original word, corrected word, the OCR confidence that permitted the change, the rule that produced it and the timestamp — and the semantic module additionally logs *which validator* (XLM-R or heuristic fallback) issued the verdict.

**The test that proves it:** `tests/test_hash_service.py::test_verify_detects_tampering` writes a file, records its hash, modifies one byte, and asserts verification fails. That is Table 6.8 row 2, and it is one of the three fully-real evaluation results.

### 13.13 Why XLM-RoBERTa?

**What it is used for — state this first, because it prevents the obvious misunderstanding.** XLM-R is *not* a classifier, *not* an NER model, and *not* a text generator in this system. It is a **context validator**: rule-based logic proposes a correction, and XLM-R answers one question — *does this candidate word fit this sentence?*

**Why a model is needed at all.** The rule layer (§5.12) can tell that `बोड` is a known misrecognition of `बोर्ड`, but it cannot tell whether `बोर्ड` makes sense *in this particular sentence*. Dictionaries know words; they do not know context. That is exactly what a masked language model provides.

**Why XLM-R specifically — five reasons:**

1. **It is genuinely multilingual, in one model.** XLM-R was pretrained on CommonCrawl in **100 languages including Nepali**, with a shared 250k SentencePiece vocabulary. Our evidence mixes Devanagari, English and Roman Nepali *inside one sentence*. Running separate English and Nepali models would need language routing per token and would break exactly at the mixed-script boundaries that matter most. One model, one pass.
2. **Masked language modelling is the right *task shape*.** XLM-R's pretraining objective *is* fill-in-the-blank. So validation needs no fine-tuning and no task head: mask the slot, run the fill-mask pipeline, compare the candidate's probability against the original's. `fits = score(candidate) ≥ 0.15 AND score(candidate) ≥ score(original)` (`validator.py`). A generative model would have been the wrong tool — we would have had to *stop* it from writing.
3. **It cannot corrupt evidence by construction.** The model only ever returns `ValidationVerdict(fits, confidence, reason)`. Candidates come from deterministic rules. There is no code path from model output into text. Compare this with an LLM-based corrector, which could silently rewrite `supp0rt@fake-bank.com` and destroy an identifier.
4. **mBERT was the alternative, and XLM-R is the stronger one.** XLM-R is trained on ~2.5 TB of CommonCrawl versus mBERT's Wikipedia-only corpus, and Nepali Wikipedia is small — so mBERT's Nepali representations are notably weaker. XLM-R also drops the next-sentence-prediction objective and uses a larger shared vocabulary, both of which help low-resource scripts.
5. **Inference-only fits our constraints.** No labelled Nepali OCR-correction corpus exists for us to fine-tune on, and pinning a pretrained model keeps the pipeline reproducible. `xlm-roberta-base` (~270M params) runs on CPU for the short lines we validate.

**And the fallback, which is part of the argument.** If `transformers`/`torch` is unavailable, `HeuristicSemanticValidator` (dictionary agreement + edit distance) takes over, and the audit log records which validator ran. So the system never *depends* on the model being present — the model improves precision when available, and provenance stays traceable when it is not. The validator sits behind `BaseSemanticValidator`, so a fine-tuned successor is a one-line swap.

### 13.14 Why regex, and not spaCy/NLTK NER as originally proposed?

The proposal said generic NER; we implemented **regular expressions**, and kept NER as an *evaluation baseline* (Table 4.1) rather than as the pipeline. Six reasons, and this is a defensible engineering position, not a shortcut:

1. **The targets are formally-defined strings, not linguistic entities.** A URL, an IPv4 address, an eSewa ID, a Bitcoin wallet, an OTP, a SHA-256 hash — every one of these has a *specification*. Regex matches specifications exactly. NER is built for `PERSON`, `ORG`, `LOC` — categories defined by usage and context, where statistical inference is genuinely required. Using a probabilistic model to find something a grammar defines exactly is the wrong tool.
2. **The domain-specific entities simply do not exist in any NER model.** No pretrained spaCy or NLTK model has ever heard of an **eSewa ID**, a **Khalti ID** or an **IME Pay ID**. These are Nepal-specific payment rails and they are the single most investigatively valuable entity type in our system (correlation weight **1.00**). Getting them from NER would mean annotating a Nepali corpus and training a custom model — months of labelling for entities a regex captures exactly today, *with context awareness*: `regex_patterns.py` matches on labelled context like "esewa id ma paisa pathaunus 98XXXXXXXX", not on bare digits.
3. **Determinism is a forensic requirement.** Same input → same entities, every time, with no model version, no random seed and no confidence threshold in the way. A statistical extractor that returns a phone number today and misses it after a library upgrade is not usable in evidence. And when a regex misses something, we can point at the exact pattern and fix it; when a model misses something, the answer is "retrain and hope".
4. **Precision matters more than recall for *identifiers*, and false positives are auditable.** A wrongly-extracted wallet ID could link two unrelated suspects. Regex plus explicit validation (IPv4 octets 0–255 via the `ipaddress` module, structural wallet/hash checks, trailing-punctuation stripping) gives tight, inspectable control. Our measured Table 6.2 result: **recall 1.000, precision 0.833, F1 0.909** — it found all five gold entities plus one extra derived domain.
5. **It works on multilingual and broken text.** OCR output has stray characters, broken lines and three scripts. A phone number is `9[678]\d{8}` regardless of whether the surrounding sentence is English, Devanagari or Roman Nepali. NER models degrade sharply on noisy, code-mixed, low-resource text — and spaCy has no Nepali model at all.
6. **Speed and dependency weight.** Thirty entity types extracted from a document in milliseconds, with zero model loading, on any machine. Phase-2's eight modules together take 57 ms partly because of this.

**The honest limitation to volunteer:** regex cannot extract *person names*, *organisation names* or *addresses* — genuinely contextual entities where NER is the right tool. Our system does not currently extract those, and that is a real gap. The principled answer is a **hybrid**: keep regex for specified identifiers, add NER for names/orgs — which is precisely why the report keeps generic NER as an evaluation baseline (`scripts/run_table_6_2.py` already supports a spaCy comparison run and skips cleanly when spaCy is absent). The seam is built; the comparison is future work.

---

## 14. Twenty more questions an examiner is likely to ask

**Q15. Why is there no database? Isn't that a weakness?**
See §9. Reproducibility, inspectability, offline deployability, and honesty about scale. The costs (no transactions, no indexed queries, limited concurrency) are real and named; mitigations are atomic writes, per-file locks and an mtime-keyed read cache. The repository pattern makes a future migration a per-class change.

**Q16. What are the four text layers, and why four?**
`raw_text` (verbatim OCR — the evidentiary baseline), `cleaned_text` (normalised, entity-shielded — analysis-ready), `enhanced_text` (confidence-gated dictionary corrections — improved readability), `semantic_text` (context-validated corrections — highest-quality reading). Four, because each stage's output must remain independently inspectable and independently challengeable in court. Every downstream module states which layer it consumed.

**Q17. What is the triple-agreement rule?**
A correction is written only when three independent signals agree: a dictionary produced the candidate, the OCR confidence tier permits that class of candidate, and a context check passes (same script, similar visual shape, bonus if the corrected word occurs elsewhere in the document). Any disagreement ⇒ no change. In forensics, not correcting is safer than guessing.

**Q18. Why weighted correlation instead of simple exact matching?**
Because not all matches are equally meaningful. A shared eSewa ID (weight 1.00) is near-proof of a link; a shared domain (0.60) may be coincidence; a shared money amount (0.20) is almost nothing. Exact matching treats all three identically and is either flooded with noise or blind. Our own Table 6.4: the weighted engine reaches within-case **F1 = 1.00** where both exact-match and unweighted baselines score **0.00**, because those cases had no shared *exact* entity within a case — the links came from weighted weak signals plus temporal proximity. That gap *is* the engine's contribution.

**Q19. How can ten weak signals not fake one strong link?**
Two guards. The factor cap (max 3 counted matches per factor) stops repetition, and the bounded confidence `1 − exp(−Σw/1.6)` saturates: weights add, confidence asymptotes to 1. Plus `timeline_proximity` is weighted 0.40 specifically so a temporal-only link lands in WEAK and can never outrank a genuine entity match.

**Q20. How does cross-case correlation not violate case privacy?**
A cross-case edge exposes only the matched **normalised entity value** plus the linked case/evidence ids. It does not expose the other case's content. Reading that case still requires opening it by its reference. The report's §4.8.1 additionally specifies an Administrator-approved scope policy; in the current code the Administrator surface is the password-gated panel (§2.2) — state the difference honestly.

**Q21. What happens if PaddleOCR / VirusTotal / XLM-R is unavailable?**
Each degrades gracefully, by design. No PaddleOCR ⇒ everything except image OCR still runs (and 424 tests pass with a fake engine). No VirusTotal key ⇒ its weight is redistributed among the remaining signals. No torch/transformers ⇒ the heuristic validator takes over and the audit records the fallback. No ML stack ⇒ `MLThreatIntelProvider.available == False` and the engine falls back to a static indicator file. Nothing crashes; every degradation is audited.

**Q22. Why is accuracy never used alone for model selection?**
Because accuracy hides the error that matters. A model can post high accuracy while missing a disproportionate share of phishing URLs — Naive Bayes has 80.6% accuracy and a **24.3% false-negative rate**. Our priority is F1 → ROC-AUC → Recall → Precision, fixed *before* results were inspected and recorded in `production_model.json`.

**Q23. Why emphasise PR-AUC and FNR?**
FNR because **a missed phishing URL is a scam that proceeds** — the asymmetric cost is the whole point of the system. PR-AUC because it is more informative than ROC-AUC when the positive class is what you care about and prevalence shifts between training data and deployment (a real police queue is not 52% phishing).

**Q24. How was class imbalance handled?**
The merged corpus was near-balanced by construction (305,573 / 279,467 ≈ 1.09:1), with an explicit balancing guard (`BALANCE_MAX_RATIO`) that triggers only if the ratio exceeds the configured limit. Splits are **stratified** so the ratio holds in train/val/test. XGBoost additionally supports `scale_pos_weight` if a future dataset is skewed.

**Q25. What stops the report generator from hallucinating?**
It has **no free-text capability**. Every sentence is a template over a stored value; a missing input yields an explicit "not available". No LLM writes any report text. The only model touching text is XLM-R, restricted to accept/reject verdicts on rule-proposed words.

**Q26. How long does processing take, and where does the time go?**
8.001 s for a real 3-item case: 7.945 s Phase-1 (dominated by OCR) and 0.057 s for all eight Phase-2 modules. 99.3% is OCR. Speeding it up means GPU inference or batching, not algorithmic changes.

**Q27. What is Shannon entropy doing in the feature set?**
It measures randomness. Legitimate domains are pronounceable (`nabilbank`); algorithmically generated phishing hosts are not (`x7kq2zvb`). Entropy `H = −Σ p(c) log₂ p(c)` over the character distribution captures that in one number, and we compute it separately for the URL, hostname, domain, path, subdomain and query (7 of the 71 features).

**Q28. What is Levenshtein distance doing in the feature set?**
Typosquat detection. `paypa1` is edit-distance 1 from `paypal`; `nabil-bank-verify` contains a brand token in a suspicious position. Brand features compute Levenshtein/Damerau distance to a known-brand list plus brand-in-subdomain and homoglyph flags (`config/brand_intelligence.yaml`, `official_domains.yaml`).

**Q29. What is a homoglyph attack, and do you detect it?**
Characters that render identically but differ in code point — Cyrillic «а» (U+0430) versus Latin "a" (U+0061), or `rn` versus `m`. Detection is live at component level: `security_features.py` flags it, `rule_engine.py` calls `BrandIntelligenceEngine._detect_homoglyphs`, and `tests/test_brand_intelligence.py` passes. It is Table 6.8 row 3, honestly cited as **component-level rather than end-to-end**, because `MLThreatIntelProvider` surfaces only the final verdict to the investigation engine.

**Q30. Why Django REST Framework and React specifically?**
Django because the engine is Python and DRF gives serialisation, versioned routing, permission classes and a mature testing story with almost no ceremony — and `api/engine.py` can import the engine directly, with no RPC layer or serialisation boundary to maintain. React 19 + TypeScript because the UI is genuinely stateful (polling jobs, an interactive graph, seven tabs), and TypeScript catches contract drift between engine JSON and UI at compile time (`tsc --noEmit` runs in the build). MUI for accessible components, TanStack Query for server-state caching and polling, Cytoscape.js for the graph, Recharts for analytics.

**Q31. Is `raw_text` really never modified? Prove it.**
Three proofs: (a) architectural — no module other than the Phase-1 pipeline has a write path to that field; (b) tested — cleaning and enhancement tests assert `result.raw_text == original` byte-for-byte; (c) cryptographic — the stored original re-hashes identically after all processing (`hash_verified: true`).

**Q32. Could this be used in a real court case today?**
Not yet, and claiming otherwise would be wrong. The forensic mechanics are there (SHA-256 chain of custody with tamper detection, immutable layers, full audit trail, non-hallucinating templated reports). What is missing: a validated OCR/entity corpus (current OCR ground truth is n = 3), legal admissibility review under Nepali evidence law, formal tool validation, and access control if it is deployed multi-user. It is a research prototype demonstrating a forensically-sound *architecture*, and it is presented that way.

**Q33. What is the weakest part of the system, honestly?**
The evaluation corpus. Tables 6.3, 6.7 and 6.8 are real; 6.1, 6.2, 6.4 and 6.5 run on demo gold (n = 3 images, 4 cases, 1 timeline case). The measured timestamp-resolution gap in Table 6.5 (MAE ≈ 134 days, because tier-1 in-content date extraction did not fire on that evidence) is a concrete, reportable defect we chose to publish rather than hide. Building a 30–100 item human-verified bilingual corpus is the top remaining task, and the harnesses that will consume it already exist and already refuse to emit fabricated numbers.

**Q34. What would you do next, with three more months?**
In priority order: (1) build the human-verified bilingual OCR/entity corpus and re-run Tables 6.1/6.2 for real; (2) fix tier-1 in-content date extraction and re-run Table 6.5; (3) run the Tesseract-vs-PaddleOCR CER benchmark the report currently argues architecturally; (4) add NER for person/organisation names alongside regex; (5) implement the RAG assistant with mandatory citations and its output barred from the forensic report; (6) restore RBAC on top of the two-panel model for multi-user deployment.

---

## 15. Ninety-second summary (for the opening of your defence)

> CIIS takes the pile of screenshots a cybercrime complaint actually arrives as, and turns it into structured, correlated, court-defensible intelligence — without ever altering the evidence.
>
> Evidence is hashed with SHA-256 three times and copied, never moved. Images are measured and then adaptively preprocessed, and PaddleOCR PP-OCRv5 with the Devanagari multilingual model reads English, Nepali and Roman Nepali in a single pass, returning per-line confidence and bounding boxes. Text passes through four **additive** layers — raw, cleaned, enhanced, semantic — where entities are shielded by private-use Unicode placeholders so no cleaning rule can ever damage a URL or a wallet ID, corrections are gated by the OCR's own confidence and a triple-agreement rule, and XLM-RoBERTa acts purely as a context *judge* that can never generate text. Thirty entity types are extracted by validated regex; twenty-four of them are correlation keys.
>
> URLs go to a threat subsystem that computes 71 engineered features and classifies with XGBoost — chosen from eight models on a real 87,756-row held-out test set by a pre-declared F1 → ROC-AUC → Recall → Precision priority, reaching F1 0.9800 and a 1.62% false-negative rate — then fuses ML, rules and live intelligence into an explainable 0–100 score.
>
> Eight Phase-2 modules then correlate evidence within and across cases using explainable weighted scoring, reconstruct a four-tier timeline that flags rather than guesses unresolved times, build a typed relationship graph rendered with Cytoscape.js, and generate a hash-traceable report assembled entirely from templates over stored values, so it cannot hallucinate. All of it in eight seconds per case, into plain CSV and JSON files with no database, through two panels: an Investigator workspace reached by case reference, and a password-gated Administrator panel that alone can enumerate and delete cases — with a cascade that re-analyses every case the deleted one touched.

---

*Every claim in this document was read out of the source tree. File paths are given so any of it can be opened and checked during the defence.*
