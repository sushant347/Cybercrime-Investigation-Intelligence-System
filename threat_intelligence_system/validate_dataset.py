"""Validate the dataset pipeline against real raw data files."""
import sys
sys.path.insert(0, ".")

print("=" * 60)
print("DATASET PIPELINE VALIDATION")
print("=" * 60)

from src.datasets.loader import DatasetLoader
from src.datasets.cleaner import DatasetCleaner
from src.datasets.validator import DatasetValidator
from src.datasets.merger import DatasetMerger
from src.datasets.statistics import DatasetStatistics

# 1. Load all datasets
print("\n--- 1. Loading Datasets ---")
loader = DatasetLoader()
datasets = loader.load_all()

for name, df in datasets.items():
    print(f"  {name}: {len(df)} rows, columns={list(df.columns)}")
    print(f"    Labels: {df['label'].value_counts().to_dict()}")
    print(f"    Sample URLs: {df['url'].iloc[:2].tolist()}")

# 2. Clean
print("\n--- 2. Cleaning ---")
cleaner = DatasetCleaner()
cleaned_datasets = {}
for name, df in datasets.items():
    cleaned = cleaner.clean(df)
    cleaned_datasets[name] = cleaned
    dropped = len(df) - len(cleaned)
    print(f"  {name}: {len(df)} -> {len(cleaned)} ({dropped} dropped)")

# 3. Validate
print("\n--- 3. Validating ---")
validator = DatasetValidator()
validated_datasets = {}
for name, df in cleaned_datasets.items():
    valid_df, invalid_df = validator.validate(df)
    validated_datasets[name] = valid_df
    print(f"  {name}: {len(df)} -> {len(valid_df)} valid, {len(invalid_df)} invalid")

# 4. Merge & Split
print("\n--- 4. Merging & Splitting ---")
merger = DatasetMerger()
train_df, val_df, test_df = merger.run_pipeline()

total = len(train_df) + len(val_df) + len(test_df)
print(f"  Total after pipeline: {total}")
print(f"  Train: {len(train_df)} ({len(train_df)/total*100:.1f}%)")
print(f"  Val:   {len(val_df)} ({len(val_df)/total*100:.1f}%)")
print(f"  Test:  {len(test_df)} ({len(test_df)/total*100:.1f}%)")

# Verify binary labels
for name, df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
    labels = sorted(df['label'].unique())
    assert labels == [0, 1], f"{name} has unexpected labels: {labels}"
    print(f"  {name} labels: {df['label'].value_counts().to_dict()}")

# 5. Statistics
print("\n--- 5. Statistics ---")
stats = DatasetStatistics()
summary = stats.summary(train_df)
print(f"  Train summary keys: {list(summary.keys())}")
print(f"  Total URLs: {summary.get('total_urls', 'N/A')}")
print(f"  Phishing ratio: {summary.get('phishing_ratio', 'N/A')}")

print("\n" + "=" * 60)
print("DATASET PIPELINE VALIDATION COMPLETE")
print("=" * 60)
