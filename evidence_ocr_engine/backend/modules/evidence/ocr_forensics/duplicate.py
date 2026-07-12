"""Duplicate evidence detection via SHA-256.

Reuses the existing :class:`HashService` to fingerprint each image. A
registry maps ``sha256 -> evidence_id`` so re-uploaded evidence is detected
and its previous OCR result can be reused (skipping OCR). The registry is an
injected mapping, so callers may back it with the existing ``evidence.csv``
or an in-memory dict - this module stores nothing itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, MutableMapping, Optional

from .config import OCRForensicConfig
from .schemas import DuplicateInfo


class DuplicateDetector:
    """SHA-256 based duplicate-image detection."""

    def __init__(
        self,
        config: OCRForensicConfig | None = None,
        hash_service: object = None,
        registry: Optional[MutableMapping[str, str]] = None,
    ) -> None:
        self._cfg = config or OCRForensicConfig()
        self._hash = hash_service or self._default_hash_service()
        #: sha256 -> first evidence_id that carried this image.
        self._registry: MutableMapping[str, str] = (
            registry if registry is not None else {})

    def check(
        self, image_path: Path | str, evidence_id: str = ""
    ) -> DuplicateInfo:
        """Fingerprint the image and report whether it was seen before.

        Registers the (hash -> evidence_id) mapping on first sight. When
        ``dedup_enabled`` is false, the hash is still computed (forensic
        integrity) but duplicates are not flagged/reused.
        """
        sha = self._hash.sha256_file(image_path) if self._hash else ""
        info = DuplicateInfo(image_sha256=sha)
        if not sha or not self._cfg.dedup_enabled:
            if sha and evidence_id:
                self._registry.setdefault(sha, evidence_id)
            return info

        prior = self._registry.get(sha)
        if prior is not None and prior != evidence_id:
            info.is_duplicate = True
            info.first_seen_evidence_id = prior
            info.reused_ocr = True
        else:
            if evidence_id:
                self._registry.setdefault(sha, evidence_id)
        return info

    @property
    def registry(self) -> Dict[str, str]:
        return dict(self._registry)

    @staticmethod
    def _default_hash_service() -> object:
        try:
            from ..hash_service import HashService
            return HashService()
        except Exception:  # noqa: BLE001
            return None
