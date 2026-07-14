"""Module 6 - Forensic Metadata Extraction service.

Extracts container metadata from evidence files, read-only:

* Images  - EXIF (camera make/model, device, software, dates, orientation, GPS)
* PDFs    - author, producer, creator, dates, page count (via PyMuPDF)
* Office  - core/app properties parsed straight from the OOXML zip
            (``docProps/core.xml`` + ``docProps/app.xml``) - no extra
            dependency required; works for .docx/.xlsx/.pptx

Filesystem timestamps are always captured, and cross-source consistency
notes are produced for the forgery/confidence modules.
"""

from __future__ import annotations

import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree

from PIL import ExifTags, Image

from ...logger import get_logger
from ...utils import file_extension
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .models import (
    FileSystemMetadata,
    GPSData,
    ImageMetadata,
    MetadataReport,
    OfficeMetadata,
    PDFMetadata,
)

MODULE = "metadata_extraction"

_IMAGE_EXT = {".png", ".jpg", ".jpeg"}
_OFFICE_EXT = {".docx", ".xlsx", ".pptx"}

_CORE_NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}
_APP_NS = {"ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"}


class MetadataExtractionService:
    """Structured, read-only metadata extraction for all evidence types."""

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._log = get_logger("forensics.metadata")

    # ------------------------------------------------------------------ public

    def extract(
        self,
        source_path: Path,
        *,
        evidence_id: str,
        case_id: str,
        persist: bool = True,
    ) -> MetadataReport:
        started = time.perf_counter()
        errors: List[str] = []
        extension = file_extension(source_path)
        file_type = self._classify(extension)

        report = MetadataReport(
            evidence_id=evidence_id,
            case_id=case_id,
            source_file=source_path.name,
            file_type=file_type,
            filesystem=self._filesystem(source_path, errors),
        )
        if file_type == "image":
            report.image = self._image_metadata(source_path, errors)
        elif file_type == "pdf":
            report.pdf = self._pdf_metadata(source_path, errors)
        elif file_type == "office":
            report.office = self._office_metadata(source_path, errors)

        report.extraction_errors = errors
        report.consistency_notes = self._consistency_notes(report)
        report.analysis_time_ms = round((time.perf_counter() - started) * 1000.0, 1)

        if persist:
            self._repo.save(
                evidence_id, case_id, self._cfg.metadata_report_name, report.model_dump()
            )
            self._audit.record(
                case_id, evidence_id, MODULE, "extracted",
                f"type={file_type} notes={len(report.consistency_notes)} "
                f"errors={len(errors)}",
                duration_ms=report.analysis_time_ms,
            )
        return report

    # -------------------------------------------------------------- extractors

    @staticmethod
    def _classify(extension: str) -> str:
        if extension in _IMAGE_EXT:
            return "image"
        if extension == ".pdf":
            return "pdf"
        if extension in _OFFICE_EXT:
            return "office"
        if extension in {".txt", ".csv"}:
            return "text"
        return "other"

    @staticmethod
    def _filesystem(path: Path, errors: List[str]) -> FileSystemMetadata:
        try:
            stat = path.stat()
            fmt = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()  # noqa: E731
            return FileSystemMetadata(
                file_size_bytes=stat.st_size,
                created=fmt(stat.st_ctime),
                modified=fmt(stat.st_mtime),
                accessed=fmt(stat.st_atime),
            )
        except OSError as exc:
            errors.append(f"filesystem stat failed: {exc}")
            return FileSystemMetadata()

    def _image_metadata(self, path: Path, errors: List[str]) -> ImageMetadata:
        meta = ImageMetadata()
        try:
            with Image.open(path) as img:
                exif = img.getexif()
        except OSError as exc:
            errors.append(f"image open failed: {exc}")
            return meta
        if not exif:
            return meta
        meta.has_exif = True
        tags = {}
        for tag_id, value in exif.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            tags[name] = str(value)
        meta.all_tags = tags
        meta.camera_make = tags.get("Make", "").strip()
        meta.camera_model = tags.get("Model", "").strip()
        meta.device = " ".join(x for x in (meta.camera_make, meta.camera_model) if x)
        meta.software = tags.get("Software", "").strip()
        meta.date_modified = tags.get("DateTime", "")
        meta.orientation = tags.get("Orientation", "")
        # DateTimeOriginal lives in the EXIF IFD
        try:
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            meta.date_created = str(
                exif_ifd.get(ExifTags.Base.DateTimeOriginal, tags.get("DateTime", ""))
            )
        except Exception:  # noqa: BLE001 - IFD access varies by Pillow version
            meta.date_created = tags.get("DateTime", "")
        meta.gps = self._gps(exif, errors)
        return meta

    @staticmethod
    def _gps(exif, errors: List[str]) -> Optional[GPSData]:
        try:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        except Exception:  # noqa: BLE001
            return None
        if not gps_ifd:
            return None
        raw = {ExifTags.GPSTAGS.get(k, str(k)): str(v) for k, v in gps_ifd.items()}
        data = GPSData(raw=raw)

        def _to_deg(values, ref, negative_refs) -> Optional[float]:
            try:
                d, m, s = (float(v) for v in values)
                deg = d + m / 60.0 + s / 3600.0
                return -deg if str(ref) in negative_refs else deg
            except (TypeError, ValueError, ZeroDivisionError):
                return None

        lat = gps_ifd.get(2)   # GPSLatitude
        lat_ref = gps_ifd.get(1, "N")
        lon = gps_ifd.get(4)   # GPSLongitude
        lon_ref = gps_ifd.get(3, "E")
        if lat is not None and lon is not None:
            data.latitude = _to_deg(lat, lat_ref, {"S"})
            data.longitude = _to_deg(lon, lon_ref, {"W"})
        alt = gps_ifd.get(6)
        if alt is not None:
            try:
                data.altitude_m = float(alt)
            except (TypeError, ValueError):
                pass
        return data

    def _pdf_metadata(self, path: Path, errors: List[str]) -> PDFMetadata:
        meta = PDFMetadata()
        try:
            import fitz  # PyMuPDF - already a project dependency
        except ImportError:
            errors.append("PyMuPDF not installed - PDF metadata skipped")
            return meta
        try:
            with fitz.open(path) as doc:
                info = doc.metadata or {}
                meta.author = info.get("author", "") or ""
                meta.producer = info.get("producer", "") or ""
                meta.creator = info.get("creator", "") or ""
                meta.title = info.get("title", "") or ""
                meta.subject = info.get("subject", "") or ""
                meta.creation_date = info.get("creationDate", "") or ""
                meta.modification_date = info.get("modDate", "") or ""
                meta.page_count = doc.page_count
                meta.encrypted = bool(doc.is_encrypted)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"PDF metadata extraction failed: {exc}")
        return meta

    def _office_metadata(self, path: Path, errors: List[str]) -> OfficeMetadata:
        """Parse OOXML docProps directly from the zip container (read-only)."""
        meta = OfficeMetadata()
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "docProps/core.xml" in names:
                    root = ElementTree.fromstring(archive.read("docProps/core.xml"))
                    get = lambda xpath, ns: (root.findtext(xpath, "", ns) or "")  # noqa: E731
                    meta.author = get("dc:creator", _CORE_NS)
                    meta.last_modified_by = get("cp:lastModifiedBy", _CORE_NS)
                    meta.revision_number = get("cp:revision", _CORE_NS)
                    meta.title = get("dc:title", _CORE_NS)
                    meta.created = get("dcterms:created", _CORE_NS)
                    meta.modified = get("dcterms:modified", _CORE_NS)
                if "docProps/app.xml" in names:
                    root = ElementTree.fromstring(archive.read("docProps/app.xml"))
                    meta.company = root.findtext("ep:Company", "", _APP_NS) or ""
                    meta.application = root.findtext("ep:Application", "", _APP_NS) or ""
        except (zipfile.BadZipFile, OSError, ElementTree.ParseError) as exc:
            errors.append(f"Office metadata extraction failed: {exc}")
        return meta

    # ------------------------------------------------------------- consistency

    @staticmethod
    def _consistency_notes(report: MetadataReport) -> List[str]:
        notes: List[str] = []
        img = report.image
        if img is not None:
            if not img.has_exif:
                notes.append(
                    "Image carries no EXIF metadata (typical for screenshots and "
                    "messaging-app exports; one less authenticity signal)."
                )
            else:
                if img.date_created and img.date_modified and \
                        img.date_created != img.date_modified:
                    notes.append(
                        f"EXIF capture time ({img.date_created}) differs from "
                        f"EXIF modification time ({img.date_modified})."
                    )
                if img.software:
                    notes.append(f"Image was processed by software: '{img.software}'.")
        office = report.office
        if office is not None:
            if office.author and office.last_modified_by and \
                    office.author != office.last_modified_by:
                notes.append(
                    f"Document author ('{office.author}') and last editor "
                    f"('{office.last_modified_by}') differ."
                )
        pdf = report.pdf
        if pdf is not None:
            if pdf.creation_date and pdf.modification_date and \
                    pdf.creation_date != pdf.modification_date:
                notes.append("PDF was modified after creation.")
        return notes
