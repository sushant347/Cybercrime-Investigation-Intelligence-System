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
evidence/OCR text, timeline, correlation, cross-case, graph summaries,
campaigns, suspects, analytics, priority, the analysis manifest and every
investigation-report section. Legal assessment chunks retain their supporting
evidence IDs, while official ETA/NRB source records retain their source URLs.
A stable internal `CaseKnowledgeBundle` keeps schema adaptation separate from
retrieval logic.

The engine is connected through a narrow integration boundary:

```text
analysis/upload pipeline -> Django RAG adapter -> this standalone CLI
                                             -> Chroma + local Ollama
```

The Django platform invokes this engine with its separate Python executable;
it never imports Chroma, Torch or sentence-transformers into the PaddleOCR
environment. Indexing is best-effort and cannot turn a successful evidence or
analysis job into a failure. Every question synchronizes again before retrieval,
so newly processed evidence remains visible even if the post-pipeline warm-index
step was unavailable.

The React case view exposes the assistant as a right-side drawer rather than a
new analysis tab. This keeps it available while an investigator moves between
Evidence, Graph, Timeline, Analytics and Reports.

## Safety and correctness properties

- Every vector collection is case-scoped and every query repeats the case filter.
- Chunk IDs include case, evidence, and chunk number.
- A manifest records source hashes, chunk hashes, embedding model, and chunking
  version. New, changed, and removed evidence is synchronized incrementally.
- Phase-2 evidence/file associations are checked against the canonical case
  record. A stale artifact set is ignored and reported rather than indexed.
- After a new upload, full-analysis artifacts that predate the current evidence
  set are withheld until case analysis refreshes them; current evidence,
  correlation, timeline and graph data remain searchable immediately.
- Long evidence is chunked with stable overlap and source metadata.
- Retrieval combines semantic similarity, keyword overlap, exact normalized
  entities, and bounded correlated-evidence expansion.
- Evidence is passed to Ollama as explicitly untrusted context in a separate
  user message. The system message forbids following evidence-borne instructions.
- Ollama is asked for structured JSON. A small model's source-cited plain-text
  fallback is accepted only after the same citation validation; uncited prose,
  citations outside retrieved context and prefix-ID collisions are withheld.
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
ollama pull gemma3:1b
```

On Windows, use a short environment path when the repository path is already
long. This avoids `WinError 206` while installing Torch without requiring a
registry change:

```bash
py -3.12 -m venv E:/rag312
source /e/rag312/Scripts/activate
python -m pip install -r rag_assistant_engine/requirements.txt
```

Generation defaults can be changed through `.env.example` variables. The
default `gemma3:1b` model is small enough for CPU-oriented research use and is
selected for responsive, reliable question answering with structured output.
`CIIS_RAG_OLLAMA_THINK=1` enables supported-model reasoning for experiments,
while `CIIS_RAG_OLLAMA_NUM_PREDICT` bounds answer tokens. The larger
`gemma3:4b` and `qwen3:8b` models remain selectable through
`CIIS_RAG_OLLAMA_MODEL`, but CPU-only systems should expect substantially
higher latency. Greetings, help requests, explicit evidence-pair questions,
most-connected-entity rankings, shared-entity relationship
questions, earliest/latest timeline questions and statutory-basis listings
bypass generation and are answered from canonical structured artifacts. The
generation fallback sends at most five ranked chunks and caps each prompt
excerpt at 1,400 characters, keeping CPU prompt processing bounded while the
complete stored chunks remain available in the derived index.
suggested **strongest findings** question also reads the report's canonical
executive-summary section directly, so a small model cannot replace its source
IDs with filenames or prompt text and cause an otherwise available summary to
be withheld.

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

## API/frontend integration

The repository launcher creates the separate environment, installs this
module's requirements, exports its interpreter to Django and starts the app:

```bash
./dev.sh
```

On Windows, `dev.cmd` delegates to Git Bash and uses a short RAG environment
path automatically. On macOS/Linux, run `./dev.sh` directly. Manual activation
is needed only when using this engine outside the full repository launcher.

The API endpoints are:

```text
GET  /api/cases/<CASE_ID>/assistant/status/
POST /api/cases/<CASE_ID>/assistant/ask/   {"question": "..."}
```

The status and answer endpoints never enumerate another case. Answers include
validated cited sources, supporting evidence IDs, retrieved-but-uncited
sources, deterministic evidence relationships and warnings. The frontend links
evidence citations back to their evidence pages and official legal citations
to their primary-source URLs.

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
