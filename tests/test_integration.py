"""Integration tests for end-to-end scraper pipeline."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from src.config import AppConfig, StorageConfig
from src.crawler import AmarCrawler
from src.database import DatabaseManager
from src.metadata_manager import MetadataManager
from src.report_generator import ReportGenerator
from src.validators import ArchiveValidator


@pytest.mark.asyncio
async def test_pipeline_with_mocked_responses(tmp_path: Path):
    """Test full pipeline (discovery -> metadata export -> report -> audit)."""
    # Setup temporary directory structure
    storage = StorageConfig(
        base_dir=str(tmp_path),
        data_dir="data",
        metadata_dir="metadata",
        database_dir="database",
        database_name="test_state.sqlite",
        logs_dir="logs",
        reports_dir="reports",
    )
    config = AppConfig(storage=storage)
    config.ensure_directories()

    db = DatabaseManager(config.storage.get_db_path())
    metadata_mgr = MetadataManager(db, config.storage.get_metadata_path())
    report_gen = ReportGenerator(db, config.storage.get_reports_path())

    # Seed mock records and files
    rec_id = db.upsert_record({
        "record_id": 58312,
        "title_fa": "شاخص قیمت تولیدکننده زراعت، باغداری و دامداری سنتی",
        "source_category": "آمارهای اقتصادی >> شاخص های قیمت",
        "normalized_category": "Prices and Inflation",
        "resource_type": "Statistical Reports",
        "subject_area": "قیمت‌ها و تورم",
        "publication_date": "1405/08/17",
        "reference_year": 1405,
        "original_record_url": "https://www.amar.org.ir/statistical-information/statid/58312",
    })

    file_dest = tmp_path / "data" / "prices_inflation" / "reports" / "1405" / "58312_test" / "shgzrtdamdari05-2.pdf"
    file_dest.parent.mkdir(parents=True, exist_ok=True)
    file_dest.write_bytes(b"%PDF-1.7 sample statistical report bytes")

    from src.utils import compute_sha256
    sha = compute_sha256(file_dest)

    fid = db.upsert_file({
        "record_id": rec_id,
        "original_filename": "shgzrtdamdari05-2.pdf",
        "local_filename": "shgzrtdamdari05-2.pdf",
        "relative_path": str(file_dest.relative_to(tmp_path)),
        "file_extension": ".pdf",
        "detected_file_format": "PDF",
        "mime_type": "application/pdf",
        "file_size_bytes": file_dest.stat().st_size,
        "sha256": sha,
        "download_url": "https://www.amar.org.ir/Portals/0/Articles/shgzrtdamdari05-2.pdf",
        "original_record_url": "https://www.amar.org.ir/statistical-information/statid/58312",
        "download_status": "downloaded",
        "subject_category": "prices_inflation",
        "resource_type": "reports",
        "reference_year": 1405,
    })

    # Write sidecar
    metadata_mgr.write_sidecar_metadata(
        file_path=file_dest,
        record_info={"record_id": rec_id, "title_fa": "شاخص قیمت"},
        file_info={"file_id": fid, "sha256": sha, "file_size_bytes": file_dest.stat().st_size},
        tags_fa=["قیمت", "تورم"],
        tags_en=["price", "inflation"],
    )

    # Export metadata
    metadata_mgr.export_all_metadata()
    assert (config.storage.get_metadata_path() / "records.jsonl").exists()
    assert (config.storage.get_metadata_path() / "files.csv").exists()

    # Generate reports
    stats = report_gen.generate_all_reports()
    assert stats["successfully_downloaded_files"] == 1
    assert (config.storage.get_reports_path() / "download_summary.json").exists()
    assert (config.storage.get_reports_path() / "download_summary.html").exists()

    # Audit archive
    validator = ArchiveValidator(db, base_dir=tmp_path)
    audit_res = validator.run_full_archive_audit()
    assert audit_res["valid_files"] == 1
    assert audit_res["corrupt_files"] == 0
