"""
Transformer-based models for phishing URL detection.

Supports DistilBERT, BERT, RoBERTa, and is extensible to mBERT and XLM-RoBERTa.
URLs are treated as text sequences and classified through fine-tuned transformers.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.models.base_model import BaseModel, ModelMetadata
from src.utils.exceptions import ModelError
from src.utils.logger import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


# Supported transformer identifiers
TRANSFORMER_REGISTRY: dict[str, str] = {
    "distilbert": "distilbert-base-uncased",
    "bert": "bert-base-uncased",
    "roberta": "roberta-base",
    "mbert": "bert-base-multilingual-cased",
    "xlm-roberta": "xlm-roberta-base",
}


@dataclass
class TransformerConfig:
    """
    Configuration for transformer model training and inference.

    Attributes:
        model_name: Short name key (e.g., 'distilbert', 'bert').
        pretrained_path: HuggingFace model identifier or local path.
        max_length: Maximum token sequence length.
        num_labels: Number of classification labels.
        batch_size: Training and inference batch size.
        learning_rate: Optimizer learning rate.
        num_epochs: Number of training epochs.
        warmup_ratio: Ratio of warmup steps to total steps.
        weight_decay: L2 regularization weight decay.
        mixed_precision: Whether to use FP16 mixed precision training.
        early_stopping_patience: Epochs without improvement before stopping.
        gradient_accumulation_steps: Steps before gradient update.
    """

    model_name: str = "distilbert"
    pretrained_path: str = "distilbert-base-uncased"
    max_length: int = 256
    num_labels: int = 2
    batch_size: int = 32
    learning_rate: float = 2e-5
    num_epochs: int = 5
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    mixed_precision: bool = True
    early_stopping_patience: int = 3
    gradient_accumulation_steps: int = 1


class TransformerURLClassifier(BaseModel):
    """
    Transformer-based URL classifier for phishing detection.

    Wraps HuggingFace transformers (DistilBERT, BERT, RoBERTa, etc.)
    for binary classification of URLs. Supports mixed precision training,
    early stopping, checkpoint saving, and training resumption.

    Attributes:
        config: TransformerConfig with all model and training parameters.
        tokenizer: HuggingFace tokenizer instance.
        model: HuggingFace model instance.
        device: PyTorch device (CPU or CUDA).
    """

    def __init__(
        self,
        model_name: str = "distilbert",
        config: TransformerConfig | None = None,
    ) -> None:
        """
        Initialize the transformer URL classifier.

        Args:
            model_name: Key from TRANSFORMER_REGISTRY ('distilbert', 'bert', 'roberta', etc.).
            config: Optional TransformerConfig. If None, built from settings and model_name.

        Raises:
            ModelError: If the model name is not recognized or dependencies are missing.
        """
        super().__init__(name=f"Transformer-{model_name}", model_type="transformer")

        if model_name not in TRANSFORMER_REGISTRY:
            available = ", ".join(sorted(TRANSFORMER_REGISTRY.keys()))
            raise ModelError(model_name, "init", f"Unknown transformer: {model_name}. Available: {available}")

        settings = get_settings()

        if config is None:
            config = TransformerConfig(
                model_name=model_name,
                pretrained_path=TRANSFORMER_REGISTRY[model_name],
                max_length=settings.transformer.max_length,
                batch_size=settings.transformer.batch_size,
                learning_rate=settings.transformer.learning_rate,
                num_epochs=settings.transformer.num_epochs,
                warmup_ratio=settings.transformer.warmup_ratio,
                weight_decay=settings.transformer.weight_decay,
                mixed_precision=settings.transformer.mixed_precision,
                early_stopping_patience=settings.transformer.early_stopping_patience,
                gradient_accumulation_steps=settings.transformer.gradient_accumulation_steps,
            )

        self.config = config
        self.tokenizer = None
        self.transformer_model = None
        self.device = None
        self._best_val_loss = float("inf")
        self._patience_counter = 0

        self._metadata.hyperparameters = {
            "model_name": config.model_name,
            "pretrained_path": config.pretrained_path,
            "max_length": config.max_length,
            "learning_rate": config.learning_rate,
            "batch_size": config.batch_size,
            "num_epochs": config.num_epochs,
        }

    def _initialize_model(self) -> None:
        """
        Lazily initialize the tokenizer, model, and device.

        This is called on first use to avoid importing torch/transformers at import time.

        Raises:
            ModelError: If torch or transformers are not installed.
        """
        if self.transformer_model is not None:
            return

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
        except ImportError as e:
            raise ModelError(self._name, "init", f"Missing dependency: {e}") from e

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Using device: %s", self.device)

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.pretrained_path)
            self.transformer_model = AutoModelForSequenceClassification.from_pretrained(
                self.config.pretrained_path,
                num_labels=self.config.num_labels,
            )
            self.transformer_model.to(self.device)
            logger.info("Loaded transformer: %s", self.config.pretrained_path)
        except Exception as e:
            raise ModelError(self._name, "init", f"Failed to load model: {e}") from e

    def _tokenize(self, urls: list[str]) -> dict:
        """
        Tokenize a batch of URLs.

        Args:
            urls: List of URL strings.

        Returns:
            Dictionary of tokenized inputs ready for the model.
        """
        return self.tokenizer(
            urls,
            padding="max_length",
            truncation=True,
            max_length=self.config.max_length,
            return_tensors="pt",
        )

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> dict[str, float]:
        """
        Train the transformer model.

        For transformers, X_train is expected to be an array of URL strings
        (or a 2D array with one column of strings). Labels are binary (0/1).

        Args:
            X_train: Array of URL strings.
            y_train: Binary labels.
            X_val: Optional validation URL strings.
            y_val: Optional validation labels.

        Returns:
            Dictionary of training metrics.
        """
        import torch
        from torch.utils.data import DataLoader, TensorDataset
        from torch.cuda.amp import autocast, GradScaler

        self._initialize_model()

        # Convert string arrays to lists
        train_urls = self._to_url_list(X_train)
        val_urls = self._to_url_list(X_val) if X_val is not None else None

        logger.info("Training %s on %d URLs", self._name, len(train_urls))

        # Tokenize
        train_encodings = self._tokenize(train_urls)
        train_dataset = TensorDataset(
            train_encodings["input_ids"],
            train_encodings["attention_mask"],
            torch.tensor(y_train, dtype=torch.long),
        )
        train_loader = DataLoader(train_dataset, batch_size=self.config.batch_size, shuffle=True)

        val_loader = None
        if val_urls is not None and y_val is not None:
            val_encodings = self._tokenize(val_urls)
            val_dataset = TensorDataset(
                val_encodings["input_ids"],
                val_encodings["attention_mask"],
                torch.tensor(y_val, dtype=torch.long),
            )
            val_loader = DataLoader(val_dataset, batch_size=self.config.batch_size, shuffle=False)

        # Optimizer and scheduler
        optimizer = torch.optim.AdamW(
            self.transformer_model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        total_steps = len(train_loader) * self.config.num_epochs
        warmup_steps = int(total_steps * self.config.warmup_ratio)

        from transformers import get_linear_schedule_with_warmup
        scheduler = get_linear_schedule_with_warmup(
            optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
        )

        # Mixed precision
        use_amp = self.config.mixed_precision and self.device.type == "cuda"
        scaler = GradScaler() if use_amp else None

        # Training loop
        self._best_val_loss = float("inf")
        self._patience_counter = 0
        metrics: dict[str, float] = {}

        for epoch in range(self.config.num_epochs):
            # Train phase
            self.transformer_model.train()
            total_loss = 0.0
            correct = 0
            total = 0

            for step, batch in enumerate(train_loader):
                input_ids, attention_mask, labels = [b.to(self.device) for b in batch]

                optimizer.zero_grad()

                if use_amp:
                    with autocast():
                        outputs = self.transformer_model(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                            labels=labels,
                        )
                        loss = outputs.loss / self.config.gradient_accumulation_steps
                    scaler.scale(loss).backward()

                    if (step + 1) % self.config.gradient_accumulation_steps == 0:
                        scaler.step(optimizer)
                        scaler.update()
                        scheduler.step()
                else:
                    outputs = self.transformer_model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels,
                    )
                    loss = outputs.loss / self.config.gradient_accumulation_steps
                    loss.backward()

                    if (step + 1) % self.config.gradient_accumulation_steps == 0:
                        optimizer.step()
                        scheduler.step()

                total_loss += loss.item() * self.config.gradient_accumulation_steps
                preds = torch.argmax(outputs.logits, dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

            train_acc = correct / total if total > 0 else 0.0
            avg_train_loss = total_loss / len(train_loader)

            logger.info(
                "Epoch %d/%d -- train_loss=%.4f, train_acc=%.4f",
                epoch + 1, self.config.num_epochs, avg_train_loss, train_acc,
            )

            # Validation phase
            if val_loader is not None:
                val_loss, val_acc = self._evaluate_epoch(val_loader, use_amp)
                logger.info(
                    "Epoch %d/%d -- val_loss=%.4f, val_acc=%.4f",
                    epoch + 1, self.config.num_epochs, val_loss, val_acc,
                )

                # Early stopping check
                if val_loss < self._best_val_loss:
                    self._best_val_loss = val_loss
                    self._patience_counter = 0
                else:
                    self._patience_counter += 1
                    if self._patience_counter >= self.config.early_stopping_patience:
                        logger.info("Early stopping triggered at epoch %d", epoch + 1)
                        break

                metrics["val_loss"] = val_loss
                metrics["val_accuracy"] = val_acc

            metrics["train_loss"] = avg_train_loss
            metrics["train_accuracy"] = train_acc

        self._is_trained = True
        self._metadata.training_samples = len(train_urls)
        self._metadata.training_metrics = metrics
        logger.info("Training complete for %s", self._name)
        return metrics

    def _evaluate_epoch(self, data_loader, use_amp: bool) -> tuple[float, float]:
        """
        Evaluate the model on a data loader for one epoch.

        Args:
            data_loader: PyTorch DataLoader.
            use_amp: Whether to use mixed precision.

        Returns:
            Tuple of (average_loss, accuracy).
        """
        import torch
        from torch.cuda.amp import autocast

        self.transformer_model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch in data_loader:
                input_ids, attention_mask, labels = [b.to(self.device) for b in batch]

                if use_amp:
                    with autocast():
                        outputs = self.transformer_model(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                            labels=labels,
                        )
                else:
                    outputs = self.transformer_model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels,
                    )

                total_loss += outputs.loss.item()
                preds = torch.argmax(outputs.logits, dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        avg_loss = total_loss / len(data_loader) if len(data_loader) > 0 else 0.0
        accuracy = correct / total if total > 0 else 0.0
        return avg_loss, accuracy

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Generate binary predictions from URL strings.

        Args:
            X: Array of URL strings.

        Returns:
            Array of binary predictions (0 or 1).
        """
        import torch

        self._initialize_model()
        if not self._is_trained:
            raise ModelError(self._name, "predict", "Model has not been trained")

        urls = self._to_url_list(X)
        self.transformer_model.eval()
        all_preds = []

        with torch.no_grad():
            for i in range(0, len(urls), self.config.batch_size):
                batch_urls = urls[i:i + self.config.batch_size]
                encodings = self._tokenize(batch_urls)
                input_ids = encodings["input_ids"].to(self.device)
                attention_mask = encodings["attention_mask"].to(self.device)

                outputs = self.transformer_model(input_ids=input_ids, attention_mask=attention_mask)
                preds = torch.argmax(outputs.logits, dim=1)
                all_preds.extend(preds.cpu().numpy().tolist())

        return np.array(all_preds)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Generate probability predictions for the positive class (phishing).

        Args:
            X: Array of URL strings.

        Returns:
            Array of probabilities for the phishing class.
        """
        import torch

        self._initialize_model()
        if not self._is_trained:
            raise ModelError(self._name, "predict_proba", "Model has not been trained")

        urls = self._to_url_list(X)
        self.transformer_model.eval()
        all_probs = []

        with torch.no_grad():
            for i in range(0, len(urls), self.config.batch_size):
                batch_urls = urls[i:i + self.config.batch_size]
                encodings = self._tokenize(batch_urls)
                input_ids = encodings["input_ids"].to(self.device)
                attention_mask = encodings["attention_mask"].to(self.device)

                outputs = self.transformer_model(input_ids=input_ids, attention_mask=attention_mask)
                probs = torch.softmax(outputs.logits, dim=1)[:, 1]
                all_probs.extend(probs.cpu().numpy().tolist())

        return np.array(all_probs)

    def save(self, path: Path) -> None:
        """
        Save the transformer model, tokenizer, and config to a directory.

        Args:
            path: Directory path to save the model.
        """
        if not self._is_trained:
            raise ModelError(self._name, "save", "Cannot save untrained model")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        try:
            self.transformer_model.save_pretrained(path)
            self.tokenizer.save_pretrained(path)

            # Save metadata
            import json
            meta_path = path / "model_metadata.json"
            meta_dict = {
                "name": self._name,
                "model_type": self._model_type,
                "config": {
                    "model_name": self.config.model_name,
                    "pretrained_path": self.config.pretrained_path,
                    "max_length": self.config.max_length,
                    "num_labels": self.config.num_labels,
                },
                "training_metrics": self._metadata.training_metrics,
                "training_samples": self._metadata.training_samples,
            }
            meta_path.write_text(json.dumps(meta_dict, indent=2))
            logger.info("Transformer model saved to %s", path)
        except Exception as e:
            raise ModelError(self._name, "save", str(e)) from e

    def load(self, path: Path) -> None:
        """
        Load a transformer model, tokenizer, and config from a directory.

        Args:
            path: Directory path containing the saved model.
        """
        path = Path(path)
        if not path.exists():
            raise ModelError(self._name, "load", f"Directory not found: {path}")

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import json

            # Load metadata
            meta_path = path / "model_metadata.json"
            if meta_path.exists():
                meta_dict = json.loads(meta_path.read_text())
                self._name = meta_dict.get("name", self._name)
                self._metadata.training_metrics = meta_dict.get("training_metrics", {})
                self._metadata.training_samples = meta_dict.get("training_samples", 0)

                config_data = meta_dict.get("config", {})
                self.config.model_name = config_data.get("model_name", self.config.model_name)
                self.config.max_length = config_data.get("max_length", self.config.max_length)

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.tokenizer = AutoTokenizer.from_pretrained(str(path))
            self.transformer_model = AutoModelForSequenceClassification.from_pretrained(str(path))
            self.transformer_model.to(self.device)
            self._is_trained = True
            logger.info("Transformer model loaded from %s", path)
        except Exception as e:
            raise ModelError(self._name, "load", str(e)) from e

    @staticmethod
    def _to_url_list(X: np.ndarray | list | None) -> list[str]:
        """
        Convert various input formats to a list of URL strings.

        Args:
            X: Input that may be a numpy array, list, or None.

        Returns:
            List of URL strings.
        """
        if X is None:
            return []
        if isinstance(X, np.ndarray):
            if X.ndim == 2:
                return [str(x) for x in X[:, 0]]
            return [str(x) for x in X]
        if isinstance(X, list):
            return [str(x) for x in X]
        return [str(X)]


def create_transformer_model(model_name: str = "distilbert", **kwargs: Any) -> TransformerURLClassifier:
    """
    Factory function to create a transformer model by name.

    Args:
        model_name: Key from TRANSFORMER_REGISTRY.
        **kwargs: Additional configuration overrides.

    Returns:
        Configured TransformerURLClassifier instance.

    Example:
        >>> model = create_transformer_model("roberta", batch_size=16)
    """
    config = TransformerConfig(
        model_name=model_name,
        pretrained_path=TRANSFORMER_REGISTRY.get(model_name, model_name),
    )

    # Apply overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            object.__setattr__(config, key, value)

    return TransformerURLClassifier(model_name=model_name, config=config)
