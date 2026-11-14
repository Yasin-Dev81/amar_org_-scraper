"""Unit tests for file format detector."""
from __future__ import annotations

from src.file_detector import detect_file_format, is_html_content


def test_detect_pdf():
    pdf_bytes = b"%PDF-1.7\n4 0 obj\n<<...>>"
    res = detect_file_format(file_bytes=pdf_bytes)
    assert res.format_name == "PDF"
    assert res.extension == ".pdf"
    assert res.is_binary is True
    assert res.is_html_error is False


def test_detect_html_error_page():
    html_bytes = b"<!DOCTYPE html><html><head><title>404 Not Found</title></head><body>Error</body></html>"
    res = detect_file_format(file_bytes=html_bytes)
    assert res.format_name == "HTML"
    assert res.is_html_error is True


def test_detect_zip():
    zip_bytes = b"PK\x03\x04\x14\x00\x00\x00"
    res = detect_file_format(file_bytes=zip_bytes)
    assert res.format_name in ["ZIP", "XLSX", "DOCX"]
    assert res.is_binary is True
    assert res.is_html_error is False


def test_detect_csv_text():
    csv_bytes = b"year,indicator,value\n1400,cpi,150.2\n1401,cpi,190.5"
    res = detect_file_format(file_bytes=csv_bytes)
    assert res.format_name == "CSV"
    assert res.extension == ".csv"
    assert res.is_html_error is False


def test_detect_from_extension_fallback():
    res = detect_file_format(suggested_filename="data_summary.xlsx")
    assert res.format_name == "XLSX"
    assert res.extension == ".xlsx"
