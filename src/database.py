"""SQLite database manager for persistent scraper state and metadata indexing."""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import Any


class DatabaseManager:
    """Manages SQLite persistent state, discovered records, files, tags, and sessions."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create a connection with foreign keys and row factory enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        """Create schema tables and indexes if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS scraping_sessions (
                session_id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                pages_crawled INTEGER DEFAULT 0,
                records_found INTEGER DEFAULT 0,
                files_found INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running'
            );

            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY,
                name_fa TEXT NOT NULL,
                name_en TEXT,
                slug TEXT,
                url TEXT,
                reported_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS records (
                record_id INTEGER PRIMARY KEY,
                title_fa TEXT NOT NULL,
                title_en TEXT,
                description TEXT,
                source_category TEXT,
                normalized_category TEXT,
                resource_type TEXT,
                subject_area TEXT,
                publication_date TEXT,
                publication_date_iso TEXT,
                gregorian_date_iso TEXT,
                statistical_period TEXT,
                periodicity TEXT,
                reference_year INTEGER,
                geographical_coverage TEXT DEFAULT 'National',
                province TEXT,
                source_website TEXT DEFAULT 'https://www.amar.org.ir',
                original_record_url TEXT NOT NULL,
                publisher TEXT DEFAULT 'مرکز آمار ایران',
                language TEXT DEFAULT 'fa',
                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_file_id INTEGER,
                record_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                local_filename TEXT,
                relative_path TEXT,
                file_extension TEXT,
                detected_file_format TEXT,
                mime_type TEXT,
                file_size_bytes INTEGER,
                sha256 TEXT,
                download_url TEXT NOT NULL UNIQUE,
                original_record_url TEXT NOT NULL,
                download_status TEXT DEFAULT 'discovered',
                download_timestamp TEXT,
                subject_category TEXT,
                resource_type TEXT,
                statistical_period TEXT,
                reference_year INTEGER,
                language TEXT DEFAULT 'fa',
                error_message TEXT,
                FOREIGN KEY (record_id) REFERENCES records (record_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE,
                language TEXT NOT NULL DEFAULT 'fa'
            );

            CREATE TABLE IF NOT EXISTS record_tags (
                record_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (record_id, tag_id),
                FOREIGN KEY (record_id) REFERENCES records (record_id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (tag_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS file_tags (
                file_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (file_id, tag_id),
                FOREIGN KEY (file_id) REFERENCES files (file_id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (tag_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS download_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                attempt_time TEXT NOT NULL,
                status TEXT NOT NULL,
                bytes_downloaded INTEGER DEFAULT 0,
                error_message TEXT,
                FOREIGN KEY (file_id) REFERENCES files (file_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS errors (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                url TEXT,
                message TEXT NOT NULL,
                traceback TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS visited_pages (
                url TEXT PRIMARY KEY,
                visited_at TEXT NOT NULL,
                records_count INTEGER DEFAULT 0
            );

            -- Indexes for fast querying and filtering
            CREATE INDEX IF NOT EXISTS idx_records_ref_year ON records (reference_year);
            CREATE INDEX IF NOT EXISTS idx_records_norm_cat ON records (normalized_category);
            CREATE INDEX IF NOT EXISTS idx_records_res_type ON records (resource_type);
            CREATE INDEX IF NOT EXISTS idx_records_title_fa ON records (title_fa);
            CREATE INDEX IF NOT EXISTS idx_files_record_id ON files (record_id);
            CREATE INDEX IF NOT EXISTS idx_files_status ON files (download_status);
            CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files (sha256);
            CREATE INDEX IF NOT EXISTS idx_files_format ON files (detected_file_format);
            CREATE INDEX IF NOT EXISTS idx_tags_name ON tags (tag_name);
            """)

    def record_visited_page(self, url: str, records_count: int = 0) -> None:
        """Mark a listing URL as visited."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO visited_pages (url, visited_at, records_count) VALUES (?, ?, ?);",
                (url, now, records_count),
            )

    def is_page_visited(self, url: str) -> bool:
        """Check if a listing URL was already crawled."""
        with self.get_connection() as conn:
            cur = conn.execute("SELECT 1 FROM visited_pages WHERE url = ?;", (url,))
            return cur.fetchone() is not None

    def upsert_category(
        self, category_id: int, name_fa: str, url: str, reported_count: int | None = None
    ) -> None:
        """Insert or update category information."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO categories (category_id, name_fa, url, reported_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category_id) DO UPDATE SET
                    name_fa=excluded.name_fa,
                    url=excluded.url,
                    reported_count=COALESCE(excluded.reported_count, categories.reported_count);
                """,
                (category_id, name_fa, url, reported_count),
            )

    def upsert_record(self, record_data: dict[str, Any]) -> int:
        """Insert or update a statistical record."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record_id = record_data["record_id"]
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO records (
                    record_id, title_fa, title_en, description, source_category,
                    normalized_category, resource_type, subject_area, publication_date,
                    publication_date_iso, gregorian_date_iso, statistical_period,
                    periodicity, reference_year, geographical_coverage, province,
                    source_website, original_record_url, publisher, language,
                    discovered_at, updated_at
                ) VALUES (
                    :record_id, :title_fa, :title_en, :description, :source_category,
                    :normalized_category, :resource_type, :subject_area, :publication_date,
                    :publication_date_iso, :gregorian_date_iso, :statistical_period,
                    :periodicity, :reference_year, :geographical_coverage, :province,
                    :source_website, :original_record_url, :publisher, :language,
                    :discovered_at, :updated_at
                )
                ON CONFLICT(record_id) DO UPDATE SET
                    title_fa=excluded.title_fa,
                    title_en=COALESCE(excluded.title_en, records.title_en),
                    description=COALESCE(excluded.description, records.description),
                    source_category=COALESCE(excluded.source_category, records.source_category),
                    normalized_category=COALESCE(excluded.normalized_category, records.normalized_category),
                    resource_type=COALESCE(excluded.resource_type, records.resource_type),
                    subject_area=COALESCE(excluded.subject_area, records.subject_area),
                    publication_date=COALESCE(excluded.publication_date, records.publication_date),
                    publication_date_iso=COALESCE(excluded.publication_date_iso, records.publication_date_iso),
                    gregorian_date_iso=COALESCE(excluded.gregorian_date_iso, records.gregorian_date_iso),
                    statistical_period=COALESCE(excluded.statistical_period, records.statistical_period),
                    periodicity=COALESCE(excluded.periodicity, records.periodicity),
                    reference_year=COALESCE(excluded.reference_year, records.reference_year),
                    updated_at=:updated_at;
                """,
                {
                    "record_id": record_id,
                    "title_fa": record_data.get("title_fa", ""),
                    "title_en": record_data.get("title_en"),
                    "description": record_data.get("description"),
                    "source_category": record_data.get("source_category"),
                    "normalized_category": record_data.get("normalized_category"),
                    "resource_type": record_data.get("resource_type"),
                    "subject_area": record_data.get("subject_area"),
                    "publication_date": record_data.get("publication_date"),
                    "publication_date_iso": record_data.get("publication_date_iso"),
                    "gregorian_date_iso": record_data.get("gregorian_date_iso"),
                    "statistical_period": record_data.get("statistical_period"),
                    "periodicity": record_data.get("periodicity"),
                    "reference_year": record_data.get("reference_year"),
                    "geographical_coverage": record_data.get("geographical_coverage", "National"),
                    "province": record_data.get("province"),
                    "source_website": record_data.get("source_website", "https://www.amar.org.ir"),
                    "original_record_url": record_data.get("original_record_url", ""),
                    "publisher": record_data.get("publisher", "مرکز آمار ایران"),
                    "language": record_data.get("language", "fa"),
                    "discovered_at": now,
                    "updated_at": now,
                },
            )
        return record_id

    def upsert_file(self, file_data: dict[str, Any]) -> int:
        """Insert or update a downloadable file record."""
        download_url = file_data["download_url"]
        with self.get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO files (
                    site_file_id, record_id, original_filename, local_filename, relative_path,
                    file_extension, detected_file_format, mime_type, file_size_bytes,
                    sha256, download_url, original_record_url, download_status,
                    download_timestamp, subject_category, resource_type,
                    statistical_period, reference_year, language, error_message
                ) VALUES (
                    :site_file_id, :record_id, :original_filename, :local_filename, :relative_path,
                    :file_extension, :detected_file_format, :mime_type, :file_size_bytes,
                    :sha256, :download_url, :original_record_url, :download_status,
                    :download_timestamp, :subject_category, :resource_type,
                    :statistical_period, :reference_year, :language, :error_message
                )
                ON CONFLICT(download_url) DO UPDATE SET
                    site_file_id=COALESCE(excluded.site_file_id, files.site_file_id),
                    local_filename=COALESCE(excluded.local_filename, files.local_filename),
                    relative_path=COALESCE(excluded.relative_path, files.relative_path),
                    file_extension=COALESCE(excluded.file_extension, files.file_extension),
                    detected_file_format=COALESCE(excluded.detected_file_format, files.detected_file_format),
                    mime_type=COALESCE(excluded.mime_type, files.mime_type),
                    file_size_bytes=COALESCE(excluded.file_size_bytes, files.file_size_bytes),
                    sha256=COALESCE(excluded.sha256, files.sha256),
                    download_status=COALESCE(excluded.download_status, files.download_status),
                    download_timestamp=COALESCE(excluded.download_timestamp, files.download_timestamp),
                    subject_category=COALESCE(excluded.subject_category, files.subject_category),
                    resource_type=COALESCE(excluded.resource_type, files.resource_type),
                    statistical_period=COALESCE(excluded.statistical_period, files.statistical_period),
                    reference_year=COALESCE(excluded.reference_year, files.reference_year),
                    error_message=excluded.error_message
                RETURNING file_id;
                """,
                {
                    "site_file_id": file_data.get("site_file_id"),
                    "record_id": file_data["record_id"],
                    "original_filename": file_data.get("original_filename", "unnamed"),
                    "local_filename": file_data.get("local_filename"),
                    "relative_path": file_data.get("relative_path"),
                    "file_extension": file_data.get("file_extension"),
                    "detected_file_format": file_data.get("detected_file_format"),
                    "mime_type": file_data.get("mime_type"),
                    "file_size_bytes": file_data.get("file_size_bytes"),
                    "sha256": file_data.get("sha256"),
                    "download_url": download_url,
                    "original_record_url": file_data.get("original_record_url", ""),
                    "download_status": file_data.get("download_status", "discovered"),
                    "download_timestamp": file_data.get("download_timestamp"),
                    "subject_category": file_data.get("subject_category"),
                    "resource_type": file_data.get("resource_type"),
                    "statistical_period": file_data.get("statistical_period"),
                    "reference_year": file_data.get("reference_year"),
                    "language": file_data.get("language", "fa"),
                    "error_message": file_data.get("error_message"),
                },
            )
            row = cur.fetchone()
            return row["file_id"] if row else 0

    def add_tag(self, tag_name: str, language: str = "fa") -> int:
        """Insert tag if not exists and return tag_id."""
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO tags (tag_name, language) VALUES (?, ?);",
                (tag_name, language),
            )
            cur = conn.execute("SELECT tag_id FROM tags WHERE tag_name = ?;", (tag_name,))
            row = cur.fetchone()
            return row["tag_id"] if row else 0

    def link_record_tag(self, record_id: int, tag_id: int) -> None:
        """Link record to tag."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO record_tags (record_id, tag_id) VALUES (?, ?);",
                (record_id, tag_id),
            )

    def link_file_tag(self, file_id: int, tag_id: int) -> None:
        """Link file to tag."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO file_tags (file_id, tag_id) VALUES (?, ?);",
                (file_id, tag_id),
            )

    def find_file_by_sha256(self, sha256: str) -> dict[str, Any] | None:
        """Find an existing successfully downloaded file with matching SHA-256."""
        if not sha256:
            return None
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM files WHERE sha256 = ? AND download_status = 'downloaded' LIMIT 1;",
                (sha256,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_pending_downloads(self, retry_failed: bool = False) -> list[dict[str, Any]]:
        """Get files that are ready to be downloaded."""
        statuses = "('discovered', 'queued')" if not retry_failed else "('discovered', 'queued', 'failed', 'unavailable')"
        with self.get_connection() as conn:
            cur = conn.execute(
                f"""
                SELECT f.*, r.title_fa, r.normalized_category, r.resource_type as rec_resource_type, r.reference_year as rec_year
                FROM files f
                JOIN records r ON f.record_id = r.record_id
                WHERE f.download_status IN {statuses}
                ORDER BY f.file_id ASC;
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def log_error(self, error_type: str, url: str | None, message: str, traceback_str: str | None = None) -> None:
        """Record an error in the audit log."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO errors (error_type, url, message, traceback, created_at) VALUES (?, ?, ?, ?, ?);",
                (error_type, url, message, traceback_str, now),
            )

    def get_archive_stats(self) -> dict[str, Any]:
        """Compute comprehensive statistics about the archive."""
        with self.get_connection() as conn:
            total_records = conn.execute("SELECT COUNT(*) FROM records;").fetchone()[0]
            records_without_files = conn.execute(
                """
                SELECT COUNT(*) FROM records r
                LEFT JOIN files f ON r.record_id = f.record_id
                WHERE f.file_id IS NULL;
                """
            ).fetchone()[0]

            total_files = conn.execute("SELECT COUNT(*) FROM files;").fetchone()[0]
            downloaded_files = conn.execute(
                "SELECT COUNT(*) FROM files WHERE download_status = 'downloaded';"
            ).fetchone()[0]
            failed_files = conn.execute(
                "SELECT COUNT(*) FROM files WHERE download_status = 'failed';"
            ).fetchone()[0]
            unavailable_files = conn.execute(
                "SELECT COUNT(*) FROM files WHERE download_status = 'unavailable';"
            ).fetchone()[0]
            duplicate_files = conn.execute(
                "SELECT COUNT(*) FROM files WHERE download_status = 'duplicate';"
            ).fetchone()[0]

            total_bytes = conn.execute(
                "SELECT COALESCE(SUM(file_size_bytes), 0) FROM files WHERE download_status = 'downloaded';"
            ).fetchone()[0]

            # Files by format
            cur = conn.execute(
                "SELECT detected_file_format, COUNT(*) as c FROM files GROUP BY detected_file_format ORDER BY c DESC;"
            )
            files_by_format = {row["detected_file_format"] or "UNKNOWN": row["c"] for row in cur.fetchall()}

            # Files by subject
            cur = conn.execute(
                "SELECT subject_category, COUNT(*) as c FROM files GROUP BY subject_category ORDER BY c DESC;"
            )
            files_by_subject = {row["subject_category"] or "Unclassified": row["c"] for row in cur.fetchall()}

            # Files by resource type
            cur = conn.execute(
                "SELECT resource_type, COUNT(*) as c FROM files GROUP BY resource_type ORDER BY c DESC;"
            )
            files_by_resource_type = {row["resource_type"] or "Unclassified": row["c"] for row in cur.fetchall()}

            # Records by reference year
            cur = conn.execute(
                "SELECT reference_year, COUNT(*) as c FROM records WHERE reference_year IS NOT NULL GROUP BY reference_year ORDER BY reference_year DESC;"
            )
            records_by_year = {str(row["reference_year"]): row["c"] for row in cur.fetchall()}

            # Unclassified records
            unclassified_records = conn.execute(
                "SELECT COUNT(*) FROM records WHERE normalized_category IS NULL OR normalized_category = 'Other / Unclassified';"
            ).fetchone()[0]

            visited_pages_count = conn.execute("SELECT COUNT(*) FROM visited_pages;").fetchone()[0]

            return {
                "total_listing_pages_visited": visited_pages_count,
                "total_records_discovered": total_records,
                "records_without_attachments": records_without_files,
                "unclassified_records": unclassified_records,
                "total_files_identified": total_files,
                "successfully_downloaded_files": downloaded_files,
                "failed_downloads": failed_files,
                "unavailable_files": unavailable_files,
                "duplicate_files": duplicate_files,
                "total_downloaded_size_bytes": total_bytes,
                "total_downloaded_size_mb": round(total_bytes / (1024 * 1024), 2),
                "files_by_format": files_by_format,
                "files_by_subject": files_by_subject,
                "files_by_resource_type": files_by_resource_type,
                "records_by_year": records_by_year,
            }
