"""
Lightweight character-level URL transformer (Phase 3-A).

An independent transformer model that learns phishing patterns directly from
raw URL text.  It complements -- and never replaces -- the XGBoost baseline:
both models run side by side and are merged by the
:class:`~src.ensemble.ensemble_engine.EnsembleEngine`.

Architecture (PyTorch, torch is an OPTIONAL dependency):

    char embedding -> positional embedding -> N x TransformerEncoderLayer
    -> masked mean pooling -> linear head -> phishing probability

Design notes
------------
* Torch is imported lazily.  When torch is not installed the model reports
  ``is_available() == False`` and every training/inference call raises a
  descriptive ``ModelError``; the predictor and ensemble degrade gracefully.
* Character encoding reuses :class:`~src.preprocessing.text_preprocessor.
  URLTextPreprocessor` (mode='char') so the vocabulary stays consistent
  across the engine.
* Checkpoints are directories containing ``weights.pt`` + ``config.json``
  and are saved under ``checkpoints/url_transformer/`` by default.

Training is performed offline with ``train_url_transformer.py`` (root
script); this module only defines the model and its lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.models.base_model import BaseModel
from src.preprocessing.text_preprocessor import URLTextPreprocessor
from src.utils.exceptions import ModelError
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _try_import_torch():
    """Import torch lazily; return the module or ``None`` when missing."""
    try:
        import torch  # noqa: PLC0415
        return torch
    except ImportError:
        return None


def torch_available() -> bool:
    """Return True when PyTorch is importable."""
    return _try_import_torch() is not None


class URLTransformerModel(BaseModel):
    """Character-level transformer for URL phishing detection.

    Args:
        max_length: Maximum URL length in characters.
        d_model: Embedding / hidden dimension.
        n_heads: Attention heads per encoder layer.
        n_layers: Number of transformer encoder layers.
        dim_feedforward: Feed-forward dimension inside encoder layers.
        dropout: Dropout probability.

    The default configuration (~1M parameters) is intentionally small so it
    can be trained on CPU/consumer GPUs and served with low latency.
    """

    def __init__(
        self,
        max_length: int = 200,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
    ) -> None:
        super().__init__(name="url_transformer", model_type="transformer")
        self.config: dict[str, Any] = {
            "max_length": int(max_length),
            "d_model": int(d_model),
            "n_heads": int(n_heads),
            "n_layers": int(n_layers),
            "dim_feedforward": int(dim_feedforward),
            "dropout": float(dropout),
        }
        self._preprocessor = URLTextPreprocessor(max_length=max_length, mode="char")
        self._net = None  # torch.nn.Module, built lazily
        self._device = "cpu"
        self._metadata.hyperparameters = dict(self.config)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """True when PyTorch is installed and the model can run."""
        return torch_available()

    def _require_torch(self):
        torch = _try_import_torch()
        if torch is None:
            raise ModelError(
                self.name,
                "dependency",
                "PyTorch is not installed. Install with: pip install torch",
            )
        return torch

    # ------------------------------------------------------------------
    # Network definition
    # ------------------------------------------------------------------

    def _build_network(self):
        """Construct the torch network according to ``self.config``."""
        torch = self._require_torch()
        import torch.nn as nn

        cfg = self.config
        vocab_size = self._preprocessor.vocab_size

        class _URLTransformerNet(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.char_embedding = nn.Embedding(
                    vocab_size, cfg["d_model"], padding_idx=0
                )
                self.pos_embedding = nn.Embedding(cfg["max_length"], cfg["d_model"])
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=cfg["d_model"],
                    nhead=cfg["n_heads"],
                    dim_feedforward=cfg["dim_feedforward"],
                    dropout=cfg["dropout"],
                    batch_first=True,
                )
                self.encoder = nn.TransformerEncoder(
                    encoder_layer, num_layers=cfg["n_layers"]
                )
                self.dropout = nn.Dropout(cfg["dropout"])
                self.head = nn.Linear(cfg["d_model"], 1)

            def forward(self, char_ids):  # (batch, seq)
                mask = char_ids == 0  # padding mask
                positions = (
                    torch.arange(char_ids.size(1), device=char_ids.device)
                    .unsqueeze(0)
                    .expand_as(char_ids)
                )
                x = self.char_embedding(char_ids) + self.pos_embedding(positions)
                x = self.encoder(x, src_key_padding_mask=mask)
                # Masked mean pooling
                keep = (~mask).unsqueeze(-1).float()
                pooled = (x * keep).sum(dim=1) / keep.sum(dim=1).clamp(min=1.0)
                return self.head(self.dropout(pooled)).squeeze(-1)  # logits

        self._net = _URLTransformerNet()
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._net.to(self._device)
        logger.info(
            "URLTransformer network built (%d parameters, device=%s)",
            sum(p.numel() for p in self._net.parameters()),
            self._device,
        )

    # ------------------------------------------------------------------
    # Encoding helpers
    # ------------------------------------------------------------------

    def _encode_batch(self, urls: np.ndarray) -> "Any":
        """Encode an array of URL strings into a LongTensor of char ids."""
        torch = self._require_torch()
        encoded = [self._preprocessor.encode_chars(str(u)) for u in urls]
        return torch.tensor(encoded, dtype=torch.long, device=self._device)

    # ------------------------------------------------------------------
    # BaseModel interface
    # ------------------------------------------------------------------

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
        epochs: int = 3,
        batch_size: int = 64,
        learning_rate: float = 1e-3,
    ) -> dict[str, float]:
        """Train the transformer on raw URL strings.

        Args:
            X_train: Array of URL strings.
            y_train: Binary labels (1 = phishing).
            X_val: Optional validation URLs.
            y_val: Optional validation labels.
            feature_names: Unused (transformer consumes raw text).
            epochs: Training epochs.
            batch_size: Mini-batch size.
            learning_rate: AdamW learning rate.

        Returns:
            Dictionary of final training (and validation) metrics.
        """
        torch = self._require_torch()
        if self._net is None:
            self._build_network()

        self._net.train()
        optimizer = torch.optim.AdamW(self._net.parameters(), lr=learning_rate)
        loss_fn = torch.nn.BCEWithLogitsLoss()

        y_tensor = torch.tensor(
            np.asarray(y_train, dtype=np.float32), device=self._device
        )
        n = len(X_train)
        metrics: dict[str, float] = {}

        for epoch in range(epochs):
            permutation = np.random.permutation(n)
            epoch_loss, correct = 0.0, 0
            for start in range(0, n, batch_size):
                idx = permutation[start : start + batch_size]
                batch_x = self._encode_batch(np.asarray(X_train)[idx])
                batch_y = y_tensor[idx]

                optimizer.zero_grad()
                logits = self._net(batch_x)
                loss = loss_fn(logits, batch_y)
                loss.backward()
                optimizer.step()

                epoch_loss += float(loss.item()) * len(idx)
                correct += int(
                    ((torch.sigmoid(logits) >= 0.5).float() == batch_y).sum().item()
                )

            metrics["train_loss"] = epoch_loss / max(n, 1)
            metrics["train_accuracy"] = correct / max(n, 1)
            logger.info(
                "URLTransformer epoch %d/%d -- loss=%.4f acc=%.4f",
                epoch + 1, epochs, metrics["train_loss"], metrics["train_accuracy"],
            )

        if X_val is not None and y_val is not None and len(X_val) > 0:
            proba = self.predict_proba(np.asarray(X_val))
            preds = (proba >= 0.5).astype(int)
            metrics["val_accuracy"] = float(
                (preds == np.asarray(y_val, dtype=int)).mean()
            )

        self._is_trained = True
        self._metadata.training_samples = n
        self._metadata.training_metrics = dict(metrics)
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict binary labels (1 = phishing) for URL strings."""
        return (self.predict_proba(X) >= 0.5).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict phishing probabilities for URL strings.

        Args:
            X: Array of raw URL strings.

        Returns:
            1-D array of phishing probabilities.
        """
        torch = self._require_torch()
        if self._net is None or not self._is_trained:
            raise ModelError(self.name, "prediction", "Model is not trained.")

        self._net.eval()
        probabilities: list[float] = []
        with torch.no_grad():
            for start in range(0, len(X), 256):
                batch = self._encode_batch(np.asarray(X)[start : start + 256])
                logits = self._net(batch)
                probabilities.extend(torch.sigmoid(logits).cpu().numpy().tolist())
        return np.asarray(probabilities, dtype=float)

    def save(self, path: Path) -> None:
        """Save the model checkpoint to a directory.

        Args:
            path: Checkpoint directory (created if missing).
        """
        torch = self._require_torch()
        if self._net is None:
            raise ModelError(self.name, "save", "Nothing to save -- model not built.")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        torch.save(self._net.state_dict(), path / "weights.pt")
        payload = {
            "config": self.config,
            "is_trained": self._is_trained,
            "metadata": {
                "model_version": self._metadata.model_version,
                "feature_version": self._metadata.feature_version,
                "dataset_version": self._metadata.dataset_version,
                "calibration_version": self._metadata.calibration_version,
                "training_samples": self._metadata.training_samples,
                "training_metrics": self._metadata.training_metrics,
                "training_date": self._metadata.training_date,
            },
        }
        with open(path / "config.json", "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        logger.info("URLTransformer checkpoint saved to %s", path)

    def load(self, path: Path) -> None:
        """Load a model checkpoint from a directory.

        Args:
            path: Checkpoint directory containing weights.pt + config.json.
        """
        torch = self._require_torch()
        path = Path(path)
        config_file = path / "config.json"
        weights_file = path / "weights.pt"
        if not config_file.exists() or not weights_file.exists():
            raise ModelError(
                self.name, "load", f"Checkpoint incomplete or missing at {path}"
            )

        with open(config_file, encoding="utf-8") as fh:
            payload = json.load(fh)

        self.config = dict(payload.get("config", self.config))
        self._preprocessor = URLTextPreprocessor(
            max_length=self.config["max_length"], mode="char"
        )
        self._build_network()
        state = torch.load(weights_file, map_location=self._device)
        self._net.load_state_dict(state)
        self._net.eval()
        self._is_trained = bool(payload.get("is_trained", True))

        meta = payload.get("metadata", {})
        self._metadata.model_version = meta.get("model_version", "1.0.0")
        self._metadata.feature_version = meta.get("feature_version", "char-v1")
        self._metadata.dataset_version = meta.get("dataset_version", "unknown")
        self._metadata.calibration_version = meta.get("calibration_version", "none")
        self._metadata.training_samples = int(meta.get("training_samples", 0))
        self._metadata.training_metrics = dict(meta.get("training_metrics", {}))
        logger.info("URLTransformer checkpoint loaded from %s", path)


def create_url_transformer(**kwargs: Any) -> URLTransformerModel:
    """Factory for the URL transformer model.

    Args:
        **kwargs: Passed through to :class:`URLTransformerModel`.

    Returns:
        A new ``URLTransformerModel`` instance (untrained).
    """
    return URLTransformerModel(**kwargs)


def load_url_transformer_if_available(
    checkpoint_dir: Path,
) -> Optional[URLTransformerModel]:
    """Load the URL transformer when torch + checkpoint are both present.

    This is the graceful-degradation entry point used by the predictor:
    any failure returns ``None`` instead of raising.

    Args:
        checkpoint_dir: The engine checkpoint directory; the transformer is
            expected at ``<checkpoint_dir>/url_transformer``.

    Returns:
        A trained ``URLTransformerModel`` or ``None``.
    """
    if not torch_available():
        logger.debug("PyTorch not installed -- URL transformer disabled.")
        return None
    path = Path(checkpoint_dir) / "url_transformer"
    if not (path / "weights.pt").exists():
        logger.debug("No URL transformer checkpoint at %s -- disabled.", path)
        return None
    try:
        model = URLTransformerModel()
        model.load(path)
        return model
    except Exception as exc:  # noqa: BLE001 -- degradation must never raise
        logger.warning("Failed to load URL transformer: %s", exc)
        return None
