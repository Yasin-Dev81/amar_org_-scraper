"""Deduplicator for canonical file storage and SHA-256 collision checking."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from src.database import DatabaseManager


class Deduplicator:
    """Manages duplicate detection across download URLs and computed SHA-256 hashes."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def check_duplicate_by_sha256(self, sha256: str) -> dict[str, Any] | None:
        """Check if an identical file has already been downloaded and indexed."""
        return self.db.find_file_by_sha256(sha256)

    def handle_duplicate_file(
        self,
        current_file_id: int,
        canonical_file: dict[str, Any],
        download_url: str,
    ) -> None:
        """Mark current file as duplicate and link to canonical copy in metadata."""
        canonical_path = canonical_file.get("relative_path")
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE files
                SET download_status = 'duplicate',
                    relative_path = ?,
                    local_filename = ?,
                    sha256 = ?,
                    file_size_bytes = ?,
                    detected_file_format = ?,
                    mime_type = ?,
                    error_message = ?
                WHERE file_id = ?;
                """,
                (
                    canonical_path,
                    canonical_file.get("local_filename"),
                    canonical_file.get("sha256"),
                    canonical_file.get("file_size_bytes"),
                    canonical_file.get("detected_file_format"),
                    canonical_file.get("mime_type"),
                    f"Duplicate of file_id {canonical_file.get('file_id')} ({canonical_path})",
                    current_file_id,
                ),
            )
