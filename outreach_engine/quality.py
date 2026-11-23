"""Fit + freshness: is this a job a GUTTS grad could get, what sector is it, and is the posting still live?"""
import datetime
import re

ENTRY = re.compile(r"apprentice|helper|trainee|entry|junior|\bjr\b|level\s?(1|i)\b|\b(tech(nician)?|engineer|mechanic)\s?(1|i)\b|"
                   r"assistant|laborer|no experience|will train|pre-?apprentice|porter|groundskeeper|make.?ready", re.I)
STARTER = re.compile(r"apprentice|helper|trainee|pre-?apprentice", re.I)
NEEDS_EXP = re.compile(r"experienced|\b\d\+?\s?(yrs?|years?)\b", re.I)
DESC_ENTRY = re.compile(r"no (prior )?experience (is )?(required|necessary|needed)|will(ing to)? train|entry[- ]level|paid training|we train", re.I)
SENIOR = re.compile(r"senior|\bsr\b|lead\b|chief|supervisor|manager|director|master|foreman|superintendent|estimator|"
                    r"\b(iv|v|4|5)\b|principal|journeyman|licensed", re.I)
DEAD = re.compile(r"no longer (available|accepting|active|open)|has expired|job (has )?expired|position (has been|was) filled|"
                  r"posting (has been )?(closed|removed)|this job is closed|job not found|page not found|no longer exists|"
                  r"isn.t available anymore|expired job", re.I)

BY_COMPANY = [  # CRM Employers 'Industry' picklist value, decided by the company name first
    ("Technology", r"data ?cent|colocation|equinix|cyrusone|sabey|cologix|vantage|digital realty|aligned|qts\b|stack infra|iron mountain|lightedge"),
    ("Services", r"plumb|hvac|heating|cooling|\bair\b|air cond|refriger|comfort|drain|sewer|boiler|mechanical services|water"),
    ("Education", r"university|college|school|academy"),
    ("Facility Management Commercial", r"jll|cbre|cushman|able services|\babm\b|sodexo|aramark|c&w services|facilit|hines|airports? authority"),
    ("Property Management", r"apartment|residential|multifamily|property|properties|communit(y|ies)|living|greystar|kettler|bozzuto|avenue5|gates hudson|management|realty|related\b"),
    ("Commercial Construction", r"construction|contract(or|ing)|mechanical|builders|sheet ?metal|engineering"),
    ("Real Estate", r"real estate|investment|trust|holdings"),
]
BY_TITLE = [("Technology", r"data ?cent|critical (facilit|environment)"),
            ("Facility Management Commercial", r"building engineer|facilit|stationary engineer|plant operations|central plant")]
TRADE = [("HVAC & Plumbing", r"(hvac|heating|cooling|air).*(plumb)|(plumb).*(hvac|heating|cooling|air)"),
         ("Plumbing", r"plumb|pipe ?fitt|drain|sewer|backflow"),
         ("HVAC", r"hvac|heating|cooling|air cond|refriger|chiller|boiler|mechanical"),
         ("Facility Maintenance", r"maintenance|building engineer|facilit|critical|data ?cent")]


YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|to)\s*\d{1,2}\s*)?(?:years?|yrs?)[^.\n]{0,40}experience", re.I)


def years_required(description):
    """Smallest 'N years of experience' the posting asks for; None when it names none."""
    found = [int(m) for m in YEARS.findall(description or "") if int(m) <= 15]
    return min(found) if found else None


def level(title, description=""):
    """Entry / Mid / Senior. The title decides first; then the experience the posting asks for:
    5+ years is Senior, 2-4 is Mid, and 'no experience / will train' wording upgrades a plain title to Entry."""
    if SENIOR.search(title) and not STARTER.search(title):
        return "Senior"
    yrs = years_required(description)
    if STARTER.search(title):
        return "Entry"
    if yrs is not None and yrs >= 5:
        return "Senior"
    if NEEDS_EXP.search(title) or (yrs is not None and yrs >= 2):
        return "Mid"
    if ENTRY.search(title) or DESC_ENTRY.search(description or ""):
        return "Entry"
    return "Mid"


def requirements(description):
    """Short flags a caller can read at a glance, pulled from the posting text."""
    d = description or ""
    out = []
    yrs = years_required(d)
    if yrs:
        out.append(f"{yrs}+ yrs experience")
    elif DESC_ENTRY.search(d):
        out.append("Will train / no experience")
    if re.search(r"epa\s*(section\s*)?608|epa (universal|certif)", d, re.I):
        out.append("EPA 608")
    if re.search(r"driver.?s? licen[sc]e", d, re.I):
        out.append("Driver's license")
    if re.search(r"(journeyman|master)('?s)? (plumb\w+ |hvac |tradesman |gas ?fitter )?(licen[sc]e|card)", d, re.I):
        out.append("Journeyman/Master license")
    if re.search(r"osha[- ]?(10|30)", d, re.I):
        out.append("OSHA")
    return "; ".join(out)


def sector(company, title):
    for name, pat in BY_COMPANY:
        if re.search(pat, company, re.I):
            return name
    for name, pat in BY_TITLE:
        if re.search(pat, title, re.I):
            return name
    return "Services"


def trade(title, company=""):
    for name, pat in TRADE:
        if re.search(pat, f"{title} {company}", re.I):
            return name
    return "Facility Maintenance"


def is_fresh(posted, today, max_days):
    try:
        return (today - datetime.date.fromisoformat(posted[:10])).days <= max_days
    except Exception:
        return True  # no date given: keep, the live check decides


BOARDS = ("Indeed", "ZipRecruiter", "Adzuna")


def check_live(job, get_status):
    """get_status(url) -> (http_status or None, text). Returns:
    Live    - opened the posting (or the employer's own apply page) today and it is still up
    Active  - the job board returned it in today's search results, but blocks automated page checks
    Expired - dead link or 'no longer available' text (these are dropped)
    Board feeds (Greenhouse, Lever, Workable, USAJobs) only list open jobs, so they are Live by definition."""
    if job["source"] in ("Greenhouse", "Lever", "Workable", "USAJobs"):
        return "Live"
    for url in [u for u in (job.get("direct_url"), job["url"]) if u]:
        status, text = get_status(url)
        if status in (404, 410):
            return "Expired"
        if status == 200 and text:
            if DEAD.search(text[:60000]):
                return "Expired"
            words = re.findall(r"[a-z]{4,}", job["title"].lower())[:2]
            if words and all(w in text.lower() for w in words):
                return "Live"
    return "Active" if job["source"] in BOARDS else "Unverified"
