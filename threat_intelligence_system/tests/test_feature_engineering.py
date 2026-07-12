"""Unit tests for feature engineering extractors and pipeline."""
import pandas as pd
from src.feature_engineering.length_features import LengthFeatureExtractor
from src.feature_engineering.entropy_features import EntropyFeatureExtractor
from src.feature_engineering.character_features import CharacterFeatureExtractor
from src.feature_engineering.structural_features import StructuralFeatureExtractor
from src.feature_engineering.lexical_features import LexicalFeatureExtractor
from src.feature_engineering.brand_features import BrandFeatureExtractor
from src.feature_engineering.security_features import SecurityFeatureExtractor
from src.feature_engineering.tld_features import TLDFeatureExtractor
from src.feature_engineering.pipeline import FeaturePipeline

def test_length_extractor(sample_parsed_url):
    ext = LengthFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert features["url_length"] > 0
    assert features["hostname_length"] > 0
    assert "domain_length" in features

def test_entropy_extractor(sample_parsed_url):
    ext = EntropyFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "url_entropy" in features
    assert "hostname_entropy" in features
    assert features["url_entropy"] > 0

def test_character_extractor(sample_parsed_url):
    ext = CharacterFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "dot_count" in features
    assert "slash_count" in features
    assert "letter_count" in features

def test_structural_extractor(sample_parsed_url):
    ext = StructuralFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "directory_depth" in features
    assert "has_query" in features

def test_lexical_extractor(sample_parsed_url):
    ext = LexicalFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "contains_suspicious_keyword" in features
    assert "suspicious_keyword_count" in features

def test_brand_extractor(sample_parsed_url):
    ext = BrandFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "brand_in_domain" in features
    assert "closest_brand" in features
    assert features["closest_brand"] == "paypal"
    # Should flag typosquatting or brand in domain since hostname is 'paypal-login-security.xyz'
    assert features["brand_in_domain"] == 1

def test_security_extractor(sample_parsed_url):
    ext = SecurityFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "is_https" in features
    assert "is_ip_based" in features

def test_tld_extractor(sample_parsed_url):
    ext = TLDFeatureExtractor()
    features = ext.extract(sample_parsed_url)
    assert "is_suspicious_tld" in features
    assert "tld_risk_score" in features
    # xyz is suspicious in default settings
    assert features["is_suspicious_tld"] == 1

def test_feature_pipeline(feature_pipeline, sample_urls):
    # Single URL
    features = feature_pipeline.extract(sample_urls["phishing"])
    assert len(features) >= 72
    assert features["is_https"] == 1
    assert features["closest_brand"] == "paypal"
    
    # Feature Names
    names = feature_pipeline.get_feature_names()
    assert len(names) == 71
    assert "url_length" in names
    
    # Batch extraction
    urls = [sample_urls["legitimate"], sample_urls["phishing"]]
    batch_res = feature_pipeline.extract_batch(urls)
    assert len(batch_res) == 2
    assert batch_res[0]["is_https"] == 1
    
    # DataFrame extraction
    df = feature_pipeline.get_feature_dataframe(urls)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "url" in df.columns
    assert "url_length" in df.columns
