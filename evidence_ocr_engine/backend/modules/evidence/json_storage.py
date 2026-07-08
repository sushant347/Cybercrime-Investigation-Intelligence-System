"""JSON persistence: one file per case containing complete OCR output.

``storage/json/CASE_0001.json`` holds every processed evidence item of the
case with full page/line/bounding-box detail. Writes are atomic (temp file +
rename) so a crash can never corrupt previously stored evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import EvidenceConfig
from .logger import get_logger
from .schemas import EvidenceOCRResult
from .utils import StorageError, utc_now_iso


class JSONCaseStorage:
    """Stores complete OCR results grouped by case."""

    def __init__(self, config: EvidenceConfig) -> None:
        self._dir = config.json_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log = get_logger("json_storage")

    def case_file(self, case_id: str) -> Path:
        """Path of the JSON document for ``case_id`` (e.g. CASE_0001.json)."""
        return self._dir / f"{case_id}.json"

    def save_result(self, result: EvidenceOCRResult) -> Path:
        """Insert or replace one evidence result inside its case document.

        Returns:
            Path of the case JSON file that was written.
        """
        path = self.case_file(result.case_id)
        document = self._load_or_create(result.case_id, path)

        payload = result.model_dump()
        items = document["evidence"]
        for index, existing in enumerate(items):
            if existing.get("evidence_id") == result.evidence_id:
                items[index] = payload  # idempotent re-processing
                break
        else:
            items.append(payload)
        document["updated_at"] = utc_now_iso()
        document["evidence_count"] = len(items)

        self._atomic_write(path, document)
        self._log.info("saved %s -> %s", result.evidence_id, path.name)
        return path

    def load_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Load the full case document, or ``None`` when it does not exist."""
        path = self.case_file(case_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot read case JSON '{path}': {exc}") from exc

    # ---------------------------------------------------------------- internal

    def _load_or_create(self, case_id: str, path: Path) -> Dict[str, Any]:
        if path.exists():
            document = self.load_case(case_id) or {}
            document.setdefault("evidence", [])
            return document
        return {
            "case_id": case_id,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "evidence_count": 0,
            "evidence": [],
        }

    def _atomic_write(self, path: Path, document: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
            tmp_path.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write case JSON '{path}': {exc}") from exc
