"""
Optuna-based hyperparameter optimization for the training pipeline.

Tunes the four tree-based models (XGBoost, LightGBM, Random Forest,
Extra Trees) over the hyperparameters requested for the Threat Intelligence
System: ``max_depth``, ``learning_rate``, ``n_estimators``, ``subsample``,
``colsample_bytree``, ``gamma``, ``min_child_weight`` and L1/L2
regularization (where the estimator supports them).

Key properties
--------------
* **Early stopping** for the gradient-boosting models via an internal
  validation split; the best iteration count is recorded so the final model
  is trained with an effective ``n_estimators``.
* **Resumable studies** through Optuna's storage API (SQLite by default),
  so tuning can be interrupted and continued at any time.
* **Optional stratified tuning subsample** (``sample_size``) bounds the cost
  of each trial on very large datasets; the *final* model is always trained
  on the full training split with the best parameters found.
* Best parameters are persisted to ``results/best_hyperparameters.json``
  keyed by model name.

The inference pipeline is untouched: tuned parameters flow through the
existing ``create_baseline_model(name, **params)`` factory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Models supported by the tuner.
TUNABLE_MODELS: tuple[str, ...] = (
    "xgboost", "lightgbm", "random_forest", "extra_trees",
)

#: Default file name for persisted best parameters.
BEST_PARAMS_FILENAME = "best_hyperparameters.json"


def _import_optuna():
    """Lazy Optuna import with a clear error message."""
    try:
        import optuna
        return optuna
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "optuna is required for hyperparameter optimization "
            "(pip install optuna)"
        ) from exc


@dataclass
class TuningResult:
    """Outcome of one tuning study.

    Attributes:
        model_name: Tuned model registry key.
        best_params: Best hyperparameters (ready for ``create_baseline_model``).
        best_score: Best objective value (validation F1).
        n_trials: Number of completed trials.
        study_name: Optuna study name (for resuming).
    """

    model_name: str
    best_params: dict[str, Any]
    best_score: float
    n_trials: int
    study_name: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "model_name": self.model_name,
            "best_params": self.best_params,
            "best_score": self.best_score,
            "n_trials": self.n_trials,
            "study_name": self.study_name,
        }


class OptunaTuner:
    """Hyperparameter optimizer for the tree-based baseline models.

    Args:
        model_name: One of ``TUNABLE_MODELS``.
        n_trials: Trials to run in :meth:`tune` (additional calls resume
            the same study and add more trials).
        sample_size: Optional stratified cap on tuning rows (0 = all).
        validation_ratio: Fraction of tuning rows held out for the trial
            validation score and early stopping.
        early_stopping_rounds: Early-stopping patience for boosters.
        storage: Optuna storage URL.  Defaults to a SQLite database inside
            the results directory so studies survive interruptions.
        random_seed: Seed for sampling, splitting and the TPE sampler.
        results_dir: Directory for persisted best parameters.
    """

    def __init__(
        self,
        model_name: str,
        n_trials: int = 25,
        sample_size: int = 0,
        validation_ratio: float = 0.2,
        early_stopping_rounds: int = 30,
        storage: str | None = None,
        random_seed: int | None = None,
        results_dir: Path | None = None,
    ) -> None:
        if model_name not in TUNABLE_MODELS:
            raise ValueError(
                f"Unsupported model '{model_name}'. "
                f"Tunable models: {', '.join(TUNABLE_MODELS)}"
            )
        settings = get_settings()
        self.model_name = model_name
        self.n_trials = int(n_trials)
        self.sample_size = int(sample_size)
        self.validation_ratio = float(validation_ratio)
        self.early_stopping_rounds = int(early_stopping_rounds)
        self.random_seed = (
            random_seed if random_seed is not None
            else settings.dataset.random_seed
        )
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.storage = storage or f"sqlite:///{self.results_dir / 'optuna_studies.db'}"
        self.study_name = f"tune_{model_name}"
        logger.info(
            "OptunaTuner initialised - model=%s trials=%d sample=%s",
            model_name, n_trials, sample_size or "all",
        )

    # ------------------------------------------------------------------
    # Search spaces
    # ------------------------------------------------------------------

    def _suggest_params(self, trial: Any) -> dict[str, Any]:
        """Suggest a hyperparameter set for the current trial."""
        if self.model_name in ("xgboost", "lightgbm"):
            params: dict[str, Any] = {
                "max_depth": trial.suggest_int("max_depth", 4, 12),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 100, 600),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float(
                    "colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float(
                    "reg_alpha", 1e-3, 10.0, log=True),
                "reg_lambda": trial.suggest_float(
                    "reg_lambda", 1e-3, 10.0, log=True),
            }
            if self.model_name == "xgboost":
                params["gamma"] = trial.suggest_float(
                    "gamma", 1e-3, 5.0, log=True)
                params["min_child_weight"] = trial.suggest_int(
                    "min_child_weight", 1, 10)
            else:
                params["num_leaves"] = trial.suggest_int("num_leaves", 31, 255)
                params["min_child_samples"] = trial.suggest_int(
                    "min_child_samples", 5, 100)
            return params

        # random_forest / extra_trees
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "max_depth": trial.suggest_int("max_depth", 10, 40),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
            "max_features": trial.suggest_categorical(
                "max_features", ["sqrt", "log2"]),
        }

    # ------------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------------

    def _build_objective(
        self, X: np.ndarray, y: np.ndarray
    ) -> Callable[[Any], float]:
        """Create the Optuna objective closure over a fixed data split."""
        x_fit, x_val, y_fit, y_val = train_test_split(
            X, y,
            test_size=self.validation_ratio,
            random_state=self.random_seed,
            stratify=y,
        )

        def objective(trial: Any) -> float:
            params = self._suggest_params(trial)
            estimator = self._fit_trial_estimator(
                params, x_fit, y_fit, x_val, y_val, trial
            )
            y_pred = estimator.predict(x_val)
            score = float(f1_score(y_val, y_pred, zero_division=0))
            # Record the effective iteration count for boosters so the
            # final training run uses the early-stopped n_estimators.
            best_iter = getattr(estimator, "best_iteration", None)
            if best_iter is None:
                best_iter = getattr(estimator, "best_iteration_", None)
            if best_iter is not None and best_iter > 0:
                trial.set_user_attr("effective_n_estimators", int(best_iter) + 1)
            return score

        return objective

    def _fit_trial_estimator(
        self,
        params: dict[str, Any],
        x_fit: np.ndarray,
        y_fit: np.ndarray,
        x_val: np.ndarray,
        y_val: np.ndarray,
        trial: Any,
    ) -> Any:
        """Fit one trial estimator (with early stopping for boosters)."""
        if self.model_name == "xgboost":
            import xgboost as xgb
            estimator = xgb.XGBClassifier(
                **params,
                random_state=self.random_seed,
                n_jobs=-1,
                tree_method="hist",
                eval_metric="logloss",
                early_stopping_rounds=self.early_stopping_rounds,
            )
            estimator.fit(x_fit, y_fit, eval_set=[(x_val, y_val)], verbose=False)
            return estimator

        if self.model_name == "lightgbm":
            import lightgbm as lgb
            estimator = lgb.LGBMClassifier(
                **params, random_state=self.random_seed, n_jobs=-1, verbose=-1,
            )
            estimator.fit(
                x_fit, y_fit,
                eval_set=[(x_val, y_val)],
                callbacks=[lgb.early_stopping(self.early_stopping_rounds,
                                              verbose=False)],
            )
            return estimator

        from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
        cls = (RandomForestClassifier if self.model_name == "random_forest"
               else ExtraTreesClassifier)
        estimator = cls(**params, random_state=self.random_seed, n_jobs=-1)
        estimator.fit(x_fit, y_fit)
        return estimator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_study(self) -> Any:
        """Create or load the resumable Optuna study."""
        optuna = _import_optuna()
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        return optuna.create_study(
            study_name=self.study_name,
            storage=self.storage,
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=self.random_seed),
            pruner=optuna.pruners.MedianPruner(n_warmup_steps=2),
            load_if_exists=True,
        )

    def subsample(
        self, X: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Stratified subsample of the tuning data (``sample_size`` rows)."""
        if not self.sample_size or self.sample_size >= len(y):
            return X, y
        rng = np.random.RandomState(self.random_seed)
        idx_parts = []
        for cls in np.unique(y):
            cls_idx = np.where(y == cls)[0]
            take = int(round(self.sample_size * len(cls_idx) / len(y)))
            idx_parts.append(rng.choice(cls_idx, size=min(take, len(cls_idx)),
                                        replace=False))
        idx = np.concatenate(idx_parts)
        rng.shuffle(idx)
        return X[idx], y[idx]

    def tune(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_trials: int | None = None,
        timeout: float | None = None,
    ) -> TuningResult:
        """Run (or resume) the tuning study.

        Args:
            X: Training feature matrix.
            y: Training labels.
            n_trials: Trials to add in this call (default: ``self.n_trials``).
            timeout: Optional wall-clock budget in seconds for this call.

        Returns:
            ``TuningResult`` with the best parameters found so far.
        """
        X_t, y_t = self.subsample(np.asarray(X), np.asarray(y))
        study = self.create_study()
        study.optimize(
            self._build_objective(X_t, y_t),
            n_trials=n_trials if n_trials is not None else self.n_trials,
            timeout=timeout,
            gc_after_trial=True,
            show_progress_bar=False,
        )
        return self._result_from_study(study)

    def best_result(self) -> TuningResult:
        """Return the best result of the persisted study without new trials."""
        return self._result_from_study(self.create_study())

    def _result_from_study(self, study: Any) -> TuningResult:
        """Convert an Optuna study into a ``TuningResult``."""
        best = study.best_trial
        params = dict(best.params)
        effective = best.user_attrs.get("effective_n_estimators")
        if effective:
            params["n_estimators"] = int(effective)
        result = TuningResult(
            model_name=self.model_name,
            best_params=params,
            best_score=float(best.value),
            n_trials=len(study.trials),
            study_name=self.study_name,
        )
        logger.info(
            "Tuning %s: best F1=%.4f after %d trials",
            self.model_name, result.best_score, result.n_trials,
        )
        return result

    def save_best_params(self, result: TuningResult) -> Path:
        """Merge the best parameters into ``results/best_hyperparameters.json``."""
        path = self.results_dir / BEST_PARAMS_FILENAME
        payload: dict[str, Any] = {}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
        payload[result.model_name] = result.to_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Best hyperparameters saved to %s", path)
        return path


def load_best_params(
    results_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load persisted best hyperparameters keyed by model name.

    Returns an empty dict when no tuning has been performed yet, so the
    training pipeline transparently falls back to the default parameters.
    """
    settings = get_settings()
    path = Path(results_dir or settings.paths.results_dir) / BEST_PARAMS_FILENAME
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read %s - using default parameters", path)
        return {}
    return {
        name: entry.get("best_params", {})
        for name, entry in payload.items()
        if isinstance(entry, dict)
    }
