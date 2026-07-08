"""Unit tests for threat intelligence connectors and aggregator."""
from unittest.mock import patch, MagicMock
from src.intelligence.base_connector import IntelligenceResult
from src.intelligence.virustotal import VirusTotalConnector
from src.intelligence.whois_connector import WhoisConnector
from src.intelligence.dns_connector import DNSConnector
from src.intelligence.ssl_connector import SSLConnector
from src.intelligence.geoip_connector import GeoIPConnector
from src.intelligence.aggregator import IntelligenceAggregator

def test_virustotal_connector_no_key():
    with patch("src.config.settings.get_settings") as mock_settings:
        mock_settings.return_value.api.virustotal_api_key = None
        conn = VirusTotalConnector()
        res = conn.query("example.com")
        assert isinstance(res, IntelligenceResult)
        assert res.success is False
        assert "API key" in res.error_message

def test_whois_connector_exception():
    with patch("whois.whois", side_effect=Exception("WHOIS error")):
        conn = WhoisConnector()
        res = conn.query("example.com")
        assert res.success is False
        assert "WHOIS error" in res.error_message

def test_dns_connector_nxdomain():
    # dnspython library can raise exceptions on missing domains
    with patch("dns.resolver.resolve", side_effect=Exception("NoAnswer")):
        conn = DNSConnector()
        res = conn.query("nonexistent.xyz")
        assert res.success is True  # We capture records and flag SPF/DMARC as False
        assert res.data["has_spf"] is False
        assert res.data["has_dmarc"] is False
        assert res.data["record_count"] == 0

def test_ssl_connector_valid():
    # Mock Try 1 success
    mock_cert = {
        "subject": ((("commonName", "example.com"),),),
        "issuer": ((("commonName", "DigiCert"),),),
        "notAfter": "Jan 01 12:00:00 2030 UTC",
    }
    with patch.object(SSLConnector, "_fetch_certificate", return_value=(mock_cert, b"raw_der", "TLSv1.3", 2, "VALID")), \
         patch("src.utils.helpers.safe_request", return_value=None):
        conn = SSLConnector()
        res = conn.query("example.com")
        assert res.success is True
        assert res.data["ssl_status"] == "VALID"
        assert res.data["has_ssl"] is True

def test_ssl_connector_expired():
    # Mock Try 1 verify failed, Try 2 returns expired cert
    mock_cert = {
        "subject": ((("commonName", "example.com"),),),
        "issuer": ((("commonName", "DigiCert"),),),
        "notAfter": "Jan 01 12:00:00 2020 UTC",  # Expired
    }
    with patch.object(SSLConnector, "_fetch_certificate", return_value=(mock_cert, b"raw_der", "TLSv1.3", 1, "INVALID")), \
         patch("src.utils.helpers.safe_request", return_value=None):
        conn = SSLConnector()
        res = conn.query("example.com")
        assert res.success is True
        assert res.data["ssl_status"] == "INVALID"
        assert res.data["is_expired"] is True

def test_ssl_connector_self_signed():
    # Mock self-signed (issuer == subject)
    mock_cert = {
        "subject": ((("commonName", "Self Signed"),),),
        "issuer": ((("commonName", "Self Signed"),),),
    }
    with patch.object(SSLConnector, "_fetch_certificate", return_value=(mock_cert, b"raw_der", "TLSv1.3", 1, "INVALID")), \
         patch("src.utils.helpers.safe_request", return_value=None):
        conn = SSLConnector()
        res = conn.query("example.com")
        assert res.success is True
        assert res.data["ssl_status"] == "INVALID"
        assert res.data["is_self_signed"] is True

def test_ssl_connector_timeout():
    import socket
    with patch("socket.socket.connect", side_effect=socket.timeout("timeout")):
        conn = SSLConnector()
        res = conn.query("example.com")
        assert res.success is False
        assert res.data["ssl_status"] == "UNKNOWN"
        assert res.data["has_ssl"] == "unknown"

def test_ssl_connector_dns_failure():
    import socket
    with patch("socket.socket.connect", side_effect=socket.gaierror(-2, "Name or service not known")):
        conn = SSLConnector()
        res = conn.query("nonexistent.example.com")
        assert res.success is False
        assert res.data["ssl_status"] == "UNKNOWN"
        assert res.data["has_ssl"] == "unknown"

def test_geoip_connector_fallback():
    # Mock socket resolution and free geolocation api fallback
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "success",
        "country": "United States",
        "countryCode": "US",
        "city": "Chicago",
        "lat": 41.85,
        "lon": -87.65,
        "as": "AS15169 Google LLC"
    }
    
    with patch("socket.gethostbyname", return_value="8.8.8.8"), \
         patch("src.intelligence.geoip_connector.safe_request", return_value=mock_response):
        conn = GeoIPConnector()
        res = conn.query("google.com")
        assert res.success is True
        assert res.data["country"] == "United States"
        assert res.data["country_code"] == "US"
        assert res.data["city"] == "Chicago"

def test_intelligence_aggregator():
    # Mock all connectors inside aggregator
    m_vt = MagicMock()
    m_vt.name = "virustotal"
    m_vt.query.return_value = IntelligenceResult("virustotal", "example.com", {"positives": 0}, True)
    
    m_whois = MagicMock()
    m_whois.name = "whois"
    m_whois.query.return_value = IntelligenceResult("whois", "example.com", {"domain_age_days": 100}, True)
    
    agg = IntelligenceAggregator(connectors=[m_vt, m_whois])
    res = agg.gather("example.com")
    
    assert "virustotal" in res
    assert "whois" in res
    assert res["virustotal"].success is True
    assert res["whois"].data["domain_age_days"] == 100
    
    # Flattened dict check
    flat = agg.gather_dict("example.com")
    assert flat["virustotal_success"] is True
    assert flat["virustotal_positives"] == 0
    assert flat["whois_domain_age_days"] == 100
