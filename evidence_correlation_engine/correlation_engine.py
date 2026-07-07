"""
Module 4 - Evidence Correlation Engine
========================================
Cybercrime Investigation Intelligence System (CIIS)

Consumes case JSON files produced by the OCR/evidence engine (Module 2),
and links evidence items together based on:

  1. Shared entities (URLs, domains, phone numbers, emails, wallet IDs,
     eSewa/Khalti/IMEPay IDs, bank accounts, social media handles, etc.)
  2. Temporal proximity (evidence items close in time are more likely
     related), used only as a fallback when no shared-entity link exists.
"""

import json
import os
import sys
from datetime import datetime
from itertools import combinations
from collections import defaultdict

CORRELATABLE_ENTITY_TYPES = [
    "urls", "emails", "domains", "ipv4", "ipv6", "mac_addresses",
    "phones", "bank_accounts", "esewa_ids", "khalti_ids", "imepay_ids",
    "eth_wallets", "btc_wallets", "telegram_usernames", "whatsapp_numbers",
    "facebook_usernames", "instagram_usernames", "social_media_urls",
    "hashes_sha256", "hashes_sha1", "hashes_md5", "cve_ids",
]

TEMPORAL_PROXIMITY_HOURS = 24
OUTPUT_DIR = "output"


def load_case(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_entity_index(case: dict) -> dict:
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


def correlate_cases(cases: list) -> dict:
    combined_index = defaultdict(list)
    all_evidence_meta = {}

    for case in cases:
        case_id = case.get("case_id", "UNKNOWN_CASE")
        for evidence in case.get("evidence", []):
            evidence_id = evidence.get("evidence_id", "UNKNOWN_EVID")
            all_evidence_meta[evidence_id] = {
                "id": evidence_id,
                "case_id": case_id,
                "file_name": evidence.get("file_name"),
                "upload_time": evidence.get("upload_time"),
            }

        case_index = extract_entity_index(case)
        for value, occurrences in case_index.items():
            combined_index[value].extend(occurrences)

    edge_map = {}
    for value, occurrences in combined_index.items():
        if len(occurrences) < 2:
            continue

        for occ_a, occ_b in combinations(occurrences, 2):
            id_a, id_b = occ_a["evidence_id"], occ_b["evidence_id"]
            if id_a == id_b:
                continue
            key = tuple(sorted([id_a, id_b]))

            if key not in edge_map:
                edge_map[key] = {
                    "source": key[0],
                    "target": key[1],
                    "type": "shared_entity",
                    "shared_entities": [],
                    "weight": 0.0,
                }
            edge_map[key]["shared_entities"].append({
                "value": value,
                "type": occ_a["entity_type"],
            })
            edge_map[key]["weight"] += 1.0

    # Temporal proximity fallback -- only where no shared-entity edge exists
    evidence_ids = list(all_evidence_meta.keys())
    for id_a, id_b in combinations(evidence_ids, 2):
        key = tuple(sorted([id_a, id_b]))
        if key in edge_map:
            continue

        t_a = all_evidence_meta[id_a].get("upload_time")
        t_b = all_evidence_meta[id_b].get("upload_time")
        if not t_a or not t_b:
            continue

        try:
            dt_a = datetime.fromisoformat(t_a.replace("Z", "+00:00"))
            dt_b = datetime.fromisoformat(t_b.replace("Z", "+00:00"))
        except ValueError:
            continue

        delta = abs((dt_a - dt_b).total_seconds()) / 3600.0
        if delta <= TEMPORAL_PROXIMITY_HOURS:
            edge_map[key] = {
                "source": key[0],
                "target": key[1],
                "type": "temporal_proximity",
                "shared_entities": [],
                "weight": max(0.1, 1.0 - (delta / TEMPORAL_PROXIMITY_HOURS)),
            }

    return {
        "nodes": list(all_evidence_meta.values()),
        "edges": list(edge_map.values()),
        "entity_index": {
            value: occs for value, occs in combined_index.items()
            if len(occs) >= 2
        },
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python correlation_engine.py <case1.json> [case2.json] ...")
        sys.exit(1)

    cases = [load_case(p) for p in sys.argv[1:]]
    graph = correlate_cases(cases)
    print(f"Loaded {len(cases)} case(s), {len(graph['nodes'])} evidence item(s)")
    print(f"Found {len(graph['edges'])} correlation link(s)")


if __name__ == "__main__":
    main()
