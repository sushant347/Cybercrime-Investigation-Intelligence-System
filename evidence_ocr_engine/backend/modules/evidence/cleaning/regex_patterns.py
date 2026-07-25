"""Production-grade, reusable regular expressions for forensic entity work.

Single source of truth: every pattern used by entity preservation, entity
extraction and validation lives here, compiled once at import time. Patterns
are deliberately conservative - in a forensic context a missed match is
recoverable (the raw text is preserved), but a false positive contaminates
the investigation record.
"""

from __future__ import annotations

import re
from typing import Dict, Pattern

# --------------------------------------------------------------------------- #
# Network / web entities
# --------------------------------------------------------------------------- #

#: Full URLs (scheme or www-prefixed). Trailing punctuation is trimmed later.
URL: Pattern[str] = re.compile(
    r"""\b(?:https?://|www\.)[^\s<>"'ऀ-ॿ]+""",
    re.IGNORECASE,
)

#: RFC-5322-practical email addresses.
EMAIL: Pattern[str] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}\b"
)

#: Bare domains (labels + real-looking TLD). Overlaps with URL/EMAIL are
#: handled by the extractor, which prefers the longer entity.
DOMAIN: Pattern[str] = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b",
    re.IGNORECASE,
)

#: IPv4 with strict octet validation (0-255).
IPV4: Pattern[str] = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b"
)

#: IPv6 candidates: full 8-group form or any hex/colon run containing "::".
#: Candidates are strictly validated with the `ipaddress` module in the
#: extractor, so the pattern only needs to capture the complete span.
IPV6: Pattern[str] = re.compile(
    r"(?<![\w:.])(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}(?![\w:])"
    r"|(?<![\w:.])[0-9A-Fa-f:]*::[0-9A-Fa-f:]*(?![\w:.])"
)

#: MAC addresses (colon or hyphen separated).
MAC_ADDRESS: Pattern[str] = re.compile(
    r"\b[0-9A-Fa-f]{2}(?:([:-])[0-9A-Fa-f]{2})(?:\1[0-9A-Fa-f]{2}){4}\b"
)

#: Ports - contextual only ("port 8080", ":443" after a *host-like* token).
#:
#: The second alternative used to accept ``:(\d{2,5})`` after any alphanumeric,
#: which matched the minutes of every clock time ("11:15 AM" -> port 15) and
#: filled the entity record with phantom ports. A port now has to follow either
#: a token containing a letter (a hostname) or a dotted-quad IPv4, which is the
#: only place ``host:port`` legitimately appears.
PORT: Pattern[str] = re.compile(
    r"(?:\bport\s*(?:no\.?|number)?\s*[:#]?\s*(\d{1,5})\b)"
    r"|(?:\b(?:[a-z0-9-]*[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*"
    r"|\d{1,3}(?:\.\d{1,3}){3})"
    r":(\d{2,5})(?=[/\s,]|$))",
    re.IGNORECASE,
)

#: CVE identifiers.
CVE: Pattern[str] = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

# --------------------------------------------------------------------------- #
# Contact entities
# --------------------------------------------------------------------------- #

#: Phone numbers: Nepali mobiles (+977 96/97/98xxxxxxxx), Nepali landlines,
#: and generic international numbers.
PHONE: Pattern[str] = re.compile(
    r"(?:\+?977[-\s]?)?9[678]\d{8}\b"          # Nepali mobile
    r"|\b0\d{1,2}[-\s]?\d{6,7}\b"              # Nepali landline
    r"|\+\d{1,3}[-\s]?\d{6,12}\b"              # generic international
)

# --------------------------------------------------------------------------- #
# Temporal entities
# --------------------------------------------------------------------------- #

DATE: Pattern[str] = re.compile(
    r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b"                            # 2026-01-04
    r"|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"                         # 04/01/2026
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{4}\b",
    re.IGNORECASE,
)

TIME: Pattern[str] = re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s?(?:AM|PM|am|pm)?\b"
)

# --------------------------------------------------------------------------- #
# Financial entities
# --------------------------------------------------------------------------- #

#: Money amounts with currency markers (NPR/Rs/रु, USD/$, INR, EUR, GBP).
MONEY: Pattern[str] = re.compile(
    r"(?:(?:NPR|Rs\.?|रु\.?|₹|\$|USD|INR|EUR|GBP|£|€)\s?\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?:\d[\d,]*(?:\.\d{1,2})?\s?(?:NPR|USD|INR|EUR|GBP|rupees|rupaiya|paisa|dollars?))",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# Label -> value glue
#
# Screenshots and receipts print the label and the value on *separate lines*
# ("Sent To (Khalti ID)\n9801122334", "Depositor Account No.:\n0501-0198765432").
# The original contextual patterns required the value on the same line, so a
# receipt - the single most common evidence type in a payment-fraud case -
# yielded no wallet id, no account number and no transaction code at all.
#
# ``_LABEL_GAP`` therefore allows the separator characters, an optional
# punctuation run, and **at most one** line break before the value. One line is
# the deliberate limit: it covers the label/value layout of every receipt in the
# corpus without letting a label on one line bind to an unrelated number three
# lines below it.
# --------------------------------------------------------------------------- #

#: Optional "no./number/#/code/id" qualifier that may follow a label word.
_LABEL_QUALIFIER = r"(?:[ \t]*(?:no|number|num|code|id|#)\b\.?)?"
#: Separator between a label and its value: punctuation, spaces, one newline.
_LABEL_GAP = r"[^\S\n]*[:#.\-)\]]*[^\S\n]*\n?[^\S\n]*"
#: Wider gap for prose ("esewa id ma paisa pathaunus 98XXXXXXXX"), still
#: capped and still limited to a single line break.
_PROSE_GAP = r"[^\d\n]{0,40}\n?[^\d\n]{0,25}"

#: Nepali mobile number as it appears inside a contextual capture group.
_NP_MOBILE = r"(?:\+?977[-\s]?)?9[678]\d{8}"

#: Bank account numbers - contextual (label, then the digits, possibly on the
#: next line). Accepts the "Account No.:" form the previous pattern rejected.
BANK_ACCOUNT: Pattern[str] = re.compile(
    r"(?:a/c|acc?(?:oun)?t|khata|खाता)" + _LABEL_QUALIFIER + _LABEL_GAP +
    r"(\d[\d\- ]{7,24}\d)",
    re.IGNORECASE,
)

#: Payment card numbers (13-19 digits, optionally grouped). Every candidate is
#: Luhn-validated by the extractor, so a receipt total or a long reference
#: number cannot masquerade as a card.
CARD_NUMBER: Pattern[str] = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")

#: Transaction / voucher / reference codes.
#:
#: Two ways in: a label ("Transaction Code", "Voucher No.:", "Ref:") followed by
#: the code, or the two unmistakable code *shapes* used by Nepali payment rails
#: and banks - ``0119.0625.987456`` (eSewa) and ``KH-2026-0611-77245`` /
#: ``MBL-2026-441829`` (wallet + bank vouchers). The structural forms matter
#: because OCR frequently mangles the label itself ("TansatianD") while the
#: code - printed in a monospaced field - survives intact.
TRANSACTION_ID: Pattern[str] = re.compile(
    r"(?:\b(?:transaction|txn|trxn|tranx|voucher|receipt|reference|ref|invoice|"
    r"order|bill|payment)\b" + _LABEL_QUALIFIER + _LABEL_GAP +
    r"([A-Za-z0-9][A-Za-z0-9._/-]{4,29}))"
    r"|(\b\d{3,6}(?:\.\d{3,6}){2}\b)"
    r"|(\b[A-Z]{2,5}-\d{2,4}(?:-\d{2,6}){1,3}\b)",
    re.IGNORECASE,
)

#: OTP / verification codes - contextual, 4-8 digits.
OTP: Pattern[str] = re.compile(
    r"(?:\botp\b|\bcode\b|\bpin\b|\bpassword\b|\bओटीपी\b)\D{0,12}?"
    r"(?<![\d-])(\d{4,8})(?![\d-])",  # reject digits inside hyphenated codes
    re.IGNORECASE,
)

#: Nepali digital wallet IDs - contextual.
#:
#: A wallet id is either the registered mobile number *or* the registered email
#: address (all three rails accept both), so both shapes are captured. The
#: value may sit on the label's line ("esewa id ma paisa pathaunus 98XXXXXXXX")
#: or on the next line, which is how every receipt screenshot lays it out
#: ("Sent To (Khalti ID)\n9801122334").
_WALLET_VALUE = (
    r"(" + _NP_MOBILE +
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24})"
)

ESEWA_ID: Pattern[str] = re.compile(
    r"\be[\s-]?sewa\b" + _LABEL_QUALIFIER + _LABEL_GAP + _WALLET_VALUE +
    r"|\be[\s-]?sewa\b" + _PROSE_GAP + r"(" + _NP_MOBILE + r")",
    re.IGNORECASE,
)
KHALTI_ID: Pattern[str] = re.compile(
    r"\bkhalti\b" + _LABEL_QUALIFIER + _LABEL_GAP + _WALLET_VALUE +
    r"|\bkhalti\b" + _PROSE_GAP + r"(" + _NP_MOBILE + r")",
    re.IGNORECASE,
)
IMEPAY_ID: Pattern[str] = re.compile(
    r"\bime[\s-]?pay\b" + _LABEL_QUALIFIER + _LABEL_GAP + _WALLET_VALUE +
    r"|\bime[\s-]?pay\b" + _PROSE_GAP + r"(" + _NP_MOBILE + r")",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# Cryptographic entities
# --------------------------------------------------------------------------- #

MD5: Pattern[str] = re.compile(r"\b[a-fA-F0-9]{32}\b")
SHA1: Pattern[str] = re.compile(r"\b[a-fA-F0-9]{40}\b")
SHA256: Pattern[str] = re.compile(r"\b[a-fA-F0-9]{64}\b")
SHA512: Pattern[str] = re.compile(r"\b[a-fA-F0-9]{128}\b")

#: Bitcoin: legacy Base58 (1.../3...) and Bech32 (bc1...).
BTC_WALLET: Pattern[str] = re.compile(
    r"\b(?:bc1[ac-hj-np-z02-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"
)

#: Ethereum: 0x + 40 hex chars.
ETH_WALLET: Pattern[str] = re.compile(r"\b0x[a-fA-F0-9]{40}\b")

# --------------------------------------------------------------------------- #
# Social media entities
# --------------------------------------------------------------------------- #

SOCIAL_MEDIA_URL: Pattern[str] = re.compile(
    r"\b(?:https?://)?(?:www\.)?"
    r"(?:facebook\.com|fb\.com|fb\.me|instagram\.com|t\.me|telegram\.me|"
    r"wa\.me|api\.whatsapp\.com|twitter\.com|x\.com|tiktok\.com|youtube\.com|youtu\.be)"
    r"/[^\s<>\"']+",
    re.IGNORECASE,
)

TELEGRAM_USERNAME: Pattern[str] = re.compile(
    r"(?:(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{4,31}))"
    r"|(?:^|[\s(])@([A-Za-z][A-Za-z0-9_]{4,31})\b"
)

WHATSAPP_NUMBER: Pattern[str] = re.compile(
    r"(?:(?:https?://)?wa\.me/(\+?\d{8,15}))"
    r"|(?:\bwhats\s?app\b\D{0,12}((?:\+?977[-\s]?)?9[678]\d{8}|\+\d{8,15}))",
    re.IGNORECASE,
)

FACEBOOK_USERNAME: Pattern[str] = re.compile(
    r"(?:https?://)?(?:www\.)?(?:facebook\.com|fb\.com)/(?!share|groups|pages|watch|events)"
    r"([A-Za-z0-9.]{5,50})",
    re.IGNORECASE,
)

INSTAGRAM_USERNAME: Pattern[str] = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{2,30})",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# Pattern registries
# --------------------------------------------------------------------------- #

#: Bare transaction/voucher code *shapes*, used only for preservation. The
#: contextual :data:`TRANSACTION_ID` pattern spans the label too, and shielding
#: a label from cleaning would degrade the cleaned text for no benefit - only
#: the code itself must survive byte-for-byte.
TRANSACTION_CODE_SHAPE: Pattern[str] = re.compile(
    r"\b\d{3,6}(?:\.\d{3,6}){2}\b|\b[A-Z]{2,5}-\d{2,4}(?:-\d{2,6}){1,3}\b"
)

#: Patterns used by :class:`EntityPreserver` to shield spans from cleaning.
#: Ordered longest/most-specific first so protection is maximal.
PROTECTED_PATTERNS: Dict[str, Pattern[str]] = {
    "url": URL,
    "email": EMAIL,
    "card_number": CARD_NUMBER,
    "transaction_code": TRANSACTION_CODE_SHAPE,
    "sha512": SHA512,
    "sha256": SHA256,
    "sha1": SHA1,
    "md5": MD5,
    "eth_wallet": ETH_WALLET,
    "btc_wallet": BTC_WALLET,
    "ipv6": IPV6,
    "ipv4": IPV4,
    "mac_address": MAC_ADDRESS,
    "cve": CVE,
    "phone": PHONE,
    "money": MONEY,
    "date": DATE,
    "time": TIME,
}

#: Known TLD sanity list used to validate bare-domain matches (extendable).
COMMON_TLDS: frozenset[str] = frozenset(
    {
        "com", "net", "org", "edu", "gov", "mil", "int", "info", "biz", "io",
        "co", "np", "in", "uk", "us", "au", "de", "fr", "cn", "jp", "ru",
        "top", "xyz", "site", "online", "shop", "store", "app", "dev", "ai",
        "me", "tv", "cc", "link", "click", "live", "vip", "pro", "asia",
    }
)
