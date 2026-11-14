"""Metadata manager for sidecar JSON files and export formats (JSONL, CSV)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from src.database import DatabaseManager


class MetadataManager:
    """Handles generating sidecar JSON metadata and exporting global archive catalogs."""

    def __init__(self, db: DatabaseManager, metadata_dir: Path | str) -> None:
        self.db = db
        self.metadata_dir = Path(metadata_dir)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def write_sidecar_metadata(
        self,
        file_path: Path,
        record_info: dict[str, Any],
        file_info: dict[str, Any],
        tags_fa: list[str],
        tags_en: list[str],
    ) -> Path:
        """Write `<original_file>.<ext>.metadata.json` sidecar alongside the downloaded file."""
        sidecar_path = file_path.with_name(f"{file_path.name}.metadata.json")

        metadata_payload = {
            "record": {
                "record_id": record_info.get("record_id"),
                "title_fa": record_info.get("title_fa"),
                "title_en": record_info.get("title_en"),
                "description": record_info.get("description"),
                "source_category": record_info.get("source_category"),
                "normalized_category": record_info.get("normalized_category"),
                "resource_type": record_info.get("resource_type"),
                "subject_area": record_info.get("subject_area"),
                "publication_date_fa": record_info.get("publication_date"),
                "publication_date_iso": record_info.get("publication_date_iso"),
                "gregorian_date_iso": record_info.get("gregorian_date_iso"),
                "statistical_period": record_info.get("statistical_period"),
                "reference_year": record_info.get("reference_year"),
                "geographical_coverage": record_info.get("geographical_coverage", "National"),
                "province": record_info.get("province"),
                "publisher": record_info.get("publisher", "مرکز آمار ایران"),
                "source_website": record_info.get("source_website", "https://www.amar.org.ir"),
                "original_record_url": record_info.get("original_record_url"),
                "language": record_info.get("language", "fa"),
            },
            "file": {
                "file_id": file_info.get("file_id"),
                "original_filename": file_info.get("original_filename"),
                "local_filename": file_path.name,
                "relative_path": file_info.get("relative_path"),
                "file_extension": file_info.get("file_extension"),
                "detected_file_format": file_info.get("detected_file_format"),
                "mime_type": file_info.get("mime_type"),
                "file_size_bytes": file_info.get("file_size_bytes"),
                "sha256": file_info.get("sha256"),
                "download_url": file_info.get("download_url"),
                "original_record_url": file_info.get("original_record_url"),
                "download_status": file_info.get("download_status"),
                "download_timestamp": file_info.get("download_timestamp"),
                "subject_category": file_info.get("subject_category"),
                "resource_type": file_info.get("resource_type"),
                "statistical_period": file_info.get("statistical_period"),
                "reference_year": file_info.get("reference_year"),
                "language": file_info.get("language", "fa"),
            },
            "tags": {
                "tags_fa": tags_fa,
                "tags_en": tags_en,
            },
        }

        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(metadata_payload, f, ensure_ascii=False, indent=2)

        return sidecar_path

    def _export_table_streaming(self, conn: Any, query: str, name: str, batch_size: int = 500) -> None:
        """Write a query result to JSONL and CSV in batches without loading it fully into memory."""
        cur = conn.execute(query)
        keys = [col[0] for col in cur.description]
        jsonl_path = self.metadata_dir / f"{name}.jsonl"
        csv_path = self.metadata_dir / f"{name}.csv"
        wrote_rows = False

        with open(jsonl_path, "w", encoding="utf-8") as jf, open(
            csv_path, "w", newline="", encoding="utf-8-sig"
        ) as cf:
            writer = csv.DictWriter(cf, fieldnames=keys)
            writer.writeheader()
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                wrote_rows = True
                for row in rows:
                    item = dict(row)
                    jf.write(json.dumps(item, ensure_ascii=False) + "\n")
                    writer.writerow(item)

        if not wrote_rows:
            csv_path.unlink(missing_ok=True)

    def export_all_metadata(self) -> None:
        """Export records and files to JSONL, CSV, and summary JSON catalogs."""
        with self.db.get_connection() as conn:
            # 1-2. Export Records and Files (streamed row by row to bound memory)
            self._export_table_streaming(conn, "SELECT * FROM records ORDER BY record_id ASC;", "records")
            self._export_table_streaming(conn, "SELECT * FROM files ORDER BY file_id ASC;", "files")

            # 3. Export Categories
            cur = conn.execute("SELECT * FROM categories ORDER BY category_id ASC;")
            categories = [dict(r) for r in cur.fetchall()]
            with open(self.metadata_dir / "categories.json", "w", encoding="utf-8") as f:
                json.dump(categories, f, ensure_ascii=False, indent=2)

            # 4. Export Tags
            cur = conn.execute(
                """
                SELECT t.tag_id, t.tag_name, t.language,
                       (SELECT COUNT(*) FROM record_tags WHERE tag_id = t.tag_id) as record_count,
                       (SELECT COUNT(*) FROM file_tags WHERE tag_id = t.tag_id) as file_count
                FROM tags t
                ORDER BY (record_count + file_count) DESC;
                """
            )
            tags = [dict(r) for r in cur.fetchall()]
            with open(self.metadata_dir / "tags.json", "w", encoding="utf-8") as f:
                json.dump(tags, f, ensure_ascii=False, indent=2)

            # 5. Export Duplicate Files
            cur = conn.execute(
                """
                SELECT sha256, COUNT(*) as count, GROUP_CONCAT(download_url, ' || ') as urls,
                       GROUP_CONCAT(file_id, ', ') as file_ids
                FROM files
                WHERE sha256 IS NOT NULL AND sha256 != ''
                GROUP BY sha256
                HAVING count > 1;
                """
            )
            duplicates = [dict(r) for r in cur.fetchall()]
            with open(self.metadata_dir / "duplicate_files.json", "w", encoding="utf-8") as f:
                json.dump(duplicates, f, ensure_ascii=False, indent=2)
