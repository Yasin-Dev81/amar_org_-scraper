"""Utility functions for text normalization, dates, URLs, hashes, and logging."""
from __future__ import annotations

import hashlib
import logging
from logging.handlers import RotatingFileHandler
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote, unquote

# Arabic to Persian / English character replacements
PERSIAN_TO_ENGLISH_DIGITS = {
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

ARABIC_TO_PERSIAN_CHARS = {
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "ۀ": "ه",
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "ء": "",
    "\u200c": " ",  # ZWNJ to space in text search/slugs
    "\xa0": " ",    # Non-breaking space
}


def normalize_persian_text(text: str | None) -> str:
    """Normalize Persian text: standardize digits, Arabic kaf/yeh, and whitespace."""
    if not text:
        return ""
    # Strip leading/trailing whitespace
    text = text.strip()

    # Standardize characters
    for k, v in ARABIC_TO_PERSIAN_CHARS.items():
        text = text.replace(k, v)

    # Standardize digits to English
    for k, v in PERSIAN_TO_ENGLISH_DIGITS.items():
        text = text.replace(k, v)

    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_reference_year(text: str | None) -> int | None:
    """Extract 4-digit Persian solar calendar year (e.g., 1335 to 1410)."""
    if not text:
        return None
    normalized = normalize_persian_text(text)
    # Search for 4-digit years between 1330 and 1420
    matches = re.findall(r"\b(13[3-9]\d|14[0-2]\d)\b", normalized)
    if matches:
        return int(matches[-1])  # Usually the most relevant is the last mentioned
    return None


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """Convert Jalali (Shamsi) date to Gregorian date without external dependencies."""
    jy_adj = jy - 979
    jm_adj = jm - 1
    jd_adj = jd - 1

    j_day_no = 365 * jy_adj + (jy_adj // 33) * 8 + ((jy_adj % 33 + 3) // 4)
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    for i in range(jm_adj):
        j_day_no += j_days_in_month[i]
    j_day_no += jd_adj

    g_day_no = j_day_no + 79

    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097

    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365

    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    i = 0
    while True:
        dim = g_days_in_month[i] + (1 if i == 1 and leap else 0)
        if g_day_no < dim:
            break
        g_day_no -= dim
        i += 1

    gm = i + 1
    gd = g_day_no + 1
    return gy, gm, gd


def parse_jalali_date(date_str: str | None) -> tuple[str | None, str | None]:
    """Parse Jalali date string (e.g. '1405/08/17' or '1405-08-17').
    
    Returns (jalali_iso, gregorian_iso) e.g. ('1405-08-17', '2026-11-07').
    """
    if not date_str:
        return None, None
    clean = normalize_persian_text(date_str)
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", clean)
    if not match:
        return None, None

    jy = int(match.group(1))
    jm = int(match.group(2))
    jd = int(match.group(3))

    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        return None, None

    jalali_iso = f"{jy:04d}-{jm:02d}-{jd:02d}"
    try:
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        gregorian_iso = f"{gy:04d}-{gm:02d}-{gd:02d}"
        return jalali_iso, gregorian_iso
    except Exception:
        return jalali_iso, None


def normalize_url(url: str, base_url: str = "https://www.amar.org.ir") -> str:
    """Normalize and resolve relative or unquoted URLs."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http://") and not url.startswith("https://"):
        url = urljoin(base_url, url)

    # Ensure HTTPS and www.amar.org.ir for consistency
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc == "amar.org.ir":
        netloc = "www.amar.org.ir"

    scheme = parsed.scheme
    if netloc in ["amar.org.ir", "www.amar.org.ir"]:
        scheme = "https"

    # Encode path parts if they contain raw non-ASCII unicode
    path = quote(unquote(parsed.path), safe="/:@!$&'()*+,;=")
    query = parsed.query

    normalized = f"{scheme}://{netloc}{path}"
    if query:
        normalized += f"?{query}"
    return normalized


def parse_file_size_string(size_str: str | None) -> int | None:
    """Convert human readable Persian/English file size string to integer bytes."""
    if not size_str:
        return None
    normalized = normalize_persian_text(size_str).upper()
    # Match patterns like '0.76 MB', '15 KB', 'حجم: 2.1 GB', '500 B'
    match = re.search(r"([\d\.]+)\s*(GB|MB|KB|B|گیگابایت|مگابایت|کیلوبایت|بایت)?", normalized)
    if not match:
        return None

    try:
        val = float(match.group(1))
    except ValueError:
        return None

    unit = match.group(2) or "B"
    multipliers = {
        "GB": 1024**3,
        "گیگابایت": 1024**3,
        "MB": 1024**2,
        "مگابایت": 1024**2,
        "KB": 1024,
        "کیلوبایت": 1024,
        "B": 1,
        "بایت": 1,
    }
    multiplier = multipliers.get(unit, 1)
    return int(val * multiplier)


def compute_sha256(file_path: Path | str, chunk_size: int = 65536) -> str:
    """Calculate SHA-256 hash of a local file in a streaming fashion."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def sanitize_filename(name: str) -> str:
    """Sanitize filename to be safe on all operating systems while preserving Persian."""
    if not name:
        return "unnamed_file"
    # Remove URL query string if format is path.ext?query
    if "?" in name and "." in name.split("?")[0]:
        name = name.split("?")[0]
    if "#" in name:
        name = name.split("#")[0]
    # Replace dangerous filesystem characters
    cleaned = re.sub(r'[\x00/\\:*?"<>|]', "_", name).strip()
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned)
    # Avoid leading dots
    if cleaned.startswith("."):
        cleaned = "_" + cleaned[1:]
    return cleaned or "unnamed_file"



def slugify(text: str) -> str:
    """Convert string to a safe directory name slug."""
    text = normalize_persian_text(text).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text or "unclassified"


def setup_logging(logs_dir: Path | str, level: int = logging.INFO) -> logging.Logger:
    """Set up structured logging to file and console."""
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("amar_scraper")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Bounded rotating file handlers (5MB each, max 3 backups) to protect disk space
    file_handler = RotatingFileHandler(
        logs_path / "scraper.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Error file handler with rotation
    error_handler = RotatingFileHandler(
        logs_path / "download_errors.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    return logger
