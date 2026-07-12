"""Script to train and persist baseline models on a sampled subset of processed data."""
import sys
sys.path.insert(0, ".")

import pandas as pd
import numpy as np
from pathlib import Path
from src.config.settings import get_settings
from src.feature_engineering.pipeline import FeaturePipeline
from src.training.baseline_trainer import BaselineTrainer
from src.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    print("=" * 60)
    print("TRAINING BASELINE MODELS")
    print("=" * 60)

    settings = get_settings()
    processed_dir = Path(settings.paths.processed_data_dir)
    
    train_path = processed_dir / "train.csv"
    val_path = processed_dir / "validation.csv"
    
    if not train_path.exists() or not val_path.exists():
        print(f"Error: Processed splits not found at {processed_dir}. Run validate_dataset.py first.")
        sys.exit(1)
        
    print("Loading datasets...")
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    
    # Sample subset to train quickly and avoid CPU timeout
    train_sample_size = 5000
    val_sample_size = 1000
    
    print(f"Sampling {train_sample_size} training samples and {val_sample_size} validation samples...")
    # Use simple, version-safe stratified sampling to keep classes balanced
    train_phish = train_df[train_df['label'] == 1].sample(min(len(train_df[train_df['label'] == 1]), train_sample_size // 2), random_state=42)
    train_legit = train_df[train_df['label'] == 0].sample(min(len(train_df[train_df['label'] == 0]), train_sample_size // 2), random_state=42)
    train_sample = pd.concat([train_phish, train_legit]).sample(frac=1.0, random_state=42)

    val_phish = val_df[val_df['label'] == 1].sample(min(len(val_df[val_df['label'] == 1]), val_sample_size // 2), random_state=42)
    val_legit = val_df[val_df['label'] == 0].sample(min(len(val_df[val_df['label'] == 0]), val_sample_size // 2), random_state=42)
    val_sample = pd.concat([val_phish, val_legit]).sample(frac=1.0, random_state=42)
    
    print("Extracting features (this may take a few seconds)...")
    pipeline = FeaturePipeline()
    
    # Extract training features
    train_features_df = pipeline.get_feature_dataframe(train_sample["url"].tolist())
    val_features_df = pipeline.get_feature_dataframe(val_sample["url"].tolist())
    
    # Get sorted feature names to match predictor behavior
    feature_cols = pipeline.get_feature_names()
    
    # Prepare matrices (only keep feature columns, exclude 'url' column) and fill NaNs with 0.0
    X_train = train_features_df[feature_cols].fillna(0.0).to_numpy().astype(np.float32)
    y_train = train_sample["label"].to_numpy()
    
    X_val = val_features_df[feature_cols].fillna(0.0).to_numpy().astype(np.float32)
    y_val = val_sample["label"].to_numpy()
    
    print(f"Feature matrix shape: X_train={X_train.shape}, X_val={X_val.shape}")
    
    # Initialize trainer
    trainer = BaselineTrainer()
    
    # Train all 8 models
    print("\nTraining all 8 baseline models...")
    all_metrics = trainer.train_all(X_train, y_train, X_val, y_val, save_checkpoints=True, feature_names=feature_cols)
    
    # Check best model
    best_name, best_model = trainer.get_best_model(metric="val_f1")
    print(f"\nBest model by F1 score: {best_name}")
    print(f"Best model metadata metrics: {best_model.metadata.training_metrics}")
    
    # Confirm default predictor works with the trained checkpoints
    print("\nVerifying predictor loading from checkpoint...")
    from src.prediction.predictor import PhishingPredictor
    
    # Initialize with the best model
    predictor = PhishingPredictor(model_type=best_name, use_intelligence=False)
    
    # Run test prediction
    test_url = "https://paypal-verify-login.xyz/login"
    result = predictor.predict(test_url)
    print(f"Predictor result for '{test_url}':")
    print(f"  Prediction: {result.prediction}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Risk level: {result.risk_level}")
    print(f"  Reasons: {result.reasons}")

if __name__ == "__main__":
    main()
