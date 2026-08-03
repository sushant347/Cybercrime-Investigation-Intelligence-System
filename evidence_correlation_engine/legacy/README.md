# Evidence Correlation Engine

**Module 4** of the Cybercrime Investigation Intelligence System (CIIS).

This module links pieces of evidence together. It takes the structured case
JSON files produced by the OCR/evidence engine (Module 2) — each already
containing extracted entities (phone numbers, eSewa/Khalti/IMEPay IDs, URLs,
wallets, emails, bank accounts, etc.) — and figures out which evidence items
are actually connected to each other, and *why*.

The output is a correlation graph that downstream modules build on:

```text
ocr_output / case JSON  (Module 2)
        ↓
Correlation Engine  (this module)
        ↓
correlation_graph.json + correlation_summary.json
        ↓
Timeline Reconstruction (Module 5)  +  Report Generator (Module 6)
```

## What It Does

Given one or more case JSON files, the engine:

1. **Reads entities directly from Module 2's output.** No re-extraction, no
   NER dependency — it uses the `cleaning.entities` block that the OCR
   engine already produces for every evidence item.
2. **Links evidence that shares an entity.** If the same phone number,
   eSewa ID, wallet address, URL, or other entity appears in two different
   pieces of evidence, those two evidence items get connected. The more
   entities two items share, the stronger the link (higher edge weight).
3. **Falls back to temporal proximity.** If two evidence items don't share
   any entity but were uploaded within 24 hours of each other, they get a
   weaker "might be related" link. This only applies when no stronger
   entity-based link already exists, so it never dilutes a real match.
4. **Works across cases, not just within one.** Pass in multiple case
   files and it will still correlate entities that appear across them —
   useful when the same suspect shows up in evidence from two different
   investigations.

## NetworkX Investigation Graph (`graph_builder.py`)

On top of the legacy dict-based correlation graph (`correlate_cases`, kept for
backward compatibility), this module now ships a `networkx.MultiDiGraph`-backed
investigation graph — the backbone of the Investigation Engine. It sits in the
pipeline immediately after Entity Extraction:

```
Entity Extraction -> NetworkX Graph Builder -> Correlation / Timeline /
                                               Campaign / Suspect / Analytics /
                                               Report Generation
```

`GraphBuilder` consumes the already-extracted `cleaning.entities` (it never
re-runs OCR or extraction), turns every entity into a typed node and every
relationship into a directed edge, and **automatically merges duplicate
entities** — the same wallet/URL/phone seen in three evidence items becomes one
node with three evidence links.

Reusable API:

```python
from graph_builder import GraphBuilder

builder = GraphBuilder(case_id="CASE_0021")
builder.build_graph(cases)            # MultiDiGraph, dedup + temporal edges
builder.degree_centrality()           # + betweenness / closeness
builder.connected_components()        # investigation clusters
builder.community_detection()         # suspicious communities
builder.find_shortest_path(a, b)      # indirect victim<->suspect links
builder.find_isolated_nodes()
builder.investigation_features()      # most-connected suspect, reused URL, ...
artifacts = builder.serialize_graph() # {graph, graph_statistics, graph_summary}
```

`serialize_graph()` emits JSON byte-compatible with the React frontend contract
(`RelationshipGraph` / `GraphStatistics` / `GraphSummary`), so it drops straight
into the existing Django/DRF `/cases/{id}/artifacts/graph*` endpoints. Rebuilds
are skipped when the input signature is unchanged (cache). Requires
`networkx>=3.0` (see `requirements.txt`). Unit tests: `tests/test_graph_builder.py`.

## What It Does NOT Do

- It does not re-run OCR or re-extract entities from raw text — that's
  Module 2's job. This module is purely a linking/graph layer on top of
  already-structured data.
- It does not currently run a general-purpose NER pass for names/organizations
  that aren't already captured by Module 2's regex-based entity extractor.
  This is a deliberate scope decision to keep the prototype fast; it's a
  natural place to plug in an NER model later if needed.
- It does not order evidence into a narrative — that's Module 5 (Timeline
  Reconstruction), which consumes this module's output.

## Input Format

One or more case JSON files shaped like Module 2's output. At minimum, each
evidence item needs:

```json
{
  "case_id": "CASE_0021",
  "evidence": [
    {
      "evidence_id": "EVID_00031",
      "file_name": "screenshot.jpg",
      "upload_time": "2026-07-08T18:12:00.000Z",
      "cleaning": {
        "entities": {
          "phones": [{"value": "9841122334", "normalized": "9841122334"}],
          "esewa_ids": [{"value": "rajesh.thapa99", "normalized": "rajesh.thapa99"}]
        }
      }
    }
  ]
}
```

Entity types currently correlated on: `urls`, `emails`, `domains`, `ipv4`,
`ipv6`, `mac_addresses`, `phones`, `bank_accounts`, `esewa_ids`,
`khalti_ids`, `imepay_ids`, `eth_wallets`, `btc_wallets`,
`telegram_usernames`, `whatsapp_numbers`, `facebook_usernames`,
`instagram_usernames`, `social_media_urls`, `hashes_sha256`,
`hashes_sha1`, `hashes_md5`, `cve_ids`.

## Usage

```bash
python correlation_engine.py case1.json
python correlation_engine.py case1.json case2.json case3.json
```

Or import it directly in a notebook:

```python
from correlation_engine import correlate_cases, summarize_correlation, load_case

cases = [load_case("case1.json"), load_case("case2.json")]
graph = correlate_cases(cases)
summary = summarize_correlation(graph)
```

## Output

Two files are written to `output/`:

### `correlation_graph.json`

```json
{
  "nodes": [
    {"id": "EVID_00031", "case_id": "CASE_0021", "file_name": "...", "upload_time": "..."}
  ],
  "edges": [
    {
      "source": "EVID_00031",
      "target": "EVID_00032",
      "type": "shared_entity",
      "shared_entities": [
        {"value": "9841122334", "type": "phones"},
        {"value": "rajesh.thapa99", "type": "esewa_ids"}
      ],
      "weight": 2.0
    }
  ],
  "entity_index": {
    "9841122334": [
      {"case_id": "CASE_0021", "evidence_id": "EVID_00031", "entity_type": "phones"},
      {"case_id": "CASE_0021", "evidence_id": "EVID_00032", "entity_type": "phones"}
    ]
  }
}
```

`nodes` and `edges` are graph-ready — hand this straight to a graph
visualization library (e.g. `vis.js`, `d3`, `networkx` + `pyvis`) for
Module 8's dashboard. `entity_index` only includes entities that appear in
2+ evidence items — i.e. only entities that actually correlate something.

### `correlation_summary.json`

A flat, human-readable summary for quick review without parsing the full
graph:

```json
{
  "total_evidence_items": 3,
  "total_correlation_links": 1,
  "shared_entity_links": 1,
  "temporal_only_links": 0,
  "top_connecting_entities": [
    {"value": "9841122334", "connects_evidence_count": 2, "entity_type": "phones"}
  ]
}
```

## Design Notes

- **Weight scoring**: shared-entity edges accumulate weight as more shared
  entities are found between the same pair of evidence items (2 shared
  entities → weight 2.0). Temporal-only edges are capped below 1.0 and
  scaled by how close in time the two items are — this keeps them
  visually/structurally weaker than any real entity-based link, which
  matters once Module 8 renders this as a weighted graph.
- **Entity matching is case-insensitive and whitespace-trimmed**, but
  otherwise exact-match only. It does not currently do fuzzy matching
  (e.g. `98411-22334` vs `9841122334` won't match unless Module 2's
  normalization already handles that — which it does, via the
  `normalized` field this module reads from).
- **Self-links are never created.** An evidence item is never linked to
  itself even if it appears in the entity index multiple times.

## Tested Against

Validated against synthetic data shaped exactly like Module 2's real
output (see `case_0021_test.json` in this repo), covering:

- Two evidence items sharing both a phone number and an eSewa ID → correctly
  linked with combined weight 2.0
- A third, unrelated evidence item with no shared entities and outside the
  24-hour temporal window → correctly produces zero edges (not falsely
  bundled in)
- Pure temporal-proximity correlation (no shared entities, but evidence
  timestamps within a few hours) → correctly produces a weaker
  `temporal_proximity` edge

## Next Steps

- **Module 5 (Timeline Reconstruction)** consumes this module's
  `correlation_graph.json` plus each evidence item's `upload_time` and any
  extracted `dates`/`times` entities to build a chronological narrative.
- **Module 6 (Report Generator)** uses `entity_index` and `edges` directly
  to write sentences like *"Suspect identified via phone 9841122334 and
  eSewa ID rajesh.thapa99, linking messenger_chat_screenshot.jpg and
  esewa_payment_request.jpg."*
- A pluggable NER hook could be added later for name/organization
  correlation beyond what Module 2's regex extractor already catches —
  useful for cases where entities aren't cleanly formatted (e.g. a name
  mentioned in prose rather than a structured ID).
