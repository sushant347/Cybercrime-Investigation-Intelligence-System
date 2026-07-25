"""System settings - engine configuration exposed READ-ONLY (the engine owns
its tunables; the platform only displays them)."""
from dataclasses import fields
from pathlib import Path

from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import require

from .. import engine


def _dataclass_dict(instance) -> dict:
    out = {}
    for f in fields(instance):
        value = getattr(instance, f.name)
        if isinstance(value, Path):
            value = str(value)
        elif isinstance(value, frozenset):
            value = sorted(value)
        elif isinstance(value, dict):
            value = {str(k): v for k, v in value.items()}
        elif isinstance(value, tuple):
            value = list(value)
        out[f.name] = value
    return out


class SystemSettingsView(APIView):
    permission_classes = (require("settings.view"),)

    def get(self, request):
        ecfg = _dataclass_dict(engine.evidence_config())
        icfg = _dataclass_dict(engine.investigation_config())
        return Response(
            {
                "ocr": {
                    k: ecfg[k]
                    for k in (
                        "ocr_lang", "ocr_version", "ocr_timeout_seconds",
                        "low_confidence_threshold", "strict_empty_ocr",
                        "pdf_render_dpi", "pdf_max_pages",
                    )
                    if k in ecfg
                },
                "preprocessing": {
                    k: v for k, v in ecfg.items()
                    if "threshold" in k or "dimension" in k or "deskew" in k
                },
                "storage": {
                    k: v for k, v in ecfg.items()
                    if k.endswith(("_dir", "_csv")) or k == "max_file_size_bytes"
                },
                "supported_extensions": ecfg.get("supported_extensions", []),
                "investigation": icfg,
                "health": engine.engine_health(),
            }
        )
