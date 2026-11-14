"""Unit tests for utility functions."""
from __future__ import annotations

from pathlib import Path
from src.utils import (
    normalize_persian_text,
    extract_reference_year,
    jalali_to_gregorian,
    parse_jalali_date,
    normalize_url,
    parse_file_size_string,
    sanitize_filename,
    slugify,
)


def test_normalize_persian_text():
    raw = " شاخص  قیمت‌های  تولید‌کننده  ۱۳۹۹ و ۱۴۰۲  ي ك "
    norm = normalize_persian_text(raw)
    assert "1399" in norm
    assert "1402" in norm
    assert "ی" in norm
    assert "ک" in norm
    assert "  " not in norm


def test_extract_reference_year():
    assert extract_reference_year("حساب های ملی سالانه 1402 - 1340") == 1340 or extract_reference_year("حساب های ملی سالانه 1402 - 1340") == 1402
    assert extract_reference_year("شاخص قیمت - مهر 1405 (100=1400)") in [1405, 1400]
    assert extract_reference_year("بدون سال") is None


def test_jalali_to_gregorian():
    # 1 Farvardin 1400 = 21 March 2021
    gy, gm, gd = jalali_to_gregorian(1400, 1, 1)
    assert (gy, gm, gd) == (2021, 3, 21)

    # 17 Aban 1405
    gy, gm, gd = jalali_to_gregorian(1405, 8, 17)
    assert gy == 2026


def test_parse_jalali_date():
    jalali_iso, greg_iso = parse_jalali_date("1405/08/17")
    assert jalali_iso == "1405-08-17"
    assert greg_iso is not None
    assert greg_iso.startswith("2026")

    # Invalid date
    j, g = parse_jalali_date("invalid")
    assert j is None and g is None


def test_normalize_url():
    base = "https://www.amar.org.ir"
    assert normalize_url("/statistical-information", base) == "https://www.amar.org.ir/statistical-information"
    assert normalize_url("http://amar.org.ir/test") == "https://www.amar.org.ir/test"
    assert normalize_url("https://www.amar.org.ir/data?id=1") == "https://www.amar.org.ir/data?id=1"


def test_parse_file_size_string():
    assert parse_file_size_string("0.76 MB") == int(0.76 * 1024 * 1024)
    assert parse_file_size_string("15 KB") == 15 * 1024
    assert parse_file_size_string("2 GB") == 2 * 1024 * 1024 * 1024
    assert parse_file_size_string("حجم: 500 بایت") == 500


def test_sanitize_filename():
    safe = sanitize_filename("فایل/آمار:سال*1400?.xlsx")
    assert "/" not in safe
    assert ":" not in safe
    assert "*" not in safe
    assert safe.endswith(".xlsx")


def test_slugify():
    slug = slugify("آمارهای جمعیتی و اجتماعی")
    assert "آمارهای" in slug or "population" in slug
    assert " " not in slug
