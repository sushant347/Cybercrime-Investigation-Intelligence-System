# CIIS — Technical Report

Cybercrime Investigation Intelligence System. Every number in this document is
read from the source; the file path is given so each claim can be checked.

---

## 1. Problem

A cybercrime complaint arrives as a folder of screenshots, chat exports, payment
receipts and PDFs. An investigator must read all of it, work out what happened
and when, notice that two receipts share a wallet address, spot that three cases
are the same offender, and write a report that survives scrutiny. That is hours
of manual work per case and it does not scale.

CIIS automates the mechanical parts — extraction, correlation, chronology,
reporting — and shows its working for every conclusion. It does **not** decide
guilt, and it is designed so that it cannot appear to.

**Design constraint that shapes everything:** no machine learning in the scoring
path. Every correlation weight, suspect score and priority band is deterministic
and carries a written justification. The one ML component (phishing-URL
classification) is isolated in its own module and is optional — the system
degrades to heuristics without it. The reason is evidentiary: a score an
investigator cannot explain in court is worthless.

---

## 2. Architecture

Four engines in a straight chain. Each imports only the one before it, so the
dependency graph is acyclic and any stage can be tested alone.

```
                     ┌─────────────┐
                     │  frontend   │  React 19 + Vite + MUI
                     └──────┬──────┘
                            │ REST
                     ┌──────▼──────┐
                     │  ciis_api   │  Django + DRF; api/engine.py is the
                     └──────┬──────┘  ONLY module that touches the engines
                            ▼
        1. evidence_ocr_engine ────────── OCR, cleaning, entities, forensics
                            │             writes storage/
                            ▼
        2. threat_intelligence_system ─── phishing-URL classifier (optional,
                            │             own virtualenv, lazily imported)
                            ▼
        3. evidence_correlation_engine ── correlation, cross-case, campaigns,
                            │             suspects  + shared infrastructure
                            ▼
        4. timeline_report_engine ─────── timeline, graph, analytics,
                                          priority, report  + pipeline root
```

| Concern | Location |
|---|---|
| Engine roots | `ciis_api/config/settings.py` — `ENGINE_ROOT`, `CORRELATION_ROOT`, `TIMELINE_REPORT_ROOT` |
| Path bootstrap | each package's `__init__.py` puts its upstream on `sys.path`; chained |
| Composition root | `ciis_timeline_report/pipeline.py :: build_default_pipeline()` |

**Why the threat engine is separate.** PaddleOCR requires `numpy<2`; the ML
stack requires `numpy>=2`. They cannot share a virtualenv. It gets
`.venv-threat`; everything else uses `.venv-platform`. The adapter
(`ciis_correlation/threat/ml_provider.py`) imports it lazily and reports
`available == False` if the import fails, so the pipeline never breaks on it.

---

## 3. Pipeline, stage by stage

### 3.1 Evidence acquisition and OCR

`evidence_ocr_engine/backend/modules/evidence/`

| Parameter | Value | Source |
|---|---|---|
| OCR engine | PaddleOCR PP-OCRv5 | `config.py:66` |
| Language | `ne` (Nepali; Devanagari + Latin) | `config.py:60` |
| Max file size | 50 MB | `config.py:49` |
| OCR timeout | 180 s | `config.py:67` |
| Max pixels per OCR call | 700,000 | `config.py:75` |
| PDF render DPI | 220 | `config.py:88` |

**The 700,000-pixel cap is not arbitrary.** Large images segfaulted the OCR
process and killed the whole API. Images above the cap are split into
horizontal bands, OCR'd separately and stitched. This is the fix in commit
`716c389`.

Chain of custody: SHA-256 is taken before processing and again after, and both
are stored in `evidence.csv` with a `hash_verified` flag. Originals are never
modified.

### 3.2 Cleaning, enhancement, entity extraction

Post-OCR the text passes through three stages:

1. **Cleaning** — normalisation, whitespace, character repair.
2. **Enhancement** — dictionary correction. English lexicon: 30 corrections,
   205 vocabulary words. Nepali: 183 corrections, 122 valid words (counts
   printed at engine warm-up).
3. **Semantic extraction** — entities into `entities.csv`, one row per
   occurrence: `case_id, evidence_id, entity_type, value, normalized`.

**Normalisation matters more than it looks.** `rs 2,000`, `Rs 2000` and
`NPR 2000` must normalise to one value or correlation cannot match them. The
money normaliser was added for exactly this (`22b83b0`).

Current corpus: **4 cases, 25 evidence items, 152 entity occurrences across 11
entity types** (money 26, transaction_ids 24, domains 22, dates 19, phones 16,
emails 12, esewa_ids 8, bank_accounts 7, …).

### 3.3 Phase-1 forensics

`forensics/` — image quality, forgery detection, EXIF/metadata, file
fingerprints, logo/brand detection, multi-OCR fusion, and an **Evidence
Confidence Score** combining six dimensions:

| Dimension | Weight |
|---|---|
| image_quality | 0.20 |
| forgery | 0.20 |
| hash_verification | 0.20 |
| ocr_confidence | 0.20 |
| metadata | 0.10 |
| processing | 0.10 |

`forensics/config.py:157`. Weights are **renormalised over available
dimensions** — if metadata is missing the remaining five are rescaled rather
than the score being penalised for an absent input.

Bands: `VERY_LOW <20 ≤ LOW <40 ≤ MODERATE <60 ≤ HIGH <80 ≤ VERY_HIGH`
(`config.py:161`).

---

## 4. Threat intelligence (the ML module)

`threat_intelligence_system/`. This is the only supervised learning in the
system, and the answer to "what alpha, what split".

### 4.1 The 70/15/15 split

`src/config/settings.py:83-89`, implemented in `src/datasets/merger.py:168-183`.

| Split | Ratio | Purpose |
|---|---|---|
| Train | 0.70 | model fitting |
| Validation | 0.15 | calibration fitting and threshold selection |
| Test | 0.15 | held out; touched once, for reported metrics |

Three properties that a supervisor will ask about:

**It is stratified.** `stratify=df["label"]` on both calls, so the phishing /
legitimate ratio is preserved in all three splits. Without this a random split
on an imbalanced corpus can put most positives in one partition and the test
metric becomes meaningless.

**It is done in two stages, and the second ratio is recomputed.** You cannot
take 15% twice from different denominators. The test set is carved off first,
then validation is taken from what remains using
`relative_val_ratio = val_ratio / (train_ratio + val_ratio)` = `0.15 / 0.85`
= **0.1765**. Taking a flat 0.15 of the remainder would yield 12.75% of the
original, not 15%.

**It is reproducible.** `random_state = RANDOM_SEED = 42`
(`settings.py:94`), passed to both calls. Same input, same split, every run.

Also relevant:
- `balance_max_ratio = 1.5` — when the majority/minority ratio exceeds 1.5 the
  majority class is downsampled. Prevents a classifier that scores well by
  always predicting the majority.
- `max_training_rows = 0` — no cap by default.
- `tranco_sample_size = 300,000` — legitimate-URL sample size.

### 4.2 Models and hyperparameters

`src/models/baseline_models.py`. All use `random_state=42`.

| Model | Key hyperparameters |
|---|---|
| Logistic Regression | `C`, `max_iter`, `solver` (line 356-367) |
| Random Forest | `n_estimators=200`, `max_depth=30`, `max_features`, `n_jobs=-1` |
| Decision Tree | `max_depth=20`, `min_samples_split`, `min_samples_leaf` |
| Extra Trees | `n_estimators=200`, `max_depth=30`, `min_samples_split=5`, `min_samples_leaf=2`, `max_features="sqrt"` |
| XGBoost | lazily imported (`_import_xgboost`, line 41) |

### 4.3 Calibration — why raw probabilities are not used

`src/scoring/calibrator.py`. A model that outputs 0.9 does not necessarily mean
90% of such URLs are phishing; tree ensembles in particular are systematically
over-confident. `ConfidenceCalibrator` corrects this post-hoc.

Default method: **Platt scaling** — `f(p) = sigmoid(A·p + B)`, fitted by
logistic regression on held-out predictions. Alternatives implemented:
`isotonic`, `temperature`, `identity`.

**Fitted on the validation split**, falling back to train if validation is
unavailable (`baseline_models.py:119-131`). Fitting a calibrator on the
training set the model already saw is the classic mistake — the model is
over-confident *on that data by construction*, so the calibrator learns nothing.
If calibration fails the code degrades to `identity` rather than shipping a
wrongly-scaled probability.

This is what makes reported confidence meaningful: among URLs scored 0.8, about
80% should be phishing. Measured by ECE/MCE.

### 4.4 Decision fusion

The final verdict is not the classifier alone. `config/settings.yaml`:

**Decision weights** — ml_probability 0.35, rule_engine 0.30,
threat_intelligence 0.20, domain_trust_signals 0.15.

**Ensemble weights** — xgboost 0.35, transformer 0.20, rules 0.20,
threat_intelligence 0.15, trust 0.10. *Weights of unavailable signals are
redistributed*, so a missing transformer does not silently drag every score
down.

**Three-class thresholds** on the composite risk score: legitimate ≤30,
suspicious ≤60, phishing ≤100.

Rules and trust signals carry 45–65% of the decision. A model failure degrades
the verdict; it does not invert it.

---

## 5. Correlation — the mathematics

`evidence_correlation_engine/ciis_correlation/correlation/`

### 5.1 The scoring formula

For every unordered pair of evidence items in a case, twelve factor types are
evaluated. Each contributing factor adds:

```
factor weight = type weight × value specificity
```

summed over shared values, then squashed:

```
confidence = 1 − exp(−Σweight / 1.6)
```

`correlation_confidence_normaliser = 1.6` (`core/config.py:141`), applied at
`correlation/service.py:298`.

**Why exponential squashing.** Weight is unbounded — twenty shared entities give
twenty times one entity's weight — but confidence must lie in [0,1] and must
saturate. `1 − exp(−x/λ)` is monotonic, has no ceiling artefacts, and its
derivative falls as evidence accumulates: the tenth shared phone number should
add less than the first. λ=1.6 sets where saturation begins — a single wallet
match (weight 1.00) yields `1 − exp(−0.625)` = **0.465**, landing in MEDIUM;
two independent strong factors reach STRONG. λ was chosen so that one strong
identifier alone is suggestive but not conclusive.

### 5.2 Type weights

`core/config.py:77`. How identifying a *kind* of entity is:

| Type | Weight | Type | Weight |
|---|---|---|---|
| wallets, esewa/khalti/imepay ids, bank_accounts, card_numbers, eth/btc wallets, file_hash | **1.00** | urls | 0.75 |
| transaction_ids | 0.95 | device_metadata, social_media_urls | 0.70 |
| phones, whatsapp_numbers | 0.90 | domains, ipv4, ipv6 | 0.60 |
| emails, mac_addresses | 0.85 | image_metadata | 0.50 |
| threat_intelligence | 0.80 | timeline_proximity | 0.40 |
| social/telegram/facebook/instagram | 0.80 | otp | 0.25, money 0.20 |

A shared wallet address is near-conclusive; a shared amount of money is barely
evidence. `correlation_factor_cap = 3` limits how many values of one type
contribute, so twenty shared domains cannot dominate.

### 5.3 Value specificity — the unsupervised learning

`correlation/specificity.py`. **This is the part most worth defending in a
viva.**

The problem: type weight alone treats every value of a type identically. "Both
items mention NPR 2,000" scored exactly like "both items share this wallet
address". On a real corpus that linked essentially every case to every other on
round amounts alone.

The fix: multiply by how identifying *this particular value* is, blending two
estimates.

**Rarity (corpus-learned)** — inverse document frequency, normalised so that
`df = 2` scores 1.0:

```
rarity = log1p(corpus_size / df) / log1p(corpus_size / 2)
```

Two items sharing a value means df is at least 2, so that is the most
identifying case possible and is pinned to 1.0.

**Intrinsic (prior)** — Shannon-style information in the string itself: length
× bits per symbol of its alphabet, scaled against the point where a value is
long and varied enough to be a unique identifier. Digit strings are scored
against a 10-symbol alphabet, alphanumerics against a much larger one.

**Blending** — weighted geometric mean in log space:

```
specificity = exp( trust·log(rarity) + (1−trust)·log(intrinsic) )
trust = corpus_size / (corpus_size + k),  k = 12
```

`correlation_corpus_prior_strength = 12.0` (`config.py:133`).

**Why a geometric mean and not arithmetic.** Both terms are multiplicative
evidence about the same quantity; averaging them in log space is a log-linear
opinion pool, and it means either term being near zero pulls the result down —
which is correct, because a value that is common *or* structurally trivial is
not identifying.

**Why `trust` shrinks toward the prior.** With 5 evidence items, df counts are
statistically meaningless; with 5,000 they are reliable. `k=12` means the corpus
gets equal weight with the prior at 12 documents, and dominates beyond. This is
Bayesian shrinkage, and it is why the system behaves sensibly on day one with an
empty corpus.

Floor: `correlation_specificity_floor = 0.02` — a factor is never multiplied to
exactly zero, so an explanation always shows why something was discounted rather
than silently vanishing.

**Why unsupervised.** Correlation has no ground truth. Nobody has labelled which
evidence pairs are genuinely related, and manufacturing those labels would
produce a classifier whose confidence means nothing. The learning that *is*
justified by the data is estimating how common each value is — and that is what
runs. The per-factor breakdown persisted in every artifact is already the
feature vector a supervised ranker would consume, once investigators have
confirmed or rejected enough links to serve as labels.

### 5.4 Relationship bands

`config.py:143` — `NO_RELATIONSHIP <0.05 ≤ WEAK <0.30 ≤ MEDIUM <0.55 ≤ STRONG
<0.80 ≤ VERY_STRONG`.

### 5.5 Cross-case correlation

`crosscase.py`. Every entity lives in exactly one file (`entities.csv`), so
there is no second index to fall out of sync. Lookups are served from an
in-memory index invalidated by the file's mtime+size. Deleting a case's rows
removes it from cross-case correlation automatically.

Cross-case reuses the same weights, factor cap, normaliser and bands, so
cross-case and within-case confidence are on one scale.

**Bidirectional propagation:** when a new case links to an already-analysed
case, that case's report is regenerated from its stored artifacts
(`regenerate_with_cross_case`) so it reflects the new link without re-running
its full analysis.

---

## 6. Downstream analysis

### 6.1 Campaigns

Connected-component clustering over correlation pairs with confidence ≥
`campaign_min_confidence = 0.55` (STRONG and above), minimum 2 members
(`config.py:181`). Signature = top 5 shared entities.

### 6.2 Suspects

Anchored on identity entities. Six weighted components (`config.py`):

| Component | Weight | Meaning |
|---|---|---|
| identity_strength | 0.25 | a wallet identifies better than an email |
| evidence_count | 0.20 | breadth across the case |
| evidence_confidence | 0.15 | mean Phase-1 score of its evidence |
| threat_intelligence | 0.15 | anchor or co-occurring URL flagged |
| correlation_strength | 0.15 | how tightly its evidence set inter-links |
| timeline_span | 0.10 | sustained activity, not one burst |

### 6.3 Timeline

Timestamp resolution, in strict precedence:

1. **`content_date_time`** — explicit date+time in the OCR text. Highest
   forensic value: when the event actually happened.
2. **`content_date_only`** / **`content_time_only`** — partial, combined with
   the upload date.
3. **`upload_time`** — last resort. This is when the *file was processed*, not
   when the event occurred, and is labelled as such.

Attack stages: `initial_contact → social_engineering → credential_theft →
financial_transaction → post_attack`. Progression is checked against this
canonical order and flagged when inconsistent.

The algorithm (`timeline/engine.py`) is framework-independent — plain dicts in,
plain dicts out, standard library only. That is what makes it testable alone
and is why it has a local plural helper rather than importing one.

### 6.4 Priority

Six weighted dimensions (`config.py`): evidence_confidence 0.20,
threat_intelligence 0.20, forgery_risk 0.15, campaign_size 0.15,
correlation_strength 0.15, timeline_criticality 0.15.

**Weights are renormalised over available dimensions** — a case with no threat
intel is not penalised as though it had scored zero. Bands: LOW <30 ≤ MEDIUM
<55 ≤ HIGH <75 ≤ CRITICAL.

### 6.5 Report

19 sections + Statement of Limitations, in pipeline order: Evidence → Timeline →
Correlation → Cross-Case → Campaign → Suspect → … The order is defined once in
`reporting/service.py :: SECTION_ORDER` and the Markdown, JSON and PDF
renderers all derive from it, so the three exports cannot drift.

Every sentence is templated over a concrete stored value. The generator has no
free-text capability, so it structurally cannot state something the analysis did
not compute; missing inputs render "not available".

PDF: cover page with handling caveat and document control block, contents with
real page numbers (two-pass layout), numbered sections, running header,
Statement of Limitations, signature block, end-of-report marker.

---

## 7. Storage and API

One tree, owned by the OCR engine, read strictly read-only by everything
downstream through `CaseDataRepository`:

```
storage/
  cases.csv  evidence.csv  entities.csv  ocr_results.csv    chain of custody
  json/<CASE_ID>.json                                       full OCR output
  forensics/<EVIDENCE_ID>/                                  Phase-1 reports
  investigation/<CASE_ID>/                                  analysis artifacts
  investigation/investigation_audit_log.csv                 every module, every run
```

No database. Platform state is CSV/JSON. Every write goes through the
filesystem, so mtime-keyed caches stay exactly as fresh as the file.

**Failure isolation:** each pipeline module is wrapped so one broken analysis is
audited as ERROR and the rest continue. A case is never left with no report
because one module failed.

---

## 8. Verification

### Test suites (all passing)

| Suite | Tests |
|---|---|
| `evidence_ocr_engine` | 392 |
| `evidence_correlation_engine` | 93 |
| `timeline_report_engine` | 52 |
| `ciis_api` | 53 |
| `ciis_frontend` (vitest) | 67 |
| **Total** | **657** |

Plus `tsc --noEmit` clean.

### Refactor equivalence

The four-module split was verified by A/B: a git worktree at the pre-refactor
commit, both trees seeded with byte-identical storage, the same case analysed
through old and new code. **91 artifacts compared, differences only in
`analysis_time_ms`, `computed_at`, and the provenance hashes downstream of
them.** Every correlation weight, campaign membership, suspect score, graph node
and timeline event identical. Both runs: `priority 75.9/100 CRITICAL`.

### Running system (verified live)

```
API          http://127.0.0.1:8001   Django, engines loaded in-process
frontend     http://localhost:5173   Vite (binds IPv6 [::1]; use localhost)
```

- `GET /api/cases/<id>/reports/` returns the JSON, Markdown **and PDF** entries.
- `GET /api/cases/<id>/reports/investigation_report.pdf/download/` →
  `HTTP 200`, `Content-Type: application/pdf`,
  `Content-Disposition: attachment`, 47,721 bytes, `%PDF-1.4` header.
- Changed frontend modules transform cleanly and contain the new code
  (`data-timeline-tooltip`, `timeline-label-column`, `GAP_LABEL_MIN_PX`,
  `Download PDF`, `format === "pdf"`).

### Accuracy evaluation

Harnesses exist and run against gold labels:

| Script | Measures |
|---|---|
| `evidence_ocr_engine/scripts/run_table_6_1.py` | OCR accuracy |
| `evidence_ocr_engine/scripts/run_table_6_2.py` | entity extraction |
| `evidence_correlation_engine/scripts/run_table_6_4.py` | correlation vs gold, with baselines |
| `timeline_report_engine/scripts/run_table_6_5.py` | timeline order/timestamp accuracy |
| `timeline_report_engine/scripts/report_review.py` | report correctness |

Correlation is scored against two **baselines** — exact entity matching and
unweighted shared-entity counting (`evaluation/correlation_baselines.py`) — so
the weighted engine has to beat something, not just produce a number. Timeline
is scored against the naive upload-time-order baseline.

> **Numbers are not reproduced here.** The gold corpus in this repository is
> illustrative demo data, not a labelled research set, and quoting accuracy
> figures from it would misrepresent them. Run the scripts against a real
> labelled corpus before citing any figure.

---

## 9. Anticipated questions

**Why no ML for correlation?**
No ground truth exists. See §5.3. The architecture is ready for it — the
per-factor breakdown is the feature vector — once investigator decisions supply
labels.

**Why 1.6, 12, 0.55, 0.02?**
1.6 sets where confidence saturates so one strong identifier is suggestive but
not conclusive (§5.1). 12 is where corpus evidence matches the prior in
strength (§5.3). 0.55 is the STRONG band boundary, so campaigns cluster only on
strong links. 0.02 keeps discounted factors visible in explanations. All live in
`config.py` with `INVESTIGATION_*` env overrides; **no service contains a
hardcoded value**.

**Why 70/15/15 and not 80/20?**
Because calibration needs its own data. An 80/20 split gives you nowhere
untouched to fit the calibrator, and fitting it on training data teaches it
nothing (§4.3). The test 15% is touched once.

**Is the report reproducible?**
Deterministic given the same storage state — verified by the A/B run. Volatile
fields are timing and IDs only. Every report carries SHA-256 digests of the
exact artifacts it was built from.

**Can the system hallucinate a finding?**
Structurally no. The report generator is templated over stored values with no
free-text path. The one generative-adjacent component (the ML classifier) only
scores URLs and its output is labelled and weighted, never asserted as fact.

**What happens if a module fails?**
Audited as ERROR; the others continue; the report says the input was
unavailable. Verified by `test_one_failing_module_does_not_abort`.

**Biggest weakness?**
The gold corpus is small and illustrative, so accuracy figures are not yet
defensible. Entity extraction is rule-based and tuned to Nepali payment
ecosystems — it will need retuning elsewhere. Cross-case correlation is
O(cases × entities) and has not been load-tested beyond a few hundred items.

---

## 10. Reproducing this

```bash
./dev.sh doctor            # verify toolchain
./dev.sh up                # API + frontend + engines
./dev.sh test              # all suites

cd timeline_report_engine
python investigation_cli.py analyze <CASE_ID>   # or --all
```

Threat engine (separate virtualenv):

```bash
./dev.sh threat <url>
```
