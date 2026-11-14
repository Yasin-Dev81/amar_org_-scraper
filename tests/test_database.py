"""Unit tests for SQLite database operations and archive validators."""
from __future__ import annotations

import json
from pathlib import Path
from src.database import DatabaseManager
from src.validators import ArchiveValidator
from src.utils import compute_sha256


def test_database_operations(tmp_path: Path):
    db_file = tmp_path / "test_scraper.sqlite"
    db = DatabaseManager(db_file)

    # 1. Visited pages
    db.record_visited_page("https://www.amar.org.ir/page/1", 25)
    assert db.is_page_visited("https://www.amar.org.ir/page/1") is True
    assert db.is_page_visited("https://www.amar.org.ir/page/999") is False

    # 2. Insert record
    rec_id = db.upsert_record({
        "record_id": 1001,
        "title_fa": "آمار نمونه تورم",
        "source_category": "اقتصادی",
        "normalized_category": "Prices and Inflation",
        "resource_type": "Statistical Reports",
        "reference_year": 1402,
        "original_record_url": "https://www.amar.org.ir/statistical-information/statid/1001",
    })
    assert rec_id == 1001

    # 3. Insert file
    file_id = db.upsert_file({
        "record_id": 1001,
        "original_filename": "sample.pdf",
        "download_url": "https://www.amar.org.ir/sample.pdf",
        "download_status": "discovered",
        "subject_category": "prices_inflation",
        "resource_type": "reports",
    })
    assert file_id > 0

    # 4. Check stats
    stats = db.get_archive_stats()
    assert stats["total_records_discovered"] == 1
    assert stats["total_files_identified"] == 1


def test_validator_integrity(tmp_path: Path):
    db_file = tmp_path / "test_val.sqlite"
    db = DatabaseManager(db_file)

    # Create dummy downloaded file
    data_file = tmp_path / "data" / "sample.pdf"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    content = b"%PDF-1.7 sample content"
    data_file.write_bytes(content)
    sha256 = compute_sha256(data_file)

    # Create dummy sidecar
    sidecar = data_file.with_name(f"{data_file.name}.metadata.json")
    sidecar.write_text(json.dumps({
        "record": {"record_id": 1},
        "file": {"file_id": 1},
        "tags": {"tags_fa": ["تست"], "tags_en": ["test"]},
    }))

    db.upsert_record({
        "record_id": 1,
        "title_fa": "تست",
        "original_record_url": "https://example.com/1",
    })
    fid = db.upsert_file({
        "record_id": 1,
        "original_filename": "sample.pdf",
        "local_filename": "sample.pdf",
        "relative_path": str(data_file.relative_to(tmp_path)),
        "sha256": sha256,
        "file_size_bytes": len(content),
        "download_url": "https://example.com/sample.pdf",
        "download_status": "downloaded",
    })

    validator = ArchiveValidator(db, base_dir=tmp_path)
    is_valid, msg = validator.validate_file_integrity(fid)
    assert is_valid is True
    assert msg == "Valid"
