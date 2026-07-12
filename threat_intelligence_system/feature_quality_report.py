"""
Feature quality analysis (ML Improvement, step 2).

Analyses every feature of the production XGBoost model:
  * importance by gain, weight and cover (XGBoost booster)
  * mean |SHAP| value (global SHAP importance via pred_contribs)
  * pairwise correlation (redundancy detection)
  * variance (dead/unused feature detection)

Automatically flags low-value, redundant, highly-correlated and unused
features and writes results/feature_quality_report.json with
recommendations.

Usage:  python feature_quality_report.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np

CACHE = Path("data/processed/cache")
REPORT = Path("results/feature_quality_report.json")
SHAP_SAMPLE = 3000  # pred_contribs is ~130 rows/s on 2 CPUs
CORR_THRESHOLD = 0.95
LOW_VALUE_SHARE = 0.002  # < 0.2% of total gain AND total |SHAP|


def main() -> int:
    import logging; logging.disable(logging.INFO)
    import xgboost as xgb
    from src.models.baseline_models import create_baseline_model

    meta = json.loads((CACHE / "train_curated_meta.json").read_text())
    names: list[str] = meta["feature_names"]
    X = np.load(CACHE / "train_curated_X.npy")

    model = create_baseline_model("xgboost")
    model.load("checkpoints/xgboost.pkl")
    booster = model.model.get_booster()

    # --- 1. Booster importances (gain / weight / cover) --------------------
    def score_map(kind: str) -> dict[str, float]:
        raw = booster.get_score(importance_type=kind)
        out = {}
        for key, val in raw.items():
            if key.startswith("f") and key[1:].isdigit():
                out[names[int(key[1:])]] = float(val)
            else:
                out[key] = float(val)
        return out

    gain = score_map("gain")
    weight = score_map("weight")
    cover = score_map("cover")
    total_gain = sum(gain.values()) or 1.0

    # --- 2. Global SHAP (mean |contribution|) -------------------------------
    rng = np.random.RandomState(42)
    idx = rng.choice(len(X), size=min(SHAP_SAMPLE, len(X)), replace=False)
    dmat = xgb.DMatrix(X[idx].astype(float), feature_names=names)
    contribs = booster.predict(dmat, pred_contribs=True)[:, :-1]
    mean_abs_shap = np.abs(contribs).mean(axis=0)
    total_shap = mean_abs_shap.sum() or 1.0

    # --- 3. Correlation & variance (larger, cheap sample) -------------------
    corr_idx = rng.choice(len(X), size=min(20000, len(X)), replace=False)
    sample = X[corr_idx].astype(float)
    stds = sample.std(axis=0)
    unused = [names[i] for i in range(len(names)) if stds[i] == 0.0]

    corr_pairs: list[dict] = []
    with np.errstate(invalid="ignore"):
        corr = np.corrcoef(sample, rowvar=False)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            c = corr[i, j]
            if np.isfinite(c) and abs(c) >= CORR_THRESHOLD:
                # keep the one with higher SHAP; flag the other as redundant
                keep, drop = (i, j) if mean_abs_shap[i] >= mean_abs_shap[j] else (j, i)
                corr_pairs.append({
                    "feature_a": names[i], "feature_b": names[j],
                    "correlation": round(float(c), 4),
                    "recommend_drop": names[drop],
                })

    # --- 4. Per-feature table + flags -----------------------------------------
    features: dict[str, dict] = {}
    low_value: list[str] = []
    for i, name in enumerate(names):
        gain_share = gain.get(name, 0.0) / total_gain
        shap_share = float(mean_abs_shap[i]) / total_shap
        entry = {
            "gain": round(gain.get(name, 0.0), 2),
            "gain_share": round(gain_share, 5),
            "weight": weight.get(name, 0.0),
            "cover": round(cover.get(name, 0.0), 2),
            "mean_abs_shap": round(float(mean_abs_shap[i]), 5),
            "shap_share": round(shap_share, 5),
            "std": round(float(stds[i]), 4),
        }
        flags = []
        if name in unused:
            flags.append("unused (zero variance)")
        if gain_share < LOW_VALUE_SHARE and shap_share < LOW_VALUE_SHARE:
            flags.append("low_value")
            low_value.append(name)
        entry["flags"] = flags
        features[name] = entry

    redundant = sorted({p["recommend_drop"] for p in corr_pairs})

    ranked_shap = sorted(features.items(), key=lambda kv: kv[1]["shap_share"], reverse=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": model.metadata.model_version,
        "n_features": len(names),
        "shap_sample_size": int(len(idx)),
        "top10_by_shap": [k for k, _ in ranked_shap[:10]],
        "unused_features": unused,
        "low_value_features": low_value,
        "highly_correlated_pairs": corr_pairs,
        "redundant_features_recommend_drop": redundant,
        "recommendation": (
            f"{len(low_value)} low-value and {len(redundant)} redundant feature(s) "
            "could be removed with negligible performance impact. Re-run "
            "optimize_model.py after any removal to confirm."
        ),
        "features": features,
    }
    def np_safe(obj):
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        raise TypeError(f"not serialisable: {type(obj)}")

    REPORT.write_text(json.dumps(report, indent=2, default=np_safe))

    print("Top 10 by SHAP:", ", ".join(report["top10_by_shap"]))
    print("Unused        :", unused or "none")
    print("Low value     :", len(low_value), low_value[:8])
    print("Redundant     :", len(redundant), redundant[:8])
    print("Corr pairs>=%.2f: %d" % (CORR_THRESHOLD, len(corr_pairs)))
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
