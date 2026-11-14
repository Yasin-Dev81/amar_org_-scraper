"""Report generator for summary JSON, interactive HTML dashboard, and error CSVs."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
import jinja2

from src.database import DatabaseManager


HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>گزارش آرشیو اطلاعات آماری مرکز آمار ایران (amar.org.ir)</title>
    <style>
        :root {
            --primary: #1e3a8a;
            --primary-light: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Vazirmatn", Tahoma, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
            direction: rtl;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
            color: white;
            padding: 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        }
        header h1 {
            margin: 0 0 8px 0;
            font-size: 24px;
        }
        header p {
            margin: 0;
            opacity: 0.9;
            font-size: 14px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.05);
        }
        .stat-card .label {
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 6px;
        }
        .stat-card .value {
            font-size: 26px;
            font-weight: 700;
            color: var(--primary);
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }
        @media (max-width: 768px) {
            .grid-2 { grid-template-columns: 1fr; }
        }
        .panel {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.05);
        }
        .panel h2 {
            margin-top: 0;
            font-size: 18px;
            border-bottom: 2px solid var(--border);
            padding-bottom: 10px;
            color: var(--primary);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        th, td {
            padding: 10px 12px;
            text-align: right;
            border-bottom: 1px solid var(--border);
        }
        th {
            background: #f1f5f9;
            font-weight: 600;
        }
        tr:hover {
            background-color: #f8fafc;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-success { background: #d1fae5; color: #065f46; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-info { background: #dbeafe; color: #1e40af; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>سامانه آرشیو و داده‌کاوی درگاه ملی آمار ایران (amar.org.ir)</h1>
            <p>گزارش تحلیلی کشف، دسته‌بندی و دانلود داده‌ها و مستندات آماری کشور</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">صفحات کاوش شده</div>
                <div class="value">{{ stats.total_listing_pages_visited }}</div>
            </div>
            <div class="stat-card">
                <div class="label">کل رکوردهای کشف شده</div>
                <div class="value">{{ stats.total_records_discovered }}</div>
            </div>
            <div class="stat-card">
                <div class="label">کل فایل‌های شناسایی شده</div>
                <div class="value">{{ stats.total_files_identified }}</div>
            </div>
            <div class="stat-card">
                <div class="label">فایل‌های دانلود شده</div>
                <div class="value" style="color: var(--success);">{{ stats.successfully_downloaded_files }}</div>
            </div>
            <div class="stat-card">
                <div class="label">حجم کل دانلود شده</div>
                <div class="value">{{ stats.total_downloaded_size_mb }} مگابایت</div>
            </div>
            <div class="stat-card">
                <div class="label">فایل‌های ناموجود / خطا</div>
                <div class="value" style="color: var(--danger);">{{ stats.failed_downloads + stats.unavailable_files }}</div>
            </div>
            <div class="stat-card">
                <div class="label">فایل‌های تکراری (deduplicated)</div>
                <div class="value" style="color: var(--warning);">{{ stats.duplicate_files }}</div>
            </div>
            <div class="stat-card">
                <div class="label">رکوردهای بدون پیوست</div>
                <div class="value">{{ stats.records_without_attachments }}</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="panel">
                <h2>توزیع بر اساس فرمت فایل‌ها</h2>
                <table>
                    <thead>
                        <tr>
                            <th>فرمت</th>
                            <th>تعداد فایل</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for fmt, count in stats.files_by_format.items() %}
                        <tr>
                            <td><span class="badge badge-info">{{ fmt }}</span></td>
                            <td>{{ count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <div class="panel">
                <h2>توزیع بر اساس حوزه موضوعی</h2>
                <table>
                    <thead>
                        <tr>
                            <th>حوزه موضوعی</th>
                            <th>تعداد منابع</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for sub, count in stats.files_by_subject.items() %}
                        <tr>
                            <td>{{ sub }}</td>
                            <td>{{ count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="grid-2">
            <div class="panel">
                <h2>توزیع بر اساس نوع منبع آماری</h2>
                <table>
                    <thead>
                        <tr>
                            <th>نوع منبع</th>
                            <th>تعداد</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for rt, count in stats.files_by_resource_type.items() %}
                        <tr>
                            <td>{{ rt }}</td>
                            <td>{{ count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <div class="panel">
                <h2>توزیع زمانی (سال مرجع)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>سال آماری</th>
                            <th>تعداد رکوردها</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for yr, count in stats.records_by_year.items() %}
                        <tr>
                            <td>{{ yr }}</td>
                            <td>{{ count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """Generates summary JSON, HTML dashboard, and CSV error/unclassified exports."""

    def __init__(self, db: DatabaseManager, reports_dir: Path | str) -> None:
        self.db = db
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_reports(self) -> dict[str, Any]:
        """Generate download_summary.json, download_summary.html, and error CSVs."""
        stats = self.db.get_archive_stats()

        # 1. Summary JSON
        summary_json_path = self.reports_dir / "download_summary.json"
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        # 2. Interactive HTML Summary
        template = jinja2.Template(HTML_REPORT_TEMPLATE)
        html_out = template.render(stats=stats)
        html_summary_path = self.reports_dir / "download_summary.html"
        with open(html_summary_path, "w", encoding="utf-8") as f:
            f.write(html_out)

        # 3. Unclassified Resources CSV
        with self.db.get_connection() as conn:
            cur = conn.execute(
                """
                SELECT record_id, title_fa, source_category, normalized_category, original_record_url
                FROM records
                WHERE normalized_category IS NULL OR normalized_category = 'Other / Unclassified';
                """
            )
            unclassified = [dict(r) for r in cur.fetchall()]

        unclass_csv = self.reports_dir / "unclassified_resources.csv"
        with open(unclass_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["record_id", "title_fa", "source_category", "normalized_category", "original_record_url"],
            )
            writer.writeheader()
            writer.writerows(unclassified)

        # 4. Download Errors CSV
        with self.db.get_connection() as conn:
            cur = conn.execute(
                """
                SELECT file_id, record_id, original_filename, download_url, download_status, error_message
                FROM files
                WHERE download_status IN ('failed', 'unavailable') OR error_message IS NOT NULL;
                """
            )
            errors = [dict(r) for r in cur.fetchall()]

        errors_csv = self.reports_dir / "download_errors.csv"
        with open(errors_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["file_id", "record_id", "original_filename", "download_url", "download_status", "error_message"],
            )
            writer.writeheader()
            writer.writerows(errors)

        return stats
