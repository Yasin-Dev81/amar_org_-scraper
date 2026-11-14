"""Classification engine for Subject Domains and Resource Types."""
from __future__ import annotations

from typing import NamedTuple
from src.utils import normalize_persian_text


class ClassificationResult(NamedTuple):
    subject_category_en: str
    subject_category_fa: str
    subject_slug: str
    resource_type_en: str
    resource_type_fa: str
    resource_slug: str
    confidence: float
    matched_rules: list[str]


# Subject Domain Taxonomy
SUBJECT_DOMAINS = [
    {
        "en": "Census",
        "fa": "سرشماری",
        "slug": "census",
        "keywords": ["سرشماری", "نفوس و مسکن", "سرشماری عمومی", "census"],
    },
    {
        "en": "Prices and Inflation",
        "fa": "قیمت‌ها و تورم",
        "slug": "prices_inflation",
        "keywords": [
            "شاخص قیمت", "شاخص های قیمت", "شاخص‌های قیمت", "قیمت", "قیمت ها", "قیمت‌ها",
            "تورم", "تولیدکننده", "مصرف کننده", "مصرف‌کننده", "قیمت کالا", "اقلام خوراکی",
            "شاخص بهای", "price", "cpi", "ppi"
        ],
    },

    {
        "en": "Household Expenditure and Income",
        "fa": "هزینه و درآمد خانوار",
        "slug": "household_income_expenditure",
        "keywords": ["هزینه و درآمد", "بودجه خانوار", "درآمد خانوار", "هزینه خانوار", "دهک های درآمدی", "دهک"],
    },
    {
        "en": "Employment and Labor Market",
        "fa": "اشتغال و بازار کار",
        "slug": "employment_labor",
        "keywords": ["اشتغال", "بیکاری", "نیروی کار", "شاغل", "بیکار", "بازار کار", "مزد و حقوق", "employment", "labor"],
    },
    {
        "en": "Agriculture",
        "fa": "کشاورزی",
        "slug": "agriculture",
        "keywords": ["کشاورزی", "زراعت", "باغداری", "دامداری", "دام", "کشتارگاه", "محصولات کشاورزی", "طیور", "مرغداری", "گاوداری", "شیلات"],
    },
    {
        "en": "Industry and Manufacturing",
        "fa": "صنعت و معدن",
        "slug": "industry_manufacturing",
        "keywords": ["صنعت", "معدن", "صنعتی", "کارگاه صنعتی", "تولید صنعتی", "معادن", "ساخت"],
    },
    {
        "en": "Construction and Housing",
        "fa": "ساختمان و مسکن",
        "slug": "construction_housing",
        "keywords": ["ساختمان", "مسکن", "پروانه های ساختمانی", "پروانه ساختمانی", "ساختمانی", "زمین و ساختمان", "معاملات مسکن", "اجاره"],
    },
    {
        "en": "Economy and National Accounts",
        "fa": "اقتصاد و حساب‌های ملی",
        "slug": "economy_national_accounts",
        "keywords": ["حساب های ملی", "حساب‌های ملی", "حساب های منطقه ای", "تولید ناخالص", "اقتصادی", "ارزش افزوده", "gdp", "سرمایه گذاری"],
    },
    {
        "en": "Population and Demographics",
        "fa": "جمعیت و نفوس",
        "slug": "population",
        "keywords": ["جمعیت", "جمعیتی", "ولادت", "وفات", "ازدواج", "طلاق", "مهاجرت", "تراکم جمعیت", "ساختار سنی"],
    },
    {
        "en": "Environment and Natural Resources",
        "fa": "محیط زیست و منابع طبیعی",
        "slug": "environment_natural_resources",
        "keywords": ["محیط زیست", "منابع طبیعی", "آب", "هوا", "آلودگی", "پسماند", "جنگل", "مراتع", "بارندگی", "اقلیم"],
    },
    {
        "en": "Energy",
        "fa": "انرژی",
        "slug": "energy",
        "keywords": ["انرژی", "برق", "نفت", "گاز", "پتروشیمی", "نیروگاه", "سوخت"],
    },
    {
        "en": "Trade and Commerce",
        "fa": "بازرگانی و تجارت",
        "slug": "trade_commerce",
        "keywords": ["بازرگانی", "تجارت", "صادرات", "واردات", "گمرک", "تراز بازرگانی"],
    },
    {
        "en": "Transportation",
        "fa": "حمل و نقل",
        "slug": "transportation",
        "keywords": ["حمل و نقل", "راه آهن", "هوایی", "دریایی", "جاده ای", "خودرو", "سفر"],
    },
    {
        "en": "Education",
        "fa": "آموزش",
        "slug": "education",
        "keywords": ["آموزش", "دانش آموز", "دانشجو", "دانشگاه", "مدرسه", "سواد", "تحصیلات"],
    },
    {
        "en": "Health",
        "fa": "بهداشت و سلامت",
        "slug": "health",
        "keywords": ["سلامت", "بهداشت", "درمان", "بیمارستان", "پزشک", "بیماری", "مرگ و میر"],
    },
    {
        "en": "Social Statistics",
        "fa": "آمارهای اجتماعی و فرهنگی",
        "slug": "social_statistics",
        "keywords": ["اجتماعی", "فرهنگی", "رفاه", "تامین اجتماعی", "جرم", "قضایی", "سینما", "کتاب"],
    },
    {
        "en": "Regional and Provincial Statistics",
        "fa": "آمارهای منطقه‌ای و استانی",
        "slug": "regional_provincial",
        "keywords": ["استانی", "استان", "شهرستان", "منطقه ای", "سالنامه استانی"],
    },
    {
        "en": "Information and Communication Technology",
        "fa": "ارتباطات و فناوری اطلاعات",
        "slug": "ict",
        "keywords": ["ارتباطات", "فناوری اطلاعات", "اینترنت", "تلفن همراه", "رایانه", "فاوا", "ict"],
    },
    {
        "en": "Culture and Tourism",
        "fa": "فرهنگ و گردشگری",
        "slug": "culture_tourism",
        "keywords": ["گردشگری", "سیاحت", "هتل", "مسافر", "میراث فرهنگی", "جهانگردی"],
    },
]

# Resource Type Taxonomy
RESOURCE_TYPES = [
    {
        "en": "Statistical Yearbooks",
        "fa": "سالنامه‌های آماری",
        "slug": "yearbooks",
        "keywords": ["سالنامه", "سالنامه آماری", "yearbook"],
    },
    {
        "en": "Census Results",
        "fa": "نتایج سرشماری",
        "slug": "census_results",
        "keywords": ["سرشماری عمومی", "نتایج سرشماری"],
    },
    {
        "en": "Statistical Tables",
        "fa": "جداول آماری",
        "slug": "statistical_tables",
        "keywords": ["جدول", "جداول", "سری زمانی", "اکسل", "table"],
    },
    {
        "en": "Statistical Reports",
        "fa": "گزارش‌های آماری",
        "slug": "reports",
        "keywords": ["گزارش", "نشریه", "نتایج طرح", "طرح آمارگیری", "اطلاعات پروانه", "report"],
    },
    {
        "en": "Methodologies",
        "fa": "روش‌شناسی",
        "slug": "methodologies",
        "keywords": ["روش شناسی", "روش‌شناسی", "مفاهیم و تعاریف", "دستورالعمل", "طرح تفصیلی"],
    },
    {
        "en": "Questionnaires",
        "fa": "پرسشنامه‌ها",
        "slug": "questionnaires",
        "keywords": ["پرسشنامه", "فرم آمارگیری"],
    },
    {
        "en": "Maps and Spatial Data",
        "fa": "نقشه‌ها و داده‌های مکانی",
        "slug": "spatial_data",
        "keywords": ["نقشه", "مکانی", "gis", "ژئودب"],
    },
    {
        "en": "Datasets",
        "fa": "مجموعه‌داده",
        "slug": "datasets",
        "keywords": ["داده ها", "مجموعه داده", "پایگاه داده", "ریز داده", "میکروداده", "داده های خام"],
    },
]


def classify_record(
    title: str | None,
    source_category: str | None,
    release_type: str | None = None,
    file_format: str | None = None,
) -> ClassificationResult:
    """Classify a record into a Subject Domain and a Resource Type."""
    clean_cat = normalize_persian_text(source_category).lower()
    clean_title = normalize_persian_text(title).lower()
    text_corpus = f"{clean_cat} {clean_title}"
    matched_rules: list[str] = []

    # Hierarchy parts (e.g. Top >> Middle >> Leaf)
    cat_parts = [p.strip() for p in clean_cat.split(">>")] if ">>" in clean_cat else [clean_cat]
    leaf_cat = cat_parts[-1] if cat_parts else ""

    # 1. Subject Classification
    selected_subject = None
    max_subject_score = 0

    for domain in SUBJECT_DOMAINS:
        score = 0
        for kw in domain["keywords"]:
            kw_low = kw.lower()
            if leaf_cat and kw_low in leaf_cat:
                score += 15  # Leaf category has highest specificity
                matched_rules.append(f"subject_leaf:{domain['slug']}:{kw}")
            elif clean_cat and kw_low in clean_cat:
                score += 4   # Higher-level category
                matched_rules.append(f"subject_category:{domain['slug']}:{kw}")
            elif kw_low in clean_title:
                score += 2   # Title keyword
                matched_rules.append(f"subject_title:{domain['slug']}:{kw}")
        if score > max_subject_score:
            max_subject_score = score
            selected_subject = domain

    if selected_subject and max_subject_score > 0:
        sub_en = selected_subject["en"]
        sub_fa = selected_subject["fa"]
        sub_slug = selected_subject["slug"]
    else:
        sub_en = "Other / Unclassified"
        sub_fa = "سایر / دسته‌بندی نشده"
        sub_slug = "other"

    # 2. Resource Type Classification
    selected_resource = None
    max_res_score = 0

    # If explicit release_type was extracted from HTML
    clean_release_type = normalize_persian_text(release_type).lower()
    if clean_release_type:
        for rt in RESOURCE_TYPES:
            for kw in rt["keywords"]:
                if kw in clean_release_type:
                    selected_resource = rt
                    matched_rules.append(f"resource_type_header:{rt['slug']}")
                    break
            if selected_resource:
                break

    if not selected_resource:
        for rt in RESOURCE_TYPES:
            score = 0
            for kw in rt["keywords"]:
                if kw.lower() in text_corpus:
                    score += 1
                    matched_rules.append(f"resource:{rt['slug']}:{kw}")
            if score > max_res_score:
                max_res_score = score
                selected_resource = rt


    # Fallback heuristic based on file format
    if not selected_resource:
        if file_format in ["XLS", "XLSX", "CSV"]:
            selected_resource = {
                "en": "Statistical Tables",
                "fa": "جداول آماری",
                "slug": "statistical_tables",
            }
            matched_rules.append("resource:format_fallback:table")
        else:
            selected_resource = {
                "en": "Statistical Reports",
                "fa": "گزارش‌های آماری",
                "slug": "reports",
            }
            matched_rules.append("resource:format_fallback:report")

    res_en = selected_resource["en"]
    res_fa = selected_resource["fa"]
    res_slug = selected_resource["slug"]

    confidence = min(1.0, 0.4 + (max_subject_score * 0.2) + (max_res_score * 0.2))

    return ClassificationResult(
        subject_category_en=sub_en,
        subject_category_fa=sub_fa,
        subject_slug=sub_slug,
        resource_type_en=res_en,
        resource_type_fa=res_fa,
        resource_slug=res_slug,
        confidence=confidence,
        matched_rules=matched_rules,
    )
