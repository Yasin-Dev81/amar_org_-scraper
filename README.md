# سامانه جامع کاوش، استخراج و آرشیوسازی داده‌های آماری درگاه ملی آمار ایران (amar.org.ir)

سیستم پیشرفته و ماژولار مبتنی بر پایتون ۳.۱۲+ برای کاوش خودکار، استخراج جامع فراداده‌ها، دسته‌بندی موضوعی دوبعدی، دانلود اتمیک فایل‌ها و ایجاد آرشیو محلی ساختاریافته و جستجوپذیر از داده‌ها و نشریات مرکز آمار ایران ([amar.org.ir](https://www.amar.org.ir/)).

---

## ۱. ویژگی‌های کلیدی سامانه

- **کاوش هوشمند و بدون محدودیت سخت (Smart Discovery & Pagination):**
  - شناسایی خودکار سازوکار صفحه‌بندی دینامیک DNN درگاه ملی آمار بدون نیاز به کدگذاری تعداد صفحات.
  - پیمایش صفحات فهرست و استخراج لینک تمامی رکوردهای تفصیلی (`/statistical-information/statid/{id}`).
  - ردیابی صفحات مشاهده‌شده در SQLite و جلوگیری از حلقه‌های تکراری.
- **موتور دانلود اتمیک و مقاوم (Atomic Download Engine):**
  - تشخیص نوع واقعی فایل بر اساس امضای بایتی (Magic Bytes)، سرآیندهای پاسخ و اعتبارسنجی ساختار فایل‌ها (عدم اتکا به پسوند URL).
  - دانلود جریانی (Streaming) و ذخیره‌سازی موقت با پسوند `.part` و تغییر نام اتمیک پس از پایان دانلود موفق.
  - پشتیبانی از ادامه دانلود فایل‌های متوقف‌شده (Resume via HTTP Range Requests).
  - محاسبه بلادرنگ چک‌سام امنیتی SHA-256 برای تضمین یکپارچگی داده‌ها.
- **جلوگیری هوشمند از افزونگی و ذخیره‌سازی داده‌های تکراری (Deduplication):**
  - شناسایی فایل‌های یکسان با محتوای مشابه در رکوردهای مختلف بر مبنای هش SHA-256 و ذخیره یک نسخه مرجع (Canonical) با پیوند در فراداده‌ها.
- **دسته‌بندی موضوعی دوبعدی (Two-Dimensional Taxonomy):**
  - **بعد اول (حوزه موضوعی - Subject Domain):** جمعیت، سرشماری، تورم و شاخص‌های قیمت، اقتصاد و حساب‌های ملی، کشاورزی، مسکن، صنعت و معدن، اشتغال و بازار کار، تجارت، انرژی، محیط زیست و...
  - **بعد دوم (نوع منبع آماری - Resource Type):** جداول آماری، گزارش‌های آماری، سالنامه‌ها، نتایج سرشماری، روش‌شناسی، پرسشنامه‌ها، نقشه‌ها و داده‌های مکانی، مجموعه‌داده‌ها.
- **برچسب‌گذاری دوزبانه (فارسی و انگلیسی):**
  - استخراج خودکار تگ‌های موضوعی، فرمت فایل، سال مرجع و دوره آماری برای تسهیل جستجوی آینده.
- **تولید خودکار شناسنامه فراداده (JSON Sidecar):**
  - ایجاد یک فایل فراداده ساختاریافته `.metadata.json` به ازای هر فایل دانلود شده در کنار فایل اصلی.
- **پایگاه‌داده توکار رابطه ای SQLite:**
  - ثبت تمام رکوردها، وضعیت فایل‌ها، تاریخچه دانلود، تگ‌ها و خطاها با پشتیبانی از WAL mode و نمایه‌سازی (Indexing).
- **داشبورد تحلیلی و گزارش‌های جامع:**
  - تولید خودکار گزارش آماری بصری HTML (`reports/download_summary.html`)، خروجی‌های استاندارد `records.csv`، `files.csv`، `records.jsonl`، `files.jsonl` و گزارش خطاهای دانلود.

---

## ۲. معماری ماژولار پروژه

```text
amar_statistical_archive/
│
├── data/                               # آرشیو ساختاریافته فایل‌های دانلود شده
│   └── {subject_slug}/                 # دسته‌بندی موضوعی (مانند: prices_inflation, population)
│       └── {resource_slug}/            # نوع منبع (مانند: reports, statistical_tables)
│           └── {year}/                 # سال مرجع آماری (مانند: 1404)
│               └── {record_id}_{slug}/ # پوشه اختصاصی رکورد
│                   ├── file.xlsx       # فایل داده اصلی
│                   └── file.xlsx.metadata.json # شناسنامه فراداده
│
├── metadata/                           # کاتالوگ‌های جامع فراداده‌ها
│   ├── records.jsonl                   # رکوردهای کشف شده در قالب JSONL
│   ├── files.jsonl                     # فایل‌های کشف شده در قالب JSONL
│   ├── records.csv                     # خروجی جدول رکوردهای آماری
│   ├── files.csv                       # خروجی جدول مشخصات فایل‌ها
│   ├── categories.json                 # دسته‌بندی‌های رسمی کشف شده از درگاه
│   ├── tags.json                       # تگ‌های استخراج شده
│   └── duplicate_files.json            # گزارش فایل‌های دارای هش یکسان
│
├── database/
│   └── scraper_state.sqlite            # پایگاه‌داده وضعیت کاوش و دانلود
│
├── logs/
│   ├── scraper.log                     # گزارش عمومی عملیات
│   └── download_errors.log             # گزارش خطاهای احتمالی
│
├── reports/
│   ├── download_summary.html           # داشبورد مدیریتی و بصری نتایج
│   ├── download_summary.json           # خلاصه آماری آرشیو به صورت JSON
│   ├── unclassified_resources.csv      # رکوردهای نیازمند بازبینی
│   └── download_errors.csv             # فهرست فایل‌های غیرقابل دسترس
│
├── config/
│   └── config.yaml                     # تنظیمات سامانه
│
├── src/                                # کدهای منبع سامانه
│   ├── main.py                         # رابط خط فرمان (CLI)
│   ├── config.py                       # بارگذاری و اعتبارسنجی تنظیمات
│   ├── crawler.py                      # موتور اصلی کاوش و هماهنگی عملیات
│   ├── pagination.py                   # مدیریت صفحه‌بندی و پیمایش دینامیک
│   ├── page_parser.py                  # استخراج اطلاعات صفحات فهرست
│   ├── record_parser.py                # استخراج اطلاعات صفحه تفصیلی رکورد
│   ├── download_manager.py             # دانلود فایل‌ها، هشینگ و ایجاد Sidecar
│   ├── file_detector.py                # تشخیص فرمت از روی امضای بایتی
│   ├── classifier.py                   # موتور دسته‌بندی دوبعدی
│   ├── tagger.py                       # سیستم برچسب‌گذاری دوزبانه
│   ├── metadata_manager.py             # تولید فایل‌های Sidecar و کاتالوگ‌ها
│   ├── database.py                     # مدیریت پایگاه‌داده SQLite
│   ├── deduplicator.py                 # اعتبارسنجی و پیوند فایل‌های تکراری
│   ├── validators.py                   # ممیزی و ارزیابی صحت فایل‌ها
│   ├── report_generator.py             # تولید گزارش‌های تحلیلی و HTML
│   └── utils.py                        # ابزارهای نرمال‌سازی فارسی، تاریخ و URL
│
├── tests/                              # تست‌های خودکار واحد و یکپارچگی
│   ├── fixtures/                       # صفحات نمونه واقعی سایت برای تست آفلاین
│   ├── test_utils.py
│   ├── test_file_detector.py
│   ├── test_classifier.py
│   ├── test_record_parser.py
│   ├── test_database.py
│   ├── test_validators.py
│   └── test_integration.py
│
├── pyproject.toml                      # پیکربندی بسته‌ها و uv
├── uv.lock                             # نسخه قفل‌شده وابستگی‌ها
└── README.md                           # راهنمای جامع فارسی سامانه
```

---

## ۳. پیش‌نیازها و راهنمای نصب

سامانه از مدیر بسته **uv** (نسخه `0.13.x`) و **Python 3.11** سیستمی (`/usr/bin/python3.11`) استفاده می‌کند.

> **محیط هدف:** Debian 12 (Bookworm) با معماری `i386` (۳۲ بیتی، `i686-unknown-linux-gnu`)، بدون رابط گرافیکی و با ۲ گیگابایت رم. چون uv برای لینوکس `i686` پایتون آماده ارائه نمی‌دهد، دانلود خودکار پایتون در `uv.toml` غیرفعال شده (`python-downloads = "manual"`) و از پایتون سیستم استفاده می‌شود. همچنین `concurrent-builds = 1` از کمبود حافظه هنگام ساخت بسته‌ها از سورس جلوگیری می‌کند.

### گام اول: نصب ابزار uv (در صورت عدم نصب)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### گام دوم: همگام‌سازی محیط مجازی و وابستگی‌ها
در دایرکتوری پروژه فرمان زیر را اجرا نمایید:
```bash
sudo apt install python3.11 python3.11-venv python3.11-dev build-essential
cd amar_org
UV_CONCURRENT_BUILDS=1 uv sync --no-python-downloads --python /usr/bin/python3.11
```

تمامی بسته‌ها شامل `httpx`، `beautifulsoup4`، `pydantic`، `jinja2`، `filetype`، `pyyaml` و ابزارهای تست در محیط مجازی `.venv` نصب می‌شوند. برای سازگاری با معماری ۳۲ بیتی، به‌جای `lxml` از تجزیه‌گر داخلی `html.parser` استفاده می‌شود. بسته‌های `pyyaml` و `markupsafe` برای `i686` چرخ (wheel) آماده ندارند و از سورس ساخته می‌شوند (ساخت سبک و کم‌مصرف).

### گام سوم: متغیرهای محیطی
```bash
cp .env.example .env
uv run --env-file .env python -m src.main run
```

### اجرای طولانی‌مدت از طریق SSH
برای اجرای بدون نظارت، از `tmux`، `screen` یا `nohup` استفاده کنید:
```bash
nohup uv run --env-file .env python -m src.main run --resume > logs/nohup.out 2>&1 &
```
فایل‌های لاگ با چرخش خودکار (حداکثر ۵ مگابایت و ۳ نسخه پشتیبان) محدود می‌شوند. در صورت کمبود فضای دیسک: `uv cache prune`.

---

## ۴. راهنمای استفاده از رابط خط فرمان (CLI)

سامانه دارای دستورات متنوع و مجزا برای مراحل مختلف است:

### ۱. بررسی و شناسایی ساختار سایت (Inspect)
بررسی آنلاین سرآیندها، ساختار ماژول‌ها و تست اتصال به صفحه شاخص درگاه:
```bash
uv run python -m src.main inspect
```

### ۲. اجرای کامل فرآیند (Run)
اجرای خودکار تمامی مراحل (کشف رکوردها -> دانلود فایل‌ها -> خروجی فراداده‌ها -> تولید گزارش HTML):
```bash
uv run python -m src.main run
```

برای محدود کردن تعداد صفحات یا رکوردها در تست اولیه:
```bash
uv run python -m src.main run --max-pages 5 --max-records 20
```

برای کاوش و ثبت فراداده‌ها بدون دانلود فیزیکی فایل‌ها (حالت شبیه‌سازی):
```bash
uv run python -m src.main run --dry-run
```

### ۳. ادامه فرآیند متوقف‌شده (Resume)
در صورتی که عملیات به دلیل قطعی اینترنت متوقف شود، سامانه از وضعیت ذخیره‌شده در SQLite کار را ادامه می‌دهد:
```bash
uv run python -m src.main run --resume
```

### ۴. کاوش رکوردهای جدید بدون دانلود (Discover)
```bash
uv run python -m src.main discover
```

### ۵. دانلود فایل‌های صف‌آرایی‌شده (Download)
```bash
uv run python -m src.main download
```

### ۶. تلاش مجدد برای فایل‌های ناموفق (Retry Failed)
```bash
uv run python -m src.main retry-failed
```

### ۷. ممیزی و راستی‌آزمایی یکپارچگی فایل‌های دانلود شده (Audit)
بررسی یک‌به‌یک فایل‌های روی دیسک، اعتبارسنجی مجدد هش SHA-256 و اطمینان از سلامت فایل‌های Sidecar:
```bash
uv run python -m src.main audit
```

### ۸. مشاهده آمار آرشیو (Stats)
```bash
uv run python -m src.main stats
```

### ۹. تولید مجدد گزارش‌ها و کاتالوگ‌های فراداده (Report)
```bash
uv run python -m src.main report
```

---

## ۵. تنظیمات سامانه (`config/config.yaml`)

فایل [config/config.yaml](file:///Users/yasin_dev81/Desktop/amar_org/config/config.yaml) امکان کنترل تمامی پارامترها را فراهم می‌سازد:

```yaml
website:
  base_url: "https://www.amar.org.ir"
  start_urls:
    - "https://www.amar.org.ir/statistical-information/currentpage/3"
    - "https://www.amar.org.ir/statistical-information"
  user_agent: "Mozilla/5.0 ..."
  include_external_domains: false

scraping:
  max_concurrent_requests: 4    # حداکثر اتصالات همزمان
  request_delay: 0.5            # تاخیر مودبانه بین درخواست‌ها (ثانیه)
  connection_timeout: 30.0      # تایم‌اوت ارتباط
  retry_count: 3                # تعداد دفعات تلاش مجدد
  retry_backoff_factor: 2.0     # ضریب افزایش تاخیر تلاش مجدد

download:
  max_concurrent_downloads: 3   # حداکثر دانلود همزمان فایل‌ها
  download_delay: 0.3
  max_file_size_bytes: 524288000 # حداکثر حجم فایل (۵۰۰ مگابایت)
  verify_ssl: false             # غیرفعال‌سازی برای سرورهای دولتی با ریشه ملی
  chunk_size_bytes: 65536       # سایز بافر دانلود (۶۴ کیلوبایت)
  resume_interrupted: true      # پشتیبانی از ادامه دانلود فایل‌های نیمه‌کاره
```

---

## ۶. ساختار فراداده‌ها (Metadata Sidecar JSON)

برای هر فایل دانلود شده، یک فایل هم‌نام با پسوند `.metadata.json` تولید می‌شود:

```json
{
  "record": {
    "record_id": 58297,
    "title_fa": "نتایج آمارگیری از گردشگران ملی - بهار و تابستان 1404",
    "source_category": "آمارهای اقتصادی >> گردشگری >> گردشگری",
    "normalized_category": "Culture and Tourism",
    "resource_type": "Statistical Reports",
    "subject_area": "فرهنگ و گردشگری",
    "publication_date_fa": "1405/07/28",
    "publication_date_iso": "1405-07-28",
    "gregorian_date_iso": "2026-10-20",
    "statistical_period": "بهار و تابستان 1404",
    "reference_year": 1404,
    "geographical_coverage": "National",
    "publisher": "درگاه ملی آمار",
    "original_record_url": "https://www.amar.org.ir/statistical-information/statid/58297",
    "language": "fa"
  },
  "file": {
    "file_id": 1,
    "original_filename": "ne_gardeshgaran_melli_1404_01-02-14050804130328.xlsx",
    "local_filename": "ne_gardeshgaran_melli_1404_01-02-14050804130328.xlsx",
    "relative_path": "data/culture_tourism/reports/1404/.../file.xlsx",
    "file_extension": ".xlsx",
    "detected_file_format": "XLSX",
    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "file_size_bytes": 163815,
    "sha256": "1b455d3daa86be343ac349649f61d78b344ee99697ce25d63fde0a8ff84316ae",
    "download_url": "https://www.amar.org.ir/Portals/0/Statistics/...",
    "download_status": "downloaded",
    "download_timestamp": "2026-11-12T10:09:05.427491+00:00",
    "subject_category": "culture_tourism",
    "resource_type": "reports",
    "reference_year": 1404,
    "language": "fa"
  },
  "tags": {
    "tags_fa": ["اکسل", "بهار و تابستان 1404", "سال 1404", "فرهنگ و گردشگری"],
    "tags_en": ["culture-and-tourism", "reports", "xlsx", "year-1404"]
  }
}
```

---

## ۷. تست‌های خودکار (Automated Testing)

پروژه دارای یک مجموعه کامل از تست‌های واحد و یکپارچگی است که با `pytest` اجرا می‌شوند:

```bash
uv run pytest -v
```

پوشش تست‌ها:
- نرمال‌سازی کاراکترها و اعداد فارسی و تاریخ شمسی به میلادی
- اعتبارسنجی امضاهای بایتی (Magic Bytes) و شناسایی صفحات خطای سرور
- دسته‌بندی موضوعی و استخراج برچسب‌های دوزبانه
- پارس صفحات واقعی فهرست و جزئیات رکورد با استفاده از HTML Fixtures
- تراکنش‌ها و جداول SQLite
- آزمون پایپ‌لاین کامل و ممیزی اعتبارسنجی فایل‌ها

---

## ۸. نکات اجرایی و خطایابی

1. **گواهینامه SSL مراکز دولتی ایران:**
   سرورهای درگاه ملی آمار از گواهینامه‌های صادرشده توسط مراجع ریشه ملی استفاده می‌کنند. در `config.yaml` مقدار `verify_ssl: false` قرار داده شده است تا از خطای اعتبارسنجی SSL در محیط‌های غیراستاندارد جلوگیری شود.
2. **پشتیبانی سرور از HEAD vs GET:**
   سرور درگاه درخواست‌های `HEAD` (`curl -I`) را مسدود می‌کند. سامانه منحصراً از درخواست‌های `GET` جریانی و هدرهای `Range` برای دریافت قطعه اول و دانلود فایل‌ها استفاده می‌کند.
3. **نرخ درخواست مودبانه:**
   درگاه ملی آمار یک سرور سازمانی است. به منظور پایداری ارتباط، پارامترهای تاخیر (`request_delay` و `download_delay`) روی مقادیر معقول تنظیم شده‌اند.
