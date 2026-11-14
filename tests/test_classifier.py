"""Unit tests for classifier and tagger."""
from __future__ import annotations

from src.classifier import classify_record
from src.tagger import generate_tags


def test_classify_prices_and_inflation():
    res = classify_record(
        title="شاخص قیمت تولیدکننده زراعت، باغداری و دامداری سنتی - تابستان 1405",
        source_category="آمارهای اقتصادی >> شاخص های قیمت",
        release_type="گزارش",
        file_format="PDF",
    )
    assert res.subject_slug == "prices_inflation"
    assert "قیمت" in res.subject_category_fa
    assert res.resource_slug == "reports"
    assert res.confidence >= 0.6


def test_classify_census():
    res = classify_record(
        title="نتایج تفصیلی سرشماری عمومی نفوس و مسکن 1395",
        source_category="سرشماری ها",
        release_type="نتایج سرشماری",
        file_format="XLSX",
    )
    assert res.subject_slug == "census"
    assert "سرشماری" in res.subject_category_fa


def test_classify_unclassified():
    res = classify_record(
        title="عنوان نامشخص بدون کلمات کلیدی",
        source_category="",
        release_type=None,
        file_format=None,
    )
    assert res.subject_slug == "other"
    assert res.subject_category_en == "Other / Unclassified"


def test_generate_tags():
    tags = generate_tags(
        title="شاخص قیمت مصرف‌کننده خانوارهای شهری کشور - مهر 1405",
        source_category="آمارهای اقتصادی >> شاخص های قیمت",
        subject_category_fa="قیمت‌ها و تورم",
        subject_category_en="Prices and Inflation",
        resource_type_fa="گزارش‌های آماری",
        resource_type_en="reports",
        file_format="PDF",
        statistical_period="مهر 1405",
        publication_date_fa="1405/08/01",
    )
    assert "قیمت‌ها و تورم" in tags.tags_fa
    assert "گزارش‌های آماری" in tags.tags_fa
    assert "پی‌دی‌اف" in tags.tags_fa
    assert "prices-and-inflation" in tags.tags_en
    assert "pdf" in tags.tags_en
    assert any("1405" in t for t in tags.tags_fa)
