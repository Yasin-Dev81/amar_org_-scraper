"""Configuration loader and schema models."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field


class WebsiteConfig(BaseModel):
    base_url: str = "https://www.amar.org.ir"
    start_urls: list[str] = Field(
        default_factory=lambda: [
            "https://www.amar.org.ir/statistical-information/currentpage/3",
            "https://www.amar.org.ir/statistical-information",
        ]
    )
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    categories: dict[str, str] = Field(default_factory=dict)
    include_external_domains: bool = False
    allowed_external_domains: list[str] = Field(
        default_factory=lambda: [
            "amar.org.ir",
            "www.amar.org.ir",
            "sci.org.ir",
            "rpt.sci.org.ir",
            "ssis.sci.org.ir",
        ]
    )


class ScrapingConfig(BaseModel):
    max_concurrent_requests: int = 4
    request_delay: float = 0.5
    connection_timeout: float = 30.0
    retry_count: int = 3
    retry_backoff_factor: float = 2.0
    max_pages_to_crawl: int | None = None
    max_records_to_process: int | None = None
    browser_automation: bool = False


class DownloadConfig(BaseModel):
    max_concurrent_downloads: int = 3
    download_delay: float = 0.3
    max_file_size_bytes: int = 524_288_000  # 500 MB
    verify_ssl: bool = True
    chunk_size_bytes: int = 65_536  # 64 KB
    resume_interrupted: bool = True
    temp_extension: str = ".part"
    supported_extensions: list[str] = Field(
        default_factory=lambda: [
            ".xls", ".xlsx", ".xlsm", ".csv", ".tsv", ".txt",
            ".pdf", ".doc", ".docx", ".ppt", ".pptx",
            ".zip", ".rar", ".7z",
            ".sav", ".dta", ".sas7bdat",
            ".shp", ".kml", ".kmz", ".geojson",
            ".xml", ".json",
        ]
    )


class StorageConfig(BaseModel):
    base_dir: str = "."
    data_dir: str = "data"
    metadata_dir: str = "metadata"
    database_dir: str = "database"
    database_name: str = "scraper_state.sqlite"
    logs_dir: str = "logs"
    reports_dir: str = "reports"

    def get_base_path(self) -> Path:
        return Path(self.base_dir).resolve()

    def get_data_path(self) -> Path:
        return self.get_base_path() / self.data_dir

    def get_metadata_path(self) -> Path:
        return self.get_base_path() / self.metadata_dir

    def get_db_path(self) -> Path:
        return self.get_base_path() / self.database_dir / self.database_name

    def get_logs_path(self) -> Path:
        return self.get_base_path() / self.logs_dir

    def get_reports_path(self) -> Path:
        return self.get_base_path() / self.reports_dir


class ClassificationConfig(BaseModel):
    fallback_category: str = "other"
    strict_mode: bool = False
    confidence_threshold: float = 0.6


class AppConfig(BaseModel):
    website: WebsiteConfig = Field(default_factory=WebsiteConfig)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)

    def ensure_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        self.storage.get_data_path().mkdir(parents=True, exist_ok=True)
        self.storage.get_metadata_path().mkdir(parents=True, exist_ok=True)
        self.storage.get_db_path().parent.mkdir(parents=True, exist_ok=True)
        self.storage.get_logs_path().mkdir(parents=True, exist_ok=True)
        self.storage.get_reports_path().mkdir(parents=True, exist_ok=True)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file or return defaults."""
    if config_path is None:
        env_config = os.environ.get("CONFIG_PATH")
        if env_config:
            config_path = env_config
        else:
            default_path = Path("config/config.yaml")
            if default_path.exists():
                config_path = default_path

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
            cfg = AppConfig(**data)
            env_output = os.environ.get("OUTPUT_DIR")
            if env_output:
                cfg.storage.base_dir = env_output
            cfg.ensure_directories()
            return cfg

    cfg = AppConfig()
    env_output = os.environ.get("OUTPUT_DIR")
    if env_output:
        cfg.storage.base_dir = env_output
    cfg.ensure_directories()
    return cfg
