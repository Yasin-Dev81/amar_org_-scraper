"""Parser for statistical listing pages and pagination links."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from src.utils import normalize_url, normalize_persian_text


class DiscoveredRecordBrief(BaseModel):
    record_id: int
    url: str
    title: str


class DiscoveredCategoryBrief(BaseModel):
    category_id: int
    name_fa: str
    url: str
    record_count: int | None = None


class ParsedListingPage(BaseModel):
    page_url: str
    current_page_number: int | None = None
    records: list[DiscoveredRecordBrief] = Field(default_factory=list)
    pagination_urls: list[str] = Field(default_factory=list)
    discovered_categories: list[DiscoveredCategoryBrief] = Field(default_factory=list)
    rss_urls: list[str] = Field(default_factory=list)


def parse_listing_page_html(html_content: str, page_url: str) -> ParsedListingPage:
    """Parse a listing page to discover statistical records, pagination links, and categories."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Current page number from URL
    match_page = re.search(r"/currentpage/(\d+)", page_url)
    curr_page = int(match_page.group(1)) if match_page else 1

    # 1. Discover record links
    records: list[DiscoveredRecordBrief] = []
    seen_ids: set[int] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        match_stat = re.search(r"/statistical-information/statid/(\d+)", href)
        if match_stat:
            rec_id = int(match_stat.group(1))
            if rec_id not in seen_ids:
                seen_ids.add(rec_id)
                title = normalize_persian_text(a.get_text())
                records.append(
                    DiscoveredRecordBrief(
                        record_id=rec_id,
                        url=normalize_url(href),
                        title=title,
                    )
                )

    # 2. Discover pagination links
    pagination_urls_set: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/statistical-information/currentpage/" in href or "currentpage=" in href:
            full = normalize_url(href)
            pagination_urls_set.add(full)

    # 3. Discover category links (e.g. ?catid=3503 or /catid/3005)
    categories: list[DiscoveredCategoryBrief] = []
    seen_cat_ids: set[int] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        match_cat = re.search(r"catid[=/](\d+)", href)
        if match_cat and "statistical-information" in href:
            cat_id = int(match_cat.group(1))
            if cat_id not in seen_cat_ids:
                seen_cat_ids.add(cat_id)
                raw_text = a.get_text().strip()
                # Extract count if present e.g. "آمارهای جمعیتی و اجتماعی(890)"
                match_count = re.search(r"\((\d+)\)", raw_text)
                count = int(match_count.group(1)) if match_count else None
                name_fa = normalize_persian_text(re.sub(r"\(\d+\)", "", raw_text))
                categories.append(
                    DiscoveredCategoryBrief(
                        category_id=cat_id,
                        name_fa=name_fa,
                        url=normalize_url(href),
                        record_count=count,
                    )
                )

    # 4. Discover RSS feeds
    rss_urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "rss" in href.lower() or "ashx" in href.lower():
            rss_urls.append(normalize_url(href))

    return ParsedListingPage(
        page_url=normalize_url(page_url),
        current_page_number=curr_page,
        records=records,
        pagination_urls=sorted(list(pagination_urls_set)),
        discovered_categories=categories,
        rss_urls=sorted(list(set(rss_urls))),
    )
