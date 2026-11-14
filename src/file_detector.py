"""File format detector using magic bytes, content signatures, MIME types, and extensions."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import NamedTuple
import filetype


class DetectionResult(NamedTuple):
    format_name: str          # e.g., 'PDF', 'XLSX', 'ZIP', 'CSV', 'HTML'
    mime_type: str            # e.g., 'application/pdf'
    extension: str            # e.g., '.pdf'
    is_binary: bool           # True if binary, False if text/json/csv
    is_html_error: bool       # True if response is HTML error page instead of dataset


# Common magic byte signatures
SIGNATURES: list[tuple[bytes, str, str, str]] = [
    (b"%PDF", "PDF", "application/pdf", ".pdf"),
    (b"Rar!\x1a\x07\x00", "RAR", "application/x-rar-compressed", ".rar"),
    (b"Rar!\x1a\x07\x01\x00", "RAR", "application/x-rar-compressed", ".rar"),
    (b"7z\xbc\xaf\x27\x1c", "7Z", "application/x-7z-compressed", ".7z"),
    (b"\x1f\x8b\x08", "GZIP", "application/gzip", ".gz"),
    (b"BZh", "BZIP2", "application/x-bzip2", ".bz2"),
    (b"$FL2", "SAV", "application/x-spss-sav", ".sav"),
    (b"$FL3", "SAV", "application/x-spss-sav", ".sav"),
    (b"\x00\x00\x27\x0a", "SHP", "application/x-shapefile", ".shp"),
    (b"SQLite format 3\x00", "SQLITE", "application/x-sqlite3", ".sqlite"),
]

OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_SIGNATURE = b"PK\x03\x04"


def _inspect_zip_content(header_bytes: bytes, file_path: Path | None = None) -> tuple[str, str, str]:
    """Inspect ZIP file entries to distinguish DOCX, XLSX, PPTX, or standard ZIP."""
    if file_path and file_path.exists():
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                if any(n.startswith("xl/") for n in names):
                    return "XLSX", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
                if any(n.startswith("word/") for n in names):
                    return "DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
                if any(n.startswith("ppt/") for n in names):
                    return "PPTX", "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"
                if any(n.endswith(".kml") for n in names):
                    return "KMZ", "application/vnd.google-earth.kmz", ".kmz"
        except Exception:
            pass
    # If header contains markers
    if b"xl/" in header_bytes or b"workbook.xml" in header_bytes:
        return "XLSX", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
    if b"word/" in header_bytes or b"document.xml" in header_bytes:
        return "DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
    if b"ppt/" in header_bytes:
        return "PPTX", "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"
    return "ZIP", "application/zip", ".zip"


def _inspect_ole2_content(header_bytes: bytes, file_path: Path | None = None) -> tuple[str, str, str]:
    """Inspect OLE2 Compound Document for legacy Microsoft formats (XLS, DOC, PPT)."""
    # Legacy Excel / Word / PowerPoint signature substrings
    if b"Workbook" in header_bytes or b"Book" in header_bytes:
        return "XLS", "application/vnd.ms-excel", ".xls"
    if b"WordDocument" in header_bytes:
        return "DOC", "application/msword", ".doc"
    if b"PowerPoint Document" in header_bytes:
        return "PPT", "application/vnd.ms-powerpoint", ".ppt"
    return "XLS", "application/vnd.ms-excel", ".xls"  # Most common in amar.org.ir statistical downloads


def is_html_content(content: bytes) -> bool:
    """Check if binary content is actually HTML (e.g. 404/500/login page)."""
    sample = content[:4096].lower().strip()
    return (
        sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or b"<head>" in sample
        or b"<body>" in sample
        or b"<title>" in sample
    )


def detect_file_format(
    file_bytes: bytes | None = None,
    file_path: Path | None = None,
    content_type_header: str | None = None,
    suggested_filename: str | None = None,
) -> DetectionResult:
    """Determine the file format using magic bytes, headers, and filename."""
    header = b""
    if file_bytes:
        header = file_bytes[:4096]
    elif file_path and file_path.exists():
        try:
            with open(file_path, "rb") as f:
                header = f.read(4096)
        except Exception:
            pass

    # 1. Check if server returned an HTML page instead of the requested file
    if header and is_html_content(header):
        return DetectionResult(
            format_name="HTML",
            mime_type="text/html",
            extension=".html",
            is_binary=False,
            is_html_error=True,
        )

    # 2. Check Magic Byte Signatures
    for sig, name, mime, ext in SIGNATURES:
        if header.startswith(sig):
            return DetectionResult(
                format_name=name,
                mime_type=mime,
                extension=ext,
                is_binary=True,
                is_html_error=False,
            )

    # Check ZIP / Office Open XML
    if header.startswith(ZIP_SIGNATURE):
        name, mime, ext = _inspect_zip_content(header, file_path)
        return DetectionResult(
            format_name=name,
            mime_type=mime,
            extension=ext,
            is_binary=True,
            is_html_error=False,
        )

    # Check OLE2 Compound File (legacy XLS/DOC/PPT)
    if header.startswith(OLE2_SIGNATURE):
        name, mime, ext = _inspect_ole2_content(header, file_path)
        return DetectionResult(
            format_name=name,
            mime_type=mime,
            extension=ext,
            is_binary=True,
            is_html_error=False,
        )

    # 3. Third-party filetype detector
    if header:
        kind = filetype.guess(header)
        if kind is not None:
            return DetectionResult(
                format_name=kind.extension.upper(),
                mime_type=kind.mime,
                extension=f".{kind.extension}",
                is_binary=True,
                is_html_error=False,
            )

    # 4. Text checks (CSV, JSON, XML, TXT)
    if header:
        try:
            sample_str = header.decode("utf-8", errors="ignore").strip()
            if sample_str.startswith("{") or sample_str.startswith("["):
                return DetectionResult("JSON", "application/json", ".json", False, False)
            if sample_str.startswith("<?xml") or (sample_str.startswith("<") and ">" in sample_str):
                return DetectionResult("XML", "application/xml", ".xml", False, False)
            if "," in sample_str or ";" in sample_str or "\t" in sample_str:
                lines = sample_str.split("\n")
                if len(lines) > 1 and ("," in lines[0] or ";" in lines[0] or "\t" in lines[0]):
                    return DetectionResult("CSV", "text/csv", ".csv", False, False)
        except Exception:
            pass

    # 5. Fallback: inspect suggested filename or Content-Type header
    name_to_check = (suggested_filename or "").lower()
    if "." in name_to_check:
        ext = Path(name_to_check).suffix.lower()
        ext_map = {
            ".xlsx": ("XLSX", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", True),
            ".xls": ("XLS", "application/vnd.ms-excel", True),
            ".pdf": ("PDF", "application/pdf", True),
            ".csv": ("CSV", "text/csv", False),
            ".zip": ("ZIP", "application/zip", True),
            ".rar": ("RAR", "application/x-rar-compressed", True),
            ".7z": ("7Z", "application/x-7z-compressed", True),
            ".docx": ("DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", True),
            ".doc": ("DOC", "application/msword", True),
            ".pptx": ("PPTX", "application/vnd.openxmlformats-officedocument.presentationml.presentation", True),
            ".ppt": ("PPT", "application/vnd.ms-powerpoint", True),
            ".sav": ("SAV", "application/x-spss-sav", True),
            ".dta": ("DTA", "application/x-stata-dta", True),
            ".shp": ("SHP", "application/x-shapefile", True),
            ".kml": ("KML", "application/vnd.google-earth.kml+xml", False),
            ".kmz": ("KMZ", "application/vnd.google-earth.kmz", True),
            ".geojson": ("GEOJSON", "application/geo+json", False),
            ".json": ("JSON", "application/json", False),
            ".xml": ("XML", "application/xml", False),
            ".txt": ("TXT", "text/plain", False),
        }
        if ext in ext_map:
            fmt, mime, binary = ext_map[ext]
            return DetectionResult(fmt, mime, ext, binary, False)

    # 6. Default unknown binary / generic
    return DetectionResult(
        format_name="BIN",
        mime_type="application/octet-stream",
        extension=".bin",
        is_binary=True,
        is_html_error=False,
    )
