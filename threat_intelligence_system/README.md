# Threat Intelligence System

The **Threat Intelligence System** is a highly modular, high-performance cybersecurity intelligence component designed for the Cybercrime Investigation Intelligence System (CIIS). 

It detects phishing, malicious, and typosquatting URLs by combining **advanced machine learning models (XGBoost, LightGBM, Random Forest, etc.)**, **lexical and structural feature engineering (71 indicators)**, and **real-time threat intelligence (VirusTotal, WHOIS, SSL, DNS, GeoIP)**.

It is built to run entirely as a reusable Python library without external dependencies like FastAPI, Databases, or UIs, making it drop-in ready for other CIIS modules (OCR, timeline, reporting, correlation).

---

## Key Features

1. **Robust URL Parser & Validator**: Canonical URL normalization, Punycode/IDN homograph detection, IP-based hostname classification, and deep directory depth parsing.
2. **Comprehensive Feature Engineering**: Generates **71 numeric features** across Lengths, Character distributions, Shannon entropy, Structural flags, Lexical counts, Brand similarity (Levenshtein typosquatting checks), Security flags, and TLD reputation.
3. **Multi-Model ML Engine**: Exposes a unified `BaseModel` wrapper supporting 8 baseline models (XGBoost, LightGBM, Random Forest, Logistic Regression, etc.) and deep learning transformers (DistilBERT, BERT, RoBERTa) via PyTorch/HuggingFace.
4. **Weighted Threat Scoring**: Merges ML class probabilities, domain age, SSL validity, DNS SPF/DMARC records, and VirusTotal detections into a composite `0-100` risk score mapping to human-readable risk levels (`Safe`, `Low`, `Medium`, `High`, `Critical`).
5. **AI Explainability**: Generates clear, structured plain-English sentences justifying the classification results (e.g., brand impersonation, missing SSL, high-risk TLD, etc.).

---

## Project Scaffolding

```text
threat_intelligence_system/
├── data/
│   └── processed/          # Saved train/validation/test splits
├── checkpoints/            # Serialized model weights (.pkl, PyTorch dirs)
├── results/                # Performance comparison reports
├── src/
│   ├── config/             # Settings schema & default values
│   ├── parser/             # URLValidator & URLParser
│   ├── feature_engineering/# 8 extractors + unified pipeline
│   ├── datasets/           # Loader, cleaner, validator, merger, stats
│   ├── models/             # Baseline wrapper, transformer wrapper
│   ├── preprocessing/      # Character & subword text preprocessors
│   ├── training/           # BaselineTrainer & TransformerTrainer
│   ├── evaluation/         # ModelEvaluator (precision, recall, MCC, logloss)
│   ├── intelligence/       # VT, WHOIS, DNS, SSL, GeoIP connectors
│   ├── scoring/            # Weighted threat scorer
│   ├── explainability/     # Plain-text reason generator
│   └── prediction/         # Unified PhishingPredictor facade & PredictionResult
├── tests/                  # Complete Pytest suite (51 test cases)
├── requirements.txt        # Reproducible environment specification
└── README.md               # User manual
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.12+
- (Optional) CUDA-enabled GPU for fine-tuning transformers.

### 2. Install Dependencies
Install all package requirements in your virtual environment:
```bash
pip install -r requirements.txt
```

To install deep learning libraries for optional transformer support:
```bash
pip install torch transformers accelerate
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and configure your API keys:
```bash
cp .env.example .env
```
Key configurations include:
- `VIRUSTOTAL_API_KEY`: Required for VirusTotal domain reports. If omitted, the engine degrades gracefully using other connectors.
- `RAW_DATA_DIR`: Absolute or relative path to the directory containing raw source CSVs.

---

## Usage Guide

### 1. Unified Prediction (Recommended Integration API)
To integrate phishing URL detection into OCR, email parsing, or link scanners:

```python
from src.prediction.predictor import PhishingPredictor

# Initialize predictor (automatically loads best trained model, e.g., xgboost)
predictor = PhishingPredictor(model_type="xgboost", use_intelligence=True)

# Run end-to-end analysis
result = predictor.predict("https://paypal-verify-login.xyz/login")

# Print prediction metadata summary
print(result.summary())
# Output: [Critical] PHISHING (confidence=0.94, score=89/100) -> https://paypal-verify-login.xyz/login

# Convert result to JSON
print(result.to_json(indent=2))

# Access specific parameters
print("Is Phishing:", result.is_phishing)
print("Risk Level:", result.risk_level)
print("Explainability Reasons:")
for reason in result.reasons:
    print(f"  - {reason}")
```

### 2. Running the Dataset Pipeline
To ingest, clean, validate, and split the raw datasets into stratified splits (70/15/15 ratio):
```python
from src.datasets.merger import DatasetMerger

merger = DatasetMerger()
train_df, val_df, test_df = merger.run_pipeline()
print(f"Dataset splits generated in data/processed/")
```
Or execute the script directly:
```bash
python validate_dataset.py
```

### 3. Training & Persisting Models
Train all 8 baseline classifiers on the processed training set, serialize checkpoints, and generate comparison reports:
```bash
python train_baselines.py
```
This saves trained `.pkl` models under `checkpoints/` (e.g., `xgboost.pkl`, `random_forest.pkl`) and writes a JSON performance comparison table to `results/baseline_comparison_report.json`.

---

## Testing

Run the full conftest-powered test suite containing unit, integration, mock-network, and graceful-degradation tests:
```bash
pytest -v
```

All 51 test cases execute in less than 5 seconds.

---

## Phase 3: Modern AI Upgrade

### URL Transformer (independent module)
A lightweight character-level transformer (`src/models/url_transformer.py`) learns phishing patterns directly from URL text. PyTorch is **optional** -- without torch or a checkpoint the engine degrades gracefully and runs exactly as before.
```bash
pip install torch
python train_url_transformer.py --epochs 3          # saves checkpoints/url_transformer/
```

### Ensemble Prediction
`src/ensemble/ensemble_engine.py` merges XGBoost probability, transformer probability, rule score, threat-intelligence score, and trust score with configurable weights (`config/settings.yaml -> ensemble_weights`). Unavailable signals have their weight redistributed.
```python
predictor = PhishingPredictor(model_type="xgboost", use_ensemble=True)
result = predictor.predict(url)
print(result.decision_breakdown["ensemble"])
```
`use_ensemble` defaults to `True` (the ensemble is the production decision path). Pass `use_ensemble=False` to fall back to the Phase 2 decision engine.

### SHAP Explainability
Exact TreeSHAP contributions via XGBoost's native `pred_contribs` (no extra dependency). Every prediction includes `top_shap_features`; `SHAPExplainer.global_importance()` provides global rankings.

### Advanced Calibration
`src/scoring/calibrator.py` adds `brier_score`, `expected_calibration_error`, `reliability_diagram`, and `CalibrationEvaluator`, which fits Platt / Isotonic / Temperature / Identity and selects the best method by ECE (Brier tie-break).

### Active Learning Feedback
```python
from src.feedback.feedback_store import FeedbackStore
FeedbackStore().record(url, predicted_label="Phishing", verdict="incorrect",
                       correct_label="Legitimate", investigator="analyst-7")
```
Feedback is stored in `data/feedback/feedback.jsonl`. Nothing retrains automatically.

### Retraining Pipeline
```bash
python retrain_pipeline.py                # merges feedback corrections by default
python retrain_pipeline.py --no-feedback --extra new_dataset.csv
```
Each run stamps model/dataset/feature/calibration versions, selects the best calibration, benchmarks on the test split (accuracy, precision, recall, F1, ROC-AUC, FPR, FNR, Brier, ECE, confusion matrix), and writes `results/retraining_report_<run>.json`.

### Extension Points (future phases)
New intelligence providers (Google Safe Browsing, OpenPhish, URLHaus, PhishTank, Certificate Transparency, Passive DNS, ASN reputation) plug in by subclassing `src/intelligence/base_connector.BaseConnector` and passing instances to `IntelligenceAggregator(connectors=[...])` -- no existing module changes required. New ensemble signals are added via `EnsembleInputs` + a weight entry in YAML.

---

## Phase 4: Training Pipeline Upgrade

The ML training pipeline was strengthened while the inference path (predictor,
feature schema, checkpoints, JSON outputs) stayed byte-for-byte compatible.

- **Automatic dataset discovery** (`src/datasets/discovery.py`): drops any mix of
  CSV / TSV / TXT / JSON / JSONL / Excel into the configurable dataset folder
  (`DATASET_PATH`, default `../sample`); URL and label columns, encodings and
  delimiters are detected automatically and heterogeneous labels (0/1,
  Safe/Phishing, Benign/Malicious, …) are normalised.
- **Full-dataset training by default** (`MAX_TRAINING_ROWS=0`) with chunk-streamed,
  memory-bounded feature extraction.
- **Stratified 5-fold cross-validation** reporting Accuracy, Precision, Recall,
  F1, ROC-AUC, PR-AUC and MCC as mean ± std.
- **Optuna hyperparameter optimization** (`src/training/hyperparameter_tuner.py`)
  with early stopping and resumable studies for XGBoost, LightGBM, Random Forest
  and Extra Trees; best parameters persist and are reused automatically.
- **Calibration analysis** (`src/scoring/calibration_analysis.py`): Brier, ECE,
  MCE and reliability diagrams with automatic recalibration when beneficial.
- **Error analysis + visual reports**: false-positive / false-negative /
  high-confidence-mistake CSVs, plus ROC, PR, calibration, confusion-matrix,
  feature-importance and SHAP figures as PNG **and** PDF.

```bash
python train_from_datasets.py                       # full dataset, all stages
python train_from_datasets.py --tune --trials 25    # + Optuna tuning
```

---

## Phase 5: Brand Intelligence Engine

Real-world brand-impersonation detection built around a maintainable official-
domain database (`config/brand_intelligence.yaml`, 45 protected brands incl.
Microsoft, Google, Apple, Meta, PayPal, GitHub, OpenAI, plus eSewa, Khalti,
IME Pay, Nagarik App, Government of Nepal and major Nepali banks). Fully
additive — the ML model, feature schema (71 features) and checkpoints are
untouched. See `docs/BRAND_INTELLIGENCE.md` for details.

- **Registrable-domain comparison** via the Public Suffix List
  (`login.microsoft.com → microsoft.com`, never raw hostname matching).
- **Brand token detection** across hostname, subdomain, path and query.
- **Official-domain verification** — a referenced brand is trusted only when the
  registrable domain is on that brand's official list.
- **Typosquatting** (Damerau-Levenshtein, leetspeak, keyboard slips, repeated /
  missing / extra characters) and **homoglyph / Unicode spoofing** detection.
- **Prefix / suffix abuse** (`secure-google`, `verify-paypal`) and
  **cloud-hosting impersonation** (cloud providers are never malicious alone;
  suspicion rises only with a brand mismatch plus credential signals).
- **Brand Conflict Detection** — a trusted domain (official brand or cloud
  provider) that references a *different* protected brand is flagged, e.g.
  `github.io/microsoft-login` or `firebaseapp.com/google-login`. Same-brand
  references (`web.whatsapp.com`, `github.com`) are never flagged.
- **Explainable & additive** — findings surface as new `bi_*` Rule Engine rules
  (including `bi_brand_conflict`) that raise the rule score but never force a
  phishing verdict; the final decision stays with ML, Threat Intelligence and
  Risk Fusion.

```python
from src.intelligence.brand_intelligence import BrandIntelligenceEngine
result = BrandIntelligenceEngine().analyze("https://github.io/microsoft-login")
print(result.risk_level, [f.finding_type for f in result.findings])
```
