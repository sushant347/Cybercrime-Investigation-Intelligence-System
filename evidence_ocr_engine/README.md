# Module 2 — Digital Evidence Acquisition and OCR Engine

Part of the **Cybercrime Investigation Intelligence Engine Using Digital Evidence Correlation** (final-year research project).

This module accepts cybercrime evidence (screenshots, scanned documents, PDFs,
chat exports) and converts it into structured, machine-readable information
with forensic integrity guarantees. It owns **acquisition, hashing,
preprocessing, OCR, deterministic cleaning and enhancement, language and entity
extraction, semantic validation, Phase-1 forensics and canonical storage**.
Correlation, timeline/report generation and threat intelligence remain separate
downstream modules.

## Design decisions

Storage is plain **CSV + JSON files** (no PostgreSQL, MongoDB, Neo4j or Redis) so every experiment is reproducible on any machine. OCR is **PaddleOCR 3.x** (PP-OCRv5) behind an abstract `BaseOCR` interface, so additional engines can be plugged in without touching the pipeline. Recognised text is stored **verbatim** — never translated, autocorrected or modified.

## Architecture

```text
evidence_ocr_engine/
├── backend/modules/evidence/
│   ├── config.py          # EvidenceConfig (env-overridable, injected everywhere)
│   ├── logger.py          # console + rotating file logging, stage timers
│   ├── utils.py           # exception hierarchy, IDs, timestamps, filenames
│   ├── models.py          # dataclasses: OCRLine, OCRPageResult, records
│   ├── schemas.py         # Pydantic output contract (EvidenceOCRResult)
│   ├── hash_service.py    # SHA-256 before/after processing + verification
│   ├── upload.py          # validation, unique naming, chain of custody
│   ├── preprocessing.py   # adaptive quality-driven image enhancement
│   ├── ocr_interface.py   # BaseOCR + FutureOCRService placeholder
│   ├── paddle_service.py  # PaddleOCRService (PaddleOCR 3.x, lazy-loaded)
│   ├── pdf_processor.py   # per-page rendering, page order preserved
│   ├── csv_storage.py     # Repository pattern over 4 CSV files
│   ├── json_storage.py    # one JSON per case, atomic writes
│   ├── pipeline.py        # EvidencePipeline (composition root)
│   └── cleaning/          # Prompt 2: text cleaning + entity extraction
│       ├── regex_patterns.py      language_detector.py
│       ├── unicode_normalizer.py  noise_cleaner.py
│       ├── ocr_corrector.py       entity_preserver.py
│       ├── sentence_reconstructor.py  entity_extractor.py
│       ├── keyword_analyzer.py    cleaning_schemas.py
│       └── cleaning_pipeline.py   cleaning_storage.py  cleaning_service.py
│   └── enhancement/       # Prompt 2.5: confidence-based OCR correction
│       ├── confidence_analyzer.py  unicode_validator.py
│       ├── nepali_dictionary.py    english_dictionary.py
│       ├── context_corrector.py    ocr_correction_rules.py
│       ├── confidence_corrector.py enhancement_pipeline.py
│       ├── correction_logger.py    enhancement_service.py
│       └── data/nepali_ocr_lexicon.json  data/english_ocr_lexicon.json
├── tests/                 # 392 unit/integration tests (no Paddle required)
├── storage/               # cases.csv, evidence.csv, ocr_results.csv,
│                          # processing_log.csv, json/CASE_XXXX.json, originals/
├── samples/               # sample evidence files
├── scripts/generate_examples.py
├── cli.py                 # investigator command-line interface
└── requirements.txt
```

The pipeline flow: **upload → SHA-256 (before) → preprocessing → OCR per page → SHA-256 (after) + verification → CSV + JSON storage**, with every stage timed and written to `processing_log.csv`.

## Installation

Use Python 3.12 for consistency with the full project. On macOS, PaddlePaddle's
prebuilt CPU wheel supports Apple Silicon (arm64), not Intel Macs.

```bash
cd evidence_ocr_engine
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

PaddleOCR downloads its recognition models automatically on first use (internet required once). Everything except OCR itself (upload, hashing, PDF rendering, storage, all tests) works without PaddleOCR installed.

## Usage

```bash
# Ingest evidence into a new case
python cli.py ingest samples/phishing_email_screenshot.png --title "Bank phishing"

# Attach further evidence to the same case, with investigator notes
python cli.py ingest samples/police_scan_report.pdf --case CASE_0001 --notes "seized laptop"

# English-only evidence (faster, higher accuracy for pure English)
python cli.py ingest samples/scam_sms_screenshot.png --case CASE_0001 --lang en

python cli.py list-cases
python cli.py show-case CASE_0001
```

As a library (how other CIIE modules consume it):

```python
from backend.modules.evidence import EvidenceConfig, EvidencePipeline, PaddleOCRService

config = EvidenceConfig.from_env()
pipeline = EvidencePipeline(config, PaddleOCRService(config))
result = pipeline.process_file("evidence.png", case_title="Phishing wave 12")
print(result.raw_text, result.average_confidence, result.hash_verified)
```

## Configuration

Defaults live in `backend/modules/evidence/config.py`; the most useful can be overridden by environment variables: `EVIDENCE_STORAGE_DIR` (storage location), `EVIDENCE_OCR_LANG` (`ne` by default — Nepali, served by PaddleOCR's multilingual Devanagari model whose dictionary covers Devanagari and Latin characters, so English, Nepali and mixed English+Nepali all work; use `en` for English-only evidence), `EVIDENCE_OCR_VERSION` (pinned to `PP-OCRv5` — the only model generation with a Devanagari recogniser, so it serves Nepali, English and mixed-script uniformly; other generations are rejected), `EVIDENCE_MAX_FILE_MB` (upload limit, default 50), `EVIDENCE_OCR_TIMEOUT` (seconds, default 180) and `EVIDENCE_PDF_DPI` (default 220). Note that script-group names like `devanagari` are not valid `lang` values in PaddleOCR 3.x — use concrete codes (`ne`, `hi`, `en`, ...). Preprocessing thresholds (blur, contrast, noise, deskew) are documented in the same file.

## Supported evidence

PNG, JPEG/JPG (screenshots of phishing pages, emails, WhatsApp/Messenger/Telegram chats, banking scams, SMS), PDF (each page rendered and OCR'd separately, page order preserved), TXT and CSV (content stored verbatim, no OCR needed) and optionally DOCX (via `python-docx`).

## Forensic integrity

The submitted file is never modified. A SHA-256 hash is computed at acquisition, the file is copied under a unique name into `storage/originals/`, the copy is immediately re-hashed and compared, and after processing the stored copy is hashed again and verified against the original hash. Both hashes, the verification result and every processing stage (with durations) are recorded in `evidence.csv` and `processing_log.csv`, forming a complete chain of custody. All preprocessing (deskew, denoising, CLAHE, thresholding, etc.) operates on an in-memory working copy only.

## Adaptive preprocessing

Image quality is measured first (Laplacian blur score, brightness, contrast, noise estimate, skew angle) and only the needed corrections are applied: RGB conversion, EXIF orientation, resizing of extreme dimensions, resolution enhancement, perspective correction, deskew, median/Gaussian denoising, CLAHE contrast enhancement, sharpening, border removal with whitespace trimming, and adaptive thresholding (document scans only — binarisation is skipped for colour screenshots, where it destroys anti-aliased UI text). The exact steps applied per page are stored with the result.

## Output format

Complete OCR output is stored per case in `storage/json/CASE_XXXX.json`; each evidence item follows:

```json
{
  "case_id": "CASE_0001",
  "evidence_id": "EVID_00001",
  "file_name": "phishing_email_screenshot.png",
  "file_hash": "04c00721f…",
  "file_size": "11882",
  "upload_time": "2026-07-07T06:19:40.912Z",
  "processing_time_ms": 998.9,
  "pages": [
    {
      "page": 1,
      "confidence": 0.9337,
      "text": "…verbatim recognised text…",
      "lines": [{"text": "…", "confidence": 0.9077, "bbox": [[16,24],[352,24],[352,50],[16,50]]}],
      "bounding_boxes": [[[16,24],[352,24],[352,50],[16,50]]],
      "preprocessing_steps": ["convert_rgb", "exif_orientation", "sharpen"]
    }
  ],
  "raw_text": "…all pages merged in order…",
  "average_confidence": 0.9337,
  "hash_verified": true,
  "ocr_engine": "paddleocr"
}
```

## Adding another OCR engine

Implement `BaseOCR.recognize(image) -> list[OCRLine]` (see `FutureOCRService` in `ocr_interface.py`) and inject it: `EvidencePipeline(config, MyNewEngine(config))`. No pipeline changes required — the test suite's `FakeOCR` demonstrates this.

## Tests

```bash
pytest            # 392 tests across OCR, cleaning, enhancement and forensics
```

Tests use a deterministic in-memory OCR double, so they run without PaddleOCR or model downloads.

## Example outputs

`samples/` and `storage/` ship with a fully processed demo case (`CASE_0001`, five evidence items). They were produced by `python scripts/generate_examples.py`, which runs the real pipeline with a deterministic stub engine so the repository stays reproducible offline; run it with `--paddle` to regenerate them with genuine PaddleOCR recognition.

To validate the existing bundled evidence without regenerating samples or
touching normal case storage, run:

```bash
python scripts/validate_sample_case.py
```

This processes two screenshots with real PaddleOCR plus the PDF, text export,
and transaction CSV as one case. It checks non-empty extraction, unique
evidence IDs, and post-processing SHA-256 verification in temporary storage,
then removes that temporary case automatically.

## Prompt 2 — Hybrid Multilingual Forensic Text Cleaning and Entity Extraction

The `backend/modules/evidence/cleaning/` package consumes the OCR output of Prompt 1 and produces a cleaned working copy plus structured forensic entities. It performs no OCR, no translation, no phishing detection and uses no LLMs or transformer models — detection and cleaning are fully deterministic and offline, which keeps every result reproducible for the research evaluation.

The forensic invariant carries over from Prompt 1: `raw_text` is preserved verbatim forever and a separate `cleaned_text` field is created for downstream modules. Entities are shielded before any cleaning runs (placeholder substitution using Unicode Private-Use-Area sentinels) and restored byte-for-byte afterwards, so no cleaning operation — lowercasing, punctuation folding, line merging — can ever alter a URL, email, phone number, hash or wallet ID.

Stage order: language detection (line-level: `english`, `nepali_unicode`, `roman_nepali`, `mixed`, `unknown`) → Unicode normalisation (NFC, hidden-character removal, ZWJ/ZWNJ kept only inside Devanagari, punctuation/whitespace homoglyph folding) → structural OCR fixes (`http//` → `http://`, `www,` → `www.`) → entity preservation → token-level OCR fixes from a fixed homoglyph vocabulary (`acc0unt` → `account`, `1ogin` → `login`; unknown words are never guessed) → noise removal → whitespace normalisation (paragraphs kept) → sentence reconstruction (broken lines merged; entity lines and cross-script boundaries never merged) → Roman-Nepali line normalisation (lowercase, repeated characters; words never transliterated) → entity restoration → entity extraction → keyword and risk-signal analysis.

Extracted entity types: URLs, domains, emails, IPv4/IPv6, MAC addresses, ports, CVE IDs, phones (normalised to `+977…` for Nepali mobiles), dates, times, money, OTP codes, bank accounts, eSewa/Khalti/IME Pay IDs, MD5/SHA1/SHA256/SHA512 hashes, Bitcoin/Ethereum wallets, social-media URLs, Telegram/Facebook/Instagram usernames and WhatsApp numbers — all validated, de-duplicated and paired with a canonical `normalized` form. Keyword analysis counts bilingual scam vocabulary (English, Roman Nepali, Nepali Unicode) and aggregates it into four risk signals: urgency, financial, credential-theft and threat.

Outputs land in three places: the case JSON gains an `evidence[i].cleaning` section with the full result; `storage/entities.csv` receives one row per entity; `storage/keyword_statistics.csv` receives keyword frequencies plus risk-signal rows; and `storage/ocr_results.csv` is augmented in place with `language`, `cleaned_text_preview`, `entity_count`, `keyword_hits` and `cleaned_at` columns (old rows migrate automatically).

Usage:

```bash
python cli.py clean CASE_0001                          # whole case
python cli.py clean CASE_0001 --evidence EVID_00002    # single item
```

```python
from backend.modules.evidence.cleaning import CleaningPipeline, CleaningService

result = CleaningPipeline().clean(raw_ocr_text)         # pure, storage-free
CleaningService(EvidenceConfig.from_env()).clean_case("CASE_0001")
```

No new dependencies are required — the cleaning engine uses only the Python standard library and Pydantic (already installed for Prompt 1).

## Prompt 2.5 — Forensic OCR Post-Processing and Confidence-Based Correction

The `backend/modules/evidence/enhancement/` package adds a third text representation on top of Prompts 1 and 2: `raw_text` (verbatim OCR, never modified) → `cleaned_text` (Prompt 2, never modified here) → **`enhanced_text`** — the only field that may contain OCR corrections, with every single correction logged. Everything runs locally and deterministically: no translators, no LLMs, no online services.

Stage order: OCR confidence analysis (each cleaned line is traced back to its Prompt 1 OCR line and inherits its recognition confidence; merged lines take the weakest contributor) → structural rules (`http//` → `http://`, `www,` → `www.`, danda repairs) → entity preservation (URLs, emails, phones, hashes, wallets are shielded; only scheme/prefix punctuation may be fixed inside them — domains, digits and hash content stay byte-identical) → Unicode validation (NFC, zero-width characters, duplicate diacritics, double halants, orphan combining marks — structurally invalid sequences only) → confidence-gated dictionary correction → entity restoration.

Corrections are gated by three independent signals that must all agree: a dictionary produced the candidate, the OCR confidence tier permits it (≥ 0.90 — never corrected; 0.30–0.90 — exact lexicon lookups; < 0.30 — additionally fuzzy Nepali matching), and the context check passes (matching scripts, high shape similarity, document-consistency bonus). If any signal disagrees, the token is left unchanged — a conservative non-correction is always preferred over a guess.

The dictionaries are data files, not code: `enhancement/data/nepali_ocr_lexicon.json` (known Devanagari misrecognitions such as `बोड → बोर्ड`, `प्रतिवद्वता → प्रतिबद्धता`, plus a valid-word list for fuzzy matching) and `english_ocr_lexicon.json` (homoglyph corrections such as `acc0unt → account`, `SUPP0RT → SUPPORT`, plus the vocabulary used to validate homoglyph resolution). New OCR errors observed during testing are added as JSON entries — no code changes. Unknown words are never guessed; homoglyph resolution applies only when exactly one vocabulary word can result.

Every applied correction is stored in `storage/ocr_corrections.csv` (case, evidence, original, corrected, confidence, rule, timestamp) and inside the case JSON under `evidence[i].enhancement`, together with correction statistics (total, dictionary/unicode/english/nepali/confidence-based counts, per-language correction rates, document confidence).

Usage:

```bash
python cli.py enhance CASE_0001                          # after `clean`
python cli.py enhance CASE_0001 --evidence EVID_00002
python scripts/generate_enhancement_examples.py          # reproducible demo
```

```python
from backend.modules.evidence.enhancement import EnhancementPipeline

result = EnhancementPipeline().enhance(cleaned_text, ocr_pages)
print(result.enhanced_text, result.correction_statistics.total_corrections)
```

### Hybrid Character Confusion Resolution (layout-aware upgrade)

Real mobile screenshots produce OCR failures beyond whole-word errors, and the upgraded framework handles them with three additions. First, a **character confusion matrix** (`enhancement/data/character_confusion_matrix.json`, fully editable without code changes) lists visually confusable characters within and across scripts (`0↔O`, `1↔l`, `C↔८`, `a↔व`, `e↔ै`, `rn↔m`, `ि↔ी`, `ँ↔ं`) plus spurious leading/trailing characters. Second, a **script consistency detector** classifies every word as English, Nepali, numeric or mixed-script; for mixed-script words (`Seवson`) the minority-script characters are replaced with dominant-script look-alikes from the matrix, and the result must validate against a vocabulary (or, for short initialisms like `F८ → FC`, simply restore a single script). Verified repairs include `Nepव → Nepal`, `Seवson → Season`, `F८ → FC`, `धैरै → धेरै`, `मं → म`, `ऋसार्वजनिक → सार्वजनिक`. All repairs remain confidence-gated and context-validated (triple agreement), entities stay untouchable, and each logged correction now records the exact character replacement (`व→a`) and validating dictionary. Third, **layout-aware reconstruction** classifies each line of a screenshot (status bar, chat input, navigation, delivery ticks, presence, chat timestamp, sender, message) and returns separated `ui_text` and `message_text` views alongside the complete `enhanced_text` — UI chrome is never merged into conversation content, and message boundaries (sender/timestamp/body) are preserved. New quality metrics cover character-confusion, mixed-script and layout counts plus an average-confidence-improvement proxy.

Note on layering: English homoglyphs outside entities are usually already fixed by Prompt 2's cleaning corrector, so Prompt 2.5's English pass mainly catches lexicon-listed and homoglyph tokens that cleaning left untouched; its main contribution is confidence-gated Nepali dictionary correction and Unicode repair. No new dependencies are required.

## Error handling

Invalid images, unsupported formats, corrupted or password-protected PDFs, empty OCR output, OCR timeouts, oversized files and permission problems all raise specific exceptions derived from `EvidenceError`. Failures never lose the chain-of-custody row — the evidence record is kept and marked `failed`, and the cause is written to `processing_log.csv`.
