"""Fit + freshness: is this a job a GUTTS grad could get, what sector is it, and is the posting still live?"""
import datetime
import re

ENTRY = re.compile(r"apprentice|helper|trainee|entry|junior|\bjr\b|level\s?(1|i)\b|\b(tech(nician)?|engineer|mechanic)\s?(1|i)\b|"
                   r"assistant|installer|laborer|no experience|will train|pre-?apprentice|porter|groundskeeper|make.?ready", re.I)
SENIOR = re.compile(r"senior|\bsr\b|lead\b|chief|supervisor|manager|director|master|foreman|superintendent|estimator|"
                    r"\b(iv|v|4|5)\b|principal|journeyman|licensed", re.I)
DEAD = re.compile(r"no longer (available|accepting|active|open)|has expired|job (has )?expired|position (has been|was) filled|"
                  r"posting (has been )?(closed|removed)|this job is closed|job not found|page not found|no longer exists|"
                  r"isn.t available anymore|expired job", re.I)

SECTORS = [  # (CRM Employers 'Industry' picklist value, pattern on company + title)
    ("Technology", r"data ?cent|critical (facilit|environment)|colocation|equinix|cyrusone|sabey|cologix|vantage|digital realty|aligned|qts|stack infra|iron mountain"),
    ("Property Management", r"apartment|residential|multifamily|property (management|mgmt)|communit(y|ies)|living|greystar|kettler|bozzuto|avenue5|gates hudson|leasing|housing|realty"),
    ("Facility Management Commercial", r"facilit|building engineer|jll|cbre|cushman|able services|abm |sodexo|aramark|c&w services|janitorial"),
    ("Education", r"university|college|school|academy|public schools"),
    ("Commercial Construction", r"construction|contractor|mechanical|builders|sheet ?metal|pipefitt"),
    ("Real Estate", r"real estate|properties|investment|trust|holdings"),
    ("Services", r"plumb|hvac|heating|cooling|air cond|refriger|comfort|drain|sewer|boiler|chiller|hospital|hotel|health|county|city of|government|church|senior"),
]
TRADE = [("HVAC & Plumbing", r"(hvac|heating|cooling|air).*(plumb)|(plumb).*(hvac|heating|cooling|air)"),
         ("Plumbing", r"plumb|pipe ?fitt|drain|sewer|backflow"),
         ("HVAC", r"hvac|heating|cooling|air cond|refriger|chiller|boiler|mechanical"),
         ("Facility Maintenance", r"maintenance|building engineer|facilit|critical|data ?cent")]


def level(title):
    if SENIOR.search(title) and not re.search(r"apprentice|helper|trainee|assistant", title, re.I):
        return "Senior"
    return "Entry" if ENTRY.search(title) else "Mid"


def sector(company, title):
    blob = f"{company} {title}"
    for name, pat in SECTORS:
        if re.search(pat, blob, re.I):
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


def check_live(job, get_status):
    """get_status(url) -> (http_status or None, text). Returns Live / Expired / Unverified.
    Board feeds (Greenhouse, Lever, Workable, USAJobs) only list open jobs, so they are Live by definition."""
    if job["source"] in ("Greenhouse", "Lever", "Workable", "USAJobs"):
        return "Live"
    status, text = get_status(job["url"])
    if status in (404, 410):
        return "Expired"
    if status == 200 and text:
        if DEAD.search(text[:60000]):
            return "Expired"
        words = [w for w in re.findall(r"[a-z]{4,}", job["title"].lower())][:3]
        if words and all(w in text.lower() for w in words[:2]):
            return "Live"
    return "Unverified"  # site blocked the check (Indeed often does) - a person should click before calling
