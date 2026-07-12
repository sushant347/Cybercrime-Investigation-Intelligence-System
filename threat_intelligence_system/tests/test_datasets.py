"""Unit tests for dataset modules using mock DataFrames."""
import pandas as pd
import pytest
from src.datasets.cleaner import DatasetCleaner
from src.datasets.validator import DatasetValidator
from src.datasets.merger import DatasetMerger
from src.datasets.statistics import DatasetStatistics
from src.utils.exceptions import DatasetError

@pytest.fixture
def raw_mock_df() -> pd.DataFrame:
    """Create a mock raw dataset."""
    return pd.DataFrame({
        "url": [
            "  https://www.google.com  ",
            "http://phish-login.xyz",
            None,
            "short",  # too short (< 8 chars)
            "https://" + "a" * 3000 + ".com",  # too long (> 2048 chars)
            "https://legit.com",
        ],
        "label": [0, 1, 0, 1, 0, 0]
    })

def test_dataset_cleaner(raw_mock_df):
    cleaner = DatasetCleaner()
    cleaned = cleaner.clean(raw_mock_df)
    
    # Check that nulls, short/long URLs are removed
    # "short" -> "http://short" (length 12), so it is kept! Only null and long are dropped.
    assert len(cleaned) == 4
    # Check whitespace stripping and normalization
    assert "https://www.google.com" in cleaned["url"].values
    assert "http://phish-login.xyz" in cleaned["url"].values
    assert "https://legit.com" in cleaned["url"].values

def test_dataset_validator():
    validator = DatasetValidator()
    test_df = pd.DataFrame({
        "url": [
            "https://www.google.com",
            "http://example.com",
            "ftp://invalid-scheme.com",  # invalid scheme for our validation rules
            "no-dot",                    # missing dot
            "12345678",                  # purely numeric
        ],
        "label": [0, 1, 0, 1, 0]
    })
    
    valid, invalid = validator.validate(test_df)
    assert len(valid) == 2
    assert len(invalid) == 3
    assert "https://www.google.com" in valid["url"].values
    assert "ftp://invalid-scheme.com" in invalid["url"].values

def test_dataset_merger():
    merger = DatasetMerger()
    
    df1 = pd.DataFrame({"url": ["https://a.com", "https://b.com"], "label": [0, 1]})
    df2 = pd.DataFrame({"url": ["https://b.com", "https://c.com"], "label": [1, 1]})
    
    # Test merging with deduplication
    merged = merger.merge({"d1": df1, "d2": df2})
    assert len(merged) == 3  # b.com is deduplicated
    assert merged["label"].value_counts().to_dict() == {1: 2, 0: 1}

def test_dataset_merger_splitting():
    merger = DatasetMerger()
    
    # Create large enough mock dataset for splitting
    urls = [f"https://domain{i}.com" for i in range(100)]
    labels = [i % 2 for i in range(100)]
    df = pd.DataFrame({"url": urls, "label": labels})
    
    train, val, test = merger.split(df)
    # Ratios are 70/15/15 by default, allow small rounding variations
    assert len(train) in (69, 70)
    assert len(val) in (15, 16)
    assert len(test) in (15, 16)
    assert len(train) + len(val) + len(test) == 100
    
    # Stratification check (around half of each split should be label=1)
    assert abs(train["label"].sum() - len(train)/2) <= 1
    assert abs(val["label"].sum() - len(val)/2) <= 1
    assert abs(test["label"].sum() - len(test)/2) <= 1

def test_dataset_statistics():
    stats = DatasetStatistics()
    df = pd.DataFrame({
        "url": ["https://google.com", "https://yahoo.com/path", "https://xyz.xyz"],
        "label": [0, 0, 1]
    })
    
    summary = stats.summary(df, name="test")
    assert summary["name"] == "test"
    assert summary["total_rows"] == 3
    assert summary["duplicate_count"] == 0
    assert "top_tlds" in summary
    assert "url_length_stats" in summary
