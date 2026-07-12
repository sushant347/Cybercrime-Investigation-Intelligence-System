"""
Chunked feature-matrix extraction with on-disk caching (ML Improvement).

Builds numpy feature matrices for large URL datasets in resumable chunks so
training scripts never re-extract features. Samples are deterministic
(seed 42) and stratified; curated diversity/official rows are always kept.

Usage:
    python extract_features_cache.py --split train_curated --total 200000 --chunk 70000
    python extract_features_cache.py --split validation --total 40000
    python extract_features_cache.py --split test --total 40000

Each call processes at most --chunk rows and exits; re-run until it prints
COMPLETE. Output: data/processed/cache/<split>_X.npy, _y.npy, _meta.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.feature_engineering.pipeline import FeaturePipeline


def load_sample(split: str, total: int) -> pd.DataFrame:
    """Deterministic stratified sample of a split (keeps curated rows)."""
    settings = get_settings()
    df = pd.read_csv(settings.paths.processed_data_dir / f"{split}.csv")[["url", "label"]].dropna()
    if len(df) <= total:
        return df.reset_index(drop=True)
    # Always keep the tail rows (curated additions appended last)
    keep_tail = df.tail(3000) if split.startswith("train") else df.iloc[0:0]
    rest = df.iloc[: len(df) - len(keep_tail)]
    frac = (total - len(keep_tail)) / len(rest)
    sampled = (
        rest.groupby("label", group_keys=False)
        .apply(lambda g: g.sample(frac=frac, random_state=42))
    )
    return (
        pd.concat([sampled, keep_tail])
        .drop_duplicates(subset="url")
        .sample(frac=1.0, random_state=42)  # shuffle
        .reset_index(drop=True)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--chunk", type=int, default=70000)
    args = parser.parse_args()

    settings = get_settings()
    cache = settings.paths.processed_data_dir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    x_path = cache / f"{args.split}_X.npy"
    y_path = cache / f"{args.split}_y.npy"
    meta_path = cache / f"{args.split}_meta.json"

    pipeline = FeaturePipeline()
    names = pipeline.get_feature_names()

    # Cache the sampled rows so later chunks skip the big CSV entirely
    sample_path = cache / f"{args.split}_sample.csv"
    if sample_path.exists():
        df = pd.read_csv(sample_path)
    else:
        df = load_sample(args.split, args.total)
        df.to_csv(sample_path, index=False)
    n = len(df)

    # Shard-based extraction: each chunk saves its own small shard file,
    # so an interrupted run never corrupts previous work.
    done = 0
    shards: list[str] = []
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("total") == n and meta.get("feature_names") == names:
            done = meta.get("done", 0)
            shards = meta.get("shards", [])

    if done >= n and x_path.exists():
        print(f"COMPLETE {args.split}: {n} rows cached at {x_path}")
        return 0

    if done < n:
        end = min(n, done + args.chunk)
        rows = np.zeros((end - done, len(names)), dtype=np.float32)
        for i, url in enumerate(df["url"].iloc[done:end].astype(str)):
            try:
                feats = pipeline.extract(url)
            except Exception:
                feats = {}
            for j, name in enumerate(names):
                value = feats.get(name)
                try:
                    rows[i, j] = float(value) if value is not None else 0.0
                except (TypeError, ValueError):
                    rows[i, j] = 0.0

        shard_file = cache / f"{args.split}_shard_{done}.npy"
        np.save(shard_file, rows)
        shards.append(shard_file.name)
        done = end
        meta_path.write_text(json.dumps({
            "total": n, "done": done, "feature_names": names,
            "shards": shards, "source": f"{args.split}.csv",
        }))

    if done >= n:
        # Merge shards into the final matrix
        full_x = np.concatenate([np.load(cache / s) for s in shards], axis=0)
        assert full_x.shape == (n, len(names)), full_x.shape
        np.save(x_path, full_x)
        np.save(y_path, df["label"].astype(int).to_numpy())
        print(f"COMPLETE {args.split}: {n} rows cached at {x_path}")
    else:
        print(f"PARTIAL {args.split}: {done}/{n} rows extracted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
