"""Command-line interface for the standalone RAG assistant."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from .ciis_rag.adapters import load_case_bundle
from .ciis_rag.assistant import AssistantService, answer_without_retrieval
from .ciis_rag.core.config import RAGConfig
from .ciis_rag.core.exceptions import RAGError
from .ciis_rag.generation import OllamaAnswerGenerator
from .ciis_rag.indexing import ChromaVectorStore, IndexService, ManifestRepository
from .ciis_rag.retrieval import RetrievalService


def _config(args) -> RAGConfig:
    config = RAGConfig.from_env()
    changes = {}
    if args.storage_dir:
        changes["storage_dir"] = Path(args.storage_dir).resolve()
    if getattr(args, "model", None):
        changes["ollama_model"] = args.model
    if getattr(args, "ollama_host", None):
        changes["ollama_host"] = args.ollama_host.rstrip("/")
    if getattr(args, "top_k", None):
        changes["top_k"] = args.top_k
    config = replace(config, **changes)
    config.validate()
    return config


def _services(config: RAGConfig):
    store = ChromaVectorStore(config)
    indexing = IndexService(
        config, store, ManifestRepository(config.manifest_dir)
    )
    retrieval = RetrievalService(config, store)
    return store, indexing, retrieval


def _add_case_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-json", required=True, help="Current CIIE case JSON")
    parser.add_argument(
        "--artifact-dir", required=True,
        help="Directory containing the case's versioned Phase-2 JSON artifacts",
    )
    parser.add_argument(
        "--storage-dir", default=None,
        help="Derived RAG storage (default: CIIS_RAG_STORAGE_DIR)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone CIIE RAG assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Synchronize one case's derived index")
    _add_case_arguments(build)

    status = subparsers.add_parser("status", help="Report missing, stale, or fresh index")
    _add_case_arguments(status)

    ask = subparsers.add_parser("ask", help="Synchronize and ask one grounded question")
    ask.add_argument("question")
    _add_case_arguments(ask)
    ask.add_argument("--model", default=None)
    ask.add_argument("--ollama-host", default=None)
    ask.add_argument("--top-k", type=int, default=None)

    chat = subparsers.add_parser("chat", help="Interactive case-scoped question loop")
    _add_case_arguments(chat)
    chat.add_argument("--model", default=None)
    chat.add_argument("--ollama-host", default=None)
    chat.add_argument("--top-k", type=int, default=None)
    return parser


def _execute(args: argparse.Namespace) -> int:
    config = _config(args)
    bundle = load_case_bundle(args.case_json, args.artifact_dir)
    if args.command == "ask":
        direct_answer = answer_without_retrieval(bundle, args.question)
        if direct_answer is not None:
            print(json.dumps(asdict(direct_answer), indent=2))
            return 0
    _store, indexing, retrieval = _services(config)

    if args.command == "build":
        result = asdict(indexing.sync(bundle))
        result["warnings"] = list(bundle.warnings)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps({
            "case_id": bundle.case_id,
            "status": indexing.status(bundle),
            "source_hashes": bundle.source_hashes,
            "warnings": list(bundle.warnings),
        }, indent=2, sort_keys=True))
        return 0

    assistant = AssistantService(
        indexing, retrieval, OllamaAnswerGenerator(config)
    )
    if args.command == "ask":
        print(json.dumps(asdict(assistant.ask(bundle, args.question)), indent=2))
        return 0

    print(f"CIIE RAG chat for {bundle.case_id}. Type 'exit' to stop.")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.lower() in {"exit", "quit"}:
            return 0
        if question:
            response = assistant.ask(bundle, question)
            print(json.dumps(asdict(response), indent=2))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _execute(args)
    except RAGError as exc:
        print(json.dumps({
            "status": "error",
            "error_type": type(exc).__name__,
            "detail": str(exc),
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
