# Standalone CIIS RAG Assistant Engine

This engine lets an investigator ask case-scoped questions over canonical CIIS
evidence and receive locally generated answers with validated evidence IDs. It
is deliberately standalone: it does not import Django, React, the OCR engine,
the correlation engine, or the timeline/report engine.

## Current scope

```text
Current case JSON + versioned Phase-2 artifacts
                    |
                    v
            CIIS artifact adapter
                    |
                    v
       evidence-preserving document chunks
                    |
                    v
  case-scoped incremental Chroma index + manifest
                    |
                    v
 semantic + keyword + exact-entity + graph retrieval
                    |
                    v
       role-separated local Ollama generation
                    |
                    v
 validated citations + deterministic relationship details
```

The engine understands the current versioned artifact envelopes, including
`timeline_analysis.json`, `correlation_analysis.json`, `graph.json`,
`graph_summary.json`, and `graph_statistics.json`. A stable internal
`CaseKnowledgeBundle` keeps schema adaptation separate from retrieval logic.

This directory is not yet connected to the Django API or React frontend. That
integration is intentionally deferred until standalone evaluation is complete.

## Safety and correctness properties

- Every vector collection is case-scoped and every query repeats the case filter.
- Chunk IDs include case, evidence, and chunk number.
- A manifest records source hashes, chunk hashes, embedding model, and chunking
  version. New, changed, and removed evidence is synchronized incrementally.
- Phase-2 evidence/file associations are checked against the canonical case
  record. A stale artifact set is ignored and reported rather than indexed.
- Long evidence is chunked with stable overlap and source metadata.
- Retrieval combines semantic similarity, keyword overlap, exact normalized
  entities, and bounded correlated-evidence expansion.
- Evidence is passed to Ollama as explicitly untrusted context in a separate
  user message. The system message forbids following evidence-borne instructions.
- Ollama must return structured JSON. Citations outside retrieved context are
  discarded, prefix IDs such as `EVID_001`/`EVID_0010` cannot collide, and an
  uncited factual response is withheld.
- Ollama defaults to loopback. Remote hosts require an explicit opt-in.
- Model thinking is disabled by default and answer length is bounded for
  practical CPU latency. Both settings remain configurable for experiments.
- Ollama unavailability, timeouts, HTTP failures, and malformed responses are
  typed failures returned by the CLI as concise JSON rather than tracebacks.

## Storage model

ChromaDB is an embedded vector database, but it is only a derived, rebuildable
search index. Canonical evidence remains in the existing CSV/JSON/original-file
storage. `storage/` is ignored and must never be committed because embeddings
and Chroma metadata may reproduce sensitive evidence content.

## Installation

Use a separate virtual environment so Torch and vector dependencies cannot
conflict with OCR or threat-intelligence environments.

```bash
# Linux/macOS
python -m venv .venv-rag
source .venv-rag/bin/activate
python -m pip install -r rag_assistant_engine/requirements.txt
ollama pull llama3.2:1b
```

On Windows, use a short environment path when the repository path is already
long. This avoids `WinError 206` while installing Torch without requiring a
registry change:

```bash
py -3.12 -m venv E:/rag312
source /e/rag312/Scripts/activate
python -m pip install -r rag_assistant_engine/requirements.txt
```

Generation defaults can be changed through `.env.example` variables. In
particular, `CIIS_RAG_OLLAMA_THINK=1` enables supported-model reasoning for
experiments, while `CIIS_RAG_OLLAMA_NUM_PREDICT` bounds answer tokens. The
larger `gemma3:4b` and `qwen3:8b` models remain selectable through
`CIIS_RAG_OLLAMA_MODEL`, but CPU-only systems should expect substantially
higher latency. Explicit evidence-pair questions bypass generation and are
answered from the stored typed relationships.

The dependency ranges are intentionally separate. After validating the target
research machine, capture the installed versions in an environment lock for
reproducible experiments.

## Dependency-free artifact smoke check

This command validates the adapter and chunk builder without ChromaDB,
sentence-transformers, Torch, or Ollama:

```bash
python rag_assistant_engine/scripts/validate_current_case.py \
  --case-json evidence_ocr_engine/storage/json/CASE_ID.json \
  --artifact-dir evidence_ocr_engine/storage/investigation/CASE_ID
```

## Build or update an index

```bash
python -m rag_assistant_engine.cli build \
  --case-json evidence_ocr_engine/storage/json/CASE_ID.json \
  --artifact-dir evidence_ocr_engine/storage/investigation/CASE_ID
```

Running the command again is incremental. Unchanged chunks are not embedded
again, changed chunks are upserted, and obsolete chunks are removed.

## Check freshness

```bash
python -m rag_assistant_engine.cli status \
  --case-json evidence_ocr_engine/storage/json/CASE_ID.json \
  --artifact-dir evidence_ocr_engine/storage/investigation/CASE_ID
```

The status is `missing`, `stale`, or `fresh`.

## Ask a question

```bash
python -m rag_assistant_engine.cli ask \
  --case-json evidence_ocr_engine/storage/json/CASE_ID.json \
  --artifact-dir evidence_ocr_engine/storage/investigation/CASE_ID \
  "Which evidence shares the same wallet or phone number?"
```

`ask` synchronizes the index first, so a newly uploaded and processed evidence
item is available without a full index rebuild.

## Tests

The normal test suite uses an in-memory vector store and fake generator. It does
not download model weights or require Ollama:

```bash
python -m pytest rag_assistant_engine/tests -q
```

Coverage includes current artifact envelopes, actual/inferred timestamps,
incremental updates and deletion, case isolation, long-document chunking,
exact-entity and graph retrieval, citation collisions, prompt boundaries,
structured generation, stale-artifact rejection, exact query constraints,
answer withholding, and research metrics.

## Research evaluation

Use `scripts/evaluate_results.py` with labelled questions to calculate
Recall@K, Precision@K, mean reciprocal rank, and citation precision/recall/F1.
Before integration, add a labelled sample covering exact identifiers,
multi-evidence synthesis, insufficient-evidence questions, and bilingual OCR.

Remaining standalone evaluation work is documented by test gaps rather than
hidden behind integration: real Chroma/model benchmarking, retrieval threshold
calibration, grounded-answer scoring, and latency/scalability measurement.
