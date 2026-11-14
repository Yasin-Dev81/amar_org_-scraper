"""Unit tests for record parser and listing page parser using fixtures."""
from __future__ import annotations

from pathlib import Path
from src.page_parser import parse_listing_page_html
from src.record_parser import parse_record_html


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_listing_page():
    html_path = FIXTURES_DIR / "page_listing.html"
    assert html_path.exists(), "Listing fixture file missing"

    content = html_path.read_text(encoding="utf-8")
    parsed = parse_listing_page_html(content, "https://www.amar.org.ir/statistical-information")

    assert parsed.current_page_number == 1
    assert len(parsed.records) >= 20
    assert any("تولیدکننده" in r.title for r in parsed.records)
    assert any(r.record_id == 58312 for r in parsed.records)
    assert len(parsed.pagination_urls) > 0
    assert any("/currentpage/2" in u for u in parsed.pagination_urls)
    assert len(parsed.discovered_categories) >= 4


def test_parse_record_detail():
    html_path = FIXTURES_DIR / "record_detail.html"
    assert html_path.exists(), "Record fixture file missing"

    content = html_path.read_text(encoding="utf-8")
    record_url = "https://www.amar.org.ir/statistical-information/statid/58312"
    parsed = parse_record_html(content, record_url)

    assert parsed.record_id == 58312
    assert "شاخص قیمت تولیدکننده" in parsed.title_fa
    assert "آمارهای اقتصادی" in (parsed.source_category or "")
    assert "تابستان 1405" in (parsed.statistical_period or "")
    assert parsed.reference_year == 1405
    assert parsed.publication_date_fa == "1405/08/17"
    assert parsed.gregorian_date_iso is not None

    # Check attachments
    assert len(parsed.attachments) == 1
    att = parsed.attachments[0]
    assert att.file_id == 61127
    assert att.download_url == "https://www.amar.org.ir/Portals/0/Articles/shgzrtdamdari05-2.pdf"
    assert att.reported_format == "PDF"
    assert att.reported_size_bytes is not None
