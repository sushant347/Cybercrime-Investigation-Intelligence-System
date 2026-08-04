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

### 4.2 The training corpus

Reference run `20260712T090000Z`
(`results/TRAINING_IMPROVEMENTS_REPORT.md`):

| | |
|---|---|
| Total URLs | **585,040** (305,573 phishing / 279,467 legitimate) |
| Train | 409,528 |
| Validation | 87,756 |
| Test | 87,756 |
| Split | stratified 70/15/15, seed 42 |
| Sources | the four usable datasets in `sample/` |

Class balance is 52/48, so the `balance_max_ratio = 1.5` downsampling guard
never fires on this corpus. Feature extraction is chunk-streamed
(`EXTRACTION_CHUNK_SIZE = 50000`) into a preallocated float32 matrix, so memory
is bounded regardless of corpus size.

### 4.3 How the model is trained

Eight candidates are trained and compared on identical splits, then one is
promoted. The pipeline is `FullRetrainingPipeline.run()`
(`src/training/full_retraining.py`), stages:

```
discover datasets → clean → merge → stratified 70/15/15 split
  → extract features (chunk-streamed)
  → tune          (Optuna TPE, resumable SQLite studies)
  → train         (all 8 candidates, full 409,528-row training split)
  → cross-validate(stratified 5-fold, mean ± std)
  → evaluate      (held-out test, touched once)
  → auto-recalibrate
  → error analysis + reports
```

Every stage constant:

| Constant | Value | Source |
|---|---|---|
| `CV_FOLDS` | 5 | `settings.py:155` |
| `CV_SAMPLE_SIZE` | 0 = full split (run used 100,000; SVM 60,000) | `settings.py:159` |
| `OPTUNA_TRIALS` | 25 | `settings.py:163` |
| `TUNING_SAMPLE_SIZE` | 0 = full (run used 60,000 stratified) | `settings.py:167` |
| `EARLY_STOPPING_ROUNDS` | 30 | `settings.py:171` |
| `EXTRACTION_CHUNK_SIZE` | 50,000 | `settings.py:175` |
| ECE improvement threshold for auto-recalibration | 0.002 | `calibration_analysis.py:110` |
| Seed | 42, end to end | `settings.py:94` |

**Selection rule, stated in the pipeline:** *F1 → ROC-AUC → Recall → Precision;
never accuracy alone.* Accuracy is excluded deliberately — on a 52/48 corpus it
is a weak discriminator, and on any imbalanced slice it rewards predicting the
majority.

### 4.4 Regularisation — the alpha values

XGBoost carries two regularisation terms. Its objective is

```
L = Σ l(ŷᵢ, yᵢ)  +  Σ_k [ γ·T_k  +  ½·λ·‖w_k‖²  +  α·‖w_k‖₁ ]
                        ↑          ↑                ↑
                    leaf count   L2 (reg_lambda)  L1 (reg_alpha)
```

- **α (`reg_alpha`, L1)** drives individual leaf weights to exactly zero —
  sparsity, so uninformative features drop out of the model entirely.
- **λ (`reg_lambda`, L2)** shrinks all leaf weights smoothly toward zero —
  variance reduction without elimination.
- **γ (`gamma`)** is the minimum loss reduction required to split at all —
  pre-pruning.

Three different (α, λ) pairs exist in the codebase, for three different
purposes. This is worth being precise about:

| Context | α (L1) | λ (L2) | Other | Status |
|---|---|---|---|---|
| Class default | 0.1 | 1.0 | depth 8, lr 0.1, 300 est, γ 0.1, min_child_weight 3 | fallback only (`baseline_models.py:547`) |
| **Deployed** | **0.01599** | **0.45043** | depth 11, lr 0.0862, 186 est (early-stopped), subsample 0.693, colsample 0.918, γ 0.0545, min_child_weight 5 | **live** — read from `checkpoints/xgboost.pkl` |
| Superseded v3 | 0.5 | 2.0 | depth 7, lr 0.07, 500 est, subsample 0.9, colsample 0.7, γ 0.0 | earlier 200k corpus (`final_model_v3_report.json`) |

The deployed values are Optuna's best trial, applied verbatim — confirmed by
unpickling the live checkpoint, not by reading a report about it.

**Why so little L1 (α = 0.016)?** Because the corpus is large and the feature
space is small: 585,040 rows against **71 features**. L1's job is to zero out
uninformative dimensions, and with 71 hand-engineered features there is little
to eliminate — every one was included because it carries signal. Heavy L1 would
discard real information. The variance control is carried by λ, `subsample`
0.693 and `colsample_bytree` 0.918 instead, which is the right division of
labour when n ≫ p.

**Contrast with the superseded v3 checkpoint** (α 0.5, λ 2.0, depth 7). That was
trained on a smaller 200k corpus where the same model overfits — the untuned
baseline showed a **0.198 train/validation gap**, the worst of any candidate
bar the decision tree. Heavy regularisation was the correct response *at that
corpus size*; its recall of 0.645 shows what it cost. Growing the corpus to
585k solved the same problem better, which is why the deployed model can afford
depth 11 and α 0.016.

The general rule this illustrates: **regularisation strength is a function of
the data volume, not a property of the algorithm.** Quoting α = 0.5 as "our
value" without saying which corpus it belongs to would be meaningless.

LightGBM's tuned α is 1.037 — 65× XGBoost's — because its leaf-wise growth
overfits far more aggressively and needs heavy L1 to compensate.

### 4.5 Why XGBoost, and why not the others

The honest answer is that **XGBoost did not dominate**. It was chosen on a
specific, defensible margin. Here is the whole evidence chain.

**Stage 1 — untuned baseline** (`results/baseline_comparison_report.json`,
small early corpus). XGBoost *lost*:

| Model | Train acc | Val acc | Val F1 | Val AUC | Gap |
|---|---|---|---|---|---|
| extra_trees | 0.9262 | **0.8200** | **0.8266** | **0.9065** | 0.106 |
| random_forest | 0.9478 | 0.8130 | 0.8168 | 0.8996 | 0.135 |
| xgboost | 0.9832 | 0.7850 | 0.7869 | 0.8844 | **0.198** |
| lightgbm | 0.9794 | 0.7850 | 0.7844 | 0.8925 | 0.194 |
| decision_tree | 0.9484 | 0.7490 | 0.7426 | 0.7806 | 0.199 |
| logistic_regression | 0.7308 | 0.7420 | 0.7557 | 0.8040 | −0.011 |
| svm | 0.7316 | 0.7380 | 0.7505 | 0.8053 | −0.006 |
| naive_bayes | 0.6410 | 0.6200 | 0.6870 | 0.6935 | 0.021 |

Untuned, XGBoost was fourth. Had selection stopped here, Extra Trees would have
shipped. What this table really shows is that the boosters were **badly
regularised**, not weak — a 0.198 gap is a tuning failure, not a ceiling.

**Stage 2 — 5-fold stratified cross-validation** (full corpus, 100k sample).
After tuning, the ranking inverts and the top two converge:

| Model | F1 (mean ± std) | ROC-AUC | MCC |
|---|---|---|---|
| lightgbm | **0.9771 ± 0.0009** | 0.9967 | 0.9519 |
| xgboost | 0.9768 ± 0.0010 | 0.9966 | 0.9514 |
| random_forest | 0.9738 ± 0.0011 | 0.9957 | 0.9449 |
| extra_trees | 0.9715 ± 0.0011 | 0.9949 | 0.9400 |
| decision_tree | 0.9642 ± 0.0013 | 0.9707 | 0.9255 |
| logistic_regression | 0.8995 ± 0.0028 | 0.9497 | 0.7865 |
| svm | 0.8983 ± 0.0024 | 0.9489 | 0.7841 |
| naive_bayes | 0.8199 ± 0.0050 | 0.8935 | 0.6407 |

LightGBM leads by **0.0003 — a third of one standard deviation.** These two are
statistically indistinguishable. Optuna agrees: best trial F1 0.9769 (LightGBM)
vs 0.9759 (XGBoost). On tuning evidence alone, LightGBM is marginally ahead.

**Stage 3 — held-out test, 87,756 URLs, touched once.** This is the only
untouched measurement, and it is where XGBoost wins:

| Model | F1 | ROC-AUC | MCC | FPR | **FNR** |
|---|---|---|---|---|---|
| **xgboost** ★ | **0.9800** | 0.9973 | 0.9579 | 0.0263 | **0.0162** |
| lightgbm | 0.9784 | 0.9968 | 0.9546 | 0.0278 | 0.0180 |
| random_forest | 0.9756 | 0.9959 | 0.9488 | 0.0324 | 0.0194 |
| extra_trees | 0.9752 | 0.9958 | 0.9478 | 0.0348 | 0.0182 |
| decision_tree | 0.9727 | 0.9824 | 0.9429 | 0.0296 | 0.0275 |
| logistic_regression | 0.8968 | 0.9475 | 0.7809 | 0.1305 | 0.0901 |
| svm | 0.8968 | 0.9479 | 0.7809 | 0.1308 | 0.0898 |
| naive_bayes | 0.8027 | 0.8935 | 0.6168 | 0.1416 | 0.2427 |

#### The reasons that are not F1

**1. False-negative rate — the metric that actually matters here.**
XGBoost 1.62% vs LightGBM 1.80%. A false negative is a phishing URL reported as
safe: the investigator is told there is nothing there, and the malicious
indicator never enters the correlation graph, the timeline or the report. A
false positive merely costs a check. On 87,756 URLs that 0.18 pp difference is
~158 additional missed phishing URLs. **This asymmetry, not F1, is the
operational argument.**

**2. Native SHAP without an optional dependency.**
`src/explainability/shap_explainer.py` uses `shap.TreeExplainer` when the `shap`
package is present, and falls back to **XGBoost's own `pred_contribs`** when it
is not — the same exact-SHAP algorithm, computed by the booster itself. Every
prediction ships its top-10 contributing features. LightGBM has no equivalent
fallback wired here, so choosing it would make explanations depend on an
optional third-party package.

For a forensic system this is close to decisive. A verdict an investigator
cannot decompose into "which features drove this, and by how much" is not
usable as evidence. Model choice was constrained by explainability before
accuracy entered the argument.

**3. Calibration behaves better.** With isotonic regression on the production
XGBoost, ECE and MCE both reach 0.00000 (§4.6). Platt on the same model left an
MCE of 0.209 — a 21-point maximum calibration error in some probability bin.

**4. Regularisation is more controllable.** XGBoost exposes α, λ and γ as
independent levers, which is what allowed the production checkpoint to be pulled
back to α 0.5 / λ 2.0 / depth 7 to close the overfitting gap. LightGBM's
leaf-wise growth needed α 1.037 to achieve comparable control.

#### Why each rejected model was rejected

| Model | Reason beyond score |
|---|---|
| **LightGBM** | Statistically tied on CV, but lost on the held-out set and on FNR, and has no dependency-free SHAP path. Retained as a candidate — it is 0.0016 F1 away and would be the immediate fallback. |
| **Extra Trees** | Won the *untuned* comparison, which is why it was kept in the pool. After tuning it sits 0.0048 F1 and 0.2 pp FNR behind, with no probability-calibration advantage. |
| **Random Forest** | Consistently third among ensembles. Bagging cannot exploit residual structure the way boosting does; the gap is systematic, not noise. |
| **Decision Tree** | 0.199 train/val gap — memorises. Its 2.75% FNR is 70% worse than XGBoost's. Interpretability, its usual selling point, is redundant when SHAP is available on the ensemble. |
| **Logistic Regression** | **13.05% FPR.** Linear in feature space; phishing URL structure is full of interactions (short domain age *and* suspicious TLD *and* no SPF) that a linear boundary cannot represent. |
| **SVM** | Statistically identical to logistic regression (F1 0.8968 both), at far greater training cost — needs an 80k subsample where boosters train on the full 409,528 rows. Pays a large cost for nothing. |
| **Naive Bayes** | **24.27% FNR** — misses a quarter of all phishing. Its feature-independence assumption is flatly false here: URL length, entropy and TLD are strongly correlated. Included only as a floor. |

**Summary.** XGBoost is not the best model by a comfortable margin; it is the
best model by ~0.0016 F1 and 0.18 pp FNR over LightGBM, and it was preferred
because it wins on the untouched test set, on the error direction that matters,
and on explainability. That is a defensible basis for selection. Claiming it
dominated the field would not be.

#### Which checkpoint is deployed — verified, not assumed

Two training runs exist in `results/`, on **different corpora**, with metrics far
apart. Quoting one under the other's provenance is the easiest way to lose
credibility, so this was resolved by unpickling the live checkpoint rather than
trusting a report.

| | **Deployed** — run `20260712T090000Z` | Superseded — `final_model_v3_report.json` |
|---|---|---|
| Corpus | **585,040** URLs (305,573 phishing / 279,467 legit) | `ds-curated-200k-v3` |
| Evaluated on | 87,756 held-out test | 40,000 validation |
| Accuracy | 0.9790 | 0.8316 |
| F1 | **0.9800** | 0.7168 |
| ROC-AUC | 0.9973 | 0.9125 |
| Recall | 0.9838 | 0.6449 |
| α / λ | 0.01599 / 0.45043 | 0.5 / 2.0 |

`checkpoints/production_model.json` and the pickle agree: `run_id
20260712T090000Z`, dataset 585,040, 71 features, isotonic calibrator, XGBoost
params exactly Optuna's best trial. **The high figures are the live ones.** The
v3 report describes an earlier, smaller-corpus checkpoint that is no longer
deployed.

The checkpoint also records its own selection rationale, which is worth quoting
verbatim in a viva because it was written by the pipeline, not afterwards:

> *"Selected 'xgboost' using the priority F1 > ROC-AUC > Recall > Precision
> (accuracy alone is never used): F1=0.9800, ROC-AUC=0.9973, Recall=0.9838,
> Precision=0.9762, PR-AUC=0.9977, MCC=0.9579. Runner-up: 'lightgbm'."*

Training took 1,652 s (~28 min).

**One caveat.** `dataset_directory` in that file is
`/sessions/…/mnt/project/sample` — a sandbox path, so the model was trained in a
different environment from this checkout. The artifact is reproducible from the
recorded run id and seed, but the path will not resolve locally.

### 4.6 Calibration — why raw probabilities are not used

`src/scoring/calibrator.py`. A model that outputs 0.9 does not mean 90% of such
URLs are phishing; tree ensembles are systematically over-confident because each
leaf reports a purity, not a posterior. `ConfidenceCalibrator` corrects this
post-hoc.

Four methods implemented:

| Method | Form | Fits |
|---|---|---|
| `platt` (class default) | `f(p) = sigmoid(A·p + B)` | 2 parameters |
| `isotonic` | monotone step function | non-parametric |
| `temperature` | `f(p) = sigmoid(logit(p)/T)` | 1 parameter |
| `identity` | `f(p) = p` | none |

**Fitted on the validation split**, falling back to train only if validation is
unavailable (`baseline_models.py:119-131`). Fitting on the training set is the
classic error: the model is over-confident *on that data by construction*, so
the calibrator sees no miscalibration to correct. If fitting fails the code
degrades to `identity` rather than shipping a wrongly-scaled probability.

**Measured on the production model** (`TRAINING_IMPROVEMENTS_REPORT.md` §5):

| Calibrator | Brier ↓ | ECE ↓ | MCE ↓ |
|---|---|---|---|
| uncalibrated | 0.01517 | 0.00333 | 0.06338 |
| platt (previous) | 0.01598 | 0.00357 | **0.20943** |
| temperature | 0.01514 | 0.00111 | 0.05186 |
| **isotonic (applied)** | **0.01499** | **0.00000** | **0.00000** |

Read this carefully: **Platt was worse than no calibration at all** on this
model — Brier 0.01598 vs 0.01517, and an MCE of 0.209 meaning some probability
bin was off by 21 points. Platt assumes a sigmoidal distortion; XGBoost's
distortion here is not sigmoidal, so the two-parameter fit cannot represent it.
Isotonic, being non-parametric, can.

The pipeline switched the production calibrator from Platt to isotonic
**automatically**, because the ECE improvement exceeded the
`min_improvement = 0.002` threshold (`calibration_analysis.py:110`), and re-saved
the checkpoint in the same format — the predictor needed no change.

- **ECE** (Expected Calibration Error) — average gap between confidence and
  accuracy, weighted by bin population. The typical case.
- **MCE** (Maximum Calibration Error) — the worst bin. The one that matters for
  a forensic report, because it bounds how wrong any single quoted confidence
  can be.

This is what makes reported confidence meaningful: among URLs scored 0.8, about
80% are phishing.

### 4.7 Decision fusion

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

## 4A. The transformer — XLM-RoBERTa in semantic correction

There are two neural components in CIIS. §4 covered the phishing classifier.
This one sits much earlier, in the OCR engine, and is the more interesting of
the two because of *where* it is allowed to act.

`evidence_ocr_engine/backend/modules/evidence/semantic/`

### 4A.1 The problem it solves

OCR on a Nepali scam screenshot produces text that is mostly right and locally
wrong. A dictionary can tell you a token is not a word. It cannot tell you
*which* correction is the right one, because that depends on the sentence:

```
OCR output   : "तपाईंको खाता ब्लक भएको छ, तुरुन्तै [garbled] गर्नुहोस्"
candidates   : verify / verity / very / भेरिफाई
```

Every candidate is dictionary-valid in some sense. Only context distinguishes
them. Three properties make this hard:

1. **The text is bilingual, often mid-sentence.** Nepali scam messages mix
   Devanagari and Latin freely. A monolingual English model cannot score a
   Devanagari candidate at all.
2. **There is no labelled data.** Nobody has a corpus of Nepali OCR errors
   paired with corrections.
3. **The correction must never invent.** This is evidence. A model that
   *generates* replacement text is disqualified outright.

### 4A.2 Why XLM-RoBERTa specifically

| Requirement | Why XLM-R satisfies it |
|---|---|
| Multilingual, incl. Nepali | Pretrained on 100 languages; Devanagari is in-vocabulary |
| No fine-tuning possible | Masked-LM pretraining is *already* the task — score a word in context |
| Must not generate | Fill-mask **scores a fixed candidate list**; it never emits free text |
| Must degrade offline | Optional dependency, heuristic fallback (§4A.5) |

A monolingual model (BERT, RoBERTa) fails requirement 1. A generative model
(GPT-style, mBART) fails requirement 3. mBERT satisfies both but is weaker on
low-resource languages. **XLM-RoBERTa is the smallest model that satisfies all
four**, which is why it is the one wired in.

### 4A.3 How it is used — inference only, scoring only

`validator.py :: XLMRobertaValidator`. No training, no fine-tuning, no
checkpoint of our own. The pretrained `xlm-roberta-base` runs as a **fill-mask
pipeline**.

For each suspicious token the pipeline builds the sentence with a sentinel at
the token's position, swaps the sentinel for the model's mask token, and asks
for the top *k* predictions:

```
sentence  : "तपाईंको खाता ब्लक भएको छ, तुरुन्तै ⁣SLOT⁣ गर्नुहोस्"
masked    : "तपाईंको खाता ब्लक भएको छ, तुरुन्तै <mask> गर्नुहोस्"
predictions ← pipe(masked, top_k=20)

cand_score = P(candidate | context)      from those predictions
orig_score = P(original  | context)

accept  ⟺  cand_score ≥ 0.15  AND  cand_score ≥ orig_score
```

| Parameter | Value | Meaning |
|---|---|---|
| `top_k` | 20 | how many mask predictions to search |
| `accept_threshold` | 0.15 | minimum probability for a candidate to be usable |
| pipeline `confidence_threshold` | 0.5 | second gate before a correction is applied |

Two gates, deliberately. The model must find the candidate *plausible*
(≥ 0.15) **and** more plausible than what the OCR actually produced — a
correction that the context likes less than the original is not a correction.
The pipeline then applies its own 0.5 confidence gate on top
(`semantic_pipeline.py:63`), so a weak model opinion cannot change evidence
text.

Candidates come from the rule-based `CandidateGenerator`. **The model never
proposes a word — it only ranks words the rules proposed.** That is the
structural guarantee that it cannot hallucinate into evidence.

### 4A.4 Where it is allowed to act — the important part

```
raw_text ──► cleaned_text ──► enhanced_text ──► semantic_text ──► entities
 (frozen)      (frozen)         (frozen)        (model may act)   (rules only)
```

The forensic invariants — `raw_text`, `cleaned_text`, `enhanced_text` — are
**never modified**. The model writes to `semantic_text` and nothing else. Every
correction it accepts is recorded with its original, its candidate, the
confidence, the validator name and the reason.

Downstream, entity extraction, correlation, campaigns, suspects, timeline and
priority remain **entirely rule-based and deterministic**. The transformer
improves the *text quality* those rules read. It never contributes to a score.

This is the answer to "should the project use more ML": it already uses exactly
as much as is defensible. A model that improves recognition is auditable — you
can show the before, the after, and the probability. A model that emits a
suspect score is not.

### 4A.5 What it is worth, honestly

**Verified status of this deployment:**

```
semantic_validator   : heuristic
semantic_ml_available: false
```

`transformers` and `torch` are **commented out** of
`evidence_ocr_engine/requirements.txt` (lines 30-31) — together a multi-GB
download. So on a default install **the transformer does not run**; the
`HeuristicSemanticValidator` does, accepting a candidate when it is a
single-script dictionary-valid word replacing a mixed-script token.

That degradation is by design and correct. What was wrong until this change is
that it was **invisible**: nothing told an operator which validator their
evidence had been through. `engine_health()` now reports
`semantic_validator` / `semantic_ml_available`, and `./dev.sh doctor` prints
the same, so the mode is knowable before evidence is processed rather than
inferred afterwards from per-item fields.

**To turn it on:**

```bash
.venv-platform/Scripts/python -m pip install "transformers>=4.40" "torch>=2.0"
./dev.sh doctor      # -> semantic validator: xlm-roberta-base
```

Nothing else changes: the pipeline picks it up automatically, and the stored
`validator` field on each correction records which one ran.

**What it buys.** Fewer OCR errors surviving into entity extraction. That
matters because a mangled wallet address is a *missed correlation*, and a
missed correlation is a link between two cases that never appears. The value is
indirect but it is upstream of everything.

**What it costs.** ~1.1 GB of model weights, a slow first inference, and a
dependency that must be present on every deployment that wants it.

**Whether it is worth turning on: not measured yet.** There is no A/B of
correction accuracy with and against the heuristic, because that needs a gold
set of OCR errors and their correct resolutions, and this repository does not
have one. Until it does, "XLM-R improves extraction" is a reasonable
expectation, not a demonstrated result — and this report will not claim it as
one. The harness to measure it would be the same shape as
`scripts/run_table_6_2.py` (entity extraction against gold), run twice.

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

### 6.6 Statutory basis — mapping findings to the law

`timeline_report_engine/ciis_timeline_report/legal/`

A technical report tells an officer what the evidence shows. It does not tell
them which law that engages, and in practice that translation gets done from
memory by whoever writes the file — inconsistently, and invisibly. This module
makes it explicit and reviewable.

It maps stored findings onto the **Electronic Transactions Act, 2063 (2008)**
of Nepal, transcribed from the text in [`samples/legal_corpus/`](samples/legal_corpus/).

**Electronic Transactions Act, 2063 (2008)** — 8 of the Act's 15 offence
sections:

| Section | Offence | Engaged when |
|---|---|---|
| **52** | To commit computer fraud | payment-rail identifiers (wallet, bank account, card, transaction id) appear with a money value |
| **47** | Publication of illegal materials in electronic form | threat intelligence flags a URL or domain present in the evidence |
| **45** | Unauthorized access in computer materials | credential material (OTP, password, PIN, CVV, login) appears as an entity or in the text |
| **46** | Damage to any computer and information system | the complainant's own account describes losing access — blocked, locked out, deleted |
| **53** | Abetment / conspiracy | a campaign cluster groups two or more evidence items |
| **54** | Punishment to the accomplice | same finding as s.53; distinct liability at half the principal's penalty |
| **55** | Offence committed outside Nepal | the case shares identifiers with another case |
| **56** | Confiscation | consequential — at least one offence above is engaged, so the devices used fall within the seizure power |

**Intellectual property.** Brand impersonation is the defining feature of these
scams: a page carrying eSewa's mark that eSewa did not publish. That is an
offence twice over, prosecuted separately, and omitting the second left an
officer with a clear case of mark misuse never being told so.

| Statute | Section | Engaged when |
|---|---|---|
| Patent, Design and Trade Mark Act, 2022 | **19** | logo/brand detection identifies a registered brand's mark in the evidence |
| Copyright Act, 2059 | **27** | a brand's artwork is *template-matched*, i.e. reproduced rather than merely named |

The Copyright rule is **dormant on a default install** — template matching only
runs once an investigator places reference logos in
`storage/forensics/logo_templates/<brand>/`. It is tested with a simulated
template match so the rule is verified rather than left unexercised until
someone happens to supply artwork. Naming a brand engages the mark (s.19);
reproducing its artwork engages copyright as well, and the detector
distinguishes the two.

**What is deliberately not assessed** is recorded in
`provisions.UNASSESSED_ETA_SECTIONS` with a reason each — s.44 (no signal for
source-code tampering), s.48 (requires establishing authorised access), s.49–51
(digital-signature certification), s.57 (no organisation entity is extracted),
s.58 (residual). Their absence is a scoping decision, not an oversight.

Each entry carries the section number, the heading as enacted and the penalty
**as written** — never paraphrased into a different figure — plus the concrete
finding that engaged it and the evidence ids behind that finding.

**The design constraint that matters.** The module reports that the evidence
contains the features a provision describes. It never asserts an offence.
Intent, authorisation and identity are matters for investigation, and a caveat
saying so travels with the output wherever it renders — Markdown, JSON, PDF and
the on-screen report. A test asserts that no generated sentence contains
"is guilty", "has committed", "proves that" or "must be charged"; a sentence
that read as a finding of guilt would make the whole section inadmissible.

Two further properties, both tested:

- **Silence is not exoneration.** With nothing engaged, the summary says so
  explicitly: *"This is not a conclusion that no offence occurred — it means the
  specific features this engine looks for are absent from the evidence held."*
- **One failing rule does not cost the section.** Each rule is isolated; a
  broken one is logged and the other four still run.

Worked example, `CASE_185915593C` — the findings engage **s.52, s.47 and s.53**.
s.45 correctly did *not* fire: that case has no OTP entity and no credential
words in any evidence text. The law is separated from the trigger in
`provisions.py` for exactly this reason — the statute is fixed text that must
not drift, while the trigger is this engine's editorial judgement and is open
to challenge.

**Scope limit.** Only the five provisions above are assessed. Others in the Act,
and the subordinate instruments in `samples/legal_corpus/` (the Rules 2064, the
National Cyber Security Policy 2023, the NRB guidelines, the IP statutes
relevant to brand impersonation), are **not** modelled.

**On the corpus, precisely.** Nothing is trained on it. Five provisions of one
Act were transcribed by hand — section number, heading as enacted, penalty as
written. The defensible claim is that the module is *grounded in the primary
legislation and every citation is checkable against the source in the
repository*, which is stronger than "trained on" because it can be verified by
opening `provisions.py` beside the Act.

**The Nepali texts cannot be machine-read.** Both Nepali originals are typeset
in legacy `Preeti` / `PCSNEPALI` fonts: they display as Devanagari but the bytes
are Latin, so the Act's own title extracts as `ljB'tLo sf/f]af/ P]g`. A Preeti
transliteration table exists and is deliberately not used — applying one to
statutory text nobody here can proof-read would produce citations that look
right and are wrong, which is the failure this system exists to prevent.

What *is* taken from the Nepali material is the Act's title,
`विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३`, sourced from the gazette copy's
filename (proper Unicode), plus a standing note in every report that the
citations come from the English text and the Nepali governs where they differ.
Section headings are English-only until a Nepali reader verifies a
transliteration — that is a person problem, not a code problem.

The PDF prints the Latin note rather than the Devanagari title: its standard-14
fonts draw Devanagari as placeholder boxes, and it once emitted
`IIIIIIIII (IIIIIIIIIIII)`, which on a legal document reads as corruption. The
Markdown and JSON exports carry the Nepali in full. `samples/legal_corpus/manifest.json`
records the extractability verdict for every document.

---

## 6A. On sentiment analysis — why it was not added

This was raised as a candidate feature and rejected. The reasoning is recorded
because "why isn't there an NLP component?" is a fair question to be asked.

**Sentiment is the wrong instrument for this problem.** Generic sentiment
classifies text as positive, negative or neutral. Essentially every scam
message in the corpus is negative or neutral, so the output barely varies —
a 278M-parameter model added to learn a near-constant.

Three further objections, specific to this system:

1. **It would breach the scoring-path rule.** Everything that produces a number
   here decomposes into named factors with written justifications. A
   transformer sentiment score cannot be explained to a magistrate. Feeding it
   into correlation or priority would undo the property that makes the reports
   defensible.
2. **The explainable version already exists.** `timeline_stage_keywords`
   classifies `social_engineering` on `("urgent", "verify", "suspended",
   "blocked", "immediately", "warning", "last chance", "expire")` — manipulation
   detection that can be justified line by line.
3. **There is no data to fine-tune on.** That needs on the order of 2,000–5,000
   labelled examples; the corpus is 25 evidence items and 152 entities, OCR'd
   from mixed Nepali/Devanagari with recognition errors, where sentiment models
   are trained on clean text.

**What would be worth building instead**, if an NLP component is wanted:
*social-engineering tactic classification* — multi-label over urgency,
authority, fear, scarcity and reward, because one message carries several at
once. That is intent classification, not sentiment, and it answers a question
an investigator can act on: which manipulation technique was used. The honest
path would be `xlm-roberta-base` (already in the registry, already handles
Devanagari), labels bootstrapped by weak supervision from the existing stage
keywords and then hand-corrected, the same 70/15/15 seed-42 split, and — the
critical constraint — emitted as an advisory field and a report section, never
as an input to a correlation weight, suspect score or priority.

**What was built instead.** The material supplied for this was not sentiment
data; it was the Nepali cyber-law corpus. That turned out to be worth far more,
and became §6.6.

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
nothing (§4.6). The test 15% is touched once.

**Why XGBoost when LightGBM scored higher in cross-validation?**
It scored higher by 0.0003 F1 — a third of one standard deviation, i.e. tied.
XGBoost wins where it counts: the held-out test set touched once (F1 0.9800 vs
0.9784), and false-negative rate (1.62% vs 1.80%). Add the dependency-free SHAP
path and it is the defensible choice. It is not a dominant one, and §4.5 says so.

**What if the examiner rejects that margin?**
Then LightGBM is the answer, and swapping is a one-line change
(`PhishingPredictor(model_type="lightgbm")`) — both checkpoints are trained and
tuned. The architecture does not depend on which won.

**Why is production α = 0.5 when Optuna said 0.016?**
Optuna optimises the tuning objective, which rewards fitting the tuning sample.
The untuned baseline showed XGBoost with a 0.198 train/validation gap. The
production checkpoint deliberately over-regularises (α 0.5, λ 2.0, depth 7 vs
Optuna's 0.016 / 0.45 / depth 11), trading tuning-set score for generalisation.
§4.4.

**Why isotonic and not Platt, when Platt is the class default?**
Because measurement overruled the default. On this model Platt was *worse than
no calibration* (Brier 0.01598 vs 0.01517) with an MCE of 0.209. Platt assumes a
sigmoidal distortion; this one is not sigmoidal. The pipeline detected the
improvement and switched automatically. §4.6.

**Why exclude accuracy from model selection?**
On a 52/48 corpus accuracy barely discriminates, and on any imbalanced slice it
rewards predicting the majority. The rule is F1 → ROC-AUC → Recall → Precision.

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
