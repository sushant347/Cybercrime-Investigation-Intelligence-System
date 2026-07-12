"""
Abstract base model interface for the Phishing URL Detection Engine.

Defines the contract that all models (baseline and transformer) must implement,
ensuring consistent training, prediction, and serialization interfaces.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ModelMetadata:
    """
    Metadata associated with a trained model.

    Attributes:
        name: Human-readable model name.
        model_type: Model category (e.g., 'baseline', 'transformer').
        version: Version string for tracking.
        feature_names: Ordered list of feature names the model expects.
        training_samples: Number of samples used for training.
        training_metrics: Dictionary of training performance metrics.
        hyperparameters: Dictionary of hyperparameters used.
    """

    name: str = ""
    model_type: str = ""
    version: str = "1.0.0"
    feature_names: list[str] = field(default_factory=list)
    training_samples: int = 0
    training_metrics: dict[str, float] = field(default_factory=dict)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    model_version: str = "1.0.0"
    training_date: str = ""
    dataset_version: str = "1.0.0"
    feature_version: str = "1.0.0"
    calibration_version: str = "1.0.0"
    validation_metrics: dict[str, float] = field(default_factory=dict)
    benchmark_metrics: dict[str, float] = field(default_factory=dict)


class BaseModel(ABC):
    """
    Abstract base class for all phishing detection models.

    Defines the interface that baseline (sklearn-based) and transformer models
    must implement. Provides common functionality for model lifecycle management.

    Subclasses must implement:
        - train(): Train the model on provided data.
        - predict(): Generate binary predictions.
        - predict_proba(): Generate probability predictions.
        - save(): Persist the trained model to disk.
        - load(): Load a trained model from disk.
    """

    def __init__(self, name: str, model_type: str = "base") -> None:
        """
        Initialize the base model.

        Args:
            name: Human-readable model name.
            model_type: Category of model ('baseline' or 'transformer').
        """
        self._name = name
        self._model_type = model_type
        self._is_trained = False
        self._metadata = ModelMetadata(name=name, model_type=model_type)
        logger.info("Initialized model: %s (type=%s)", name, model_type)

    @property
    def name(self) -> str:
        """Get the model name."""
        return self._name

    @property
    def model_type(self) -> str:
        """Get the model type."""
        return self._model_type

    @property
    def is_trained(self) -> bool:
        """Check if the model has been trained."""
        return self._is_trained

    @property
    def metadata(self) -> ModelMetadata:
        """Get the model metadata."""
        return self._metadata

    @abstractmethod
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
    ) -> dict[str, float]:
        """
        Train the model on the provided data.

        Args:
            X_train: Training feature matrix.
            y_train: Training labels.
            X_val: Optional validation feature matrix.
            y_val: Optional validation labels.

        Returns:
            Dictionary of training metrics.
        """
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Generate binary predictions (0 or 1).

        Args:
            X: Feature matrix.

        Returns:
            Array of binary predictions.
        """
        ...

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Generate probability predictions.

        Args:
            X: Feature matrix.

        Returns:
            Array of probabilities for the positive class (phishing).
        """
        ...

    @abstractmethod
    def save(self, path: Path) -> None:
        """
        Save the trained model to disk.

        Args:
            path: File path to save the model.
        """
        ...

    @abstractmethod
    def load(self, path: Path) -> None:
        """
        Load a trained model from disk.

        Args:
            path: File path to load the model from.
        """
        ...

    def get_params(self) -> dict[str, Any]:
        """
        Get the model's hyperparameters.

        Returns:
            Dictionary of hyperparameters.
        """
        return self._metadata.hyperparameters

    def __repr__(self) -> str:
        status = "trained" if self._is_trained else "untrained"
        return f"{self.__class__.__name__}(name={self._name!r}, status={status})"
