"""
Baseline machine learning models for phishing URL detection.

Implements 8 classical ML classifiers wrapped in the BaseModel interface:
- Logistic Regression
- Random Forest
- Decision Tree
- Extra Trees
- Naive Bayes (Gaussian)
- Support Vector Machine
- XGBoost
- LightGBM

Each model can be trained, evaluated, saved, and loaded independently.
"""

from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.tree import DecisionTreeClassifier

from src.models.base_model import BaseModel
from src.utils.exceptions import ModelError
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Lazy imports for optional dependencies
def _import_xgboost():
    """Lazy import for XGBoost."""
    try:
        import xgboost as xgb
        return xgb
    except ImportError as e:
        raise ModelError("XGBoost", "import", "xgboost is not installed") from e


def _import_lightgbm():
    """Lazy import for LightGBM."""
    try:
        import lightgbm as lgb
        return lgb
    except ImportError as e:
        raise ModelError("LightGBM", "import", "lightgbm is not installed") from e


class BaselineModel(BaseModel):
    """
    Wrapper around sklearn-compatible classifiers implementing the BaseModel interface.

    This class provides a uniform interface for all baseline models, handling
    training, prediction, probability estimation, and model persistence.

    Attributes:
        model: The underlying sklearn-compatible classifier instance.
    """

    def __init__(self, name: str, model: Any, hyperparameters: dict[str, Any] | None = None) -> None:
        """
        Initialize a baseline model.

        Args:
            name: Human-readable model name.
            model: An sklearn-compatible classifier instance.
            hyperparameters: Optional dict of hyperparameters used to create the model.
        """
        super().__init__(name=name, model_type="baseline")
        self.model = model
        self._metadata.hyperparameters = hyperparameters or {}
        from src.scoring.calibrator import ConfidenceCalibrator
        self.calibrator = ConfidenceCalibrator(method="platt")

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
    ) -> dict[str, float]:
        """
        Train the baseline model.

        Args:
            X_train: Training feature matrix of shape (n_samples, n_features).
            y_train: Training labels of shape (n_samples,).
            X_val: Optional validation feature matrix.
            y_val: Optional validation labels.
            feature_names: Optional ordered list of feature names.

        Returns:
            Dictionary of training and validation metrics.

        Raises:
            ModelError: If training fails.
        """
        logger.info("Training %s on %d samples with %d features", self._name, len(y_train), X_train.shape[1])

        if feature_names is not None:
            self._metadata.feature_names = feature_names

        try:
            self.model.fit(X_train, y_train)
            self._is_trained = True
            self._metadata.training_samples = len(y_train)
            
            # Fit probability calibrator
            try:
                if X_val is not None and y_val is not None:
                    val_proba_raw = self.predict_proba_raw(X_val)
                    self.calibrator.fit(y_val, val_proba_raw)
                else:
                    train_proba_raw = self.predict_proba_raw(X_train)
                    self.calibrator.fit(y_train, train_proba_raw)
            except Exception as cal_err:
                logger.warning("Failed to fit calibrator for %s: %s. Falling back to identity.", self._name, cal_err)
                from src.scoring.calibrator import ConfidenceCalibrator
                self.calibrator = ConfidenceCalibrator(method="identity")
                self.calibrator.is_fitted = True
        except Exception as e:
            raise ModelError(self._name, "training", str(e)) from e

        # Compute training metrics
        metrics: dict[str, float] = {}

        train_preds = self.predict(X_train)
        train_proba = self.predict_proba(X_train)

        metrics["train_accuracy"] = float(accuracy_score(y_train, train_preds))
        metrics["train_f1"] = float(f1_score(y_train, train_preds, zero_division=0))
        try:
            metrics["train_auc"] = float(roc_auc_score(y_train, train_proba))
        except ValueError:
            metrics["train_auc"] = 0.0

        # Compute validation metrics if provided
        if X_val is not None and y_val is not None:
            val_preds = self.predict(X_val)
            val_proba = self.predict_proba(X_val)
            metrics["val_accuracy"] = float(accuracy_score(y_val, val_preds))
            metrics["val_f1"] = float(f1_score(y_val, val_preds, zero_division=0))
            try:
                metrics["val_auc"] = float(roc_auc_score(y_val, val_proba))
            except ValueError:
                metrics["val_auc"] = 0.0

        self._metadata.training_metrics = metrics
        logger.info("Training complete for %s -- metrics: %s", self._name, metrics)
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Generate binary predictions.

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Array of binary predictions (0 or 1).

        Raises:
            ModelError: If prediction fails or model is not trained.
        """
        if not self._is_trained:
            raise ModelError(self._name, "predict", "Model has not been trained")
        try:
            return self.model.predict(X)
        except Exception as e:
            raise ModelError(self._name, "predict", str(e)) from e

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Generate probability predictions for the positive class (phishing),
        with post-hoc calibration applied.

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Array of calibrated probabilities for the phishing class.
        """
        raw_proba = self.predict_proba_raw(X)
        if self.calibrator is not None and self.calibrator.is_fitted:
            # Calibrate raw probabilities
            return np.array([self.calibrator.calibrate(p) for p in raw_proba])
        return raw_proba

    def predict_proba_raw(self, X: np.ndarray) -> np.ndarray:
        """
        Generate raw, uncalibrated probability predictions for the positive class.

        Args:
            X: Feature matrix of shape (n_samples, n_features).

        Returns:
            Array of raw probabilities for the phishing class.

        Raises:
            ModelError: If probability prediction fails.
        """
        if not self._is_trained:
            raise ModelError(self._name, "predict_proba_raw", "Model has not been trained")

        try:
            if hasattr(self.model, "predict_proba"):
                probas = self.model.predict_proba(X)
                # Return probability of positive class (index 1)
                if probas.ndim == 2 and probas.shape[1] == 2:
                    return probas[:, 1]
                return probas
            elif hasattr(self.model, "decision_function"):
                # Sigmoid transformation for SVM
                decisions = self.model.decision_function(X)
                return 1.0 / (1.0 + np.exp(-decisions))
            else:
                # Fallback to binary predictions
                logger.warning("Model %s has no predict_proba or decision_function, using predict", self._name)
                return self.model.predict(X).astype(float)
        except Exception as e:
            raise ModelError(self._name, "predict_proba_raw", str(e)) from e

    def save(self, path: Path) -> None:
        """
        Save the trained model to disk using joblib.

        Args:
            path: File path to save the model (should end in .pkl).

        Raises:
            ModelError: If saving fails.
        """
        if not self._is_trained:
            raise ModelError(self._name, "save", "Cannot save untrained model")
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            calibrator_state = None
            if self.calibrator is not None:
                calibrator_state = {
                    "method": self.calibrator.method,
                    "is_fitted": self.calibrator.is_fitted,
                    "platt_A": getattr(self.calibrator, "_platt_A", 1.0),
                    "platt_B": getattr(self.calibrator, "_platt_B", 0.0),
                    "isotonic_x": getattr(self.calibrator, "_isotonic_x", []),
                    "isotonic_y": getattr(self.calibrator, "_isotonic_y", []),
                    "temperature": getattr(self.calibrator, "_temperature", 1.0),
                }

            save_data = {
                "model": self.model,
                "metadata": self._metadata,
                "name": self._name,
                "calibrator_state": calibrator_state,
            }

            # XGBoost: serialise the booster in its NATIVE format (version-
            # portable, no pickle compatibility warnings). The pickle then
            # carries everything except the sklearn estimator itself.
            xgb_mod = _import_xgboost()
            if xgb_mod is not None and isinstance(self.model, xgb_mod.XGBClassifier):
                native_path = path.with_suffix(".ubj")
                self.model.save_model(native_path)
                save_data["model"] = None
                save_data["xgb_native_file"] = native_path.name
                save_data["xgb_params"] = self.model.get_params(deep=False)

            joblib.dump(save_data, path)
            logger.info("Model %s saved to %s", self._name, path)
        except Exception as e:
            raise ModelError(self._name, "save", str(e)) from e

    def load(self, path: Path) -> None:
        """
        Load a trained model from disk.

        Args:
            path: File path to load the model from.

        Raises:
            ModelError: If loading fails or file doesn't exist.
        """
        path = Path(path)
        if not path.exists():
            raise ModelError(self._name, "load", f"File not found: {path}")
        try:
            save_data = joblib.load(path)

            native_file = save_data.get("xgb_native_file")
            if native_file:
                # New format: reconstruct the classifier and load the
                # version-portable native booster.
                xgb_mod = _import_xgboost()
                native_path = path.parent / native_file
                if not native_path.exists():
                    raise FileNotFoundError(
                        f"Native booster file missing: {native_path}"
                    )
                params = dict(save_data.get("xgb_params") or {})
                params.pop("use_label_encoder", None)  # removed in xgboost>=2
                self.model = xgb_mod.XGBClassifier(**params)
                self.model.load_model(native_path)
            else:
                # Legacy format: full pickled estimator.
                self.model = save_data["model"]

            self._metadata = save_data["metadata"]
            self._name = save_data.get("name", self._name)
            self._is_trained = True
            
            # Restore calibrator
            from src.scoring.calibrator import ConfidenceCalibrator
            calibrator_state = save_data.get("calibrator_state")
            if calibrator_state is not None:
                self.calibrator = ConfidenceCalibrator(method=calibrator_state["method"])
                self.calibrator.is_fitted = calibrator_state["is_fitted"]
                self.calibrator._platt_A = calibrator_state["platt_A"]
                self.calibrator._platt_B = calibrator_state["platt_B"]
                self.calibrator._isotonic_x = calibrator_state["isotonic_x"]
                self.calibrator._isotonic_y = calibrator_state["isotonic_y"]
                self.calibrator._temperature = calibrator_state["temperature"]
            else:
                self.calibrator = ConfidenceCalibrator(method="identity")
                self.calibrator.is_fitted = True
                
            logger.info("Model %s loaded from %s", self._name, path)
        except Exception as e:
            raise ModelError(self._name, "load", str(e)) from e


class LogisticRegressionModel(BaselineModel):
    """
    Logistic Regression classifier for phishing URL detection.

    A linear model that is fast to train and provides good probability estimates.
    Works well as a baseline and when features are well-engineered.
    """

    def __init__(
        self,
        C: float = 1.0,
        max_iter: int = 1000,
        solver: str = "lbfgs",
        random_state: int = 42,
    ) -> None:
        """
        Initialize Logistic Regression model.

        Args:
            C: Inverse of regularization strength.
            max_iter: Maximum number of iterations for the solver.
            solver: Algorithm for optimization ('lbfgs', 'saga', etc.).
            random_state: Random seed for reproducibility.
        """
        params = {"C": C, "max_iter": max_iter, "solver": solver, "random_state": random_state}
        model = LogisticRegression(**params)
        super().__init__(name="Logistic Regression", model=model, hyperparameters=params)


class RandomForestModel(BaselineModel):
    """
    Random Forest classifier for phishing URL detection.

    An ensemble of decision trees that provides robust predictions,
    feature importance rankings, and handles non-linear patterns well.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int | None = 30,
        min_samples_split: int = 5,
        min_samples_leaf: int = 2,
        max_features: str = "sqrt",
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        """
        Initialize Random Forest model.

        Args:
            n_estimators: Number of trees in the forest.
            max_depth: Maximum depth of each tree.
            min_samples_split: Minimum samples to split a node.
            min_samples_leaf: Minimum samples in a leaf node.
            max_features: Number of features for best split.
            random_state: Random seed for reproducibility.
            n_jobs: Number of parallel jobs (-1 for all CPUs).
        """
        params = {
            "n_estimators": n_estimators, "max_depth": max_depth,
            "min_samples_split": min_samples_split, "min_samples_leaf": min_samples_leaf,
            "max_features": max_features, "random_state": random_state, "n_jobs": n_jobs,
        }
        model = RandomForestClassifier(**params)
        super().__init__(name="Random Forest", model=model, hyperparameters=params)


class DecisionTreeModel(BaselineModel):
    """
    Decision Tree classifier for phishing URL detection.

    A simple, interpretable model that produces a tree of if-then rules.
    Useful for understanding which features are most important.
    """

    def __init__(
        self,
        max_depth: int | None = 20,
        min_samples_split: int = 5,
        min_samples_leaf: int = 2,
        random_state: int = 42,
    ) -> None:
        """
        Initialize Decision Tree model.

        Args:
            max_depth: Maximum depth of the tree.
            min_samples_split: Minimum samples to split a node.
            min_samples_leaf: Minimum samples in a leaf node.
            random_state: Random seed for reproducibility.
        """
        params = {
            "max_depth": max_depth, "min_samples_split": min_samples_split,
            "min_samples_leaf": min_samples_leaf, "random_state": random_state,
        }
        model = DecisionTreeClassifier(**params)
        super().__init__(name="Decision Tree", model=model, hyperparameters=params)


class ExtraTreesModel(BaselineModel):
    """
    Extra Trees (Extremely Randomized Trees) classifier.

    Similar to Random Forest but with more randomization in split thresholds,
    often resulting in slightly better generalization and faster training.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int | None = 30,
        min_samples_split: int = 5,
        min_samples_leaf: int = 2,
        max_features: str = "sqrt",
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        """
        Initialize Extra Trees model.

        Args:
            n_estimators: Number of trees.
            max_depth: Maximum tree depth.
            min_samples_split: Minimum samples to split.
            min_samples_leaf: Minimum leaf samples.
            max_features: Features for best split.
            random_state: Random seed.
            n_jobs: Parallel jobs.
        """
        params = {
            "n_estimators": n_estimators, "max_depth": max_depth,
            "min_samples_split": min_samples_split, "min_samples_leaf": min_samples_leaf,
            "max_features": max_features, "random_state": random_state, "n_jobs": n_jobs,
        }
        model = ExtraTreesClassifier(**params)
        super().__init__(name="Extra Trees", model=model, hyperparameters=params)


class NaiveBayesModel(BaselineModel):
    """
    Gaussian Naive Bayes classifier for phishing URL detection.

    A probabilistic classifier that assumes feature independence.
    Very fast to train and works well with continuous features.
    """

    def __init__(self, var_smoothing: float = 1e-9) -> None:
        """
        Initialize Gaussian Naive Bayes model.

        Args:
            var_smoothing: Portion of largest variance added to all variances.
        """
        params = {"var_smoothing": var_smoothing}
        model = GaussianNB(**params)
        super().__init__(name="Naive Bayes", model=model, hyperparameters=params)


class SVMModel(BaselineModel):
    """
    Support Vector Machine classifier for phishing URL detection.

    Uses LinearSVC with CalibratedClassifierCV for probability estimation.
    Linear SVM is efficient for high-dimensional feature spaces.
    """

    def __init__(
        self,
        C: float = 1.0,
        max_iter: int = 2000,
        random_state: int = 42,
    ) -> None:
        """
        Initialize SVM model with probability calibration.

        Args:
            C: Regularization parameter.
            max_iter: Maximum iterations for the solver.
            random_state: Random seed for reproducibility.
        """
        params = {"C": C, "max_iter": max_iter, "random_state": random_state}
        base_svm = LinearSVC(**params, dual="auto")
        model = CalibratedClassifierCV(base_svm, cv=3)
        super().__init__(name="SVM", model=model, hyperparameters=params)


class XGBoostModel(BaselineModel):
    """
    XGBoost gradient boosting classifier for phishing URL detection.

    State-of-the-art gradient boosting framework. Typically achieves the
    best accuracy among baseline models for tabular feature data.
    """

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 8,
        learning_rate: float = 0.1,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        min_child_weight: int = 3,
        gamma: float = 0.1,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
        use_gpu: bool = False,
    ) -> None:
        """
        Initialize XGBoost model.

        Args:
            n_estimators: Number of boosting rounds.
            max_depth: Maximum tree depth.
            learning_rate: Step size shrinkage.
            subsample: Subsample ratio of training instances.
            colsample_bytree: Subsample ratio of features.
            min_child_weight: Minimum sum of instance weight in a child.
            gamma: Minimum loss reduction for further partition.
            reg_alpha: L1 regularization.
            reg_lambda: L2 regularization.
            random_state: Random seed.
            n_jobs: Parallel jobs.
            use_gpu: Whether to use GPU acceleration.
        """
        xgb = _import_xgboost()

        params = {
            "n_estimators": n_estimators, "max_depth": max_depth,
            "learning_rate": learning_rate, "subsample": subsample,
            "colsample_bytree": colsample_bytree, "min_child_weight": min_child_weight,
            "gamma": gamma, "reg_alpha": reg_alpha, "reg_lambda": reg_lambda,
            "random_state": random_state, "n_jobs": n_jobs,
            "eval_metric": "logloss", "use_label_encoder": False,
            "verbosity": 0,
        }

        if use_gpu:
            params["tree_method"] = "hist"
            params["device"] = "cuda"

        model = xgb.XGBClassifier(**params)
        super().__init__(name="XGBoost", model=model, hyperparameters=params)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
    ) -> dict[str, float]:
        """
        Train XGBoost with optional early stopping on validation set.

        Args:
            X_train: Training features.
            y_train: Training labels.
            X_val: Optional validation features.
            y_val: Optional validation labels.
            feature_names: Optional ordered list of feature names.

        Returns:
            Training and validation metrics.
        """
        logger.info("Training %s on %d samples with %d features", self._name, len(y_train), X_train.shape[1])

        if feature_names is not None:
            self._metadata.feature_names = feature_names

        try:
            fit_params: dict[str, Any] = {}
            if X_val is not None and y_val is not None:
                fit_params["eval_set"] = [(X_val, y_val)]
                fit_params["verbose"] = False

            self.model.fit(X_train, y_train, **fit_params)
            self._is_trained = True
            self._metadata.training_samples = len(y_train)

            # Fit probability calibrator
            try:
                if X_val is not None and y_val is not None:
                    val_proba_raw = self.predict_proba_raw(X_val)
                    self.calibrator.fit(y_val, val_proba_raw)
                else:
                    train_proba_raw = self.predict_proba_raw(X_train)
                    self.calibrator.fit(y_train, train_proba_raw)
            except Exception as cal_err:
                logger.warning("Failed to fit calibrator for %s: %s. Falling back to identity.", self._name, cal_err)
                from src.scoring.calibrator import ConfidenceCalibrator
                self.calibrator = ConfidenceCalibrator(method="identity")
                self.calibrator.is_fitted = True
        except Exception as e:
            raise ModelError(self._name, "training", str(e)) from e

        # Compute metrics
        metrics: dict[str, float] = {}
        train_preds = self.predict(X_train)
        train_proba = self.predict_proba(X_train)
        metrics["train_accuracy"] = float(accuracy_score(y_train, train_preds))
        metrics["train_f1"] = float(f1_score(y_train, train_preds, zero_division=0))
        try:
            metrics["train_auc"] = float(roc_auc_score(y_train, train_proba))
        except ValueError:
            metrics["train_auc"] = 0.0

        if X_val is not None and y_val is not None:
            val_preds = self.predict(X_val)
            val_proba = self.predict_proba(X_val)
            metrics["val_accuracy"] = float(accuracy_score(y_val, val_preds))
            metrics["val_f1"] = float(f1_score(y_val, val_preds, zero_division=0))
            try:
                metrics["val_auc"] = float(roc_auc_score(y_val, val_proba))
            except ValueError:
                metrics["val_auc"] = 0.0

        self._metadata.training_metrics = metrics
        logger.info("Training complete for %s -- metrics: %s", self._name, metrics)
        return metrics


class LightGBMModel(BaselineModel):
    """
    LightGBM gradient boosting classifier for phishing URL detection.

    A fast, distributed gradient boosting framework. Optimized for speed
    and memory efficiency with large datasets.
    """

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 8,
        learning_rate: float = 0.1,
        num_leaves: int = 63,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        min_child_samples: int = 20,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        """
        Initialize LightGBM model.

        Args:
            n_estimators: Number of boosting iterations.
            max_depth: Maximum tree depth.
            learning_rate: Boosting learning rate.
            num_leaves: Maximum number of leaves in one tree.
            subsample: Subsample ratio.
            colsample_bytree: Feature subsample ratio.
            min_child_samples: Minimum data in one leaf.
            reg_alpha: L1 regularization.
            reg_lambda: L2 regularization.
            random_state: Random seed.
            n_jobs: Parallel jobs.
        """
        lgb = _import_lightgbm()

        params = {
            "n_estimators": n_estimators, "max_depth": max_depth,
            "learning_rate": learning_rate, "num_leaves": num_leaves,
            "subsample": subsample, "colsample_bytree": colsample_bytree,
            "min_child_samples": min_child_samples,
            "reg_alpha": reg_alpha, "reg_lambda": reg_lambda,
            "random_state": random_state, "n_jobs": n_jobs,
            "verbose": -1,
        }

        model = lgb.LGBMClassifier(**params)
        super().__init__(name="LightGBM", model=model, hyperparameters=params)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
    ) -> dict[str, float]:
        """
        Train LightGBM with optional early stopping on validation set.

        Args:
            X_train: Training features.
            y_train: Training labels.
            X_val: Optional validation features.
            y_val: Optional validation labels.
            feature_names: Optional ordered list of feature names.

        Returns:
            Training and validation metrics.
        """
        logger.info("Training %s on %d samples with %d features", self._name, len(y_train), X_train.shape[1])

        if feature_names is not None:
            self._metadata.feature_names = feature_names

        try:
            fit_params: dict[str, Any] = {}
            if X_val is not None and y_val is not None:
                fit_params["eval_set"] = [(X_val, y_val)]
                fit_params["eval_metric"] = "logloss"

            self.model.fit(X_train, y_train, **fit_params)
            self._is_trained = True
            self._metadata.training_samples = len(y_train)

            # Fit probability calibrator
            try:
                if X_val is not None and y_val is not None:
                    val_proba_raw = self.predict_proba_raw(X_val)
                    self.calibrator.fit(y_val, val_proba_raw)
                else:
                    train_proba_raw = self.predict_proba_raw(X_train)
                    self.calibrator.fit(y_train, train_proba_raw)
            except Exception as cal_err:
                logger.warning("Failed to fit calibrator for %s: %s. Falling back to identity.", self._name, cal_err)
                from src.scoring.calibrator import ConfidenceCalibrator
                self.calibrator = ConfidenceCalibrator(method="identity")
                self.calibrator.is_fitted = True
        except Exception as e:
            raise ModelError(self._name, "training", str(e)) from e

        # Compute metrics
        metrics: dict[str, float] = {}
        train_preds = self.predict(X_train)
        train_proba = self.predict_proba(X_train)
        metrics["train_accuracy"] = float(accuracy_score(y_train, train_preds))
        metrics["train_f1"] = float(f1_score(y_train, train_preds, zero_division=0))
        try:
            metrics["train_auc"] = float(roc_auc_score(y_train, train_proba))
        except ValueError:
            metrics["train_auc"] = 0.0

        if X_val is not None and y_val is not None:
            val_preds = self.predict(X_val)
            val_proba = self.predict_proba(X_val)
            metrics["val_accuracy"] = float(accuracy_score(y_val, val_preds))
            metrics["val_f1"] = float(f1_score(y_val, val_preds, zero_division=0))
            try:
                metrics["val_auc"] = float(roc_auc_score(y_val, val_proba))
            except ValueError:
                metrics["val_auc"] = 0.0

        self._metadata.training_metrics = metrics
        logger.info("Training complete for %s -- metrics: %s", self._name, metrics)
        return metrics


# ============================================================
# Model Factory
# ============================================================

# Registry of all available baseline models
BASELINE_MODEL_REGISTRY: dict[str, type[BaselineModel]] = {
    "logistic_regression": LogisticRegressionModel,
    "random_forest": RandomForestModel,
    "decision_tree": DecisionTreeModel,
    "extra_trees": ExtraTreesModel,
    "naive_bayes": NaiveBayesModel,
    "svm": SVMModel,
    "xgboost": XGBoostModel,
    "lightgbm": LightGBMModel,
}


def create_baseline_model(model_name: str, **kwargs: Any) -> BaselineModel:
    """
    Factory function to create a baseline model by name.

    Args:
        model_name: Name key from BASELINE_MODEL_REGISTRY.
        **kwargs: Hyperparameters passed to the model constructor.

    Returns:
        Instantiated baseline model.

    Raises:
        ModelError: If model_name is not recognized.

    Example:
        >>> model = create_baseline_model("xgboost", n_estimators=500)
    """
    model_name_lower = model_name.lower().replace(" ", "_").replace("-", "_")

    if model_name_lower not in BASELINE_MODEL_REGISTRY:
        available = ", ".join(sorted(BASELINE_MODEL_REGISTRY.keys()))
        raise ModelError(
            model_name, "create",
            f"Unknown model: {model_name}. Available: {available}"
        )

    model_class = BASELINE_MODEL_REGISTRY[model_name_lower]
    return model_class(**kwargs)


def create_all_baseline_models(**kwargs: Any) -> list[BaselineModel]:
    """
    Create instances of all available baseline models.

    Args:
        **kwargs: Common hyperparameters (e.g., random_state) passed to all models.

    Returns:
        List of all baseline model instances.
    """
    models = []
    for name, model_class in BASELINE_MODEL_REGISTRY.items():
        try:
            # Only pass kwargs that the constructor accepts
            import inspect
            sig = inspect.signature(model_class.__init__)
            valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            models.append(model_class(**valid_kwargs))
        except Exception as e:
            logger.warning("Failed to create model %s: %s", name, e)
    return models
