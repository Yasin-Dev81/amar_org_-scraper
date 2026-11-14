"""Parser for individual statistical record detail pages."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from src.utils import (
    normalize_persian_text,
    parse_jalali_date,
    extract_reference_year,
    normalize_url,
    parse_file_size_string,
)


class ParsedAttachment(BaseModel):
    download_url: str
    file_id: int | None = None
    reported_file_name: str | None = None
    reported_format: str | None = None
    reported_size_str: str | None = None
    reported_size_bytes: int | None = None
    release_type: str | None = None
    publication_date_fa: str | None = None
    source: str | None = None


class ParsedRecord(BaseModel):
    record_id: int
    record_url: str
    title_fa: str
    description: str | None = None
    source_category: str | None = None
    statistical_period: str | None = None
    periodicity: str | None = None
    publication_date_fa: str | None = None
    publication_date_iso: str | None = None
    gregorian_date_iso: str | None = None
    reference_year: int | None = None
    source: str | None = None
    release_type: str | None = None
    original_keywords: list[str] = Field(default_factory=list)
    attachments: list[ParsedAttachment] = Field(default_factory=list)


def parse_record_html(html_content: str, record_url: str) -> ParsedRecord:
    """Parse HTML content of a statistical record detail page."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract record ID from URL
    match_id = re.search(r"/statid/(\d+)", record_url)
    record_id = int(match_id.group(1)) if match_id else 0

    # 1. Title
    title_el = (
        soup.find("h5", class_="title-style")
        or soup.find("div", class_="main-statistics-detail")
        or soup.find("h1")
    )
    title_fa = ""
    if title_el:
        link = title_el.find("a")
        title_fa = (link.get_text() if link else title_el.get_text()).strip()
    if not title_fa and soup.title:
        title_fa = soup.title.get_text().strip()
    title_fa = normalize_persian_text(title_fa)

    # 2. Key-Value Info Fields
    source_category = None
    statistical_period = None
    periodicity = None
    description = None

    for div in soup.find_all("div", class_="each-list-type"):
        text = normalize_persian_text(div.get_text())
        if "موضوع:" in text:
            source_category = text.replace("موضوع:", "").strip()
        elif "زمان آماری:" in text:
            statistical_period = text.replace("زمان آماری:", "").strip()
        elif "دوره ی انتشار:" in text or "دوره انتشار:" in text:
            periodicity = text.split(":")[-1].strip()

    # Meta keywords / description if available
    keywords_meta = soup.find("meta", attrs={"name": "keywords"})
    original_keywords: list[str] = []
    if keywords_meta and keywords_meta.get("content"):
        original_keywords = [
            k.strip() for k in keywords_meta["content"].split("،") if k.strip()
        ]

    desc_meta = soup.find("meta", attrs={"name": "description"})
    if desc_meta and desc_meta.get("content"):
        description = normalize_persian_text(desc_meta["content"])

    # 3. Attachments extraction
    attachments: list[ParsedAttachment] = []
    seen_urls: set[str] = set()

    # Container boxes e.g. p.border-box
    boxes = soup.find_all("p", class_=lambda c: c and "border-box" in c)
    if not boxes:
        # Fallback: look for downloadable anchors directly
        boxes = soup.find_all("div", class_="inner-statistics-data-info") or [soup]

    for box in boxes:
        # Find downloadable anchors in this box
        anchors = box.find_all("a", href=True)
        for a in anchors:
            href = a["href"]
            is_downloadable = (
                "downloadable" in a.get("class", [])
                or a.has_attr("download")
                or any(ext in href.lower() for ext in [".xls", ".xlsx", ".pdf", ".zip", ".rar", ".csv"])
            )
            if not is_downloadable:
                continue

            full_url = normalize_url(href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # File ID
            file_id_str = a.get("data-id")
            file_id = int(file_id_str) if (file_id_str and file_id_str.isdigit()) else None

            # Look for adjacent metadata spans in the same box
            box_text = box.get_text()
            reported_size_str = None
            release_type = None
            source = None
            pub_date_fa = None

            size_match = re.search(r"حجم\s*:\s*([\d\.]+\s*[KMGBkmgb]+)", box_text)
            if size_match:
                reported_size_str = size_match.group(1).strip()

            rel_match = re.search(r"نوع انتشار\s*:\s*([^:\n\r]+)", box_text)
            if rel_match:
                release_type = normalize_persian_text(rel_match.group(1).split("منبع")[0])

            src_match = re.search(r"منبع\s*:\s*([^:\n\r]+)", box_text)
            if src_match:
                source = normalize_persian_text(src_match.group(1).split("زمان")[0])

            date_match = re.search(r"زمان انتشار\s*:\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})", box_text)
            if date_match:
                pub_date_fa = date_match.group(1)

            # Format from icon image or extension
            img = box.find("img")
            reported_fmt = None
            if img and img.get("src"):
                img_src = img["src"].lower()
                for fmt in ["pdf", "excel", "word", "zip", "csv"]:
                    if fmt in img_src:
                        reported_fmt = fmt.upper()
                        break
            if not reported_fmt:
                reported_fmt = Path(urlparse(full_url).path).suffix.lstrip(".").upper()

            reported_filename = Path(urlparse(full_url).path).name

            attachments.append(
                ParsedAttachment(
                    download_url=full_url,
                    file_id=file_id,
                    reported_file_name=reported_filename,
                    reported_format=reported_fmt,
                    reported_size_str=reported_size_str,
                    reported_size_bytes=parse_file_size_string(reported_size_str),
                    release_type=release_type,
                    publication_date_fa=pub_date_fa,
                    source=source,
                )
            )

    # Global date/source from first attachment if available
    first_att = attachments[0] if attachments else None
    pub_date_fa = first_att.publication_date_fa if first_att else None
    source = first_att.source if first_att else (source or "درگاه ملی آمار")
    release_type = first_att.release_type if first_att else release_type

    jalali_iso, gregorian_iso = parse_jalali_date(pub_date_fa)
    ref_year = (
        extract_reference_year(statistical_period)
        or extract_reference_year(title_fa)
        or extract_reference_year(pub_date_fa)
    )

    return ParsedRecord(
        record_id=record_id,
        record_url=normalize_url(record_url),
        title_fa=title_fa,
        description=description,
        source_category=source_category,
        statistical_period=statistical_period,
        periodicity=periodicity,
        publication_date_fa=pub_date_fa,
        publication_date_iso=jalali_iso,
        gregorian_date_iso=gregorian_iso,
        reference_year=ref_year,
        source=source,
        release_type=release_type,
        original_keywords=original_keywords,
        attachments=attachments,
    )
