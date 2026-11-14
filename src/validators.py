"""Validation utilities for downloaded files, metadata sidecars, and database consistency."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from src.database import DatabaseManager
from src.utils import compute_sha256


class ArchiveValidator:
    """Validates archive integrity, metadata completeness, and physical file consistency."""

    def __init__(self, db: DatabaseManager, base_dir: Path | str = ".") -> None:
        self.db = db
        self.base_dir = Path(base_dir).resolve()

    def validate_file_integrity(self, file_id: int) -> tuple[bool, str]:
        """Validate physical file on disk matches stored SHA-256 and non-empty size."""
        with self.db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM files WHERE file_id = ?;", (file_id,))
            row = cur.fetchone()
            if not row:
                return False, f"File ID {file_id} not found in database"

            if row["download_status"] != "downloaded":
                return True, f"File status is {row['download_status']}; skipping disk check."

            rel_path = row["relative_path"]
            if not rel_path:
                return False, "Relative path is empty"

            abs_path = self.base_dir / rel_path
            if not abs_path.exists():
                return False, f"Physical file missing on disk: {abs_path}"

            actual_size = abs_path.stat().st_size
            if actual_size == 0:
                return False, f"Physical file is empty (0 bytes): {abs_path}"

            actual_sha = compute_sha256(abs_path)
            if actual_sha != row["sha256"]:
                return (
                    False,
                    f"SHA-256 mismatch! Expected: {row['sha256']}, Actual: {actual_sha}",
                )

            # Check sidecar metadata
            sidecar_path = abs_path.with_name(f"{abs_path.name}.metadata.json")
            if not sidecar_path.exists():
                return False, f"Sidecar metadata missing: {sidecar_path}"

            try:
                with open(sidecar_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "record" not in data or "file" not in data or "tags" not in data:
                        return False, f"Sidecar metadata missing required keys in {sidecar_path}"
            except Exception as e:
                return False, f"Invalid JSON in sidecar {sidecar_path}: {e}"

            return True, "Valid"

    def run_full_archive_audit(self) -> dict[str, Any]:
        """Run complete integrity check across all downloaded files."""
        with self.db.get_connection() as conn:
            cur = conn.execute("SELECT file_id FROM files WHERE download_status = 'downloaded';")
            downloaded_ids = [r["file_id"] for r in cur.fetchall()]

        valid_count = 0
        corrupt_count = 0
        issues: list[dict[str, Any]] = []

        for fid in downloaded_ids:
            is_valid, msg = self.validate_file_integrity(fid)
            if is_valid:
                valid_count += 1
            else:
                corrupt_count += 1
                issues.append({"file_id": fid, "error": msg})

        return {
            "total_downloaded_audited": len(downloaded_ids),
            "valid_files": valid_count,
            "corrupt_files": corrupt_count,
            "issues": issues,
        }
