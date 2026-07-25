"""Structured forensic entity extraction from cleaned text.

Runs on ``cleaned_text`` (after entity restoration) and produces validated,
de-duplicated, normalised entities grouped by type. Extraction never alters
the text - values are copied out, with a separate ``normalized`` form where
normalisation is meaningful (URLs, emails, phone numbers).
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

from . import regex_patterns as rx

_TRAILING_PUNCT = ".,;:!?)]}'\"।"


@dataclass(frozen=True)
class ExtractedEntity:
    """One validated entity occurrence."""

    entity_type: str
    value: str        # exactly as present in the text
    normalized: str   # canonical form used for de-duplication / correlation


#: Every entity type the extractor can produce, grouped the way an
#: investigator reads them. This is the *schema*: :meth:`EntityExtractor.extract`
#: returns a key for each of these types on every call, empty list included, so
#: downstream consumers (analytics, UI) can distinguish "searched for and not
#: found" from "never looked for".
ENTITY_TYPE_GROUPS: Dict[str, tuple] = {
    "network": ("urls", "domains", "ipv4", "ipv6", "mac_addresses", "ports",
                "cve_ids"),
    "contact": ("emails", "phones"),
    "temporal": ("dates", "times"),
    "financial": ("money", "bank_accounts", "card_numbers", "transaction_ids",
                  "esewa_ids", "khalti_ids", "imepay_ids", "otp"),
    "crypto": ("eth_wallets", "btc_wallets", "hashes_md5", "hashes_sha1",
               "hashes_sha256", "hashes_sha512"),
    "social": ("social_media_urls", "telegram_usernames", "whatsapp_numbers",
               "facebook_usernames", "instagram_usernames"),
}

#: Flat tuple of every supported entity type (stable order).
SUPPORTED_ENTITY_TYPES: tuple = tuple(
    entity_type
    for group in ENTITY_TYPE_GROUPS.values()
    for entity_type in group
)

#: Entity types that identify a payment instrument or rail. Analytics
#: aggregates these into the "Payment & Wallet IDs" view; keeping the list here
#: means adding a new rail updates every consumer at once.
PAYMENT_ENTITY_TYPES: tuple = (
    "esewa_ids", "khalti_ids", "imepay_ids", "bank_accounts", "card_numbers",
    "eth_wallets", "btc_wallets",
)


class EntityExtractor:
    """Regex-driven extractor with per-type validation and normalisation."""

    def extract(self, text: str) -> Dict[str, List[ExtractedEntity]]:
        """Extract every supported entity type from ``text``.

        Returns:
            Mapping of entity-type name to de-duplicated entity list. Types
            with no matches are present with empty lists (stable schema).
        """
        results: Dict[str, List[ExtractedEntity]] = {}

        urls = self._collect(text, rx.URL, "urls", normalize=self._normalize_url)
        emails = self._collect(text, rx.EMAIL, "emails", normalize=str.lower)
        results["urls"] = urls
        results["emails"] = emails
        results["domains"] = self._domains(text, urls, emails)

        results["ipv4"] = self._collect(text, rx.IPV4, "ipv4")
        results["ipv6"] = self._collect(
            text, rx.IPV6, "ipv6", validate=self._valid_ipv6
        )
        results["mac_addresses"] = self._collect(
            text, rx.MAC_ADDRESS, "mac_addresses", normalize=self._normalize_mac
        )
        results["ports"] = self._group_matches(text, rx.PORT, "ports",
                                               validate=self._valid_port)
        results["cve_ids"] = self._collect(text, rx.CVE, "cve_ids",
                                           normalize=str.upper)

        results["phones"] = self._collect(
            text, rx.PHONE, "phones", normalize=self._normalize_phone,
            validate=self._valid_phone,
        )
        results["dates"] = self._collect(text, rx.DATE, "dates")
        results["times"] = self._collect(text, rx.TIME, "times")

        results["money"] = self._collect(
            text, rx.MONEY, "money", normalize=self._normalize_money
        )
        results["otp"] = self._group_matches(text, rx.OTP, "otp")
        results["bank_accounts"] = self._group_matches(
            text, rx.BANK_ACCOUNT, "bank_accounts",
            normalize=lambda v: re.sub(r"[\s-]", "", v),
        )
        results["card_numbers"] = self._collect(
            text, rx.CARD_NUMBER, "card_numbers",
            normalize=lambda v: re.sub(r"[\s-]", "", v),
            validate=self._valid_card,
        )
        results["transaction_ids"] = self._group_matches(
            text, rx.TRANSACTION_ID, "transaction_ids",
            normalize=str.upper, validate=self._valid_transaction_id,
        )
        results["esewa_ids"] = self._group_matches(
            text, rx.ESEWA_ID, "esewa_ids", normalize=self._normalize_wallet_id
        )
        results["khalti_ids"] = self._group_matches(
            text, rx.KHALTI_ID, "khalti_ids", normalize=self._normalize_wallet_id
        )
        results["imepay_ids"] = self._group_matches(
            text, rx.IMEPAY_ID, "imepay_ids", normalize=self._normalize_wallet_id
        )

        results["hashes_sha512"] = self._collect(text, rx.SHA512, "hashes_sha512",
                                                 normalize=str.lower)
        sha512_values = {e.normalized for e in results["hashes_sha512"]}
        results["hashes_sha256"] = [
            e for e in self._collect(text, rx.SHA256, "hashes_sha256", normalize=str.lower)
            if not any(e.normalized in v for v in sha512_values)
        ]
        longer = sha512_values | {e.normalized for e in results["hashes_sha256"]}
        results["hashes_sha1"] = [
            e for e in self._collect(text, rx.SHA1, "hashes_sha1", normalize=str.lower)
            if not any(e.normalized in v for v in longer)
        ]
        longer |= {e.normalized for e in results["hashes_sha1"]}
        results["hashes_md5"] = [
            e for e in self._collect(text, rx.MD5, "hashes_md5", normalize=str.lower)
            if not any(e.normalized in v for v in longer)
        ]

        eth = self._collect(text, rx.ETH_WALLET, "eth_wallets", normalize=str.lower)
        results["eth_wallets"] = eth
        eth_values = {e.value for e in eth}
        results["btc_wallets"] = [
            e for e in self._collect(text, rx.BTC_WALLET, "btc_wallets")
            if e.value not in eth_values
        ]

        results["social_media_urls"] = self._collect(
            text, rx.SOCIAL_MEDIA_URL, "social_media_urls",
            normalize=self._normalize_url,
        )
        results["telegram_usernames"] = self._group_matches(
            text, rx.TELEGRAM_USERNAME, "telegram_usernames", normalize=str.lower
        )
        results["whatsapp_numbers"] = self._group_matches(
            text, rx.WHATSAPP_NUMBER, "whatsapp_numbers",
            normalize=self._normalize_phone,
        )
        results["facebook_usernames"] = self._group_matches(
            text, rx.FACEBOOK_USERNAME, "facebook_usernames", normalize=str.lower
        )
        results["instagram_usernames"] = self._group_matches(
            text, rx.INSTAGRAM_USERNAME, "instagram_usernames", normalize=str.lower
        )
        # Stable schema: every supported type is present, empty or not, and in
        # the documented order.
        return {
            entity_type: results.get(entity_type, [])
            for entity_type in SUPPORTED_ENTITY_TYPES
        }

    @staticmethod
    def total_count(entities: Dict[str, List[ExtractedEntity]]) -> int:
        return sum(len(items) for items in entities.values())

    # -------------------------------------------------------------- collection

    def _collect(
        self,
        text: str,
        pattern: re.Pattern[str],
        entity_type: str,
        normalize: Optional[Callable[[str], str]] = None,
        validate: Optional[Callable[[str], bool]] = None,
    ) -> List[ExtractedEntity]:
        """Full-match collection with trim, validation and de-duplication."""
        seen: Set[str] = set()
        entities: List[ExtractedEntity] = []
        for match in pattern.finditer(text):
            value = match.group(0).rstrip(_TRAILING_PUNCT)
            if not value or (validate and not validate(value)):
                continue
            normalized = normalize(value) if normalize else value
            if normalized in seen:
                continue
            seen.add(normalized)
            entities.append(ExtractedEntity(entity_type, value, normalized))
        return entities

    def _group_matches(
        self,
        text: str,
        pattern: re.Pattern[str],
        entity_type: str,
        normalize: Optional[Callable[[str], str]] = None,
        validate: Optional[Callable[[str], bool]] = None,
    ) -> List[ExtractedEntity]:
        """Collection for context patterns whose value is a capture group."""
        seen: Set[str] = set()
        entities: List[ExtractedEntity] = []
        for match in pattern.finditer(text):
            value = next((g for g in match.groups() if g), None)
            if value is None:
                continue
            value = value.strip().rstrip(_TRAILING_PUNCT)
            if not value or (validate and not validate(value)):
                continue
            normalized = normalize(value) if normalize else value
            if normalized in seen:
                continue
            seen.add(normalized)
            entities.append(ExtractedEntity(entity_type, value, normalized))
        return entities

    # ------------------------------------------------------------- validation

    @staticmethod
    def _valid_ipv6(value: str) -> bool:
        if ":" not in value or value.count(":") < 2:
            return False
        try:
            ipaddress.IPv6Address(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _valid_port(value: str) -> bool:
        return value.isdigit() and 1 <= int(value) <= 65535

    @staticmethod
    def _valid_card(value: str) -> bool:
        """Issuer prefix + length + Luhn - all three, in that order.

        Luhn alone is far too weak on OCR output: a run of zeros satisfies it
        (checksum 0), and so does roughly one digit string in ten, so a phone
        number, a voucher number or a garbled digit block would be recorded as
        a payment card. Requiring a real issuer identification number (IIN)
        and that issuer's card length first is what makes the finding
        defensible - in a forensic record an invented card number is far worse
        than a missed one.
        """
        digits = re.sub(r"[^\d]", "", value)
        if not 13 <= len(digits) <= 19:
            return False
        if len(set(digits)) < 2:          # a single repeated digit is OCR noise
            return False
        length, prefix2, prefix4 = len(digits), int(digits[:2]), int(digits[:4])
        issuer_ok = (
            (digits[0] == "4" and length in (13, 16, 19))                # Visa
            or (51 <= prefix2 <= 55 and length == 16)                    # MC
            or (2221 <= prefix4 <= 2720 and length == 16)                # MC 2-series
            or (prefix2 in (34, 37) and length == 15)                    # Amex
            or (prefix4 == 6011 and length == 16)                        # Discover
            or (prefix2 == 65 and length == 16)                          # Discover
            or (prefix2 == 62 and 16 <= length <= 19)                    # UnionPay
            or (prefix2 == 35 and length == 16)                          # JCB
            or (prefix2 in (36, 38) and length == 14)                    # Diners
        )
        if not issuer_ok:
            return False
        total = 0
        for index, char in enumerate(reversed(digits)):
            digit = int(char)
            if index % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0

    @staticmethod
    def _valid_phone(value: str) -> bool:
        """Reject OCR noise blocks ("00000001", "999999999") as phone numbers.

        The landline alternative of :data:`~.regex_patterns.PHONE` starts at a
        literal ``0``, which is exactly the shape of the zero-runs PaddleOCR
        emits for unreadable Devanagari, so a chat screenshot produced a dozen
        phantom "phone numbers" per item.
        """
        digits = re.sub(r"[^\d]", "", value)
        return len(set(digits)) >= 3

    @staticmethod
    def _valid_transaction_id(value: str) -> bool:
        """A transaction code carries at least one digit and one more char.

        The label alternative of :data:`~.regex_patterns.TRANSACTION_ID` would
        otherwise capture the next ordinary word after "reference" or "order".
        """
        candidate = value.strip()
        if len(candidate) < 5 or not any(c.isdigit() for c in candidate):
            return False
        # Reject amounts ("1,500.00", "2,000") - a money value that happens to
        # follow the word "payment" is not a transaction code. The dotted
        # eSewa form ("0119.0625.987456") has two separators and survives.
        if re.fullmatch(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?", candidate):
            return False
        return not re.fullmatch(r"\d+\.\d+", candidate)

    # ---------------------------------------------------------- normalisation

    @staticmethod
    def _normalize_url(value: str) -> str:
        """Lowercase scheme+host; preserve path/query case (may be case-
        sensitive on the server). Adds no scheme - the value is evidence."""
        url = value.strip()
        match = re.match(r"^(https?://)?([^/]+)(.*)$", url, re.IGNORECASE)
        if not match:
            return url.lower()
        scheme = (match.group(1) or "").lower()
        host = match.group(2).lower()
        return f"{scheme}{host}{match.group(3)}"

    @staticmethod
    def _normalize_phone(value: str) -> str:
        """Digits-only canonical form; Nepali mobiles get the +977 prefix."""
        digits = re.sub(r"[^\d+]", "", value)
        digits = "+" + digits.lstrip("+") if value.strip().startswith("+") else digits
        bare = digits.lstrip("+")
        if re.fullmatch(r"9[678]\d{8}", bare):
            return f"+977{bare}"
        if bare.startswith("977") and len(bare) == 13:
            return f"+{bare}"
        return digits

    @classmethod
    def _normalize_wallet_id(cls, value: str) -> str:
        """Wallet ids are a mobile number *or* an email; normalise either.

        eSewa/Khalti/IME Pay all accept an email address as the account
        identifier, so running every wallet id through the phone normaliser
        (which strips non-digits) turned ``user@gmail.com`` into ``21`` and
        silently corrupted the record.
        """
        candidate = value.strip()
        if "@" in candidate:
            return candidate.lower()
        return cls._normalize_phone(candidate)

    @staticmethod
    def _normalize_mac(value: str) -> str:
        return value.lower().replace("-", ":")

    #: Currency markers (prefix or suffix, case-insensitive) -> canonical
    #: 3-letter code. "Rs"/"रु"/"rupees"/"rupaiya" are the same Nepali-rupee
    #: family used throughout this Nepal-focused engine (esewa/khalti/imepay
    #: are Nepali payment systems); paisa is a distinct subunit (1/100 NPR)
    #: and is deliberately kept out of this map rather than aliased to NPR,
    #: since collapsing them would assert an incorrect 1:1 equivalence.
    _CURRENCY_ALIASES: Dict[str, str] = {
        "npr": "NPR", "rs": "NPR", "rs.": "NPR",
        "रु": "NPR", "रु.": "NPR", "rupees": "NPR", "rupaiya": "NPR",
        "inr": "INR", "₹": "INR",
        "usd": "USD", "$": "USD", "dollar": "USD", "dollars": "USD",
        "eur": "EUR", "€": "EUR",
        "gbp": "GBP", "£": "GBP",
        "paisa": "NPR-PAISA",
    }

    @classmethod
    def _normalize_money(cls, value: str) -> str:
        """Canonical ``"<CODE> <amount>"`` form so the same amount written
        with different commas, spacing, casing, or a prefix/suffix currency
        marker (``Rs 2,000`` vs ``rs2000`` vs ``2000 NPR`` vs ``2000.00``)
        de-duplicates to one entity instead of appearing as unrelated nodes
        in the correlation engine and relationship graph.

        The regex caps fractional digits at 2 places (`MONEY` pattern), so a
        float round-trip is exact for every value it can match - amounts
        stay well inside float's ~15-digit precision - and canonicalizing
        through it is what lets ``2000`` and ``2000.00`` collapse together.
        """
        amount_match = re.search(r"\d[\d,]*(?:\.\d{1,2})?", value)
        if not amount_match:
            return value.strip()
        amount = float(amount_match.group(0).replace(",", ""))
        amount_str = (
            str(int(amount))
            if amount == int(amount)
            else f"{amount:.2f}".rstrip("0").rstrip(".")
        )
        token = (value[: amount_match.start()] + value[amount_match.end() :]).strip(" .")
        code = cls._CURRENCY_ALIASES.get(token.lower(), token.upper())
        return f"{code} {amount_str}".strip()

    # ----------------------------------------------------------------- domains

    def _domains(
        self,
        text: str,
        urls: List[ExtractedEntity],
        emails: List[ExtractedEntity],
    ) -> List[ExtractedEntity]:
        """Bare domains + hosts harvested from URLs and email addresses."""
        seen: Set[str] = set()
        domains: List[ExtractedEntity] = []

        def _add(raw: str) -> None:
            domain = raw.lower().strip().rstrip(_TRAILING_PUNCT)
            tld = domain.rsplit(".", 1)[-1]
            if (
                domain in seen
                or "." not in domain
                or re.fullmatch(rx.IPV4.pattern, domain)
                or (tld not in rx.COMMON_TLDS and len(tld) < 2)
            ):
                return
            seen.add(domain)
            domains.append(ExtractedEntity("domains", raw, domain))

        for url in urls:
            host = re.sub(r"^https?://", "", url.normalized, flags=re.IGNORECASE)
            host = host.split("/")[0].split(":")[0]
            _add(host)
        for email in emails:
            _add(email.normalized.split("@", 1)[1])
        for match in rx.DOMAIN.finditer(text):
            value = match.group(0)
            # Skip matches that are part of an email or URL (already covered)
            # or that lack a plausible TLD.
            tld = value.rsplit(".", 1)[-1].lower()
            if tld not in rx.COMMON_TLDS:
                continue
            start = match.start()
            if start > 0 and text[start - 1] in "@/.":
                continue
            _add(value)
        return domains
