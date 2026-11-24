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


def ashby(company, name):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{name}")
    return [dict(company=company, title=x["title"], location=x.get("location") or "", url=x.get("jobUrl", ""),
                 source="Ashby", posted=(x.get("publishedAt") or "")[:10]) for x in d.get("jobs", [])]


def smartrecruiters(company, cid):
    d = _get(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings", params={"limit": 100})
    out = []
    for x in d.get("content", []):
        loc = x.get("location") or {}
        out.append(dict(company=company, title=x["name"], url=f"https://jobs.smartrecruiters.com/{cid}/{x['id']}",
                        location=", ".join(v for v in [loc.get("city"), (loc.get("region") or "").upper()] if v),
                        source="SmartRecruiters", posted=(x.get("releasedDate") or "")[:10]))
    return out


def recruitee(company, slug):
    d = _get(f"https://{slug}.recruitee.com/api/offers/")
    return [dict(company=company, title=x["title"], location=x.get("location") or "", url=x.get("careers_url", ""),
                 source="Recruitee", posted=(x.get("published_at") or "")[:10]) for x in d.get("offers", [])]


def workday(company, token, terms=("HVAC", "plumber", "maintenance technician", "building engineer")):
    """token is 'tenant|wdN|site', e.g. 'jll|wd1|jllcareers'. Workday boards are huge, so search by trade terms."""
    tenant, wd, site = token.split("|")
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    out = []
    for term in terms:
        r = requests.post(f"{base}/wday/cxs/{tenant}/{site}/jobs", timeout=T, headers={**UA, "Content-Type": "application/json"},
                          json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term})
        r.raise_for_status()
        out += [dict(company=company, title=x["title"], location=x.get("locationsText", ""),
                     url=f"{base}/en-US/{site}{x['externalPath']}", source="Workday", posted="")
                for x in r.json().get("jobPostings", []) if x.get("title") and x.get("externalPath")]
    return out


BOARD_FN = {"greenhouse": greenhouse, "lever": lever, "workable": workable, "ashby": ashby,
            "smartrecruiters": smartrecruiters, "recruitee": recruitee, "workday": workday}
BOARD_PATTERNS = [  # how each hiring system shows up in an apply link or on a careers page
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"jobs\.lever\.co/([A-Za-z0-9_-]+)")),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)")),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)")),
    ("recruitee", re.compile(r"//([a-z0-9-]+)\.recruitee\.com")),
]
WORKDAY = re.compile(r"//([a-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)")
NOT_TOKENS = {"embed", "job_board", "jobs", "j", "api", "v1", "oneclick-ui", "company", "www"}


def detect_board(url):
    """('greenhouse', 'seatown') when a link points at a public hiring board; None otherwise."""
    if not url:
        return None
    m = WORKDAY.search(url)
    if m:
        return "workday", "|".join(m.groups())
    for kind, pat in BOARD_PATTERNS:
        m = pat.search(url)
        if m and m.group(1).lower() not in NOT_TOKENS:
            return kind, m.group(1)
    return None


def board_jobs(company, kind, token):
    """All open jobs on one employer's board ([] and a log line if the board cannot be read)."""
    return _safe(f"{kind}:{company}", BOARD_FN[kind], company, token)


def discover_boards(jobs):
    """Employers whose apply links reveal the hiring system they use: {(kind, token): company}."""
    found = {}
    for j in jobs:
        hit = detect_board(j.get("direct_url") or "") or detect_board(j.get("url") or "")
        if hit and j.get("company"):
            found.setdefault(hit, j["company"])
    return found


def _ld_jobs(html):
    """schema.org JobPosting blocks on a page (most job sites publish these for search engines)."""
    import json
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("@type") == "JobPosting":
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            walk(json.loads(m.group(1).strip()))
        except ValueError:
            continue  # malformed block: nothing to read
    return out


def from_job_page(html, url, source):
    """One posting dict from a job page's structured data; None when the page has none."""
    for p in _ld_jobs(html):
        org = p.get("hiringOrganization") or {}
        loc = p.get("jobLocation") or {}
        loc = loc[0] if isinstance(loc, list) and loc else loc
        addr = (loc.get("address") if isinstance(loc, dict) else {}) or {}
        if isinstance(addr, str):
            addr = {"addressLocality": addr}
        company = org.get("name") if isinstance(org, dict) else str(org)
        if not (p.get("title") and company):
            continue
        return dict(company=company, title=p["title"], url=url, source=source, posted=str(p.get("datePosted") or "")[:10],
                    location=", ".join(v for v in [addr.get("addressLocality"), addr.get("addressRegion")] if v),
                    website=(org.get("sameAs") or org.get("url") or "") if isinstance(org, dict) else "",
                    description=re.sub(r"<[^>]+>", " ", str(p.get("description") or ""))[:8000],
                    expires=str(p.get("validThrough") or "")[:10])
    return None


def ihire(listing_urls, fetcher, max_pages=80):
    """iHireConstruction: read each search page, then each job page's structured data.
    Uses the polite fetcher (robots.txt, delay, cache), so it is slow on purpose."""
    links = []
    for u in listing_urls:
        html = fetcher.get(u) or ""
        found = list(dict.fromkeys(re.findall(r'href="(?:https://www\.ihireconstruction\.com)?(/jobs/view/\d+)', html)))
        print(f"  [ihire] {len(found)} links on {u.rsplit('/', 1)[-1]}")
        links += [x for x in found if x not in links]
    out, blank = [], 0
    for path in links[:max_pages]:
        url = "https://www.ihireconstruction.com" + path
        job = from_job_page(fetcher.get(url) or "", url, "iHireConstruction")
        if job:
            out.append(job)
        else:
            blank += 1
    if blank:
        print(f"  [ihire] {blank} job pages had no readable posting data")
    return out


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


def jobspy(term, location, site, results=60, hours_old=336, distance=25):
    from jobspy import scrape_jobs  # pip install python-jobspy
    df = scrape_jobs(site_name=[site], search_term=term, location=location, results_wanted=results,
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


def collect(cfg, fetcher=None):
    jobs = []
    for b in cfg.get("ats_boards", []):
        jobs += board_jobs(b["company"], b["type"], b["token"])
    for loc in cfg["locations"]:
        for term in cfg["search_terms"]:
            for site in cfg.get("jobspy_sites", []):  # one site per call, so a blocked site shows up by name
                jobs += _safe(f"{site}:{term}@{loc}", jobspy, term, loc, site, cfg.get("results_per_search", 60),
                              cfg.get("max_days_old", 14) * 24, cfg.get("distance_miles", 25))
            jobs += _safe(f"adzuna:{term}@{loc}", adzuna, term, loc)
        for term in cfg.get("usajobs_terms", []):
            jobs += _safe(f"usajobs:{term}@{loc}", usajobs, term, loc)
    if fetcher and cfg.get("ihire_pages"):
        jobs += _safe("ihire", ihire, cfg["ihire_pages"], fetcher, cfg.get("ihire_max_jobs", 80))
    known = {(b["type"], b["token"]) for b in cfg.get("ats_boards", [])}
    for (kind, token), company in discover_boards(jobs).items():  # employers' own hiring boards, found via apply links
        if (kind, token) not in known:
            print(f"  discovered board: {company} -> {kind}:{token}")
            jobs += board_jobs(company, kind, token)
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
        if not co or any(s in co.lower() for s in skip) or not j.get("url"):
            continue
        if not inc.search(j["title"]) or exc.search(j["title"]) or not area.search(j.get("location") or ""):
            continue
        k = (co.lower(), j["title"].lower(), (j.get("location") or "").lower())
        if k in seen:
            continue
        seen.add(k)
        out.append({**j, "company": co})
    return out
