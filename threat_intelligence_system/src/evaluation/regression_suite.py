"""
Regression test suite for measuring model accuracy and preventing performance degradation.
"""

from pathlib import Path
from typing import Any
import json
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

BENCHMARK_PATH = Path("data/processed/benchmark_dataset.csv")
METRICS_HISTORY_PATH = Path("results/regression_metrics.json")


def get_or_create_benchmark() -> pd.DataFrame:
    """Load the benchmark dataset. If not present or too small, generate it by sampling from test.csv."""
    settings = get_settings()
    benchmark_path = settings.paths.project_root / BENCHMARK_PATH
    
    if benchmark_path.exists():
        try:
            df = pd.read_csv(benchmark_path)
            if len(df) >= 1000:
                logger.info("Loading existing benchmark dataset from %s", benchmark_path)
                return df
        except Exception:
            pass
        
    logger.info("Benchmark dataset not found or too small at %s. Creating one...", benchmark_path)
    test_path = settings.paths.processed_data_dir / "test.csv"
    if not test_path.exists():
        raise FileNotFoundError(f"Cannot generate benchmark dataset: test.csv not found at {test_path}")
        
    test_df = pd.read_csv(test_path)
    
    # Sample exactly 500 legitimate and 500 phishing URLs
    legit_df = test_df[test_df["label"] == 0]
    phish_df = test_df[test_df["label"] == 1]
    
    if len(legit_df) < 500 or len(phish_df) < 500:
        raise ValueError(
            f"Insufficient samples in test.csv to create benchmark. "
            f"Need at least 500 of each class, got {len(legit_df)} legit and {len(phish_df)} phishing."
        )
        
    legit_sample = legit_df.sample(n=500, random_state=42)
    phish_sample = phish_df.sample(n=500, random_state=42)
    
    benchmark_df = pd.concat([legit_sample, phish_sample]).sample(frac=1.0, random_state=42)
    benchmark_path.parent.mkdir(parents=True, exist_ok=True)
    benchmark_df.to_csv(benchmark_path, index=False)
    logger.info("Created and saved benchmark dataset (1000 samples) to %s", benchmark_path)
    return benchmark_df


def run_regression_suite(model: Any, feature_pipeline: Any, model_name: str) -> dict[str, Any]:
    """
    Evaluate the given model on the benchmark dataset.
    Calculates key performance metrics and saves them.
    
    Args:
        model: Trained BaseModel instance.
        feature_pipeline: FeaturePipeline instance.
        model_name: Name of the model.
        
    Returns:
        Dictionary of computed metrics.
    """
    logger.info("Running regression test suite on model: %s", model_name)
    df = get_or_create_benchmark()
    
    urls = df["url"].tolist()
    y_true = df["label"].to_numpy()
    
    # Extract features for all URLs in the benchmark
    features_df = feature_pipeline.get_feature_dataframe(urls)
    feature_cols = feature_pipeline.get_feature_names()
    
    # Ensure no NaN values
    features_clean = features_df[feature_cols].fillna(0.0)
    X = features_clean.to_numpy().astype(np.float32)
    
    # Run predictions
    preds = model.predict(X)
    try:
        proba = model.predict_proba(X)
    except Exception:
        # Fallback to decision function or raw predictions if predict_proba is not available
        proba = preds.astype(float)
        
    # Calculate performance metrics
    accuracy = float(accuracy_score(y_true, preds))
    precision = float(precision_score(y_true, preds, zero_division=0))
    recall = float(recall_score(y_true, preds, zero_division=0))
    f1 = float(f1_score(y_true, preds, zero_division=0))
    try:
        auc = float(roc_auc_score(y_true, proba))
    except ValueError:
        auc = 0.5
        
    # Confusion matrix for FPR / FNR
    tn, fp, fn, tp = confusion_matrix(y_true, preds, labels=[0, 1]).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0
    
    metrics = {
        "model_name": model_name,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "roc_auc": auc,
        "false_positive_rate": fpr,
        "false_negative_rate": fnr,
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    # Save/Append metrics to history
    settings = get_settings()
    history_path = settings.paths.project_root / METRICS_HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)
    
    history = {}
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    history[model_name] = metrics
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    logger.info("Saved regression metrics to %s", history_path)
    
    return metrics
