"""Job sources. Every function returns a list of dicts:
{company, title, location, url, source, posted, website(optional)}.
A source that fails or is not installed/configured returns [] and prints why - it never stops the run."""
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; GUTTS-Outreach/1.0; +https://gutts.tech)"}
T = 30


def _get(url, **kw):
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=T, **kw)
    r.raise_for_status()
    return r.json()


def _safe(name, fn, *a, **kw):
    try:
        out = fn(*a, **kw)
        print(f"  [{name}] {len(out)} postings")
        return out
    except Exception as e:
        print(f"  [{name}] skipped: {str(e)[:120]}")
        return []


# ---- public applicant-tracking boards (free, no key, meant to be read by machines) ----
def greenhouse(company, token):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    return [dict(company=company, title=j["title"], location=(j.get("location") or {}).get("name", ""),
                 url=j["absolute_url"], source="Greenhouse", posted=(j.get("updated_at") or "")[:10])
            for j in d.get("jobs", [])]


def lever(company, slug):
    d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    return [dict(company=company, title=j["text"], location=(j.get("categories") or {}).get("location", ""),
                 url=j["hostedUrl"], source="Lever", posted="") for j in d]


def workable(company, slug):
    d = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    return [dict(company=company, title=j["title"],
                 location=", ".join(x for x in [j.get("city"), j.get("state")] if x),
                 url=j.get("url") or j.get("shortlink", ""), source="Workable",
                 posted=(j.get("published_on") or "")[:10]) for j in d.get("jobs", [])]


# ---- job search APIs (free keys, read from environment variables - never from files) ----
def adzuna(what, where, pages=2):
    aid, key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (aid and key):
        raise RuntimeError("no ADZUNA_APP_ID / ADZUNA_APP_KEY set")
    out = []
    for p in range(1, pages + 1):
        d = _get(f"https://api.adzuna.com/v1/api/jobs/us/search/{p}",
                 params=dict(app_id=aid, app_key=key, what=what, where=where,
                             results_per_page=50, max_days_old=14, distance=40))
        out += [dict(company=(j.get("company") or {}).get("display_name", ""), title=j["title"],
                     location=(j.get("location") or {}).get("display_name", ""), url=j["redirect_url"],
                     source="Adzuna", posted=(j.get("created") or "")[:10]) for j in d.get("results", [])]
    return out


def usajobs(keyword, location):
    key, email = os.environ.get("USAJOBS_API_KEY"), os.environ.get("USAJOBS_EMAIL")
    if not (key and email):
        raise RuntimeError("no USAJOBS_API_KEY / USAJOBS_EMAIL set")
    d = _get("https://data.usajobs.gov/api/search",
             params=dict(Keyword=keyword, LocationName=location, ResultsPerPage=100, DatePosted=14),
             headers={"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key})
    out = []
    for it in d["SearchResult"]["SearchResultItems"]:
        m = it["MatchedObjectDescriptor"]
        out.append(dict(company=m["OrganizationName"], title=m["PositionTitle"],
                        location=m["PositionLocationDisplay"], url=m["PositionURI"],
                        source="USAJobs", posted=(m.get("PublicationStartDate") or "")[:10]))
    return out


# ---- JobSpy (open source): Indeed, ZipRecruiter, Google Jobs ----
def _pay(lo, hi, interval):
    """'$20-24/hr' style text from JobSpy's pay fields; '' when the posting lists no pay."""
    try:
        lo, hi = float(lo or 0), float(hi or 0)
    except (TypeError, ValueError):
        return ""
    if not (lo or hi):
        return ""
    unit = {"hourly": "/hr", "yearly": "/yr", "monthly": "/mo", "weekly": "/wk", "daily": "/day"}.get(str(interval).lower(), "")
    f = (lambda v: f"{v:,.0f}") if unit != "/hr" else (lambda v: f"{v:g}")
    return f"${f(lo)}-{f(hi)}{unit}" if lo and hi and lo != hi else f"${f(lo or hi)}{unit}"


def jobspy(term, location, sites, results=60, hours_old=336, distance=25):
    from jobspy import scrape_jobs  # pip install python-jobspy
    df = scrape_jobs(site_name=sites, search_term=term, location=location, results_wanted=results,
                     hours_old=hours_old, country_indeed="USA", distance=distance, verbose=0)
    out = []
    for _, j in df.iterrows():
        g = lambda k: "" if k not in j or str(j[k]) in ("nan", "None", "NaT") else str(j[k])
        out.append(dict(company=g("company"), title=g("title"), location=re.sub(r",\s*(USA?|United States)$", "", g("location")),
                        url=g("job_url"), direct_url=g("job_url_direct"),
                        source={"indeed": "Indeed", "zip_recruiter": "ZipRecruiter"}.get(g("site"), g("site")),
                        posted=g("date_posted")[:10], website=g("company_url_direct"), emails=g("emails"),
                        pay=_pay(g("min_amount"), g("max_amount"), g("interval")), description=g("description")[:8000]))
    return out


def collect(cfg):
    jobs = []
    for b in cfg.get("ats_boards", []):
        fn = {"greenhouse": greenhouse, "lever": lever, "workable": workable}[b["type"]]
        jobs += _safe(f"{b['type']}:{b['company']}", fn, b["company"], b["token"])
    sites = cfg.get("jobspy_sites", [])
    for loc in cfg["locations"]:
        for term in cfg["search_terms"]:
            if sites:
                jobs += _safe(f"jobspy:{term}@{loc}", jobspy, term, loc, sites, cfg.get("results_per_search", 60), cfg.get("max_days_old", 14) * 24, cfg.get("distance_miles", 25))
            jobs += _safe(f"adzuna:{term}@{loc}", adzuna, term, loc)
        for term in cfg.get("usajobs_terms", []):
            jobs += _safe(f"usajobs:{term}@{loc}", usajobs, term, loc)
    return jobs


def clean(jobs, cfg):
    """Keep trade-relevant titles in the target area; drop duplicates and staffing noise."""
    inc = re.compile(cfg["title_include"], re.I)
    exc = re.compile(cfg["title_exclude"], re.I)
    area = re.compile(cfg["area_regex"], re.I)
    skip = {c.lower() for c in cfg.get("skip_companies", [])}
    seen, out = set(), []
    for j in jobs:
        co = re.sub(r"\s+", " ", j.get("company") or "").strip()
        if not co or co.lower() in skip or not j.get("url"):
            continue
        if not inc.search(j["title"]) or exc.search(j["title"]) or not area.search(j.get("location") or ""):
            continue
        k = (co.lower(), j["title"].lower(), (j.get("location") or "").lower())
        if k in seen:
            continue
        seen.add(k)
        out.append({**j, "company": co})
    return out
