"""
Module 4 - Evidence Correlation Engine
========================================
Cybercrime Investigation Intelligence System (CIIS)

Consumes case JSON files produced by the OCR/evidence engine (Module 2) and
the threat intelligence scores (Module 3), and links evidence items together
based on:

  1. Shared entities (URLs, domains, phone numbers, emails, wallet IDs,
     eSewa/Khalti/IMEPay IDs, bank accounts, social media handles, etc.)
     -- pulled directly from the OCR engine's existing `entities` block,
        no re-extraction needed.
  2. Lightweight name/organization detection for text not already covered
     by the regex-based entity extractor (optional, pluggable NER hook).
  3. Temporal proximity (evidence items close in time are more likely
     related).

Output: a correlation graph (nodes = evidence + entities, edges = shared
entity / temporal links) plus a per-case correlation summary, ready to feed
Module 5 (Timeline Reconstruction) and Module 6 (Report Generator).

Usage:
    python correlation_engine.py case1.json case2.json ...
    (or import `correlate_cases` directly in a notebook)
"""

import json
import os
import sys
import re
from datetime import datetime, timedelta
from itertools import combinations
from collections import defaultdict

# Config

CORRELATABLE_ENTITY_TYPES = [
    "urls", "emails", "domains", "ipv4", "ipv6", "mac_addresses",
    "phones", "bank_accounts", "esewa_ids", "khalti_ids", "imepay_ids",
    "eth_wallets", "btc_wallets", "telegram_usernames", "whatsapp_numbers",
    "facebook_usernames", "instagram_usernames", "social_media_urls",
    "hashes_sha256", "hashes_sha1", "hashes_md5", "cve_ids",
]

TEMPORAL_PROXIMITY_HOURS = 24

OUTPUT_DIR = "output"


# Loading

def load_case(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_entity_index(case: dict) -> dict:
    """
    Build {entity_value: [(evidence_id, entity_type), ...]} for a single
    case, pulled from each evidence item's cleaning.entities block.
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


def extract_upload_time(case: dict, evidence_id: str):
    for evidence in case.get("evidence", []):
        if evidence.get("evidence_id") == evidence_id:
            ts = evidence.get("upload_time")
            if ts:
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    return None
    return None


# Correlation

def correlate_cases(cases: list) -> dict:
    """
    Build a correlation graph across one or more loaded case dicts.

    Returns:
        {
            "nodes": [{"id": evidence_id, "case_id": ..., "file_name": ...}],
            "edges": [
                {
                    "source": evidence_id_a,
                    "target": evidence_id_b,
                    "type": "shared_entity" | "temporal_proximity",
                    "shared_entities": [{"value": ..., "type": ...}],
                    "weight": float,
                }
            ],
            "entity_index": {value: [{"case_id", "evidence_id", "entity_type"}]},
        }
    """
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


def build_investigation_graph(cases: list, case_id: str = "MULTI_CASE") -> dict:
    """NetworkX-backed investigation graph, serialized to the frontend contract.

    Thin adapter over :class:`graph_builder.GraphBuilder` so callers that only
    imported this module keep working. Returns the three artifact payloads
    ``{"graph", "graph_statistics", "graph_summary"}``. Kept separate from
    :func:`correlate_cases` so the legacy evidence-only graph is preserved for
    backward compatibility.
    """
    from graph_builder import GraphBuilder

    builder = GraphBuilder(case_id=case_id)
    builder.build_graph(cases)
    return builder.serialize_graph()


def summarize_correlation(graph: dict) -> dict:
    """Human-readable summary of the correlation graph for quick review."""
    shared_entity_edges = [e for e in graph["edges"] if e["type"] == "shared_entity"]
    temporal_edges = [e for e in graph["edges"] if e["type"] == "temporal_proximity"]

    entity_ranking = sorted(
        graph["entity_index"].items(),
        key=lambda kv: len(kv[1]),
        reverse=True,
    )

    return {
        "total_evidence_items": len(graph["nodes"]),
        "total_correlation_links": len(graph["edges"]),
        "shared_entity_links": len(shared_entity_edges),
        "temporal_only_links": len(temporal_edges),
        "top_connecting_entities": [
            {
                "value": value,
                "connects_evidence_count": len(occs),
                "entity_type": occs[0]["entity_type"] if occs else None,
            }
            for value, occs in entity_ranking[:10]
        ],
    }


# CLI entry point

def main():
    if len(sys.argv) < 2:
        print("Usage: python correlation_engine.py <case1.json> [case2.json] ...")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cases = [load_case(p) for p in sys.argv[1:]]
    graph = correlate_cases(cases)
    summary = summarize_correlation(graph)

    graph_path = os.path.join(OUTPUT_DIR, "correlation_graph.json")
    summary_path = os.path.join(OUTPUT_DIR, "correlation_summary.json")

    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Loaded {len(cases)} case(s), {len(graph['nodes'])} evidence item(s)")
    print(f"Found {summary['shared_entity_links']} shared-entity links, "
          f"{summary['temporal_only_links']} temporal-only links")
    print(f"Saved -> {graph_path}")
    print(f"Saved -> {summary_path}")

    # NetworkX investigation graph artifacts (frontend-contract shape).
    try:
        case_id = cases[0].get("case_id", "MULTI_CASE") if len(cases) == 1 else "MULTI_CASE"
        artifacts = build_investigation_graph(cases, case_id=case_id)
        for key in ("graph", "graph_statistics", "graph_summary"):
            path = os.path.join(OUTPUT_DIR, f"{key}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(artifacts[key], f, indent=2, ensure_ascii=False)
            print(f"Saved -> {path}")
        stats = artifacts["graph_statistics"]
        print(f"NetworkX graph: {stats['node_count']} nodes, {stats['edge_count']} edges, "
              f"{stats['connected_components']} component(s)")
    except ImportError:
        print("networkx not installed - skipped investigation graph artifacts "
              "(pip install networkx).")

    if summary["top_connecting_entities"]:
        print("\nTop connecting entities:")
        for e in summary["top_connecting_entities"]:
            print(f"  {e['value']} ({e['entity_type']}) "
                  f"-> links {e['connects_evidence_count']} evidence items")


if __name__ == "__main__":
    main()
