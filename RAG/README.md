# Legacy RAG location

The maintained standalone engine now lives in
[`rag_assistant_engine/`](../rag_assistant_engine/README.md). This directory is
retained only so existing local references to `RAG/rag_assistant.py` receive the
new command-line interface.

The existing `chroma_db/` directory was produced by the old prototype. It is
preserved locally but ignored because it is stale, uses the legacy document
contract, and may contain evidence text. Build a new case-scoped index through
the maintained engine rather than reusing it.
