"""Evidence management: upload (Phase-1 pipeline), artifacts, download."""
import re
import tempfile
from pathlib import Path

from django.http import FileResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import require

from .. import engine
from ..pagination import DefaultPagination
from ..serializers import (
    EvidenceUploadSerializer,
    UrlEvidenceSerializer,
    job_payload,
)
from ..store import activity, jobs


class EvidenceListView(APIView):
    permission_classes = (require("evidence.view"),)

    def get(self, request, case_id: str):
        rows = engine.list_evidence(case_id)
        q = request.query_params.get("search", "").lower()
        if q:
            rows = [
                r for r in rows
                if q in r.get("original_file_name", "").lower()
                or q in r.get("evidence_id", "").lower()
            ]
        st = request.query_params.get("status")
        if st:
            rows = [r for r in rows if r.get("status") == st]
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response(page)


class EvidenceUploadView(APIView):
    permission_classes = (require("evidence.upload"),)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        serializer = EvidenceUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        suffix = Path(upload.name).suffix.lower()
        cfg = engine.evidence_config()
        if suffix not in cfg.supported_extensions:
            return Response(
                {"detail": f"Unsupported file type '{suffix}'."}, status=400
            )
        if upload.size > cfg.max_file_size_bytes:
            return Response({"detail": "File exceeds the 50 MB limit."}, status=400)

        # Persist to a temp file the engine can acquire (it re-hashes it).
        tmp_dir = Path(tempfile.mkdtemp(prefix="ciis_upload_"))
        tmp_path = tmp_dir / upload.name
        with open(tmp_path, "wb") as target:
            for chunk in upload.chunks():
                target.write(chunk)

        job = jobs.start("evidence_processing", case_id=case_id, detail=upload.name)
        engine.submit_evidence_job(
            job["id"], str(tmp_path), case_id,
            serializer.validated_data["notes"], "",
        )
        activity.record(module="evidence", action="upload",
                        case_id=case_id, detail=upload.name)
        return Response(job_payload(job), status=202)


class EvidenceUrlView(APIView):
    """Submit a **link** as evidence (no file upload).

    The URL is written to a small ``.url`` artifact and pushed through the same
    Phase-1 pipeline as a file, so it is hashed for chain of custody, stored,
    and entity-extracted. The link then participates in threat-intelligence
    scoring and cross-case correlation like any other entity.
    """

    permission_classes = (require("evidence.upload"),)

    def post(self, request, case_id: str):
        if engine.get_case(case_id) is None:
            return Response({"detail": "Case not found."}, status=404)
        serializer = UrlEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.validated_data["url"]

        # Persist the link as a .url text artifact the engine can acquire.
        tmp_dir = Path(tempfile.mkdtemp(prefix="ciis_url_"))
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[:60] or "link"
        tmp_path = tmp_dir / f"{safe_name}.url"
        tmp_path.write_text(f"{url}\n", encoding="utf-8")

        job = jobs.start("evidence_processing", case_id=case_id, detail=url)
        engine.submit_evidence_job(
            job["id"], str(tmp_path), case_id,
            serializer.validated_data["notes"], "",
        )
        activity.record(module="evidence", action="submit_url",
                        case_id=case_id, detail=url)
        return Response(job_payload(job), status=202)


class EvidenceDetailView(APIView):
    """Chain-of-custody row + every Phase-1 artifact for one evidence item."""

    permission_classes = (require("evidence.view"),)

    def get(self, request, case_id: str, evidence_id: str):
        row = engine.get_evidence(evidence_id)
        if row is None or row.get("case_id") != case_id:
            return Response({"detail": "Evidence not found."}, status=404)
        return Response(
            {
                "record": row,  # sha256 before/after, hash_verified, custody times
                "ocr": engine.evidence_ocr(case_id, evidence_id),
                "forensics": engine.forensics_artifacts(case_id, evidence_id),
            }
        )


class EvidenceDownloadView(APIView):
    permission_classes = (require("evidence.view"),)

    def get(self, request, case_id: str, evidence_id: str):
        row = engine.get_evidence(evidence_id)
        if row is None or row.get("case_id") != case_id:
            return Response({"detail": "Evidence not found."}, status=404)
        path = engine.original_path(row)
        if not path.is_file():
            return Response({"detail": "Original file missing from storage."}, status=404)
        activity.record(module="evidence", action="download",
                        case_id=case_id, detail=evidence_id)
        return FileResponse(
            open(path, "rb"), as_attachment=request.query_params.get("preview") != "1",
            filename=row["original_file_name"],
        )


class JobStatusView(APIView):
    permission_classes = (require("evidence.view"),)

    def get(self, request, job_id: int):
        job = jobs.get(job_id)
        if job is None:
            return Response({"detail": "Job not found."}, status=404)
        return Response(job_payload(job))


class JobListView(APIView):
    """Processing status feed for the dashboard."""

    permission_classes = (require("evidence.view"),)

    def get(self, request):
        rows = jobs.list(case_id=request.query_params.get("case_id", ""))
        st = request.query_params.get("status")
        if st:
            rows = [r for r in rows if r.get("status") == st]
        payload = [job_payload(r) for r in rows]
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(payload, request)
        return paginator.get_paginated_response(page)
