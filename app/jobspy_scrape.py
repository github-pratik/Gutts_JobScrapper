"""
Job board scraper aligned with GUTTS (Ground Up Trade & Talent Solutions):
entry-level Plumbing / HVAC and skilled-trades placement in Northern Virginia
and the DC metro. See GUTTS_COMPANY_CONTEXT.md for business context.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib import error, request

import pandas as pd

from jobspy import scrape_jobs

# GUTTS placement focus: plumbing, HVAC, apprentices/helpers/entry-level trade roles.
# Indeed searches title + description; use OR groups and quoted phrases as needed.
GUTTS_DEFAULT_SEARCH = (
    '(("plumbing apprentice" OR "apprentice plumber" OR "plumber helper" OR "service plumber") '
    'OR ("hvac apprentice" OR "hvac helper" OR "hvac technician" OR "refrigeration technician")) '
    '(install OR service OR maintenance OR troubleshooting) '
    '(construction OR "property management" OR facilities OR "data center" OR "commercial hvac" '
    'OR "residential hvac") '
    '-software -developer -IT -sales -marketing -dispatcher'
)

# Second pass: complementary keywords so different boards surface different postings.
GUTTS_SECOND_PASS_SEARCH = (
    '("maintenance technician" OR "building engineer" OR "service technician" '
    'OR "pipefitter" OR "sheet metal mechanic" OR "hvacr technician") '
    '(apprentice OR helper OR trainee OR "entry level") '
    '(commercial OR residential OR facilities OR contractor) '
    '-software -developer -IT -sales -marketing'
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
    include_keywords: str = ""
    exclude_keywords: str = ""
    must_have_skills: str = ""
    min_experience_years: int | None = None
    max_experience_years: int | None = None
    work_modes: list[str] = field(default_factory=list)
    include_unknown_links: bool = False
    # Extra jobspy params (passed through to scrape_jobs when set)
    job_type: str | None = None
    enforce_annual_salary: bool = False
    user_agent: str | None = None
    proxies: list[str] | None = None
    # LLM relevance scoring (provider-agnostic via OpenAI-compatible API)
    score_with_llm: bool = False
    llm_score_threshold: int = 0
    llm_provider: str = "groq"          # "groq" | "gemini" | "openrouter"
    llm_model: str | None = None        # None = sensible default per provider


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


def dedupe_jobs(jobs: pd.DataFrame, log: Callable[[str], None] | None = None) -> pd.DataFrame:
    if jobs.empty:
        return jobs

    deduped = dedupe_by_job_url(jobs)
    before = len(deduped)

    dedupe_work = deduped.copy()
    for col in ("job_title", "company", "location", "posted_date"):
        if col not in dedupe_work.columns:
            dedupe_work[col] = ""
        dedupe_work[col] = dedupe_work[col].fillna("").astype(str).str.strip().str.lower()

    missing_url = dedupe_work["job_url"].fillna("").astype(str).str.strip().eq("")
    fallback_index = dedupe_work[missing_url].drop_duplicates(
        subset=["job_title", "company", "location", "posted_date"],
        keep="first",
    ).index
    keep_with_url = deduped[~missing_url]
    fallback_deduped = deduped.loc[fallback_index]
    deduped = pd.concat([keep_with_url, fallback_deduped], ignore_index=True)

    if log and len(deduped) < before:
        log(f"Fallback dedupe applied: {before} -> {len(deduped)} rows")
    return deduped.reset_index(drop=True)


def sort_by_recency(jobs: pd.DataFrame) -> pd.DataFrame:
    if jobs.empty or "date_posted" not in jobs.columns:
        return jobs
    return jobs.sort_values(by="date_posted", ascending=False, na_position="last").reset_index(
        drop=True
    )


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return " ".join(text.split())


def _extract_summary(description: object, max_len: int = 320) -> str:
    text = _as_text(description)
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3].rstrip()}..."


def _format_salary(row: pd.Series) -> str:
    minimum = row.get("min_amount")
    maximum = row.get("max_amount")
    interval = _as_text(row.get("interval"))
    currency = _as_text(row.get("currency")) or "USD"

    min_text = _as_text(minimum)
    max_text = _as_text(maximum)

    if min_text and max_text:
        value = f"{currency} {min_text} - {max_text}"
    elif min_text:
        value = f"{currency} {min_text}+"
    elif max_text:
        value = f"Up to {currency} {max_text}"
    else:
        return ""

    if interval:
        return f"{value} / {interval}"
    return value


def _format_skills(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(_as_text(v) for v in value if _as_text(v))
    return _as_text(value)


def _infer_work_type(row: pd.Series) -> str:
    direct = _as_text(row.get("job_type"))
    if direct:
        return direct
    location_type = _as_text(row.get("job_type_raw"))
    if location_type:
        return location_type
    location = _as_text(row.get("location")).lower()
    if "remote" in location:
        return "Remote"
    return ""


def _infer_experience_text(row: pd.Series) -> str:
    value = _as_text(row.get("experience_range"))
    if value:
        return value
    level = _as_text(row.get("job_level"))
    return level


def _estimate_experience_years(experience_text: str) -> float | None:
    text = experience_text.lower()
    if not text:
        return None
    if "entry" in text or "fresher" in text or "intern" in text or "0-1" in text:
        return 0.5
    digits = []
    current = ""
    for ch in text:
        if ch.isdigit():
            current += ch
        else:
            if current:
                digits.append(int(current))
                current = ""
    if current:
        digits.append(int(current))
    if digits:
        return float(digits[0])
    return None


def validate_job_link(url: object, timeout_seconds: float = 6.0) -> str:
    text = _as_text(url)
    if not text or not text.startswith(("http://", "https://")):
        return "unknown"

    try:
        req = request.Request(text, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            return "live" if 200 <= int(status) < 400 else "dead"
    except error.HTTPError as exc:
        if exc.code in (401, 403, 405, 429):
            return "unknown"
        if exc.code in (404, 410):
            return "dead"
    except Exception:
        pass

    try:
        req = request.Request(text, method="GET", headers={"User-Agent": "Mozilla/5.0"})
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            return "live" if 200 <= int(status) < 400 else "dead"
    except error.HTTPError as exc:
        if exc.code in (401, 403, 429):
            return "unknown"
        if exc.code in (404, 410):
            return "dead"
        return "unknown"
    except Exception:
        return "unknown"


def _csv_skill_terms(value: str) -> list[str]:
    return [term.strip().lower() for term in value.split(",") if term.strip()]


def build_curated_jobs(
    jobs: pd.DataFrame,
    *,
    search_query: str,
    scraped_at: str,
) -> pd.DataFrame:
    def _series(column: str) -> pd.Series:
        if column in jobs.columns:
            return jobs[column]
        return pd.Series([""] * len(jobs), index=jobs.index)

    curated = pd.DataFrame()
    curated["job_title"] = _series("title").map(_as_text)
    curated["company"] = _series("company").map(_as_text)
    curated["source_site"] = _series("site").map(_as_text)
    posted = pd.to_datetime(_series("date_posted"), errors="coerce", utc=True)
    curated["posted_date"] = posted.dt.strftime("%Y-%m-%d").fillna("")
    curated["location"] = _series("location").map(_as_text)
    curated["work_type"] = jobs.apply(_infer_work_type, axis=1)
    curated["experience"] = jobs.apply(_infer_experience_text, axis=1)
    curated["salary"] = jobs.apply(_format_salary, axis=1)
    curated["skills"] = _series("skills").map(_format_skills)
    curated["summary"] = _series("description").map(_extract_summary)
    curated["job_url"] = _series("job_url").map(_as_text)
    if "job_url_direct" in jobs.columns:
        mask_missing = curated["job_url"].eq("")
        curated.loc[mask_missing, "job_url"] = jobs.loc[mask_missing, "job_url_direct"].map(_as_text)
    curated["search_query"] = search_query
    curated["scraped_at"] = scraped_at
    return curated


def apply_structured_filters(
    curated_jobs: pd.DataFrame,
    config: ScrapeConfig,
) -> pd.DataFrame:
    filtered = curated_jobs.copy()
    if filtered.empty:
        return filtered

    include_keywords = [kw.strip().lower() for kw in config.include_keywords.split(",") if kw.strip()]
    exclude_keywords = [kw.strip().lower() for kw in config.exclude_keywords.split(",") if kw.strip()]
    must_skills = _csv_skill_terms(config.must_have_skills)
    work_modes = [mode.strip().lower() for mode in config.work_modes if mode.strip()]

    searchable = (
        filtered["job_title"].fillna("")
        + " "
        + filtered["summary"].fillna("")
        + " "
        + filtered["skills"].fillna("")
    ).str.lower()

    for kw in include_keywords:
        filtered = filtered[searchable.str.contains(kw, na=False)]
        searchable = searchable.loc[filtered.index]

    for kw in exclude_keywords:
        filtered = filtered[~searchable.str.contains(kw, na=False)]
        searchable = searchable.loc[filtered.index]

    if must_skills:
        skills_text = filtered["skills"].fillna("").str.lower()
        for skill in must_skills:
            filtered = filtered[skills_text.str.contains(skill, na=False)]
            skills_text = skills_text.loc[filtered.index]

    if config.min_experience_years is not None or config.max_experience_years is not None:
        years = filtered["experience"].fillna("").map(_estimate_experience_years)
        if config.min_experience_years is not None:
            filtered = filtered[
                years.isna() | (years >= float(config.min_experience_years))
            ]
            years = years.loc[filtered.index]
        if config.max_experience_years is not None:
            filtered = filtered[
                years.isna() | (years <= float(config.max_experience_years))
            ]

    if work_modes:
        work_text = (
            filtered["work_type"].fillna("").str.lower() + " " + filtered["location"].fillna("").str.lower()
        )
        mode_mask = pd.Series(False, index=filtered.index)
        for mode in work_modes:
            mode_mask = mode_mask | work_text.str.contains(mode, na=False)
        filtered = filtered[mode_mask]

    return filtered.reset_index(drop=True)


def enforce_recency(
    curated_jobs: pd.DataFrame,
    *,
    max_age_days: int,
    now_utc: datetime | None = None,
) -> pd.DataFrame:
    if curated_jobs.empty:
        return curated_jobs

    now = now_utc or datetime.now(timezone.utc)
    posted = pd.to_datetime(curated_jobs.get("posted_date"), errors="coerce", utc=True)
    age_days = (now - posted).dt.total_seconds() / 86400.0
    keep_mask = posted.notna() & (age_days <= max_age_days)
    return curated_jobs[keep_mask].reset_index(drop=True)


def apply_link_status_filter(
    curated_jobs: pd.DataFrame,
    *,
    include_unknown_links: bool,
) -> pd.DataFrame:
    if curated_jobs.empty:
        return curated_jobs
    allowed = ["live", "unknown"] if include_unknown_links else ["live"]
    return curated_jobs[curated_jobs["link_status"].isin(allowed)].reset_index(drop=True)


# ── LLM relevance scoring (provider-agnostic) ────────────────────────────────

# Supported providers → (base_url, env_key, default_model)
# All use the OpenAI Chat Completions format so a single `openai` SDK handles
# every provider — just swap base_url + api_key.
_LLM_PROVIDERS: dict[str, tuple[str, str, str]] = {
    "groq": (
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        "llama-3.3-70b-versatile",
    ),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "GEMINI_API_KEY",
        "gemini-2.0-flash",
    ),
    "openrouter": (
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        "meta-llama/llama-3.3-70b-instruct:free",
    ),
}

_GUTTS_SCORE_SYSTEM = """\
You are a recruiter analyst for GUTTS (Ground Up Trade & Talent Solutions), a workforce-development
company in Fairfax, VA that places entry-level Plumbing, HVAC, and skilled-trades candidates with
employers across Northern Virginia and the DC metro area.

Score each job on a 1–10 scale for how well it fits a candidate GUTTS would place:
  10 = Perfect: entry-level / apprentice Plumbing or HVAC in NoVA / DC metro
   7 = Good: trades tech, helper, installer, or service tech in the region
   5 = Marginal: trades-adjacent but senior, high-experience, or outside area
   2 = Unlikely: non-trade, office, IT, or software role
   1 = Irrelevant: clearly outside GUTTS scope

Return ONLY a JSON array (no markdown fences, no extra text):
[{"index": <0-based int>, "score": <int 1-10>, "reason": "<one short sentence>"},...]
"""


def score_jobs_with_llm(
    curated_jobs: pd.DataFrame,
    log: Callable[[str], None] | None = None,
    *,
    provider: str = "groq",
    model: str | None = None,
    batch_size: int = 10,
    threshold: int = 0,
) -> pd.DataFrame:
    """Score jobs for GUTTS candidate fit via any OpenAI-compatible LLM provider.

    Adds ``relevance_score`` (int 1–10) and ``relevance_reason`` (str) columns,
    then sorts output by score descending.  If ``threshold`` > 0, rows below
    that score are dropped.

    Supported providers (set via ``ScrapeConfig.llm_provider``):
      * ``"groq"``       — GROQ_API_KEY, default model llama-3.3-70b-versatile
      * ``"gemini"``     — GEMINI_API_KEY, default model gemini-2.0-flash
      * ``"openrouter"`` — OPENROUTER_API_KEY, default model llama-3.3-70b-instruct:free

    Falls back gracefully when ``openai`` is not installed, the provider is
    unknown, or the required API key env-var is not set.
    """
    try:
        from openai import OpenAI  # optional dependency (pip install openai)
    except ImportError:
        if log:
            log("LLM scoring skipped: 'openai' package not installed (pip install openai)")
        out = curated_jobs.copy()
        out["relevance_score"] = None
        out["relevance_reason"] = ""
        return out

    provider = provider.lower().strip()
    if provider not in _LLM_PROVIDERS:
        if log:
            log(
                f"LLM scoring skipped: unknown provider '{provider}'. "
                f"Choose from: {', '.join(_LLM_PROVIDERS)}"
            )
        out = curated_jobs.copy()
        out["relevance_score"] = None
        out["relevance_reason"] = ""
        return out

    base_url, env_key, default_model = _LLM_PROVIDERS[provider]
    resolved_model = model or default_model
    api_key = os.environ.get(env_key, "")
    if not api_key.strip():
        if log:
            log(f"LLM scoring skipped: {env_key} environment variable not set")
        out = curated_jobs.copy()
        out["relevance_score"] = None
        out["relevance_reason"] = ""
        return out

    client = OpenAI(api_key=api_key, base_url=base_url)
    result = curated_jobs.reset_index(drop=True).copy()
    total = len(result)
    scores: dict[int, tuple[int | None, str]] = {}

    if log:
        log(f"LLM scoring {total} jobs via {provider}/{resolved_model} in batches of {batch_size} …")

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        lines: list[str] = []
        for i in range(batch_start, batch_end):
            row = result.iloc[i]
            lines.append(
                f"[{i}] title={_as_text(row.get('job_title'))} | "
                f"company={_as_text(row.get('company'))} | "
                f"location={_as_text(row.get('location'))} | "
                f"work_type={_as_text(row.get('work_type'))} | "
                f"experience={_as_text(row.get('experience'))} | "
                f"salary={_as_text(row.get('salary'))} | "
                f"summary={_as_text(row.get('summary'))[:200]}"
            )
        batch_text = "\n".join(lines)

        try:
            response = client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": _GUTTS_SCORE_SYSTEM},
                    {"role": "user", "content": batch_text},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=1024,
            )
            raw = (response.choices[0].message.content or "").strip()
            # The model may return {"results": [...]} or a bare array — handle both
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                # Unwrap common wrapper keys
                entries: list[dict] = next(
                    (parsed[k] for k in ("results", "jobs", "scores", "data") if k in parsed),
                    [],
                )
            else:
                entries = parsed
            for entry in entries:
                idx = int(entry["index"])
                scores[idx] = (int(entry["score"]), str(entry.get("reason", "")))
        except Exception as exc:
            if log:
                log(f"  LLM batch {batch_start}–{batch_end - 1}: error — {exc}")
            # Leave those indices un-scored (they'll get None)

    result["relevance_score"] = [scores.get(i, (None, ""))[0] for i in range(total)]
    result["relevance_reason"] = [scores.get(i, (None, ""))[1] for i in range(total)]

    scored_count = int(result["relevance_score"].notna().sum())
    if log:
        log(f"LLM scored {scored_count}/{total} jobs")

    if threshold > 0:
        # When a threshold is set, drop both un-scored rows (API error/batch failure)
        # AND rows that scored below the threshold — only scored rows ≥ threshold pass.
        before_threshold = len(result)
        result = result[
            result["relevance_score"].notna() & (result["relevance_score"] >= threshold)
        ].reset_index(drop=True)
        if log:
            log(f"LLM threshold (≥{threshold}) kept {len(result)}/{before_threshold} rows")

    # Sort by relevance score descending; un-scored rows go last
    result = result.sort_values(
        "relevance_score", ascending=False, na_position="last"
    ).reset_index(drop=True)
    return result


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
    job_type: str | None = None,
    enforce_annual_salary: bool = False,
    user_agent: str | None = None,
    proxies: list[str] | None = None,
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
    if job_type is not None:
        kwargs["job_type"] = job_type
    if enforce_annual_salary:
        kwargs["enforce_annual_salary"] = True
    if user_agent is not None:
        kwargs["user_agent"] = user_agent
    if proxies is not None:
        kwargs["proxies"] = proxies
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
        include_keywords=getattr(args, "include_keywords", ""),
        exclude_keywords=getattr(args, "exclude_keywords", ""),
        must_have_skills=getattr(args, "must_have_skills", ""),
        min_experience_years=getattr(args, "min_experience_years", None),
        max_experience_years=getattr(args, "max_experience_years", None),
        work_modes=getattr(args, "work_modes", []) or [],
        include_unknown_links=getattr(args, "include_unknown_links", False),
        job_type=getattr(args, "job_type", None),
        enforce_annual_salary=getattr(args, "enforce_annual_salary", False),
        user_agent=getattr(args, "user_agent", None),
        proxies=getattr(args, "proxies", None),
        score_with_llm=getattr(args, "score_with_llm", False),
        llm_score_threshold=getattr(args, "llm_score_threshold", 0),
        llm_provider=getattr(args, "llm_provider", "groq"),
        llm_model=getattr(args, "llm_model", None),
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
    max_age_days = max(1, int(config.hours_old / 24))

    if log:
        log("GUTTS-aligned job scrape (Plumbing / HVAC / skilled trades, wider DMV / DC metro)")
        log(f"Output file: {out_path}")
        log(
            f"sites={config.sites}, location='{config.location}' (+{config.distance} mi), "
            f"results_wanted={config.results_wanted}, multi_query={config.multi_query}"
        )
        log(
            f"quality filters: latest<={max_age_days} days, "
            f"include_unknown_links={config.include_unknown_links}"
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
            job_type=config.job_type,
            enforce_annual_salary=config.enforce_annual_salary,
            user_agent=config.user_agent,
            proxies=config.proxies,
        )
        df["search_pass"] = term
        frames.append(df)

    jobs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    jobs = sort_by_recency(jobs)

    if log:
        log(f"Found {len(jobs)} jobs before curation")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    primary_query = passes[0] if passes else config.search_term
    curated_jobs = build_curated_jobs(jobs, search_query=primary_query, scraped_at=timestamp)
    curated_jobs = apply_structured_filters(curated_jobs, config)

    before_recency = len(curated_jobs)
    curated_jobs = enforce_recency(curated_jobs, max_age_days=max_age_days)
    if log:
        log(f"Recency filter kept {len(curated_jobs)}/{before_recency} rows")

    curated_jobs["link_status"] = curated_jobs["job_url"].map(validate_job_link)
    before_links = len(curated_jobs)
    curated_jobs = apply_link_status_filter(
        curated_jobs,
        include_unknown_links=config.include_unknown_links,
    )
    if log:
        log(f"Link-status filter kept {len(curated_jobs)}/{before_links} rows")

    curated_jobs = dedupe_jobs(curated_jobs, log=log)

    if config.score_with_llm:
        curated_jobs = score_jobs_with_llm(
            curated_jobs,
            log=log,
            provider=config.llm_provider,
            model=config.llm_model,
            threshold=config.llm_score_threshold,
        )

    curated_columns = [
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
        "link_status",
        "search_query",
        "scraped_at",
    ]
    if config.score_with_llm:
        curated_columns += ["relevance_score", "relevance_reason"]
    for col in curated_columns:
        if col not in curated_jobs.columns:
            curated_jobs[col] = ""
    curated_jobs = curated_jobs[curated_columns]

    curated_jobs.to_csv(
        str(out_path),
        quoting=csv.QUOTE_NONNUMERIC,
        escapechar="\\",
        index=False,
    )
    if log:
        log(f"Saved {len(curated_jobs)} curated rows to {out_path}")
    return out_path, len(curated_jobs)


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
    parser.add_argument(
        "--include-keywords",
        default="",
        help="Comma-separated include keywords for post-scrape filtering.",
    )
    parser.add_argument(
        "--exclude-keywords",
        default="",
        help="Comma-separated exclude keywords for post-scrape filtering.",
    )
    parser.add_argument(
        "--must-have-skills",
        default="",
        help="Comma-separated skills required in the extracted skills column.",
    )
    parser.add_argument(
        "--min-experience-years",
        type=int,
        default=None,
        help="Minimum years of experience to keep (based on parsed experience text).",
    )
    parser.add_argument(
        "--max-experience-years",
        type=int,
        default=None,
        help="Maximum years of experience to keep (based on parsed experience text).",
    )
    parser.add_argument(
        "--work-modes",
        nargs="+",
        default=[],
        help="Allowed work modes: remote hybrid onsite.",
    )
    parser.add_argument(
        "--include-unknown-links",
        action="store_true",
        help="Include unknown (unverified) links in output in addition to live links.",
    )
    # ── jobspy pass-through extras ──
    parser.add_argument(
        "--job-type",
        default=None,
        help="Job type filter (e.g. fulltime, parttime, contract, internship).",
    )
    parser.add_argument(
        "--enforce-annual-salary",
        action="store_true",
        help="Only return jobs that advertise an annual salary.",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Custom User-Agent string for HTTP requests.",
    )
    parser.add_argument(
        "--proxies",
        nargs="+",
        default=None,
        metavar="PROXY",
        help="HTTP/HTTPS proxies to rotate (e.g. http://host:port).",
    )
    # ── LLM relevance scoring ──
    parser.add_argument(
        "--score-with-llm",
        action="store_true",
        help=(
            "Score each job for GUTTS candidate fit via an LLM (1–10 scale). "
            "Adds relevance_score / relevance_reason columns; sorts output by score desc. "
            "Requires the appropriate API key env-var (see --llm-provider)."
        ),
    )
    parser.add_argument(
        "--llm-score-threshold",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Drop jobs scoring below N when --score-with-llm is set (0 = keep all). "
            "Recommended: 7 to filter out clearly irrelevant postings."
        ),
    )
    parser.add_argument(
        "--llm-provider",
        default="groq",
        choices=["groq", "gemini", "openrouter"],
        help=(
            "LLM provider for relevance scoring. "
            "groq → GROQ_API_KEY, gemini → GEMINI_API_KEY, openrouter → OPENROUTER_API_KEY "
            "(default: groq)."
        ),
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help=(
            "Model override for the LLM provider "
            "(default: llama-3.3-70b-versatile for groq, gemini-2.0-flash for gemini, "
            "meta-llama/llama-3.3-70b-instruct:free for openrouter)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    run_gutts_scrape(config=config, log=print)


if __name__ == "__main__":
    main()
