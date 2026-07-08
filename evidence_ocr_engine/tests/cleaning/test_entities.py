"""Tests for regex patterns, entity preservation and entity extraction."""

from __future__ import annotations

import pytest

from backend.modules.evidence.cleaning.entity_extractor import EntityExtractor
from backend.modules.evidence.cleaning.entity_preserver import EntityPreserver


@pytest.fixture()
def extractor() -> EntityExtractor:
    return EntityExtractor()


def _values(entities, key):
    return [e.value for e in entities[key]]


def _normalized(entities, key):
    return [e.normalized for e in entities[key]]


# ---------------------------------------------------------------- preservation


def test_protect_and_restore_roundtrip() -> None:
    preserver = EntityPreserver()
    text = "Verify at https://Scam.Example/Login or mail Help@Bank.com, call +977-9812345678."
    protected = preserver.protect(text)
    assert "https://Scam.Example/Login" not in protected.text  # shielded
    assert protected.placeholder_count() == 3
    restored = preserver.restore(protected.text, protected)
    assert restored == text  # byte-for-byte restoration


def test_entities_survive_lowercasing_between_protect_and_restore() -> None:
    preserver = EntityPreserver()
    text = "esewa ma paisa pathaunus: https://PAY.Example/XYZ"
    protected = preserver.protect(text)
    mangled = protected.text.lower()  # cleaning may lowercase Roman Nepali
    restored = preserver.restore(mangled, protected)
    assert "https://PAY.Example/XYZ" in restored  # entity case untouched


def test_overlapping_matches_prefer_longest_span() -> None:
    preserver = EntityPreserver()
    protected = preserver.protect("see http://a.example.com/page")
    types = {e.entity_type for e in protected.vault.values()}
    assert types == {"url"}  # domain inside the URL is not double-protected


# ------------------------------------------------------------------ extraction


def test_urls_domains_emails(extractor: EntityExtractor) -> None:
    text = ("Visit https://Verify-Bank.Example/login?id=AbC and www.scam.top "
            "or write to Support@Fake-Bank.COM about fake-bank.com")
    entities = extractor.extract(text)
    assert "https://verify-bank.example/login?id=AbC" in _normalized(entities, "urls")
    assert "www.scam.top" in _normalized(entities, "urls")
    assert _normalized(entities, "emails") == ["support@fake-bank.com"]
    domains = _normalized(entities, "domains")
    assert "fake-bank.com" in domains and "www.scam.top" in domains


def test_ip_mac_port_cve(extractor: EntityExtractor) -> None:
    text = ("Attack from 192.168.1.77 and 2001:db8::ff00:42:8329, "
            "device AA-BB-CC-DD-EE-FF on port 8080, exploit CVE-2024-12345. "
            "Not an IP: 999.999.1.1")
    entities = extractor.extract(text)
    assert _values(entities, "ipv4") == ["192.168.1.77"]
    assert _values(entities, "ipv6") == ["2001:db8::ff00:42:8329"]
    assert _normalized(entities, "mac_addresses") == ["aa:bb:cc:dd:ee:ff"]
    assert "8080" in _values(entities, "ports")
    assert _normalized(entities, "cve_ids") == ["CVE-2024-12345"]


def test_phone_normalization(extractor: EntityExtractor) -> None:
    text = "Call 9812345678 or +977 9861112223 immediately"
    entities = extractor.extract(text)
    normalized = _normalized(entities, "phones")
    assert "+9779812345678" in normalized
    assert "+9779861112223" in normalized


def test_dates_times_money_otp(extractor: EntityExtractor) -> None:
    text = ("On 2026-01-04 at 09:15 PM you must pay Rs 2,000 or NPR 500.50. "
            "Your OTP code 4521 expires. Also $99 due Jan 5, 2026.")
    entities = extractor.extract(text)
    assert "2026-01-04" in _values(entities, "dates")
    assert any("Jan 5, 2026" in v for v in _values(entities, "dates"))
    assert any(v.startswith("09:15") for v in _values(entities, "times"))
    money = _values(entities, "money")
    assert "Rs 2,000" in money and "NPR 500.50" in money and "$99" in money
    assert _values(entities, "otp") == ["4521"]


def test_bank_account_and_wallets(extractor: EntityExtractor) -> None:
    text = ("Transfer to a/c no. 0071-2345-9912-33. "
            "Esewa id ma paisa pathaunus 9812345678. "
            "Khalti: 9861112223, IME Pay number 9807654321")
    entities = extractor.extract(text)
    assert _normalized(entities, "bank_accounts") == ["0071234599123 3".replace(" ", "")]
    assert _normalized(entities, "esewa_ids") == ["+9779812345678"]
    assert _normalized(entities, "khalti_ids") == ["+9779861112223"]
    assert _normalized(entities, "imepay_ids") == ["+9779807654321"]


def test_hashes_classified_by_length(extractor: EntityExtractor) -> None:
    md5 = "d41d8cd98f00b204e9800998ecf8427e"
    sha1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    entities = extractor.extract(f"files: {md5} {sha1} {sha256}")
    assert _values(entities, "hashes_md5") == [md5]
    assert _values(entities, "hashes_sha1") == [sha1]
    assert _values(entities, "hashes_sha256") == [sha256]


def test_crypto_wallets(extractor: EntityExtractor) -> None:
    btc = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    eth = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    entities = extractor.extract(f"pay {btc} or {eth}")
    assert _values(entities, "btc_wallets") == [btc]
    assert _values(entities, "eth_wallets") == [eth]


def test_social_media_entities(extractor: EntityExtractor) -> None:
    text = ("Join t.me/nepal_prize or message @scam_helper, "
            "wa.me/9779812345678, facebook.com/fake.support.np, "
            "https://instagram.com/free_gift_np")
    entities = extractor.extract(text)
    assert "nepal_prize" in _normalized(entities, "telegram_usernames")
    assert "scam_helper" in _normalized(entities, "telegram_usernames")
    assert "+9779812345678" in _normalized(entities, "whatsapp_numbers")
    assert "fake.support.np" in _normalized(entities, "facebook_usernames")
    assert "free_gift_np" in _normalized(entities, "instagram_usernames")


def test_deduplication(extractor: EntityExtractor) -> None:
    text = "http://scam.top http://SCAM.top http://scam.top"
    assert len(extractor.extract(text)["urls"]) == 1


def test_stable_schema_all_keys_present(extractor: EntityExtractor) -> None:
    entities = extractor.extract("nothing interesting here")
    for key in ("urls", "emails", "domains", "ipv4", "ipv6", "phones", "dates",
                "times", "money", "otp", "bank_accounts", "esewa_ids",
                "khalti_ids", "imepay_ids", "hashes_md5", "hashes_sha1",
                "hashes_sha256", "hashes_sha512", "mac_addresses", "ports",
                "cve_ids", "btc_wallets", "eth_wallets", "social_media_urls",
                "telegram_usernames", "whatsapp_numbers", "facebook_usernames",
                "instagram_usernames"):
        assert key in entities
        assert entities[key] == []
