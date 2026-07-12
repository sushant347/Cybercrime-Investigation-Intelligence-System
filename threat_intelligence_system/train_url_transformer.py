from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.evaluation.evaluator import ModelEvaluator
from src.models.url_transformer import URLTransformerModel, torch_available
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _load_split(path: Path, sample: int | None) -> tuple[np.ndarray, np.ndarray]:
    """Load a CSV split into (urls, labels)."""
    df = pd.read_csv(path)
    if sample and len(df) > sample:
        df = df.sample(n=sample, random_state=42)
    return df["url"].astype(str).to_numpy(), df["label"].astype(int).to_numpy()


def main() -> int:
    """Entry point for URL transformer training."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Optional cap on training rows (useful for smoke tests).",
    )
    args = parser.parse_args()

    if not torch_available():
        print("ERROR: PyTorch is not installed. Install with: pip install torch")
        return 1

    settings = get_settings()
    processed = settings.paths.processed_data_dir
    train_csv = processed / "train.csv"
    val_csv = processed / "validation.csv"
    if not train_csv.exists():
        print(f"ERROR: {train_csv} not found. Run the dataset pipeline first.")
        return 1

    x_train, y_train = _load_split(train_csv, args.sample)
    x_val, y_val = (
        _load_split(val_csv, args.sample) if val_csv.exists() else (None, None)
    )

    print(f"Training URL transformer on {len(x_train)} URLs "
          f"(epochs={args.epochs}, batch_size={args.batch_size})")

    model = URLTransformerModel()
    metrics = model.train(
        x_train, y_train, x_val, y_val,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    model.metadata.model_version = "3.0.0"
    model.metadata.feature_version = "char-v1"
    model.metadata.training_date = datetime.now(timezone.utc).isoformat()

    checkpoint = Path(settings.paths.checkpoint_dir) / "url_transformer"
    model.save(checkpoint)
    print(f"Checkpoint saved to {checkpoint}")
    print(f"Training metrics: {metrics}")

    if x_val is not None:
        proba = model.predict_proba(x_val)
        evaluator = ModelEvaluator()
        result = evaluator.evaluate(
            "url_transformer", y_val, (proba >= 0.5).astype(int), proba
        )
        evaluator.save_report("url_transformer_report.json")
        print(f"Validation: acc={result.accuracy:.4f} f1={result.f1:.4f} "
              f"auc={result.auc_roc:.4f} fpr={result.false_positive_rate:.4f} "
              f"fnr={result.false_negative_rate:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
