"""Versioned index provenance used for stale-index detection."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


MANIFEST_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class IndexManifest:
    schema_version: str
    case_id: str
    embedding_model: str
    chunking_version: str
    source_hashes: dict[str, str]
    chunk_hashes: dict[str, str]


class ManifestRepository:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, case_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id)
        return self._root / f"{safe}.json"

    def load(self, case_id: str) -> IndexManifest | None:
        path = self._path(case_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            manifest = IndexManifest(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        return manifest if manifest.case_id == case_id else None

    def save(self, manifest: IndexManifest) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path(manifest.case_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)
