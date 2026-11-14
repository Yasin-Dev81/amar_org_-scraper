"""Main crawler engine orchestrating discovery, parsing, and downloading."""
from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any
import httpx

from src.classifier import classify_record
from src.config import AppConfig
from src.database import DatabaseManager
from src.download_manager import DownloadManager
from src.metadata_manager import MetadataManager
from src.page_parser import parse_listing_page_html
from src.pagination import PaginationTraverser
from src.record_parser import parse_record_html


class AmarCrawler:
    """Orchestrates comprehensive discovery of records and file downloads."""

    def __init__(
        self,
        config: AppConfig,
        db: DatabaseManager,
        metadata_mgr: MetadataManager,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.db = db
        self.metadata_mgr = metadata_mgr
        self.logger = logger or logging.getLogger("amar_scraper.crawler")
        self.download_mgr = DownloadManager(config, db, metadata_mgr, self.logger)
        self.session_id = str(uuid.uuid4())[:8]

    def _create_http_client(self) -> httpx.AsyncClient:
        """Create configured HTTPX async client with browser User-Agent and headers."""
        headers = {
            "User-Agent": self.config.website.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fa,en-US;q=0.7,en;q=0.3",
            "Cache-Control": "no-cache",
        }
        return httpx.AsyncClient(
            headers=headers,
            timeout=self.config.scraping.connection_timeout,
            follow_redirects=True,
            verify=self.config.download.verify_ssl,
        )

    async def discover_records(
        self,
        start_urls: list[str] | None = None,
        max_pages: int | None = None,
        max_records: int | None = None,
    ) -> dict[str, int]:
        """Crawl listing pages to discover records and queue their detail pages."""
        urls_to_start = start_urls or self.config.website.start_urls
        traverser = PaginationTraverser(
            db=self.db,
            start_urls=urls_to_start,
            max_pages=max_pages,
            logger=self.logger,
        )

        pages_crawled = 0
        records_found = 0
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO scraping_sessions (session_id, start_time, status) VALUES (?, ?, 'running');",
                (self.session_id, now_iso),
            )

        client = self._create_http_client()
        try:
            self.logger.info(f"Starting discovery session {self.session_id}...")
            while traverser.has_next_page():
                if max_pages and pages_crawled >= max_pages:
                    self.logger.info(f"Reached max pages limit ({max_pages}).")
                    break

                page_url = traverser.get_next_page_url()
                if not page_url:
                    break

                pages_crawled += 1
                self.logger.info(f"Crawling listing page [{pages_crawled}]: {page_url}")

                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        self.logger.warning(f"Failed to fetch page {page_url}: HTTP {resp.status_code}")
                        traverser.record_page_result(page_url, 0)
                        continue

                    parsed_page = parse_listing_page_html(resp.text, page_url)
                    records_count = len(parsed_page.records)
                    records_found += records_count
                    traverser.record_page_result(page_url, records_count)

                    # Store discovered categories
                    for cat in parsed_page.discovered_categories:
                        self.db.upsert_category(
                            category_id=cat.category_id,
                            name_fa=cat.name_fa,
                            url=cat.url,
                            reported_count=cat.record_count,
                        )

                    # Add new pagination URLs to queue
                    traverser.add_discovered_urls(parsed_page.pagination_urls)

                    # Now process each discovered record
                    for rec_brief in parsed_page.records:
                        await self.process_record_detail(client, rec_brief.record_id, rec_brief.url)

                        if max_records and records_found >= max_records:
                            self.logger.info(f"Reached max records limit ({max_records}).")
                            break

                    await asyncio.sleep(self.config.scraping.request_delay)

                    if max_records and records_found >= max_records:
                        break

                except Exception as exc:
                    self.logger.error(f"Error crawling listing page {page_url}: {exc}")
                    self.db.log_error("page_crawl_error", page_url, str(exc))

            # Mark session complete
            end_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE scraping_sessions
                    SET end_time = ?, pages_crawled = ?, records_found = ?, status = 'completed'
                    WHERE session_id = ?;
                    """,
                    (end_iso, pages_crawled, records_found, self.session_id),
                )

        finally:
            await client.aclose()

        return {"pages_crawled": pages_crawled, "records_found": records_found}

    async def process_record_detail(
        self,
        client: httpx.AsyncClient,
        record_id: int,
        record_url: str,
    ) -> None:
        """Fetch and parse an individual record detail page, classifying and queuing its attachments."""
        try:
            self.logger.debug(f"Fetching record detail: {record_url}")
            resp = await client.get(record_url)
            if resp.status_code != 200:
                self.logger.warning(f"Could not load record detail {record_url}: HTTP {resp.status_code}")
                return

            parsed = parse_record_html(resp.text, record_url)

            # Classify record
            first_fmt = parsed.attachments[0].reported_format if parsed.attachments else None
            cls_res = classify_record(
                title=parsed.title_fa,
                source_category=parsed.source_category,
                release_type=parsed.release_type,
                file_format=first_fmt,
            )

            record_data = {
                "record_id": record_id,
                "title_fa": parsed.title_fa,
                "title_en": None,
                "description": parsed.description,
                "source_category": parsed.source_category,
                "normalized_category": cls_res.subject_category_en,
                "resource_type": cls_res.resource_type_en,
                "subject_area": cls_res.subject_category_fa,
                "publication_date": parsed.publication_date_fa,
                "publication_date_iso": parsed.publication_date_iso,
                "gregorian_date_iso": parsed.gregorian_date_iso,
                "statistical_period": parsed.statistical_period,
                "periodicity": parsed.periodicity,
                "reference_year": parsed.reference_year,
                "source_website": "https://www.amar.org.ir",
                "original_record_url": record_url,
                "publisher": parsed.source or "مرکز آمار ایران",
                "language": "fa",
            }

            self.db.upsert_record(record_data)

            # Insert attachments into files table
            for att in parsed.attachments:
                file_data = {
                    "site_file_id": att.file_id,
                    "record_id": record_id,
                    "original_filename": att.reported_file_name or "attachment",
                    "local_filename": None,
                    "relative_path": None,
                    "file_extension": None,
                    "detected_file_format": att.reported_format,
                    "mime_type": None,
                    "file_size_bytes": att.reported_size_bytes,
                    "sha256": None,
                    "download_url": att.download_url,
                    "original_record_url": record_url,
                    "download_status": "discovered",
                    "download_timestamp": None,
                    "subject_category": cls_res.subject_slug,
                    "resource_type": cls_res.resource_slug,
                    "statistical_period": parsed.statistical_period,
                    "reference_year": parsed.reference_year,
                    "language": "fa",
                    "error_message": None,
                }
                self.db.upsert_file(file_data)

        except Exception as exc:
            self.logger.error(f"Error parsing record {record_url}: {exc}")
            self.db.log_error("record_parse_error", record_url, str(exc))

    async def download_all_pending(self, retry_failed: bool = False) -> dict[str, int]:
        """Download all discovered pending files."""
        pending_files = self.db.get_pending_downloads(retry_failed=retry_failed)
        self.logger.info(f"Found {len(pending_files)} pending files to download.")

        if not pending_files:
            return {"downloaded": 0, "failed": 0, "total": 0}

        client = self._create_http_client()
        downloaded = 0
        failed = 0

        try:
            tasks = [self.download_mgr.download_file(client, f) for f in pending_files]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if res is True:
                    downloaded += 1
                else:
                    failed += 1

        finally:
            await client.aclose()

        return {"downloaded": downloaded, "failed": failed, "total": len(pending_files)}
