"""Multi-label Persian and English tag generator."""
from __future__ import annotations

import re
from typing import NamedTuple
from src.utils import normalize_persian_text, extract_reference_year


class TagsResult(NamedTuple):
    tags_fa: list[str]
    tags_en: list[str]
    needs_review: bool


# Statistical keywords mapping (Persian -> English slug)
KEYWORD_TAXONOMY = {
    "شاخص قیمت": "price-index",
    "تورم": "inflation",
    "تولیدکننده": "producer",
    "مصرف کننده": "consumer",
    "مصرف‌کننده": "consumer",
    "هزینه و درآمد": "household-income-expenditure",
    "اشتغال": "employment",
    "بیکاری": "unemployment",
    "نیروی کار": "labor-force",
    "کشاورزی": "agriculture",
    "دامداری": "livestock",
    "مرغداری": "poultry",
    "گاوداری": "cattle-farming",
    "صنعت": "industry",
    "معدن": "mining",
    "ساختمان": "construction",
    "مسکن": "housing",
    "پروانه ساختمانی": "building-permits",
    "حساب های ملی": "national-accounts",
    "حساب‌های ملی": "national-accounts",
    "حساب های منطقه ای": "regional-accounts",
    "جمعیت": "population",
    "سرشماری": "census",
    "سالنامه آماری": "statistical-yearbook",
    "گزارش آماری": "statistical-report",
    "جداول آماری": "statistical-tables",
    "فصلی": "quarterly",
    "ماهانه": "monthly",
    "سالانه": "annual",
    "شهری": "urban",
    "روستایی": "rural",
    "ایران": "iran",
    "تهران": "tehran",
}


def generate_tags(
    title: str | None,
    source_category: str | None,
    subject_category_fa: str,
    subject_category_en: str,
    resource_type_fa: str,
    resource_type_en: str,
    file_format: str | None,
    statistical_period: str | None,
    publication_date_fa: str | None,
    original_keywords: list[str] | None = None,
) -> TagsResult:
    """Generate normalized Persian and English tags for a record or file."""
    tags_fa_set: set[str] = set()
    tags_en_set: set[str] = set()

    # 1. Subject Category
    if subject_category_fa and subject_category_fa != "سایر / دسته‌بندی نشده":
        tags_fa_set.add(subject_category_fa)
        tags_en_set.add(subject_category_en.lower().replace(" ", "-"))

    # 2. Resource Type
    if resource_type_fa:
        tags_fa_set.add(resource_type_fa)
        tags_en_set.add(resource_type_en.lower().replace(" ", "-"))

    # 3. File Format
    if file_format:
        fmt = file_format.upper()
        tags_en_set.add(fmt.lower())
        format_fa_map = {
            "PDF": "پی‌دی‌اف",
            "XLS": "اکسل",
            "XLSX": "اکسل",
            "CSV": "داده متنی",
            "ZIP": "فایل فشرده",
            "RAR": "فایل فشرده",
        }
        if fmt in format_fa_map:
            tags_fa_set.add(format_fa_map[fmt])

    # 4. Statistical Period / Frequency
    if statistical_period:
        clean_period = normalize_persian_text(statistical_period)
        tags_fa_set.add(clean_period)
        if any(w in clean_period for w in ["فصل", "سه ماه"]):
            tags_en_set.add("quarterly")
        elif any(w in clean_period for w in ["ماه"]):
            tags_en_set.add("monthly")
        elif any(w in clean_period for w in ["سال"]):
            tags_en_set.add("annual")

    # 5. Reference Year
    year = extract_reference_year(title) or extract_reference_year(statistical_period) or extract_reference_year(publication_date_fa)
    if year:
        tags_fa_set.add(f"سال {year}")
        tags_en_set.add(f"year-{year}")

    # 6. Title and Category Keywords
    corpus = f"{normalize_persian_text(source_category)} {normalize_persian_text(title)}"
    for kw_fa, kw_en in KEYWORD_TAXONOMY.items():
        if kw_fa in corpus:
            tags_fa_set.add(kw_fa)
            tags_en_set.add(kw_en)

    # 7. Original keywords from website
    if original_keywords:
        for kw in original_keywords:
            clean_kw = normalize_persian_text(kw)
            if clean_kw and len(clean_kw) > 1:
                tags_fa_set.add(clean_kw)

    # Review condition: if no subject detected or very few tags
    needs_review = (subject_category_en == "Other / Unclassified") or (len(tags_fa_set) <= 2)

    # Sort for deterministic output
    tags_fa_sorted = sorted(list(tags_fa_set))
    tags_en_sorted = sorted(list(tags_en_set))

    return TagsResult(
        tags_fa=tags_fa_sorted,
        tags_en=tags_en_sorted,
        needs_review=needs_review,
    )
