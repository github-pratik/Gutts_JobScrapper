from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from jobspy_scrape import (  # noqa: E402
    ScrapeConfig,
    apply_link_status_filter,
    apply_structured_filters,
    build_curated_jobs,
    dedupe_jobs,
    enforce_recency,
)


class JobspyScrapeTests(unittest.TestCase):
    def test_build_curated_jobs_schema(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "title": "Data Analyst Intern",
                    "company": "Acme",
                    "site": "indeed",
                    "date_posted": "2026-04-21T08:00:00Z",
                    "location": "Pune, India",
                    "job_type": "Internship",
                    "experience_range": "0-1 years",
                    "min_amount": 20000,
                    "max_amount": 30000,
                    "interval": "month",
                    "currency": "INR",
                    "skills": ["excel", "sql"],
                    "description": "A" * 600,
                    "job_url": "https://example.com/job-1",
                }
            ]
        )

        curated = build_curated_jobs(raw, search_query="data analyst", scraped_at="2026-04-21 08:00:00")
        expected = {
            "job_title",
            "company",
            "source_site",
            "posted_date",
            "location",
            "work_type",
            "experience",
            "salary",
            "skills",
            "summary",
            "job_url",
            "search_query",
            "scraped_at",
        }
        self.assertTrue(expected.issubset(set(curated.columns)))
        self.assertLessEqual(len(curated.loc[0, "summary"]), 320)
        self.assertEqual(curated.loc[0, "skills"], "excel, sql")

    def test_enforce_recency(self) -> None:
        rows = pd.DataFrame(
            [
                {"job_title": "Recent", "posted_date": "2026-04-20"},
                {"job_title": "Old", "posted_date": "2026-01-01"},
            ]
        )
        filtered = enforce_recency(
            rows,
            max_age_days=14,
            now_utc=datetime(2026, 4, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(filtered["job_title"].tolist(), ["Recent"])

    def test_apply_link_status_filter(self) -> None:
        rows = pd.DataFrame(
            [
                {"job_title": "A", "link_status": "live"},
                {"job_title": "B", "link_status": "unknown"},
                {"job_title": "C", "link_status": "dead"},
            ]
        )
        strict = apply_link_status_filter(rows, include_unknown_links=False)
        relaxed = apply_link_status_filter(rows, include_unknown_links=True)
        self.assertEqual(strict["job_title"].tolist(), ["A"])
        self.assertEqual(relaxed["job_title"].tolist(), ["A", "B"])

    def test_apply_structured_filters(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    "job_title": "Data Analyst Intern",
                    "summary": "Uses SQL and Python",
                    "skills": "sql,python",
                    "experience": "0-1 years",
                    "work_type": "remote",
                    "location": "Pune",
                },
                {
                    "job_title": "Senior Manager",
                    "summary": "Leadership role",
                    "skills": "excel",
                    "experience": "8+ years",
                    "work_type": "onsite",
                    "location": "Mumbai",
                },
            ]
        )
        config = ScrapeConfig(
            include_keywords="analyst",
            exclude_keywords="manager",
            must_have_skills="sql",
            min_experience_years=0,
            max_experience_years=2,
            work_modes=["remote"],
        )
        filtered = apply_structured_filters(rows, config)
        self.assertEqual(filtered["job_title"].tolist(), ["Data Analyst Intern"])

    def test_dedupe_jobs_fallback(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    "job_title": "Data Analyst",
                    "company": "Acme",
                    "location": "Pune",
                    "posted_date": "2026-04-20",
                    "job_url": "",
                },
                {
                    "job_title": "Data Analyst",
                    "company": "Acme",
                    "location": "Pune",
                    "posted_date": "2026-04-20",
                    "job_url": "",
                },
            ]
        )
        deduped = dedupe_jobs(rows)
        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
