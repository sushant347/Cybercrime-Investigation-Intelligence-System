"""
Module 4 - Evidence Correlation Engine
========================================
Cybercrime Investigation Intelligence System (CIIS)

Consumes case JSON files produced by the OCR/evidence engine (Module 2)
and builds an index of which entities (phones, eSewa IDs, URLs, etc.)
appear in which evidence items, as a foundation for correlation.
"""

import json
import os
import sys
from collections import defaultdict

CORRELATABLE_ENTITY_TYPES = [
    "urls", "emails", "domains", "ipv4", "ipv6", "mac_addresses",
    "phones", "bank_accounts", "esewa_ids", "khalti_ids", "imepay_ids",
    "eth_wallets", "btc_wallets", "telegram_usernames", "whatsapp_numbers",
    "facebook_usernames", "instagram_usernames", "social_media_urls",
    "hashes_sha256", "hashes_sha1", "hashes_md5", "cve_ids",
]

OUTPUT_DIR = "output"


def load_case(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_entity_index(case: dict) -> dict:
    """
    Build {entity_value: [{"case_id", "evidence_id", "entity_type"}]}
    for a single case, pulled from each evidence item's
    cleaning.entities block.
    """
    index = defaultdict(list)
    case_id = case.get("case_id", "UNKNOWN_CASE")

    for evidence in case.get("evidence", []):
        evidence_id = evidence.get("evidence_id", "UNKNOWN_EVID")
        entities = evidence.get("cleaning", {}).get("entities", {})

        for entity_type in CORRELATABLE_ENTITY_TYPES:
            for item in entities.get(entity_type, []):
                value = item.get("normalized") or item.get("value")
                if not value:
                    continue
                value = str(value).strip().lower()
                if value:
                    index[value].append({
                        "case_id": case_id,
                        "evidence_id": evidence_id,
                        "entity_type": entity_type,
                    })

    return index


def main():
    if len(sys.argv) < 2:
        print("Usage: python correlation_engine.py <case1.json> [case2.json] ...")
        sys.exit(1)

    cases = [load_case(p) for p in sys.argv[1:]]
    print(f"Loaded {len(cases)} case(s)")

    for case in cases:
        index = extract_entity_index(case)
        print(f"  {case.get('case_id')}: {len(index)} distinct entities found")


if __name__ == "__main__":
    main()
