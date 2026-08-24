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


# ------------------------------------------------- receipt / statement layout
#
# Every case in this system is built on screenshots and PDF slips, where the
# label and its value sit on *separate lines*. These tests pin that layout,
# because the same-line-only patterns silently produced zero wallet ids,
# account numbers and transaction codes from exactly this evidence.


def test_wallet_id_on_the_line_below_its_label(extractor: EntityExtractor) -> None:
    text = (
        "Khalti\nPayment Receipt\nSent To (Khalti ID)\n9801122334\n"
        "Sender (Khalti ID)\n9847011223\n"
    )
    assert _normalized(extractor.extract(text), "khalti_ids") == [
        "+9779801122334", "+9779847011223",
    ]


def test_wallet_id_may_be_an_email(extractor: EntityExtractor) -> None:
    """eSewa/Khalti accept an email as the account id; the phone normaliser
    used to strip it to a meaningless digit fragment."""
    text = "From eSewa ID\nsunita.gurung21@gmail.com\n"
    assert _normalized(extractor.extract(text), "esewa_ids") == [
        "sunita.gurung21@gmail.com",
    ]


def test_bank_account_with_no_colon_label(extractor: EntityExtractor) -> None:
    text = "Depositor Account No.:\n0501-0198765432\n"
    assert _normalized(extractor.extract(text), "bank_accounts") == ["05010198765432"]


def test_transaction_codes_labelled_and_structural(extractor: EntityExtractor) -> None:
    text = (
        "Transaction Code\nKH-2026-0611-77245\n"
        "Voucher No.:\nMBL-2026-441829\n"
        "TansatianD\n0119.0625.987456\n"          # OCR-mangled label, intact code
        "Ref: DSN2026\n"
    )
    found = _normalized(extractor.extract(text), "transaction_ids")
    for code in ("KH-2026-0611-77245", "MBL-2026-441829", "0119.0625.987456",
                 "DSN2026"):
        assert code in found


def test_amounts_are_not_transaction_codes(extractor: EntityExtractor) -> None:
    assert extractor.extract("Payment 1,500.00\nAmount Rs. 2,000") \
        ["transaction_ids"] == []


# --------------------------------------------------------- false-positive gate


def test_card_number_requires_issuer_prefix_and_luhn(extractor: EntityExtractor) -> None:
    text = (
        "Card 4111 1111 1111 1111\n"      # real Visa test PAN, Luhn-valid
        "0000000000000000\n"              # OCR zero-run: Luhn-valid, not a card
        "9779801122334\n"                 # phone digits
    )
    assert _normalized(extractor.extract(text), "card_numbers") == [
        "4111111111111111",
    ]


def test_clock_time_is_not_a_port(extractor: EntityExtractor) -> None:
    entities = extractor.extract("Date & Time\n2026-06-11 10:42 AM, 11:15 AM")
    assert entities["ports"] == []
    assert _values(entities, "ports") == []


def test_host_port_is_still_a_port(extractor: EntityExtractor) -> None:
    entities = extractor.extract("connect to scam-panel.top:8443 and port 22")
    assert set(_normalized(entities, "ports")) == {"8443", "22"}


def test_ocr_zero_runs_are_not_phone_numbers(extractor: EntityExtractor) -> None:
    entities = extractor.extract("00000001 00 00000 2 0000000 और 9847011223")
    assert _normalized(entities, "phones") == ["+9779847011223"]


def test_cve_id_is_not_also_a_transaction_code(extractor: EntityExtractor) -> None:
    """A vulnerability id has the shape of the structural transaction code.

    ``CVE-2024-3400`` matches ``[A-Z]{2,5}-\\d{2,4}(-\\d{2,6}){1,3}`` exactly, so
    it was filed as both. Transaction ids correlate at 0.95 and cve_ids not at
    all, so two reports mentioning the same vulnerability linked as though they
    shared a receipt number.
    """
    entities = extractor.extract(
        "Exploited CVE-2024-3400 on the gateway; voucher ESW-2026-0714-88231."
    )
    assert _normalized(entities, "cve_ids") == ["CVE-2024-3400"]
    # The genuine code in the same sentence is untouched.
    assert _normalized(entities, "transaction_ids") == ["ESW-2026-0714-88231"]


def test_time_value_carries_no_trailing_space(extractor: EntityExtractor) -> None:
    """The TIME pattern ends in an optional ``\\s?(?:AM|PM)?``.

    With no meridiem present the space before it stayed in the value, so the
    same clock time written twice in one document de-duplicated as two
    entities - "14:22 " and "14:22".
    """
    entities = extractor.extract("Call at 14:22 or 14:22, ended 09:15.")
    assert _values(entities, "times") == ["14:22", "09:15"]
    # A meridiem is part of the time and is kept.
    assert _values(extractor.extract("Paid 9:30 PM sharp"), "times") == ["9:30 PM"]
