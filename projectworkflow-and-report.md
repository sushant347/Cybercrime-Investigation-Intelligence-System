# CIIS — Project Workflow and Technical Report

**Cybercrime Investigation Intelligence System**

*A complete walkthrough of what this system does, how each part works, what was
trained on what data, what the measured results are, and what remains unfinished.*

---

## How to read this document

This is written to be read start to finish by someone who has never seen the
codebase. Each section hands something to the next: the OCR engine produces the
text that entity extraction reads; entity extraction produces the identifiers
that correlation compares; correlation produces the confidences that the suspect
and priority scores consume; all of it lands in a report. If you read it in
order, each number you meet will already have a place to sit.

Every figure in this document was measured on this machine or read from a stored
artifact in the repository. Where something has **not** been measured, it says so
explicitly rather than estimating. That distinction matters more than usual here,
because the system's whole design premise is that a number in a report must be
traceable to the thing that produced it.

**Document conventions**

- *Measured* — produced by running code during the preparation of this document.
- *Stored* — read from a committed artifact (a training report, a CSV log).
- *Not measured* — the capability exists but no evidence has been produced.

---

## Part 1 — What this project is

### 1.1 The problem

A cybercrime complaint in Nepal typically arrives as a pile of screenshots: a
Facebook message offering a prize, an eSewa payment confirmation, a bank transfer
slip, a phishing SMS, a complaint letter. Individually each is a picture. The
investigative work is entirely in the connections between them — that the phone
number in screenshot 1 also appears in screenshot 5, that the domain in the SMS
was registered last week, that the money left the victim's account eleven minutes
after the OTP was read aloud.

Doing that by hand is slow and, worse, unreproducible. Two investigators looking
at the same twenty screenshots will build two different pictures, and neither can
show precisely why they believe what they believe.

### 1.2 The objective

The system converts that pile of images into an **evidence-backed investigation
report** in which every statement is traceable to the exact exhibit that produced
it. Six objectives follow from that, and Part 9 assesses how far each was met:

1. **Read the evidence** — extract text from screenshots and scanned documents,
   in English and Nepali, without silently corrupting it.
2. **Extract the identifiers** — pull out phones, wallets, bank accounts, URLs,
   OTPs and amounts as structured data.
3. **Judge the infrastructure** — decide whether a URL or domain in the evidence
   is a phishing site.
4. **Find the connections** — score how strongly any two exhibits are related,
   and say why in words.
5. **Reconstruct the story** — build a timeline, cluster coordinated campaigns,
   rank suspect identifiers, and map findings onto the statute.
6. **Explain itself** — produce a report a supervisor can read and a court can
   scrutinise, where no figure is unexplained.

### 1.3 The central design decision

**There is no machine learning in the scoring path.**

This is the most important thing to understand about the architecture, and it is
deliberate. Correlation weights, suspect scores, priority bands and statutory
mappings are all deterministic arithmetic over declared constants. Machine
learning appears in exactly one place — classifying whether a URL is phishing —
and its output enters the rest of the system as *one weighted factor among many*,
never as a verdict.

The reason is evidentiary. A correlation score that comes out of a learned model
cannot be explained to a court beyond "the model said so". A score computed as
`0.90 × specificity(phone) + 0.40 × proximity` can be written out in a sentence,
audited, and challenged. The system trades accuracy it might have gained from
learned scoring for the ability to defend every number it prints.

### 1.4 Scale of the system

*Measured — line counts of source files, excluding dependencies and tests.*

| Component | Language | Lines | Role |
|---|---|---:|---|
| `threat_intelligence_system` | Python | 42,272 | Phishing-URL ML classifier |
| `evidence_ocr_engine` | Python | 18,807 | OCR, cleaning, entities, forensics |
| `ciis_frontend` | TypeScript/React | 14,533 | Investigator UI |
| `timeline_report_engine` | Python | 7,951 | Timeline, graph, priority, reports |
| `evidence_correlation_engine` | Python | 6,643 | Correlation, campaigns, suspects |
| `ciis_api` | Python/Django | 4,169 | REST API, jobs, permissions |
| **Total** | | **94,375** | |

---

## Part 2 — The architecture, as a chain

Four engines run in a straight line. Each imports only the one before it, so the
dependency graph is acyclic — a constraint enforced by running each engine's test
suite in its own isolated environment in CI. A cross-engine import that only
worked because everything happened to be on one path would pass a combined test
run and fail there.

```
   React frontend
        │  REST
   Django API  (ciis_api/api/engine.py is the only bridge to the engines)
        │
        ▼
   1. evidence_ocr_engine
      upload → hash → preprocess → OCR → clean → enhance → entities → forensics
        │
        ▼
   2. threat_intelligence_system            (optional, lazily imported)
      phishing-URL classifier; absent ⇒ heuristics only
        │
        ▼
   3. evidence_correlation_engine
      correlation → cross-case → campaigns → suspects
        │
        ▼
   4. timeline_report_engine
      timeline → graph → analytics → priority → legal basis → report
```

Storage is **flat files, not a database**: CSVs for tabular records, JSON for
structured artifacts, and the original evidence files kept byte-for-byte. This is
an unusual choice that pays off for a forensic tool — an artifact on disk with a
SHA-256 digest is something you can hand to another party, and it survives the
application being uninstalled.

---

## Part 3 — Phase 1: Reading the evidence

This is where a picture becomes text and structured identifiers. Everything
downstream depends on this stage being both accurate and honest about its own
uncertainty.

### 3.1 Acquisition and integrity

Before anything else, the file is hashed. A SHA-256 digest is taken on
acquisition and re-taken after storage, and the two are compared. This is the
foundation of the chain of custody: if the digests disagree the item is marked
unverified and every later stage that reads it inherits that doubt.

*Measured — mean 3.6 ms, median 2.0 ms per file. Hashing is free relative to
everything else in the pipeline.*

### 3.2 Preprocessing

Before OCR, images pass through a preprocessing pipeline (deskew, denoise,
contrast normalisation, adaptive thresholding) built on OpenCV. A separate
*advanced preprocessing* module plans a per-image operation sequence rather than
applying a fixed chain, because a clean phone screenshot and a photographed paper
receipt need opposite treatments.

*Measured — mean 129.7 ms, median 83.4 ms, max 365 ms per image.*

### 3.3 OCR — PaddleOCR PP-OCRv5

The recognition engine is **PaddleOCR**, version PP-OCRv5, chosen for its
Devanagari support — Nepali evidence is a first-class requirement, and most
alternatives treat it as an afterthought.

*Stored — from `storage/ocr_results.csv`, 25 processed exhibits:*

| Metric | Value |
|---|---|
| Engine | `paddleocr-v5` (100% of items) |
| Mean confidence | 0.93 |
| Median confidence | 0.98 |
| Minimum confidence | 0.56 |
| Mean lines detected | 16.4 per exhibit |
| Language: English | 18 items |
| Language: mixed (English + Nepali) | 7 items |

The gap between the 0.98 median and the 0.56 minimum is the interesting part: a
typical screenshot reads almost perfectly, and the occasional bad exhibit reads
badly. The system's job is to notice which is which, which is what the confidence
score is for.

**A note on multi-engine fusion.** The architecture supports three OCR engines
(PaddleOCR, EasyOCR, Tesseract) with a fusion layer that reconciles their output
line by line. *Measured: only PaddleOCR is installed* — `easyocr` and
`pytesseract` are absent from both virtualenvs. The fusion service therefore runs
single-engine in practice, and the cross-engine agreement signal it was designed
to produce is currently unavailable. This is listed in Part 10.

**A note on large images.** PaddleOCR's cost grows faster than linearly with
pixel count and, past roughly 2 megapixels, segfaulted on this build — taking the
whole API process down with it. Large images are now read in overlapping
horizontal bands so every call stays inside the safe range. This is why the
maximum recorded OCR time (91 seconds) is so far above the median (3.5 seconds):
that is the one scanned PDF page in the corpus, processed in bands.

*Measured — OCR stage: mean 14.3 s, median 3.0 s, 95th percentile 29.6 s,
max 162.7 s.*

### 3.4 Cleaning and enhancement

Raw OCR output is not usable text. It contains broken line wrapping, confusable
characters (`0`/`O`, `1`/`l`, Devanagari lookalikes), and noise. The cleaning
chain addresses this in stages:

1. **Unicode normalisation** and script detection (Latin vs Devanagari vs mixed).
2. **Noise removal** — junk lines, OCR artefacts.
3. **Confidence-gated correction** — a character-confusion model plus English and
   Nepali dictionaries, applied *only* where OCR confidence is low. A correction
   applied to text the engine read confidently is more likely to introduce an
   error than fix one.
4. **Sentence reconstruction** — rejoining wrapped lines into readable sentences.

**Entity protection** is the critical safety mechanism here. Before any
correction runs, every identifier already recognised (URL, phone, hash, wallet)
is replaced with a placeholder token like `<URL_1>`, and restored afterwards.
Without this, a dictionary correction would happily "fix" a wallet address into
a real word and destroy the single most important datum in the exhibit.

*Stored — lexicons loaded at startup: Nepali 183 corrections / 122 valid words;
English 30 corrections / 205 vocabulary words.*

### 3.5 The semantic layer — XLM-RoBERTa

There is a fourth, optional correction stage that uses a transformer.

**What it does.** When the pipeline has a low-confidence word and a candidate
replacement, it builds the sentence with the word masked and asks a pretrained
**`xlm-roberta-base`** masked-language model, in fill-mask mode, whether the
candidate fits the context better than the original. The candidate is accepted
only if it scores at least 0.15 *and* scores at least as well as the original
word.

**Three things about how it is constrained**, all of which matter:

- **Inference only.** The model is never fine-tuned. It is used purely as a
  frozen judge of linguistic plausibility.
- **It can only ever choose between candidates the deterministic layer already
  proposed.** It cannot invent a word.
- **It never touches a protected entity.** The placeholder mechanism from §3.4
  applies here too.

**Its actual status.** *Measured: `transformers` and `torch` are not installed in
either virtualenv.* The semantic stage is wired into the live API pipeline, but
the XLM-R validator reports itself unavailable and the stage falls back to its
offline heuristic validator. So the transformer path is architecturally complete
and currently dormant. No measurement of its contribution exists.

### 3.6 Entity extraction

Text becomes structured identifiers here, through a deterministic regex layer
tuned to Nepali cybercrime specifically: eSewa IDs, Khalti IDs, IME Pay IDs,
Nepali bank account formats, and NPR amounts, alongside the universal types
(phones, emails, URLs, domains, crypto wallets, card numbers, OTPs).

*Stored — 154 entities extracted across 26 exhibits, 11 distinct types:*

| Entity type | Count | | Entity type | Count |
|---|---:|---|---|---:|
| money | 26 | | emails | 12 |
| transaction_ids | 24 | | esewa_ids | 8 |
| domains | 23 | | urls | 7 |
| dates | 19 | | bank_accounts | 7 |
| phones | 16 | | khalti_ids | 7 |
| | | | times | 5 |

Mean 6.4 entities per exhibit; the richest single exhibit yielded 25.

### 3.7 Phase-1 forensics

Independently of the text, each image is examined for signs of manipulation and
scored for reliability. Six forensic services run:

**Forgery detection** combines five techniques into one 0–100 score:

| Technique | Weight | What it detects |
|---|---:|---|
| Error Level Analysis (ELA) | 0.30 | Regions recompressed differently from the rest |
| Compression analysis | 0.20 | JPEG history inconsistent with a single capture |
| Copy-move detection | 0.20 | A region cloned from elsewhere in the same image |
| Metadata analysis | 0.15 | EXIF that contradicts the pixels |
| Noise inconsistency | 0.15 | Sensor noise that differs across regions |

Bands: LOW < 25, MEDIUM < 50, HIGH < 75, CRITICAL ≥ 75. At 50 or above the item
is flagged for manual examination.

**Evidence confidence** is a weighted mean over six dimensions — image quality
0.20, forgery 0.20, hash verification 0.20, OCR confidence 0.20, metadata 0.10,
processing 0.10 — banded VERY_LOW through VERY_HIGH.

The renormalisation rule here recurs throughout the system and is worth stating
once: **a dimension with no input is excluded from the weighted mean, not scored
zero.** An exhibit with no EXIF data is not thereby less trustworthy; the system
simply knows less about it. Scoring the absence as zero would silently punish
every screenshot, since screenshots never carry EXIF.

### 3.8 End-to-end Phase-1 cost

*Measured — from `storage/processing_log.csv`, 129 stage events:*

| Stage | Events | Mean | Median | p95 | Max |
|---|---:|---:|---:|---:|---:|
| Full pipeline | 25 | 17.45 s | 4.64 s | 29.78 s | 162.79 s |
| OCR | 30 | 14.32 s | 3.04 s | 29.59 s | 162.66 s |
| Preprocessing | 23 | 129.7 ms | 83.4 ms | 322.3 ms | 365.0 ms |
| Upload | 26 | 21.0 ms | 10.9 ms | 45.4 ms | 47.0 ms |
| Hashing | 25 | 3.6 ms | 2.0 ms | 5.2 ms | 27.4 ms |

**OCR is 82% of total pipeline time.** Everything else is rounding error. Any
future performance work belongs there and nowhere else.

---

## Part 4 — Phase 1.5: The threat intelligence model

This is the only trained machine-learning component in the system, and the only
place in this document where the words "training", "epochs" and "test set" have
their usual meaning.

### 4.1 What it decides

Given a URL or domain found in the evidence, is it a phishing site? The answer
feeds into correlation as one factor among many (weight 0.80) and into the case
priority score (weight 0.20).

### 4.2 The training data

*Stored — from `results/full_retraining_report_20260712T090000Z.json`.*

Five candidate dataset files were discovered; four were used and one was
correctly rejected:

| Dataset | Rows | Phishing | Legitimate |
|---|---:|---:|---:|
| StealthPhisher2025.csv | 336,749 | 175,806 | 160,943 |
| dataset2.csv | 149,726 | 54,807 | 94,919 |
| PhishBD_2026.csv | 131,167 | 91,817 | 39,350 |
| PhishTank_2026.csv | 64,280 | 64,280 | 0 |
| *phishing_email_detection_2026.csv* | *1,500* | — | *skipped* |

The fifth file was skipped automatically because it contains no URL column — it
is an email-feature dataset (`sender_email`, `urgency_score`, `spelling_errors`),
not a URL dataset. The loader detected this and excluded it rather than
misinterpreting its columns.

**Cleaning**, applied in order:

| Step | Rows removed |
|---|---:|
| Loaded | 683,422 |
| Malformed URLs | −826 |
| Duplicates | −96,043 |
| Conflicting labels | −13 |
| **Final** | **585,040** |

The 13 conflicting-label removals are small but important: those are URLs
labelled phishing in one source and legitimate in another. Keeping them would
teach the model to be uncertain about exactly the cases where the sources
disagree.

Final balance: **305,573 phishing / 279,467 legitimate** — 52.2% / 47.8%, near
enough to balanced that no resampling was applied (`balance_downsampled: 0`).

**Split — 70 / 15 / 15, stratified:**

| Split | Rows |
|---|---:|
| Train | 409,528 |
| Validation | 87,756 |
| Test | 87,756 |

### 4.3 The features — 71 of them

Feature version 2.0.0. All 71 are computed from the URL string itself, with no
network calls, which is what makes inference fast and deterministic. They fall
into eight families:

| Family | Count | Examples |
|---|---:|---|
| Length | 12 | `url_length`, `hostname_length`, `max_path_segment_length` |
| Character counts | 16 | `digit_count`, `at_symbol_count`, `hyphen_count` |
| Entropy | 8 | `url_entropy`, `domain_entropy`, `digit_entropy_ratio` |
| Structural | 10 | `directory_depth`, `has_port`, `path_segment_count` |
| Lexical | 7 | `suspicious_keyword_count`, `avg_token_length` |
| Brand | 6 | `brand_levenshtein_distance`, `is_typosquatting` |
| Security | 8 | `is_https`, `is_punycode`, `has_homograph_chars` |
| TLD | 4 | `tld_risk_score`, `is_new_gtld` |

The brand and security families are the domain-specific ones. `is_typosquatting`
and `brand_levenshtein_distance` catch `nabi1-bank.com` impersonating
`nabilbank.com`; `has_homograph_chars` catches Cyrillic characters substituted
for Latin lookalikes.

### 4.4 Training

**On the question of epochs:** these are gradient-boosted tree and classical
models, not neural networks, so there are no epochs. The equivalent capacity
control is the number of boosting rounds (`n_estimators`) and tree depth, both
tuned per model. XGBoost's tuned configuration uses **186 estimators at depth
11**; LightGBM uses **512 estimators at depth 5**.

**Hyperparameter optimisation** used Optuna with a 60,000-row stratified
subsample per trial and early stopping:

| Model | Trials | Best tuning score |
|---|---:|---:|
| XGBoost | 25 | 0.9759 |
| LightGBM | 25 | 0.9769 |
| Random Forest | 16 | 0.9727 |
| Extra Trees | 15 | 0.9691 |

Final models were then trained on the **full 409,528-row** training split.

*Stored — total training duration: **1,652.2 seconds (27.5 minutes)** for all
eight models including tuning, cross-validation and calibration.*

Two pragmatic compromises are recorded in the run's own notes: cross-validation
used a 100,000-row stratified sample (60,000 for SVM) for tractability, and SVM
was trained on an 80,000-row subsample because `LinearSVC` cost scales badly —
though it was *evaluated* on the full test split like everything else.

### 4.5 Results — eight models on the held-out test set

*Stored — 87,756 test rows, never seen during training or tuning.*

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | MCC | FPR | FNR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **XGBoost** | **0.9790** | **0.9762** | **0.9838** | **0.9800** | **0.9973** | **0.9579** | **2.63%** | **1.62%** |
| LightGBM | 0.9773 | 0.9748 | 0.9820 | 0.9784 | 0.9968 | 0.9546 | 2.78% | 1.80% |
| Random Forest | 0.9744 | 0.9707 | 0.9806 | 0.9756 | 0.9959 | 0.9488 | 3.24% | 1.94% |
| Extra Trees | 0.9739 | 0.9686 | 0.9818 | 0.9752 | 0.9958 | 0.9478 | 3.48% | 1.82% |
| Decision Tree | 0.9715 | 0.9729 | 0.9725 | 0.9727 | 0.9824 | 0.9429 | 2.96% | 2.75% |
| SVM | 0.8906 | 0.8839 | 0.9102 | 0.8968 | 0.9479 | 0.7809 | 13.08% | 8.98% |
| Logistic Regression | 0.8906 | 0.8841 | 0.9099 | 0.8968 | 0.9475 | 0.7809 | 13.05% | 9.01% |
| Naive Bayes | 0.8056 | 0.8540 | 0.7573 | 0.8027 | 0.8935 | 0.6168 | 14.16% | 24.27% |

The tree ensembles cluster tightly at the top (F1 0.975–0.980) and the linear
models sit nine points behind. That gap is itself informative: phishing URLs are
not linearly separable in this feature space. Naive Bayes' 24% false-negative
rate makes it unusable here — it would miss one phishing URL in four.

**Model selection** was automatic, by the declared priority **F1 → ROC-AUC →
Recall → Precision**, with accuracy explicitly never used as the deciding
criterion. Accuracy is the wrong metric for a security classifier because it
treats a missed phishing site and a false alarm as equally costly. XGBoost won;
LightGBM was runner-up.

**XGBoost confusion matrix (test set, n = 87,756):**

|  | Predicted legitimate | Predicted phishing |
|---|---:|---:|
| **Actually legitimate** | 40,819 | 1,101 |
| **Actually phishing** | 743 | 45,093 |

743 phishing URLs missed; 1,101 legitimate URLs wrongly flagged.

**Cross-validation** (5-fold) confirms the ranking is stable, not an artefact of
one split — standard deviations are tiny:

| Model | Mean F1 | Std | Mean ROC-AUC |
|---|---:|---:|---:|
| LightGBM | 0.9771 | ±0.0009 | 0.9967 |
| XGBoost | 0.9768 | ±0.0010 | 0.9966 |
| Random Forest | 0.9738 | ±0.0011 | 0.9957 |
| Extra Trees | 0.9715 | ±0.0011 | 0.9949 |
| Decision Tree | 0.9642 | ±0.0013 | 0.9707 |
| Logistic Regression | 0.8995 | ±0.0028 | 0.9497 |
| SVM | 0.8983 | ±0.0024 | 0.9489 |
| Naive Bayes | 0.8199 | ±0.0050 | 0.8935 |

A ±0.001 standard deviation on F1 means the model's performance is essentially
identical across folds.

### 4.6 Calibration — why the probability is trustworthy

A classifier that is 97% accurate can still be badly *calibrated*: when it says
"90% confident", it might be right only 60% of the time. That matters here
because the confidence figure is printed in a report an investigator acts on.

*Stored — the training run measured calibration and automatically switched the
production calibrator from Platt scaling to isotonic regression:*

| Metric | Platt | Isotonic (selected) |
|---|---:|---:|
| Expected Calibration Error | 0.0036 | **0.0000** |
| Brier score | 0.0160 | **0.0150** |

An ECE of essentially zero means that when the model says 80%, it is right about
80% of the time. The confidence number in the report means what it says.

### 4.7 Error analysis

*Stored — the run exported every mistake for inspection:* 1,101 false positives,
743 false negatives, and **200 high-confidence mistakes** — cases where the model
was confidently wrong. That last file is the valuable one: high-confidence errors
are where a model's blind spots live, and they are the natural starting point for
the next training round.

### 4.8 Inference — how it behaves at runtime

*Measured — on this machine, in the API's virtualenv, with live network
enrichment disabled:*

| Measurement | Value |
|---|---:|
| Provider initialisation | 684 ms |
| First lookup (cold, loads model) | 2,261 ms |
| Warm lookup (mean of 59) | **7.03 ms** |
| Sustained throughput | **142 URLs/second** |

Results are memoised per value, so a URL appearing in five exhibits costs one
inference. At 7 ms warm, threat scoring is negligible against Phase 1's 17-second
mean — it is not a bottleneck and never will be.

**A verified discrepancy worth recording.** The classifier loads correctly and
returns verdicts sourced `ml:xgboost` — confirmed live during preparation of this
document, on both a known-bad and a known-good URL. However, the stored report
for the sample case records every verdict's source as `heuristics`, not
`ml:xgboost`. The most likely explanation is that the analysis was run before the
ML provider was enabled, or in a process where it failed to load. **The stored
case artifacts therefore under-represent the system's actual threat-detection
capability**, and re-running analysis on those cases would change their verdicts.
This is listed in Part 10.

### 4.9 The decision chain

Threat intelligence is not a single provider but a chain, tried in order, taking
the most serious *explained* verdict:

1. **Static indicator file** — a curated list, if the deployment supplies one.
2. **ML classifier** — the XGBoost model above, when its dependencies are present.
3. **Heuristics** — always available; an offline, fully explainable rule set.

The heuristics are the floor, not the ceiling. Because they always work, a
deployment with no indicator file and no ML stack still scores every URL rather
than reporting "intelligence unavailable" on every case — which is precisely what
happened before the chain existed.

---

## Part 5 — Phase 2: Finding the connections

We now have, for each exhibit: verified text, structured identifiers, a forensic
confidence score, and threat verdicts on any URLs. The question becomes *how do
these exhibits relate to each other?*

### 5.1 The correlation formula

Every pair of exhibits is scored. For a pair, the engine accumulates weighted
factors and converts the total to a confidence:

```
confidence = 1 − exp(−Σ weights / 1.6)
```

The exponential form is chosen so that confidence saturates: the first shared
wallet moves the score a great deal, the fourth adds very little. This prevents a
pair with many weak coincidences from outranking a pair sharing one decisive
identifier.

**Type weights** encode how identifying each kind of match is:

| Weight | Entity types | Reasoning |
|---:|---|---|
| 1.00 | wallets, eSewa/Khalti/IME IDs, bank accounts, card numbers, file hash | A shared payment rail is nearly conclusive |
| 0.95 | transaction_ids | The same payment seen from both sides |
| 0.90 | phones, WhatsApp numbers | Strong but reassignable |
| 0.85 | emails, MAC addresses | |
| 0.80 | social accounts, threat intelligence | |
| 0.75 / 0.70 | URLs / device metadata, social URLs | |
| 0.60 | domains, IPv4, IPv6 | Shared hosting is common |
| 0.50 | image metadata | |
| 0.40 | timeline proximity (within 48 h) | Weak on its own |
| **0.25 / 0.20** | **OTP / money** | **Deliberately near-worthless alone** |

The bottom row is the important one. Without it, "both exhibits mention NPR
2,000" would score like "both exhibits reference the same wallet", and in a
corpus of payment screenshots *every case would correlate with every other case*
on round amounts. The low weights keep such matches visible in the report —
they are still facts — without letting them carry a relationship.

A **factor cap of 3** limits how many matches of one type can count, so a single
spammy entity cannot dominate a pair's score.

### 5.2 Value specificity — the unsupervised layer

Type weights alone are still too blunt: the phone number of a national bank's
helpline and a scammer's burner phone are both `phones`, weight 0.90, but they
are worlds apart evidentially.

So each matched *value* is additionally weighted by how identifying it is,
combining two estimates:

- **Learned rarity** — how often the value appears across the whole corpus.
- **Intrinsic information content** — how many bits the value carries by its own
  structure. 40 bits (a 12-digit account number, a 9-character handle) counts as
  fully identifying.

These are blended with a **prior strength of 12**: below a corpus of about a
dozen cases the intrinsic estimate dominates, which is what keeps a fresh
deployment sensible — a brand-new wallet address is rare *because* nothing has
been seen yet, and the learned estimate alone would be meaningless.

A **floor of 0.02** ensures a match on a ubiquitous value is never reduced to
nothing. It remains a fact worth showing; it simply must not carry the case.

This is the one genuinely unsupervised learning component in the scoring path,
and it is deliberately transparent: the specificity of any value can be printed
and explained.

### 5.3 Relationship bands

| Band | Confidence |
|---|---|
| NO_RELATIONSHIP | < 0.05 |
| WEAK | < 0.30 |
| MEDIUM | < 0.55 |
| STRONG | < 0.80 |
| VERY_STRONG | ≥ 0.80 |

*Stored — sample case, 9 exhibits, 36 pairs examined, all 36 related:*
1 VERY_STRONG, 4 STRONG, 5 MEDIUM, 26 WEAK. Strongest pair 94%.

That distribution is healthy and demonstrates the weighting working as intended:
most pairs are weakly linked (they share an amount or a date), and the handful
that matter stand clearly above them.

### 5.4 Performance and its scaling limit

Correlation is inherently **O(n²)** — every pair must be scored.

*Measured — pairwise scoring throughput:*

| Exhibits | Pairs | Time | ms/pair | Pairs/sec |
|---:|---:|---:|---:|---:|
| 10 | 45 | 0.003 s | 0.075 | 13,381 |
| 25 | 300 | 0.013 s | 0.044 | 22,933 |
| 50 | 1,225 | 0.053 s | 0.043 | 23,193 |
| 100 | 4,950 | 0.217 s | 0.044 | 22,857 |
| 200 | 19,900 | 0.865 s | 0.044 | 23,010 |
| 400 | 79,800 | 3.536 s | 0.044 | 22,571 |

Per-pair cost is flat at **0.044 ms** (~23,000 pairs/second), so the quadratic
term is the only thing that matters. Extrapolating: 1,000 exhibits ≈ 500k pairs
≈ **22 seconds**; 2,000 exhibits ≈ 2M pairs ≈ **87 seconds**.

For realistic case sizes this is comfortable — and note it is dwarfed by OCR,
which would take hours for 1,000 exhibits. The quadratic growth only becomes the
binding constraint on cases far larger than the tool currently targets. It is
recorded in Part 10 rather than treated as an immediate problem.

### 5.5 Cross-case correlation

The same scoring runs *between* cases, on the same explainable scale. A single
shared entity is enough to create a link (`cross_case_min_shared_entities: 1`),
because in practice one shared wallet across two complaints is exactly the lead
worth surfacing.

*Stored — the sample case links to 2 other cases, sharing 29 and 21 identifiers
respectively, both VERY_STRONG at 100% confidence.*

This is arguably the highest-value output of the whole system: it is how five
separate small complaints are revealed to be one operation.

### 5.6 Campaign detection

Campaigns are found by **connected-components clustering** over the correlation
graph — exhibits linked above a threshold form a cluster. Not k-means, not
DBSCAN: the graph structure already encodes the relationships, and connected
components require no parameter that would need justifying in court.

*Stored — sample case: 1 campaign of 5 exhibits at 71% confidence, 4 exhibits
unclustered, with the shared signature recorded (`domains:esewa-cashback-offer.xyz`,
`phones:+9779847011223`, `emails:sunita.gurung21@gmail.com`).*

### 5.7 Suspect assessment

Identifiers — not people — are ranked by how strongly the evidence connects them
to the case. Six weighted dimensions:

| Dimension | Weight | Meaning |
|---|---:|---|
| Identity strength | 0.25 | Anchor type (wallet 100 > phone 85 > email 75) |
| Evidence count | 0.20 | Breadth of appearances |
| Evidence confidence | 0.15 | Mean Phase-1 confidence of its exhibits |
| Threat intelligence | 0.15 | Whether the anchor is independently flagged |
| Correlation strength | 0.15 | How tightly its exhibit set is linked |
| Timeline span | 0.10 | Sustained activity over time |

The language is chosen with care. The system produces *suspect identity anchors*,
never suspects. The report states explicitly that an anchor is not a suspect in
law until corroborated by investigation. This is not decoration — it is the
difference between an investigative aid and an accusation.

*Stored — sample case: 13 identity anchors; top anchor `+9779801122334`
(Khalti ID) at 77.6/100, HIGH risk.*

---

## Part 6 — Phase 3: Reconstructing the story

### 6.1 Timeline

Events are placed on a timeline using timestamps recovered from exhibit content
where possible, falling back to acquisition time — and **labelled as such**, so a
reader can always tell a reconstructed time from a filesystem time.

Events are classified into attack stages by keyword matching:
`initial_contact → social_engineering → credential_theft →
financial_transaction → post_attack`.

**Critical events** are those involving OTPs or financial transfers — the moments
where control or money actually moved. These drive the timeline criticality score.

*Stored — sample case: 9 events spanning 1,331 hours (55 days), 0 unresolved
timestamps, 4 stages observed, 7 critical events.*

The sample case's stage order was flagged **out of order** against the canonical
progression, which the report notes can indicate multiple actors or a re-contact.
This is a good example of the system surfacing an anomaly rather than smoothing
it away.

### 6.2 Relationship graph

The correlation results are projected into a graph: exhibits, entities, cases and
timeline events as nodes; correlations, shared entities and temporal proximity as
edges. Rendered with Cytoscape and an fCoSE layout in the frontend.

One design note worth recording: edges representing "uploaded in the same batch"
are labelled as an artefact of collection rather than a finding, because they
grow with every upload and were the main cause of a visually tangled graph that
implied relationships which did not exist.

### 6.3 Case priority

A single 0–100 urgency score, from six weighted components:

| Component | Weight | Direction |
|---|---:|---|
| Evidence confidence | 0.20 | Higher is better |
| Threat intelligence | 0.20 | Higher is worse |
| Forgery risk | 0.15 | Higher is worse |
| Campaign size | 0.15 | Higher is worse |
| Correlation strength | 0.15 | Higher is better |
| Timeline criticality | 0.15 | Higher is worse |

Bands: LOW < 30, MEDIUM < 55, HIGH < 75, CRITICAL ≥ 75.

The renormalisation rule from §3.7 applies again: only components with data are
included, and the divisor is their weight sum.

*Stored — sample case scored **74.5 / 100 (HIGH)** from all six components:*

| Component | Score | Weight | Contribution |
|---|---:|---:|---:|
| Evidence confidence | 89.9 | 0.20 | 18.0 |
| Campaign size | 100.0 | 0.15 | 15.0 |
| Timeline criticality | 100.0 | 0.15 | 15.0 |
| Correlation strength | 92.2 | 0.15 | 13.8 |
| Threat intelligence | 44.4 | 0.20 | 8.9 |
| Forgery risk | 25.2 | 0.15 | 3.8 |
| | | | **74.5** |

The contributions sum exactly to the headline score — verified during this
document's preparation.

### 6.4 Statutory basis

Findings are mapped onto **10 provisions of Nepal's Electronic Transactions Act,
2063 (2008)** — sections 19, 27, 45, 46, 47, 52, 53, 54, 55 and 56 — covering
computer fraud, unauthorised access, data tampering, privacy breach and
intellectual-property offences.

Each provision carries four fields: the **conduct** it covers, the **penalty** on
conviction, the specific **finding that engaged it**, and the **exhibits** behind
that finding. A mandatory caveat is displayed wherever provisions appear, stating
that this is not a charging decision.

*Stored — sample case engages 6 provisions: s.52, s.47, s.53, s.54, s.19, s.56.*

**A known limitation.** The Act's authoritative text is Nepali. The PDF renderer
uses the standard-14 PostScript fonts, which cover Latin-1 only; Devanagari
passed to them is silently drawn as placeholder boxes. Rather than print
corrupted text on a legal document, the PDF prints an explicit note directing the
reader to the Nepali gazette copy, and the Markdown and JSON exports carry the
full Nepali title. The proper fix — embedding a Devanagari face such as Noto Sans
— is in Part 10.

---

## Part 7 — Phase 4: The outputs

Every analysis produces the same report in three formats from one section model,
so they cannot drift: **JSON** (machine-readable), **Markdown** (diffable), and
**PDF** (the document that leaves the building).

### 7.1 Report structure

21 numbered sections, from Executive Summary through Statutory Basis to
Provenance and Appendix. Numbering exists so findings can be cited precisely —
"see 6.2" is how an investigator, prosecutor or defence expert refers to
something, and an unnumbered document cannot be cross-referenced at all.

### 7.2 Provenance and integrity

Every PDF carries:

- A **SHA-256 digest of every source artifact** it was built from.
- An **evidence-set digest** tying it to an exact evidence state.
- A page footer with report ID and "Page X of Y" so a missing page is detectable.
- A **RESTRICTED — LAW ENFORCEMENT SENSITIVE** banner on every page, because a
  forensic report circulates beyond the unit that produced it and the handling
  constraint must travel with the paper.
- A **Statement of Limitations** stating plainly what the report cannot support:
  that correlation is association not causation, that an identity anchor is not a
  suspect, and that findings reflect only the evidence held at the date of issue.

### 7.3 The PDF layout work

The PDF originally had proper layouts for only 4 of its 21 sections. The other 17
fell through to a generic recursive emitter that walked nested data and produced
bullet lists — correlation alone turned 36 exhibit pairs into roughly 140 nested
bullets that could not be scanned or compared.

Every section now has a layout matched to its data: ranked tables with repeating
headers, KPI strips for headline counts, definition tables for flat mappings, and
prose kept beneath the table it explains. Four chart types were added, each placed
directly above the table it summarises so no figure exists only as a picture:

- Correlation strength distribution (vertical bars)
- Suspect confidence ranking (horizontal bars)
- Threat verdict split (proportional bar)
- Attack stage progression (ribbon)

Charts are drawn from primitive shapes rather than a charting library, so the
same input produces the same marks on the page — a requirement for an evidentiary
artifact.

*Measured — sample case report: 24 pages → 18 pages, with more of it readable.*

**Verification of information preservation.** Because a bespoke renderer reads
named keys, it is exactly the kind of change where a field quietly stops being
printed. The work was checked by walking the stored report data and asserting
every scalar value reaches the page, across all five stored cases:

| Case | Values absent (old) | Values absent (new) |
|---|---:|---:|
| CASE_665F85EBBC | 41 | 41 |
| CASE_1A1BF573F3 | 34 | **32** |
| CASE_2CF24DBA5F | 13 | 13 |
| CASE_D6A81F224B | 15 | 15 |
| CASE_EE8250FB76 | 11 | 11 |

Zero information lost; one case gained two facts. The residual absences are
pre-existing and benign — empty strings, booleans rendered as "VERIFIED", and the
deliberately-skipped Devanagari title. This check is retained as a permanent test.

---

## Part 8 — The application layer

### 8.1 API

Django REST, **27 endpoints**, covering intake, evidence upload, job status,
artifacts, reports, dashboard, audit and admin. `ciis_api/api/engine.py` is the
single bridge to the engines — nothing else in the API imports them, which keeps
the boundary enforceable.

Analysis runs as a background job. Jobs abandoned by a crashed process are retired
at startup, so a crash cannot leave a case permanently "analysing".

### 8.2 Frontend

React 19 + TypeScript + MUI v6 + Vite, with Recharts for charts and Cytoscape for
the relationship graph. Case views cover Overview, Evidence, Investigation, Graph,
Timeline, Analytics and Reports.

Recent UI work addressed four classes of problem:

- **Terminology** — a glossary derived from the scoring code, surfaced through
  hover definitions with a visible affordance and keyboard access. Metrics are now
  coloured by *direction*, so a high forgery risk no longer looks as reassuring as
  a high evidence confidence, and each component's real weighted contribution is
  shown rather than leaving `44.4 × 0.20` for the reader to resolve.
- **Density** — investigation results moved from stacked accordions to sortable,
  searchable, paginated tables. A case with 36 pairs and 13 suspects previously
  rendered about fifty full-width cards.
- **Contrast** — the report view hardcoded print inks. Section headings measured
  **1.90:1** against the dark canvas and generated chart labels **1.18:1**, both
  far below the 4.5:1 WCAG AA threshold; they are now 11.70:1 and 14.50:1. Light
  mode had the mirror-image bug, with MEDIUM and WEAK severity chips at roughly
  1.5:1 on white.
- **Presentation** — the statutory basis restructured around how it is read:
  which section, why it is engaged, what it carries.

### 8.3 Security posture

*Honest assessment.* The admin surface is gated by a **single shared password**
(`CIIS_ADMIN_PASSWORD`), with a shipped default of `hello123`. The codebase
detects this itself: a Django deployment check raises `ciis.E001` whenever the
default is still in place, and the check is tested.

Two structural consequences follow, both in Part 10:

1. The default is committed to a public repository, so it cannot protect anything
   real and must be treated as a development convenience only.
2. A single shared password means **no attribution** — the system cannot record
   *who* deleted a case. For a tool that cares about chain of custody elsewhere,
   this is the sharpest inconsistency in the design.

---

## Part 9 — Testing, and what has been achieved

### 9.1 Test coverage

*Measured — full suite run during preparation of this document:*

| Suite | Tests | Result |
|---|---:|---|
| `evidence_ocr_engine` | 392 | pass |
| `threat_intelligence_system` | 400 (+9 skipped) | pass |
| `evidence_correlation_engine` | 102 | pass |
| `timeline_report_engine` | 81 | pass |
| `ciis_api` | 67 | pass |
| `ciis_frontend` (vitest) | 67 | pass |
| **Total** | **1,109 passing** | |

Plus a TypeScript build with no type errors. CI runs every suite on every push,
each engine in its own environment to prove the module boundaries hold.

Only **2 `TODO`/`NotImplementedError` markers** exist in the entire codebase, and
both are an intentional research placeholder. The gaps in Part 10 were found by
investigation, not by reading markers — which is itself a signal about the
codebase's maturity.

### 9.2 Objectives assessed

| # | Objective | Status | Evidence |
|---|---|---|---|
| 1 | Read evidence (English + Nepali) | **Achieved, unquantified** | PP-OCRv5 running; 0.93 mean confidence on 25 exhibits. **CER/WER never measured** — see 10.1 |
| 2 | Extract identifiers | **Achieved, unquantified** | 154 entities, 11 types, Nepal-specific rails. **P/R/F1 never measured** — see 10.1 |
| 3 | Judge infrastructure | **Achieved and quantified** | XGBoost F1 0.9800, ROC-AUC 0.9973 on 87,756 held-out rows |
| 4 | Find connections, explainably | **Achieved** | Deterministic weighted scoring; every pair carries a written justification |
| 5 | Reconstruct the story | **Achieved** | Timeline, campaigns, suspects, cross-case links, 10 statutory provisions |
| 6 | Explain itself | **Achieved** | 21-section report in 3 formats, SHA-256 provenance, mandatory limitations |

**The honest summary:** five of six objectives are met, and one — the threat
classifier — is met with rigorous, reproducible evidence. The significant caveat
is that objectives 1 and 2, the foundation everything else rests on, are
*demonstrably working but not measured*. The system reads text well enough to
produce sensible downstream results, but there is no defensible accuracy figure
for the OCR or the entity extractor. That is the single largest gap in the
project and is the first item in Part 10.

### 9.3 What the project genuinely demonstrates

Setting aside the gaps, four things here are done to a standard above what the
brief required:

1. **Explainability is architectural, not cosmetic.** The refusal to put ML in
   the scoring path is a real constraint that was honoured throughout, and it is
   the reason every figure in a report can be defended.
2. **The ML component is properly evaluated.** Eight models, 5-fold
   cross-validation, calibration analysis with automatic recalibration, error
   export, and selection by a declared metric priority that explicitly rejects
   accuracy. This is a complete evaluation, not a single train/test number.
3. **Absence is distinguished from zero.** The renormalisation rule appears
   independently in evidence confidence, priority scoring and suspect scoring. It
   is a subtle correctness property that most implementations get wrong.
4. **The evidentiary framing is consistent.** Identity anchors are not suspects,
   correlation is association not causation, handling constraints travel with the
   document. The language discipline holds from the scoring code to the PDF footer.

---

## Part 10 — What remains to be done

Ordered by importance. Each entry states the problem, why it matters, and the
concrete next step.

### 10.1 Measure OCR and entity-extraction accuracy — *highest priority*

**Problem.** The evaluation harnesses exist and are unit-tested — CER, WER,
entity precision/recall/F1, entity preservation rate — but *no real annotated
corpus exists*. `samples/ground_truth/` contains only `*_example.json` and
`*_template.json` files, and the benchmark scripts deliberately refuse to treat
the examples as real data.

**Why it matters.** These two stages are the foundation of everything downstream.
Without them the project can state its threat classifier's F1 to four decimal
places but cannot say how accurately it reads a screenshot.

**Next step.** Build the corpus the README already specifies: 30–100
representative exhibits, English and Nepali/Devanagari, human-transcribed, then
run `scripts/run_table_6_1.py` and `run_table_6_2.py`. The infrastructure is
finished; only the annotation work remains. This is measured in days, not weeks,
and it would close the project's largest evidential gap.

### 10.2 Resolve the threat-intelligence discrepancy

**Problem.** The classifier demonstrably works (§4.8), but stored case artifacts
record verdicts sourced `heuristics`, not `ml:xgboost`.

**Why it matters.** The stored reports under-represent the system's real
capability, and any evaluation based on them measures the heuristics rather than
the trained model.

**Next step.** Re-run analysis on the stored cases with the ML provider confirmed
active, and log the chain composition per run so the provenance of every verdict
is recorded in the artifact itself.

### 10.3 Introduce per-user accounts and attribution

**Problem.** One shared admin password, no user identity, no record of who did
what. The shipped default `hello123` is committed publicly.

**Why it matters.** A tool built around chain of custody cannot say who deleted a
case. This is the sharpest internal inconsistency in the system.

**Next step.** Real accounts with per-user sessions, an audit trail keyed to user
identity, and removal of the shipped default in favour of a required environment
variable that fails closed.

### 10.4 Restore multi-engine OCR fusion

**Problem.** Three OCR adapters exist; only PaddleOCR is installed, so fusion
runs single-engine and the cross-engine agreement signal is unavailable.

**Why it matters.** Agreement between independent engines is one of the
strongest available quality signals, and it is currently designed-for but unused.

**Next step.** Add EasyOCR and Tesseract to the platform environment, then
measure whether fusion actually improves CER — which requires 10.1 first.

### 10.5 Activate or remove the semantic layer

**Problem.** The XLM-RoBERTa validator is implemented and wired in, but
`transformers`/`torch` are absent, so it silently falls back to the heuristic
validator. Its contribution has never been measured.

**Why it matters.** Dormant code that looks active is misleading — a reader of
the codebase would reasonably conclude a transformer is in the pipeline.

**Next step.** Either install the dependencies and measure the correction-accuracy
delta against the heuristic path (again requiring 10.1), or document it clearly as
an optional research path. Do not leave it ambiguous.

### 10.6 Embed a Devanagari font in the PDF

**Problem.** The PDF cannot render Nepali text; the statute's authoritative title
is replaced with a pointer to the gazette copy.

**Why it matters.** The Act's Nepali text governs where the two versions differ.
A Nepali legal document that cannot print Nepali is a real limitation.

**Next step.** Embed Noto Sans Devanagari (OFL) and register it with ReportLab.
The renderer already detects unrenderable strings, so the detection logic is in
place and only the font registration is missing.

### 10.7 Address correlation's quadratic scaling

**Problem.** O(n²) at 0.044 ms/pair — fine to a few hundred exhibits, ~87 seconds
at 2,000.

**Why it matters.** Not urgent at current case sizes, and dominated by OCR cost
regardless. It becomes binding only for cases well beyond the current target.

**Next step.** When needed: block on shared high-specificity entities so only
plausible pairs are scored in full. Do not do this pre-emptively — it adds
complexity for no present benefit.

### 10.8 Housekeeping

- **`timeline_reconstruction/`** contains nothing but stale `__pycache__` — an
  orphaned directory that should be deleted.
- **Frontend bundle** — `CaseDetailPage` is 1.16 MB (345 KB gzipped). Route-level
  code splitting would help first load.
- **`shap` and `optuna` are absent** from both virtualenvs, so SHAP explanations
  and hyperparameter retuning cannot currently be reproduced, even though the
  training report contains their outputs.
- **No containerisation.** Deployment is `dev.sh` and two virtualenvs; there is no
  Docker image or production deployment path.

---

## Part 11 — Reproducing the results

```bash
./dev.sh
```

Starts the API, the web UI and both engines. First run installs ~500 MB of
OCR/ML packages; subsequent runs start in seconds.

**Test suites** (each engine has its own pytest root):

```bash
cd evidence_ocr_engine && python -m pytest
```

**Frontend:**

```bash
cd ciis_frontend && npm test && npm run build
```

**Threat-model training artifacts** — the full run is recorded at
`threat_intelligence_system/results/full_retraining_report_20260712T090000Z.json`
and the selected checkpoint at `checkpoints/production_model.json`. Every figure
in Part 4 comes from these two files.

**Accuracy benchmarks** (once a real corpus exists, per 10.1):

```bash
python evidence_ocr_engine/scripts/run_table_6_1.py --manifest samples/ground_truth/ocr_corpus.json
```

---

## Closing

The system does what it set out to do: it turns a pile of screenshots into a
report where every claim points back at the exhibit that produced it. The
engineering discipline behind that — the acyclic engine chain, the refusal to put
learned scoring in the evidentiary path, the consistent distinction between "no
data" and "zero", the language care around suspects and causation — is the
project's real achievement, more than any individual number.

The threat classifier is rigorously evaluated and performs well: F1 0.9800 with
near-perfect calibration on 87,756 held-out URLs. The correlation and reporting
layers are complete, explainable and tested by 1,109 passing tests.

The gap that matters is 10.1. The project can state its classifier's performance
to four decimal places but cannot yet say how accurately it reads a screenshot —
and every downstream number inherits that uncertainty. The harnesses are built
and tested; what remains is the annotation work. Closing that gap would turn a
well-engineered system into a fully evidenced one.

---

*Every figure in this document was measured on this machine or read from a
committed artifact. Where a capability exists but has not been measured, it is
labelled as such rather than estimated.*
