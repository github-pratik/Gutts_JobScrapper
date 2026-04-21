"""
Job board scraper aligned with GUTTS (Ground Up Trade & Talent Solutions):
entry-level Plumbing / HVAC and skilled-trades placement in Northern Virginia
and the DC metro. See GUTTS_COMPANY_CONTEXT.md for business context.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from jobspy import scrape_jobs

# GUTTS placement focus: plumbing, HVAC, apprentices/helpers/entry-level trade roles.
# Indeed searches title + description; use OR groups and quoted phrases as needed.
GUTTS_DEFAULT_SEARCH = (
    '(plumber OR plumbing OR HVAC OR HVACR OR "sheet metal" OR pipefitter OR steamfitter '
    'OR "commercial HVAC" OR "residential HVAC" OR boilermaker OR apprentice) '
    '(apprentice OR "entry level" OR helper OR trainee OR installer OR technician '
    'OR "field service" OR journeyman) '
    '-software -developer -IT -python -java'
)

# Second pass: complementary keywords so different boards surface different postings.
GUTTS_SECOND_PASS_SEARCH = (
    '(HVAC OR HVACR OR refrigeration OR chiller OR boiler OR "service technician" '
    'OR "maintenance technician" OR "building engineer" OR controls) '
    '(apprentice OR installer OR mechanic OR trainee OR helper OR "route technician") '
    'OR (mechanical OR contractor OR "facilities") (plumber OR plumbing) apprentice '
    '-software -developer -IT'
)

# DC metro centroid + wide radius covers NOVA, DC, MD suburbs, and more of the region.
GUTTS_DEFAULT_LOCATION = "Washington, DC"
GUTTS_DEFAULT_DISTANCE_MILES = 100

# Google Jobs: optional override. If None, JobSpy builds a query from search_term + location + recency.
# Paste a query copied from Google Jobs in the browser for best results (see JobSpy README).
GUTTS_GOOGLE_SEARCH_TERM: str | None = None


@dataclass
class ScrapeConfig:
    search_term: str = GUTTS_DEFAULT_SEARCH
    second_pass_search: str = GUTTS_SECOND_PASS_SEARCH
    location: str = GUTTS_DEFAULT_LOCATION
    distance: int = GUTTS_DEFAULT_DISTANCE_MILES
    sites: list[str] = field(
        default_factory=lambda: [
            "indeed",
            "zip_recruiter",
            "linkedin",
            "glassdoor",
            "google",
        ]
    )
    results_wanted: int = 50
    multi_query: bool = False
    hours_old: int = 336
    country_indeed: str = "USA"
    google_search_term: str | None = GUTTS_GOOGLE_SEARCH_TERM
    output: str | None = None
    output_dir: str = "."
    linkedin_fetch_description: bool = False
    verbose: int = 1


def resolve_output_path(output: str | None, output_dir: str) -> Path:
    """
    If output is None, write a new file each run: gutts_jobs_YYYY-MM-DD_HHMMSS.csv
    If output is set, use that path (relative paths join output_dir).
    """
    base = Path(output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    if output:
        p = Path(output)
        path = p if p.is_absolute() else (base / p)
    else:
        stamp = datetime.now().strftime("gutts_jobs_%Y-%m-%d_%H%M%S")
        path = base / f"{stamp}.csv"
    return path.resolve()


def dedupe_by_job_url(jobs: pd.DataFrame) -> pd.DataFrame:
    if jobs.empty or "job_url" not in jobs.columns:
        return jobs
    before = len(jobs)
    subset = jobs[jobs["job_url"].notna() & (jobs["job_url"].astype(str).str.len() > 0)]
    if subset.empty:
        return jobs
    deduped = jobs.drop_duplicates(subset=["job_url"], keep="first").reset_index(drop=True)
    if len(deduped) < before:
        print(f"Deduplicated by job_url: {before} -> {len(deduped)} rows")
    return deduped


def sort_by_recency(jobs: pd.DataFrame) -> pd.DataFrame:
    if jobs.empty or "date_posted" not in jobs.columns:
        return jobs
    return jobs.sort_values(by="date_posted", ascending=False, na_position="last").reset_index(
        drop=True
    )


def run_one_scrape(
    *,
    site_name: list[str],
    search_term: str,
    location: str,
    distance: int,
    results_wanted: int,
    hours_old: int,
    country_indeed: str,
    google_search_term: str | None,
    linkedin_fetch_description: bool,
    verbose: int,
) -> pd.DataFrame:
    kwargs: dict = dict(
        site_name=site_name,
        search_term=search_term,
        location=location,
        distance=distance,
        results_wanted=results_wanted,
        hours_old=hours_old,
        country_indeed=country_indeed,
        linkedin_fetch_description=linkedin_fetch_description,
        verbose=verbose,
    )
    if google_search_term is not None and str(google_search_term).strip():
        kwargs["google_search_term"] = google_search_term.strip()
    return scrape_jobs(**kwargs)


def config_from_args(args: argparse.Namespace) -> ScrapeConfig:
    return ScrapeConfig(
        search_term=args.search_term,
        second_pass_search=args.second_pass_search,
        location=args.location,
        distance=args.distance,
        sites=args.sites,
        results_wanted=args.results_wanted,
        multi_query=args.multi_query,
        hours_old=args.hours_old,
        country_indeed=args.country_indeed,
        google_search_term=args.google_search_term,
        output=args.output,
        output_dir=args.output_dir,
        linkedin_fetch_description=args.linkedin_fetch_description,
        verbose=args.verbose,
    )


def _normalize_google_term(value: str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def run_gutts_scrape(
    config: ScrapeConfig,
    log: Callable[[str], None] | None = print,
) -> tuple[Path, int]:
    out_path = resolve_output_path(config.output, config.output_dir)
    google_term = _normalize_google_term(config.google_search_term)

    if log:
        log("GUTTS-aligned job scrape (Plumbing / HVAC / skilled trades, wider DMV / DC metro)")
        log(f"Output file: {out_path}")
        log(
            f"sites={config.sites}, location='{config.location}' (+{config.distance} mi), "
            f"results_wanted={config.results_wanted}, multi_query={config.multi_query}"
        )

    passes: list[str] = [config.search_term]
    if config.multi_query:
        passes.append(config.second_pass_search)

    frames: list[pd.DataFrame] = []
    for i, term in enumerate(passes, start=1):
        if log:
            label = f"pass {i}/{len(passes)}"
            log(f"{label}: search ({len(term)} chars)...")
        df = run_one_scrape(
            site_name=config.sites,
            search_term=term,
            location=config.location,
            distance=config.distance,
            results_wanted=config.results_wanted,
            hours_old=config.hours_old,
            country_indeed=config.country_indeed,
            google_search_term=google_term,
            linkedin_fetch_description=config.linkedin_fetch_description,
            verbose=config.verbose,
        )
        df["search_pass"] = term[:200] + ("..." if len(term) > 200 else "")
        frames.append(df)

    jobs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    jobs = dedupe_by_job_url(jobs)
    jobs = sort_by_recency(jobs)

    if log:
        log(f"Found {len(jobs)} jobs (after merge/dedupe)")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    jobs["scraped_at"] = timestamp
    jobs.to_csv(
        str(out_path),
        quoting=csv.QUOTE_NONNUMERIC,
        escapechar="\\",
        index=False,
    )
    if log:
        log(f"Saved results to {out_path}")
    return out_path, len(jobs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape job listings (JobSpy) with defaults tuned for GUTTS: "
            "Plumbing/HVAC and entry-level skilled trades near Fairfax / NOVA / DC metro. "
            "Uses multiple boards by default (Indeed, ZipRecruiter, LinkedIn, Glassdoor, Google)."
        )
    )
    parser.add_argument(
        "--search-term",
        default=GUTTS_DEFAULT_SEARCH,
        help="Primary job search phrase (Indeed/LinkedIn/Glassdoor/Zip; default: GUTTS trades).",
    )
    parser.add_argument(
        "--second-pass-search",
        default=GUTTS_SECOND_PASS_SEARCH,
        help="Alternate query used when --multi-query is enabled.",
    )
    parser.add_argument(
        "--location",
        default=GUTTS_DEFAULT_LOCATION,
        help=(
            "Search center for boards that use it (default: Washington, DC — broad DMV / NOVA reach "
            "with --distance)."
        ),
    )
    parser.add_argument(
        "--distance",
        type=int,
        default=GUTTS_DEFAULT_DISTANCE_MILES,
        help="Search radius in miles from --location (default: 100 for wide DC metro / MD / VA).",
    )
    parser.add_argument(
        "--sites",
        nargs="+",
        default=["indeed", "zip_recruiter", "linkedin", "glassdoor", "google"],
        help=(
            "Job boards to query together. Examples: indeed zip_recruiter linkedin glassdoor google. "
            "LinkedIn is stricter on rate limits; reduce --results-wanted if you see 429 errors."
        ),
    )
    parser.add_argument(
        "--results-wanted",
        type=int,
        default=50,
        help="Target rows per site per scrape (default: 50). Lower if boards rate-limit.",
    )
    parser.add_argument(
        "--multi-query",
        action="store_true",
        help=(
            "Run a second scrape with --second-pass-search, merge, and dedupe. "
            "Improves recall; takes roughly 2x longer and doubles load on each site."
        ),
    )
    parser.add_argument(
        "--hours-old",
        type=int,
        default=336,
        help="Max job age in hours (default: 336 = 14 days; wider net for listings).",
    )
    parser.add_argument(
        "--country-indeed",
        default="USA",
        help="Indeed/Glassdoor country filter (default: USA).",
    )
    parser.add_argument(
        "--google-search-term",
        default=GUTTS_GOOGLE_SEARCH_TERM,
        help=(
            "Exact Google Jobs query (overrides JobSpy's auto Google query). "
            "Tip: copy a working query from Google Jobs in your browser. "
            "Leave unset to let JobSpy build from --search-term + location + recency."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE.csv",
        help=(
            "Output CSV path. If omitted, a new file is created each run: "
            "gutts_jobs_YYYY-MM-DD_HHMMSS.csv under --output-dir (never overwrites by default)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output CSV (default: current directory). Used for auto names and relative --output.",
    )
    parser.add_argument(
        "--linkedin-fetch-description",
        action="store_true",
        help="Fetch full LinkedIn descriptions (slower, more requests).",
    )
    parser.add_argument(
        "--verbose",
        type=int,
        default=1,
        choices=[0, 1, 2],
        help="JobSpy log level: 0 errors only, 1 + warnings, 2 all (default: 1).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    run_gutts_scrape(config=config, log=print)


if __name__ == "__main__":
    main()
