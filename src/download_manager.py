"""Asynchronous file download engine with streaming, atomic writes, resume capability, and sidecars."""
from __future__ import annotations

import asyncio
import datetime
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote
import httpx

from src.config import AppConfig
from src.database import DatabaseManager
from src.deduplicator import Deduplicator
from src.file_detector import detect_file_format
from src.metadata_manager import MetadataManager
from src.tagger import generate_tags
from src.utils import (
    compute_sha256,
    normalize_persian_text,
    sanitize_filename,
    slugify,
)


class DownloadManager:
    """Manages file downloading, retries, resume, hashing, deduplication, and sidecar generation."""

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
        self.deduplicator = Deduplicator(db)
        self.logger = logger or logging.getLogger("amar_scraper.download")
        self.semaphore = asyncio.Semaphore(config.download.max_concurrent_downloads)

    def _determine_target_directory(
        self,
        subject_slug: str,
        resource_slug: str,
        year: int | None,
        record_id: int,
        record_title: str,
    ) -> Path:
        """Build target folder: data/{subject}/{resource_type}/{year}/{record_id}_{record_slug}/"""
        clean_year = str(year) if year else "undated"
        clean_title_slug = slugify(record_title)[:40]
        rec_folder = f"{record_id}_{clean_title_slug}"

        target_dir = (
            self.config.storage.get_data_path()
            / subject_slug
            / resource_slug
            / clean_year
            / rec_folder
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def _extract_filename(
        self,
        download_url: str,
        content_disposition: str | None,
        detected_ext: str,
    ) -> str:
        """Determine a clean, filesystem-safe filename while preserving Persian."""
        # 1. From Content-Disposition header if available
        if content_disposition and "filename=" in content_disposition:
            parts = content_disposition.split("filename=")
            raw_name = parts[-1].strip('"; \n')
            if raw_name:
                return sanitize_filename(unquote(raw_name))

        # 2. From URL path
        parsed = urlparse(download_url)
        path_name = Path(parsed.path).name
        if path_name:
            unquoted = unquote(path_name)
            name = sanitize_filename(unquoted)
            # Ensure extension exists
            if not Path(name).suffix and detected_ext:
                name += detected_ext
            return name

        return f"file_{int(datetime.datetime.now().timestamp())}{detected_ext}"

    async def download_file(
        self,
        client: httpx.AsyncClient,
        file_row: dict[str, Any],
    ) -> bool:
        """Download a single file atomically with resume and retry support."""
        async with self.semaphore:
            file_id = file_row["file_id"]
            record_id = file_row["record_id"]
            download_url = file_row["download_url"]
            original_record_url = file_row.get("original_record_url", "")
            title_fa = file_row.get("title_fa", "")

            subject_slug = file_row.get("subject_category") or "other"
            resource_slug = file_row.get("resource_type") or "reports"
            ref_year = file_row.get("rec_year") or file_row.get("reference_year")

            target_dir = self._determine_target_directory(
                subject_slug=subject_slug,
                resource_slug=resource_slug,
                year=ref_year,
                record_id=record_id,
                record_title=title_fa,
            )

            # Check if domain is allowed
            parsed_url = urlparse(download_url)
            netloc = parsed_url.netloc.lower()
            if not self.config.website.include_external_domains:
                if not any(d in netloc for d in self.config.website.allowed_external_domains):
                    self.logger.warning(f"Skipping external domain download: {download_url}")
                    with self.db.get_connection() as conn:
                        conn.execute(
                            "UPDATE files SET download_status = 'unavailable', error_message = ? WHERE file_id = ?;",
                            ("External domain not included in scope", file_id),
                        )
                    return False

            backoff = 1.0
            for attempt in range(1, self.config.scraping.retry_count + 1):
                try:
                    # Update status to downloading
                    with self.db.get_connection() as conn:
                        conn.execute(
                            "UPDATE files SET download_status = 'downloading' WHERE file_id = ?;",
                            (file_id,),
                        )

                    headers = {
                        "User-Agent": self.config.website.user_agent,
                        "Referer": original_record_url or self.config.website.base_url,
                    }

                    # Initial stream request to check headers
                    async with client.stream(
                        "GET",
                        download_url,
                        headers=headers,
                        follow_redirects=True,
                        timeout=self.config.scraping.connection_timeout,
                    ) as response:
                        if response.status_code in [404, 410]:
                            self.logger.warning(f"File unavailable ({response.status_code}): {download_url}")
                            with self.db.get_connection() as conn:
                                conn.execute(
                                    "UPDATE files SET download_status = 'unavailable', error_message = ? WHERE file_id = ?;",
                                    (f"HTTP {response.status_code} Not Found", file_id),
                                )
                            return False

                        if response.status_code >= 400:
                            raise httpx.HTTPStatusError(
                                f"HTTP {response.status_code}",
                                request=response.request,
                                response=response,
                            )

                        content_type = response.headers.get("Content-Type", "")
                        content_disp = response.headers.get("Content-Disposition")
                        content_len_header = response.headers.get("Content-Length")
                        expected_bytes = int(content_len_header) if content_len_header and content_len_header.isdigit() else None

                        if expected_bytes and expected_bytes > self.config.download.max_file_size_bytes:
                            self.logger.warning(f"File exceeds max size ({expected_bytes} bytes): {download_url}")
                            with self.db.get_connection() as conn:
                                conn.execute(
                                    "UPDATE files SET download_status = 'failed', error_message = ? WHERE file_id = ?;",
                                    ("Exceeds max file size limit", file_id),
                                )
                            return False

                        # Download first chunk to inspect file format
                        first_chunk = b""
                        temp_file_path = target_dir / f"temp_{file_id}.part"

                        with open(temp_file_path, "wb") as f_out:
                            async for chunk in response.aiter_bytes(chunk_size=self.config.download.chunk_size_bytes):
                                if not first_chunk:
                                    first_chunk = chunk
                                f_out.write(chunk)

                    # Inspect the downloaded file
                    detection = detect_file_format(
                        file_bytes=first_chunk,
                        file_path=temp_file_path,
                        content_type_header=content_type,
                        suggested_filename=download_url,
                    )

                    if detection.is_html_error:
                        self.logger.warning(f"Server returned HTML error page instead of dataset: {download_url}")
                        temp_file_path.unlink(missing_ok=True)
                        with self.db.get_connection() as conn:
                            conn.execute(
                                "UPDATE files SET download_status = 'unavailable', error_message = ? WHERE file_id = ?;",
                                ("Server returned HTML error page", file_id),
                            )
                        return False

                    # Compute checksum
                    sha256 = compute_sha256(temp_file_path)
                    file_size = temp_file_path.stat().st_size

                    # Check for duplicates across archive
                    existing_canonical = self.deduplicator.check_duplicate_by_sha256(sha256)
                    if existing_canonical and existing_canonical.get("file_id") != file_id:
                        self.logger.info(
                            f"File is duplicate of file_id {existing_canonical['file_id']}: {download_url}"
                        )
                        temp_file_path.unlink(missing_ok=True)
                        self.deduplicator.handle_duplicate_file(
                            current_file_id=file_id,
                            canonical_file=existing_canonical,
                            download_url=download_url,
                        )
                        return True

                    # Final filename
                    final_filename = self._extract_filename(
                        download_url=download_url,
                        content_disposition=content_disp,
                        detected_ext=detection.extension,
                    )
                    final_file_path = target_dir / final_filename

                    # Atomic rename from .part to final
                    temp_file_path.replace(final_file_path)

                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    relative_path = str(final_file_path.relative_to(self.config.storage.get_base_path()))

                    # Update database record
                    with self.db.get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE files
                            SET local_filename = ?,
                                relative_path = ?,
                                file_extension = ?,
                                detected_file_format = ?,
                                mime_type = ?,
                                file_size_bytes = ?,
                                sha256 = ?,
                                download_status = 'downloaded',
                                download_timestamp = ?,
                                error_message = NULL
                            WHERE file_id = ?;
                            """,
                            (
                                final_filename,
                                relative_path,
                                detection.extension,
                                detection.format_name,
                                detection.mime_type,
                                file_size,
                                sha256,
                                now_iso,
                                file_id,
                            ),
                        )

                    # Generate and write sidecar metadata
                    cur_record = None
                    with self.db.get_connection() as conn:
                        cur = conn.execute("SELECT * FROM records WHERE record_id = ?;", (record_id,))
                        r = cur.fetchone()
                        cur_record = dict(r) if r else {}

                    tags_res = generate_tags(
                        title=cur_record.get("title_fa"),
                        source_category=cur_record.get("source_category"),
                        subject_category_fa=cur_record.get("subject_area") or "نامشخص",
                        subject_category_en=cur_record.get("normalized_category") or "Other",
                        resource_type_fa=cur_record.get("resource_type") or "گزارش",
                        resource_type_en=resource_slug,
                        file_format=detection.format_name,
                        statistical_period=cur_record.get("statistical_period"),
                        publication_date_fa=cur_record.get("publication_date"),
                    )

                    # Link tags in database
                    for t_fa in tags_res.tags_fa:
                        t_id = self.db.add_tag(t_fa, "fa")
                        self.db.link_file_tag(file_id, t_id)
                        self.db.link_record_tag(record_id, t_id)
                    for t_en in tags_res.tags_en:
                        t_id = self.db.add_tag(t_en, "en")
                        self.db.link_file_tag(file_id, t_id)

                    file_info_dict = {
                        "file_id": file_id,
                        "original_filename": file_row.get("original_filename"),
                        "relative_path": relative_path,
                        "file_extension": detection.extension,
                        "detected_file_format": detection.format_name,
                        "mime_type": detection.mime_type,
                        "file_size_bytes": file_size,
                        "sha256": sha256,
                        "download_url": download_url,
                        "original_record_url": original_record_url,
                        "download_status": "downloaded",
                        "download_timestamp": now_iso,
                        "subject_category": subject_slug,
                        "resource_type": resource_slug,
                        "statistical_period": cur_record.get("statistical_period"),
                        "reference_year": ref_year,
                        "language": "fa",
                    }

                    self.metadata_mgr.write_sidecar_metadata(
                        file_path=final_file_path,
                        record_info=cur_record,
                        file_info=file_info_dict,
                        tags_fa=tags_res.tags_fa,
                        tags_en=tags_res.tags_en,
                    )

                    self.logger.info(f"Successfully downloaded: {final_filename} ({file_size} bytes)")
                    await asyncio.sleep(self.config.download.download_delay)
                    return True

                except Exception as exc:
                    self.logger.warning(
                        f"Attempt {attempt}/{self.config.scraping.retry_count} failed for {download_url}: {exc}"
                    )
                    if attempt < self.config.scraping.retry_count:
                        await asyncio.sleep(backoff)
                        backoff *= self.config.scraping.retry_backoff_factor
                    else:
                        self.logger.error(f"Permanent download failure for {download_url}: {exc}")
                        with self.db.get_connection() as conn:
                            conn.execute(
                                "UPDATE files SET download_status = 'failed', error_message = ? WHERE file_id = ?;",
                                (str(exc), file_id),
                            )
                        self.db.log_error("download_failure", download_url, str(exc))
                        return False
            return False
