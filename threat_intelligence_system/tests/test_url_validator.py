"""Unit tests for URLValidator."""
from src.parser.url_validator import URLValidator, ValidationResult

def test_url_validator_valid():
    validator = URLValidator()
    res = validator.validate("https://www.google.com")
    assert res.is_valid is True
    assert res.has_scheme is True
    assert res.scheme == "https"
    assert res.is_https is True
    assert res.is_http is False
    assert res.is_ip_address is False

def test_url_validator_empty():
    validator = URLValidator()
    res = validator.validate("")
    assert res.is_valid is False
    assert res.is_malformed is True
    assert "empty" in res.validation_errors[0]

def test_url_validator_ip_address():
    validator = URLValidator()
    res = validator.validate("http://192.168.1.1/admin")
    assert res.is_valid is True
    assert res.is_ip_address is True
    assert res.is_ipv4 is True
    assert res.is_ipv6 is False

def test_url_validator_ipv6():
    validator = URLValidator()
    # IPv6 format in URLs is bracket-enclosed
    res = validator.validate("http://[2001:db8::1]/index.html")
    assert res.is_valid is True
    assert res.is_ip_address is True
    assert res.is_ipv6 is True
    assert res.is_ipv4 is False

def test_url_validator_punycode():
    validator = URLValidator()
    res = validator.validate("https://xn--80ak6aa92e.com")
    assert res.is_valid is True
    assert res.is_punycode is True

def test_url_validator_shortener():
    validator = URLValidator()
    res = validator.validate("https://bit.ly/abc123")
    assert res.is_valid is True
    assert res.is_url_shortener is True

def test_url_validator_data_uri():
    validator = URLValidator()
    res = validator.validate("data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==")
    assert res.is_valid is False
    assert res.is_data_uri is True
    assert "data URI" in res.validation_errors[0]

def test_url_validator_malformed():
    validator = URLValidator()
    res = validator.validate("https://example.com/path with spaces")
    assert res.is_valid is False
    assert res.is_malformed is True

def test_url_validator_consecutive_dots():
    validator = URLValidator()
    res = validator.validate("https://example..com/index.html")
    assert res.is_valid is False
    assert res.is_malformed is True
    assert any("dots" in err for err in res.validation_errors)
