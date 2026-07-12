"""Unit tests for URLParser."""
import pytest
from src.parser.url_parser import URLParser, ParsedURL
from src.utils.exceptions import URLParsingError

def test_url_parser_standard():
    parser = URLParser()
    res = parser.parse("https://sub.domain.example.co.uk:8080/path/to/file.html?q=1&verify=true#anchor")
    
    assert isinstance(res, ParsedURL)
    assert res.scheme == "https"
    assert res.hostname == "sub.domain.example.co.uk"
    assert res.registered_domain == "example.co.uk"
    assert res.domain == "example"
    assert res.subdomain == "sub.domain"
    assert res.suffix == "co.uk"
    assert res.port == 8080
    assert res.has_port is True
    
    assert res.path == "/path/to/file.html"
    assert res.path_segments == ["path", "to", "file.html"]
    assert res.path_segment_count == 3
    assert res.directory_depth == 2
    assert res.filename == "file.html"
    assert res.file_extension == "html"
    
    assert res.query == "q=1&verify=true"
    assert res.has_query is True
    assert res.query_param_count == 2
    assert "q" in res.query_params
    assert "verify" in res.query_params
    
    assert res.fragment == "anchor"
    assert res.has_fragment is True

def test_url_parser_empty():
    parser = URLParser()
    with pytest.raises(URLParsingError):
        parser.parse("")

def test_url_parser_ip_based():
    parser = URLParser()
    res = parser.parse("http://192.168.1.1/index.php")
    assert res.is_ip_based is True
    assert res.hostname == "192.168.1.1"
    assert res.domain == "192.168.1.1"
    assert res.registered_domain == ""

def test_url_parser_tokenization():
    parser = URLParser()
    res = parser.parse("https://paypal-login-security.xyz/verify")
    # Tokens split by non-alphanumeric chars
    assert "paypal" in res.url_tokens
    assert "login" in res.url_tokens
    assert "security" in res.url_tokens
    assert "xyz" in res.url_tokens
    assert "verify" in res.url_tokens
