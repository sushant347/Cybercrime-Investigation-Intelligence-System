"""Shared conftest fixtures for Pytest."""
import pytest
from src.parser.url_parser import URLParser, ParsedURL
from src.feature_engineering.pipeline import FeaturePipeline

@pytest.fixture
def sample_urls() -> dict[str, str]:
    """Provide a dictionary of typical test URLs."""
    return {
        "legitimate": "https://www.google.com/search?q=test",
        "phishing": "https://paypal-login-security.xyz/login",
        "ip_based": "http://192.168.1.1/admin",
        "punycode": "https://xn--80ak6aa92e.com",
        "shortener": "https://bit.ly/abc123",
        "no_https": "http://example.com",
    }

@pytest.fixture
def sample_parsed_url() -> ParsedURL:
    """Provide a sample ParsedURL instance."""
    parser = URLParser()
    return parser.parse("https://paypal-login-security.xyz/login?verify=true")

@pytest.fixture
def feature_pipeline() -> FeaturePipeline:
    """Provide a FeaturePipeline instance."""
    return FeaturePipeline()

@pytest.fixture
def sample_features(feature_pipeline, sample_urls) -> dict:
    """Provide feature extraction results for testing."""
    return feature_pipeline.extract(sample_urls["phishing"])
