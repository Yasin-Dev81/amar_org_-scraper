"""CLI interface for the Iran Statistical Center (amar.org.ir) scraper."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from src.config import AppConfig, load_config
from src.crawler import AmarCrawler
from src.database import DatabaseManager
from src.metadata_manager import MetadataManager
from src.report_generator import ReportGenerator
from src.utils import setup_logging, normalize_url
from src.validators import ArchiveValidator


def get_configured_logger(config: AppConfig) -> logging.Logger:
    """Initialize logger respecting LOG_LEVEL environment variable."""
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)
    return setup_logging(config.storage.get_logs_path(), level=level)


async def cmd_inspect(args: argparse.Namespace) -> None:
    """Inspect website structure, headers, and sample record."""
    config = load_config(args.config)
    logger = get_configured_logger(config)
    logger.info("Inspecting website structure...")

    import httpx
    from src.page_parser import parse_listing_page_html
    from src.record_parser import parse_record_html

    target_url = args.url or config.website.start_urls[0]
    headers = {"User-Agent": config.website.user_agent}

    print(f"\n[+] Probing target listing URL: {target_url}")
    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        verify=config.download.verify_ssl,
    ) as client:
        resp = await client.get(target_url)

        print(f"Status Code: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type')}")

        parsed_page = parse_listing_page_html(resp.text, target_url)
        print(f"\n[+] Listing Discovery Results:")
        print(f"    - Current Page: {parsed_page.current_page_number}")
        print(f"    - Discovered Records on this page: {len(parsed_page.records)}")
        print(f"    - Discovered Pagination Links: {len(parsed_page.pagination_urls)}")
        print(f"    - Discovered Categories: {len(parsed_page.discovered_categories)}")

        if parsed_page.discovered_categories:
            print("\n[+] Sample Discovered Categories:")
            for cat in parsed_page.discovered_categories[:5]:
                print(f"    • ID {cat.category_id}: {cat.name_fa} ({cat.record_count or 'N/A'} items) -> {cat.url}")

        if parsed_page.records:
            sample_rec = parsed_page.records[0]
            print(f"\n[+] Probing sample record detail: {sample_rec.title} ({sample_rec.url})")
            rec_resp = await client.get(sample_rec.url)
            parsed_rec = parse_record_html(rec_resp.text, sample_rec.url)
            print(f"    - Title FA: {parsed_rec.title_fa}")
            print(f"    - Category: {parsed_rec.source_category}")
            print(f"    - Statistical Period: {parsed_rec.statistical_period}")
            print(f"    - Publication Date: {parsed_rec.publication_date_fa} (Gregorian: {parsed_rec.gregorian_date_iso})")
            print(f"    - Attachments Count: {len(parsed_rec.attachments)}")
            for att in parsed_rec.attachments:
                print(f"       -> Format: {att.reported_format} | Size: {att.reported_size_str} | URL: {att.download_url}")


async def cmd_discover(args: argparse.Namespace) -> None:
    """Discover all records and downloadable resources from listing pages."""
    config = load_config(args.config)
    logger = setup_logging(config.storage.get_logs_path())
    db = DatabaseManager(config.storage.get_db_path())
    metadata_mgr = MetadataManager(db, config.storage.get_metadata_path())
    crawler = AmarCrawler(config, db, metadata_mgr, logger)

    max_pages = args.max_pages or config.scraping.max_pages_to_crawl
    max_records = args.max_records or config.scraping.max_records_to_process

    logger.info(f"Starting discovery (max_pages={max_pages}, max_records={max_records})...")
    res = await crawler.discover_records(max_pages=max_pages, max_records=max_records)
    logger.info(f"Discovery completed! Crawled {res['pages_crawled']} pages, found {res['records_found']} records.")


async def cmd_download(args: argparse.Namespace) -> None:
    """Download all discovered files."""
    config = load_config(args.config)
    logger = setup_logging(config.storage.get_logs_path())
    db = DatabaseManager(config.storage.get_db_path())
    metadata_mgr = MetadataManager(db, config.storage.get_metadata_path())
    crawler = AmarCrawler(config, db, metadata_mgr, logger)

    logger.info("Starting file download process...")
    res = await crawler.download_all_pending(retry_failed=args.retry_failed)
    logger.info(
        f"Download process completed! Downloaded: {res['downloaded']}, Failed: {res['failed']}, Total: {res['total']}"
    )


async def cmd_run(args: argparse.Namespace) -> None:
    """Run end-to-end: discovery -> downloading -> metadata export -> reports."""
    config = load_config(args.config)
    logger = setup_logging(config.storage.get_logs_path())
    db = DatabaseManager(config.storage.get_db_path())
    metadata_mgr = MetadataManager(db, config.storage.get_metadata_path())
    report_gen = ReportGenerator(db, config.storage.get_reports_path())
    crawler = AmarCrawler(config, db, metadata_mgr, logger)

    max_pages = args.max_pages or config.scraping.max_pages_to_crawl
    max_records = args.max_records or config.scraping.max_records_to_process

    logger.info("=== STEP 1: Discovery ===")
    await crawler.discover_records(max_pages=max_pages, max_records=max_records)

    logger.info("=== STEP 2: Downloading Files ===")
    if not args.dry_run:
        await crawler.download_all_pending()
    else:
        logger.info("Dry-run mode: skipping physical file downloads.")

    logger.info("=== STEP 3: Exporting Global Metadata Catalogs ===")
    metadata_mgr.export_all_metadata()

    logger.info("=== STEP 4: Generating Reports ===")
    report_gen.generate_all_reports()

    logger.info("=== Complete! ===")
    stats = db.get_archive_stats()
    print("\n" + "=" * 50)
    print("ARCHIVE EXECUTION SUMMARY")
    print("=" * 50)
    print(f"Total Records Discovered:       {stats['total_records_discovered']}")
    print(f"Total Files Identified:         {stats['total_files_identified']}")
    print(f"Successfully Downloaded Files:  {stats['successfully_downloaded_files']}")
    print(f"Failed / Unavailable Files:     {stats['failed_downloads'] + stats['unavailable_files']}")
    print(f"Duplicate Files Deduplicated:   {stats['duplicate_files']}")
    print(f"Total Downloaded Size:          {stats['total_downloaded_size_mb']} MB")
    print("=" * 50)


async def cmd_report(args: argparse.Namespace) -> None:
    """Generate metadata catalogs and HTML/JSON summary reports."""
    config = load_config(args.config)
    logger = setup_logging(config.storage.get_logs_path())
    db = DatabaseManager(config.storage.get_db_path())
    metadata_mgr = MetadataManager(db, config.storage.get_metadata_path())
    report_gen = ReportGenerator(db, config.storage.get_reports_path())

    logger.info("Exporting metadata...")
    metadata_mgr.export_all_metadata()
    logger.info("Generating reports...")
    stats = report_gen.generate_all_reports()
    logger.info(f"Reports successfully generated in {config.storage.get_reports_path()}")


def cmd_stats(args: argparse.Namespace) -> None:
    """Display archive statistics."""
    config = load_config(args.config)
    db = DatabaseManager(config.storage.get_db_path())
    stats = db.get_archive_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_audit(args: argparse.Namespace) -> None:
    """Audit archive and validate integrity of downloaded files and sidecars."""
    config = load_config(args.config)
    db = DatabaseManager(config.storage.get_db_path())
    validator = ArchiveValidator(db, config.storage.get_base_path())
    res = validator.run_full_archive_audit()
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main() -> None:
    """Entry point parsing command line arguments."""
    parser = argparse.ArgumentParser(
        prog="amar_scraper",
        description="Comprehensive Statistical Data Scraper for Iran Statistical Center (amar.org.ir)",
    )
    parser.add_argument("--config", "-c", type=str, default="config/config.yaml", help="Path to config.yaml")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect website structure and sample record")
    p_inspect.add_argument("--url", type=str, help="Specific URL to inspect")

    # discover
    p_discover = subparsers.add_parser("discover", help="Discover statistical records and downloadable resources")
    p_discover.add_argument("--max-pages", type=int, help="Maximum listing pages to crawl")
    p_discover.add_argument("--max-records", type=int, help="Maximum records to process")

    # download
    p_download = subparsers.add_parser("download", help="Download discovered files")
    p_download.add_argument("--retry-failed", action="store_true", help="Retry failed downloads")

    # run
    p_run = subparsers.add_parser("run", help="Run full pipeline: discover, download, metadata, reports")
    p_run.add_argument("--resume", action="store_true", help="Resume previous scraping session")
    p_run.add_argument("--dry-run", action="store_true", help="Crawl and record metadata without downloading files")
    p_run.add_argument("--max-pages", type=int, help="Maximum listing pages to crawl")
    p_run.add_argument("--max-records", type=int, help="Maximum records to process")

    # retry-failed
    subparsers.add_parser("retry-failed", help="Retry failed or unavailable downloads")

    # report
    subparsers.add_parser("report", help="Generate metadata and classification reports")

    # stats
    subparsers.add_parser("stats", help="Display archive statistics in JSON format")

    # audit
    subparsers.add_parser("audit", help="Validate file checksums and sidecar metadata integrity")

    args = parser.parse_args()

    if args.command == "inspect":
        asyncio.run(cmd_inspect(args))
    elif args.command == "discover":
        asyncio.run(cmd_discover(args))
    elif args.command == "download":
        asyncio.run(cmd_download(args))
    elif args.command == "retry-failed":
        args.retry_failed = True
        asyncio.run(cmd_download(args))
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "report":
        asyncio.run(cmd_report(args))
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "audit":
        cmd_audit(args)


if __name__ == "__main__":
    main()
