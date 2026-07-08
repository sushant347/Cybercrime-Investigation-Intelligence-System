"""Unit tests for ML models and baseline wrappers."""
import numpy as np
import pytest
from src.models.baseline_models import create_baseline_model, BASELINE_MODEL_REGISTRY
from src.utils.exceptions import ModelError

@pytest.fixture
def synthetic_data() -> tuple[np.ndarray, np.ndarray]:
    """Provide small synthetic dataset for training."""
    # 5 features, 20 samples
    X = np.random.randn(20, 5)
    # Binary targets
    y = np.random.randint(0, 2, size=20)
    return X, y

def test_model_registry():
    assert "logistic_regression" in BASELINE_MODEL_REGISTRY
    assert "random_forest" in BASELINE_MODEL_REGISTRY
    assert "xgboost" in BASELINE_MODEL_REGISTRY
    assert "lightgbm" in BASELINE_MODEL_REGISTRY

@pytest.mark.parametrize("model_name", ["logistic_regression", "random_forest", "xgboost", "lightgbm"])
def test_baseline_models_lifecycle(model_name, synthetic_data, tmp_path):
    X, y = synthetic_data
    
    # 1. Creation
    model = create_baseline_model(model_name)
    assert model.name.lower().replace("-", "_").replace(" ", "_") == model_name or model_name in model.name.lower()
    assert model.is_trained is False
    
    # 2. Training
    metrics = model.train(X, y, X, y)
    assert model.is_trained is True
    assert "train_accuracy" in metrics
    assert "val_accuracy" in metrics
    
    # 3. Prediction
    preds = model.predict(X)
    assert preds.shape == (20,)
    assert set(preds).issubset({0, 1})
    
    proba = model.predict_proba(X)
    assert proba.shape == (20,)
    assert np.all(proba >= 0.0) and np.all(proba <= 1.0)
    
    # 4. Save & Load
    save_path = tmp_path / f"{model_name}.pkl"
    model.save(save_path)
    assert save_path.exists()
    
    # Load into new model
    new_model = create_baseline_model(model_name)
    new_model.load(save_path)
    assert new_model.is_trained is True
    
    new_preds = new_model.predict(X)
    np.testing.assert_array_equal(preds, new_preds)

def test_untrained_model_raises():
    model = create_baseline_model("logistic_regression")
    X = np.random.randn(5, 5)
    with pytest.raises(ModelError):
        model.predict(X)
