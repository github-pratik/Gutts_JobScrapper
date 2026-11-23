"""Find each employer's website, crawl its public pages, and pull out phone, email and named people.
Parsing is separate from fetching so it can be unit-tested without the network."""
import hashlib
import json
import re
import threading
import time
from collections import Counter
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

from scrapling.parser import Selector

BOT = "GUTTS-Outreach"
LINK_WORDS = re.compile(r"contact|about|team|leader|staff|people|career|job|employ|join|location|office|management", re.I)
GUESS = ["/contact", "/contact-us", "/about", "/about-us", "/careers", "/our-team", "/team", "/leadership", "/locations"]
TITLES = (r"Owner|Co-Owner|Founder|Co-Founder|President|Vice President|VP|CEO|COO|CFO|"
          r"General Manager|Operations Manager|Service Manager|Office Manager|Facilit(?:y|ies) Manager|"
          r"Chief Engineer|Director of (?:Engineering|Facilities|Operations|Maintenance|Human Resources|Talent)|"
          r"HR Manager|HR Director|Human Resources(?: Manager| Director)?|Recruiter|Talent Acquisition(?: Manager| Partner)?|"
          r"Hiring Manager|Project Manager|Branch Manager|Maintenance (?:Manager|Supervisor|Director)")
NAME = r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-zA-Z'\-]+"
P_NAME_TITLE = re.compile(rf"({NAME})\s*[,\-–|:]\s*({TITLES})\b")
P_TITLE_NAME = re.compile(rf"\b({TITLES})\s*[:\-–|]\s*({NAME})")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\d.])(?:\+?1[\s.\-]?)?\(?(\d{3})\)?[\s.\-]{1,2}(\d{3})[\s.\-](\d{4})(?!\d)")
BAD_EMAIL = ("example.", "sentry", "wixpress", "godaddy", ".png", ".jpg", ".webp", ".gif", ".svg", "@2x",
             "domain.com", "email.com", "yourname", "name@", "noreply", "no-reply", "donotreply", "privacy@", "abuse@")
BAD_NAMES = {"Contact Us", "About Us", "Our Team", "Read More", "Learn More", "Customer Service",
             "Air Conditioning", "Heating Cooling", "Privacy Policy", "Human Resources"}
EMAIL_RANK = ["hr", "humanresources", "careers", "career", "jobs", "recruit", "talent", "hiring", "employment",
              "info", "contact", "office", "hello", "admin", "service", "sales"]
NOT_NAMES = set("""as our the and for with data management human resources mission integration acquisitions development
    operations services service team company group meet about contact vice chief executive senior general regional property
    properties business customer client office finance marketing sales board founder president owner director manager new
    north south east west united national american first capital community housing health care project construction
    engineering facilities maintenance commercial residential plumbing heating cooling air conditioning mechanical
    operator execution global technology resorts worldwide chair co hotels international associates partners""".split())
LOW_VALUE = ("leave", "hrscleave", "benefit", "accommodat", "press", "media", "communications", "stratcom", "marketing", "investor", "legal", "webmaster", "sales", "news")
LOCAL_AREA = {"703", "571", "202", "301", "240", "410", "443", "540", "804"}
NOT_A_SITE = ("indeed.", "linkedin.", "facebook.", "yelp.", "glassdoor.", "ziprecruiter.", "bbb.org", "mapquest.",
              "zoominfo.", "yellowpages.", "angi.", "homeadvisor.", "thumbtack.", "instagram.", "twitter.", "x.com",
              "youtube.", "wikipedia.", "crunchbase.", "dnb.com", "buildzoom.", "manta.", "chamberofcommerce.",
              "simplyhired.", "careerbuilder.", "monster.", "google.", "bing.", "apple.com", "nextdoor.", "porch.",
              "bloomberg.", "opencorporates.", "rocketreach.", "signalhire.", "apollo.io", "lensa.", "talent.com",
              "salary.com", "comparably.", "builtin.", "themuse.", "jobs.", "greenhouse.io", "lever.co", "workable.",
              "icims.", "myworkdayjobs.", "ihire", "snagajob.", "jooble.", "adzuna.", "usajobs.")


def fmt(a, b, c):
    return f"({a}) {b}-{c}"


def _cf_decode(h):
    """Cloudflare shows emails to browsers by decoding this hex string; do the same."""
    try:
        k = int(h[:2], 16)
        return "".join(chr(int(h[i:i + 2], 16) ^ k) for i in range(2, len(h), 2))
    except ValueError:
        return ""


def _jsonld(page):
    found = {"phones": [], "emails": []}

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "telephone" and isinstance(v, str):
                    found["phones"].append(v)
                elif k == "email" and isinstance(v, str):
                    found["emails"].append(v.replace("mailto:", ""))
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for s in page.css('script[type="application/ld+json"]::text').getall():
        try:
            walk(json.loads(s))
        except (ValueError, TypeError):
            continue  # malformed structured data on the page: nothing to read from it
    return found


def parse_page(html):
    """html in -> {emails, phones (strong first), people, links}."""
    page = Selector(html)
    text = re.sub(r"\s+", " ", page.get_all_text())
    hrefs = page.css("a::attr(href)").getall()
    ld = _jsonld(page)

    emails = [h[7:].split("?")[0] for h in hrefs if h.lower().startswith("mailto:")]
    emails += ld["emails"]
    emails += [_cf_decode(x) for x in page.css("[data-cfemail]::attr(data-cfemail)").getall()]
    emails += [_cf_decode(h.split("#")[-1]) for h in hrefs if "/cdn-cgi/l/email-protection#" in h]
    emails += EMAIL.findall(text)
    emails = [e.strip().strip(".").lower() for e in emails if e and "@" in e]
    emails = list(dict.fromkeys(e for e in emails if EMAIL.fullmatch(e) and not any(b in e for b in BAD_EMAIL)))

    strong = []  # tel: links and structured data are the numbers the company chose to publish
    for raw in [h for h in hrefs if h.lower().startswith("tel:")] + ld["phones"]:
        d = re.sub(r"\D", "", raw)
        if len(d) == 11 and d[0] == "1":
            d = d[1:]
        if len(d) == 10:
            strong.append(fmt(d[:3], d[3:6], d[6:]))
    weak = [fmt(*m) for m in PHONE.findall(text)]
    phones = list(dict.fromkeys(strong + weak))

    people = {}
    for name, title in P_NAME_TITLE.findall(text):
        people[name] = title
    for title, name in P_TITLE_NAME.findall(text):
        people.setdefault(name, title)
    people = {n: t for n, t in people.items() if n not in BAD_NAMES and not (set(n.lower().replace(".", "").split()) & NOT_NAMES)}

    links = []
    for a in page.css("a"):
        h = a.attrib.get("href", "")
        if h and not h.startswith(("mailto:", "tel:", "#", "javascript:")) and LINK_WORDS.search(h + " " + (a.text or "")):
            links.append(h)
    return {"emails": emails, "phones": phones, "strong_phones": list(dict.fromkeys(strong)), "people": people, "links": links}


def best_email(emails, host):
    root = ".".join(host.replace("www.", "").split(".")[-2:])
    own = [e for e in emails if e.split("@")[1].endswith(root)]
    pool = own or [e for e in emails if e.split("@")[1] in ("gmail.com", "outlook.com", "yahoo.com", "aol.com", "verizon.net", "comcast.net")]

    def rank(e):
        p = re.sub(r"[^a-z]", "", e.split("@")[0])
        if p.startswith(LOW_VALUE):
            return len(EMAIL_RANK) + 1
        for i, w in enumerate(EMAIL_RANK):
            if p.startswith(w):
                return i
        return len(EMAIL_RANK)
    return sorted(pool, key=rank)[0] if pool else ""


def best_phone(counts, strong):
    if not counts:
        return ""
    def score(p):
        return (p in strong) * 3 + (p[1:4] in LOCAL_AREA) * 2 + min(counts[p], 5) - (p[1:4] in ("800", "888", "877", "866", "855", "844")) * 1
    return max(counts, key=score)


# ------------------------------- fetching -------------------------------
class Fetcher:
    """Polite fetcher: disk cache, robots.txt, one request per host at a time with a delay."""

    def __init__(self, cache_dir="cache", delay=1.0, timeout=20):
        self.cache = Path(cache_dir)
        self.cache.mkdir(exist_ok=True)
        self.delay, self.timeout = delay, timeout
        self.locks, self.robots, self.g = {}, {}, threading.Lock()
        self.errors = []  # fetch failures, reported at the end of the run
        self.no_browser, self.browser_lock = False, threading.Lock()

    def _raw(self, url):
        try:
            from scrapling.fetchers import Fetcher as SF
            r = SF.get(url, stealthy_headers=True, timeout=self.timeout, follow_redirects=True)
            if r.status == 200:
                return str(r.html_content)
        except Exception as e:  # any network/TLS failure: fall through to the plain client
            self.errors.append(f"{url}: {str(e)[:80]}")
        import requests
        try:
            r = requests.get(url, timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"})
            if r.status_code == 200 and "html" in r.headers.get("content-type", "html"):
                return r.text
        except requests.RequestException as e:
            self.errors.append(f"{url}: {str(e)[:80]}")
        return None

    def render(self, url):
        """Load a page in a real headless browser (Scrapling DynamicFetcher) for sites that build their
        content with JavaScript. Returns None when the browser is not installed or the page fails."""
        if self.no_browser or not self.allowed(url):
            return None
        try:
            import scrapling.fetchers as sf
            browser = getattr(sf, "DynamicFetcher", None) or getattr(sf, "PlayWrightFetcher", None)
            if browser is None:
                self.no_browser = True
                return None
            with self.browser_lock:
                r = browser.fetch(url, headless=True, network_idle=True, timeout=30000)
            return str(r.html_content) if r.status == 200 else None
        except Exception as e:
            self.errors.append(f"browser {url}: {str(e)[:120]}")
            if "install" in str(e).lower() or "executable" in str(e).lower():
                self.no_browser = True  # browser missing: stop trying for the rest of the run
            return None

    def allowed(self, url):
        host = urlparse(url).netloc
        if host not in self.robots:
            rp = robotparser.RobotFileParser()
            txt = self._raw(f"{urlparse(url).scheme}://{host}/robots.txt")
            rp.parse(txt.splitlines() if txt and "<html" not in txt[:300].lower() else [])
            self.robots[host] = rp
        return self.robots[host].can_fetch(BOT, url)

    def get(self, url):
        f = self.cache / (hashlib.sha1(url.encode()).hexdigest() + ".html")
        if f.exists() and time.time() - f.stat().st_mtime < 14 * 86400:
            return f.read_text(errors="ignore") or None
        host = urlparse(url).netloc
        with self.g:
            lock = self.locks.setdefault(host, threading.Lock())
        with lock:
            if not self.allowed(url):
                return None
            html = self._raw(url)
            time.sleep(self.delay)
        f.write_text(html or "")
        return html


STOP = {"inc", "llc", "co", "corp", "the", "and", "company", "services", "service", "group", "incorporated", "of", "us", "ltd"}
SEARCH_BACKENDS = ("brave", "bing", "yahoo", "mojeek", "duckduckgo")


def name_matches(company, host, title=""):
    """True when a website plausibly belongs to the company: a distinctive word of the name, or its
    initials (GMU, MWAA, HCPSS), appears in the host name or page title."""
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", company.lower()).split() if w not in STOP]
    if not words:
        return False
    flat = re.sub(r"[^a-z0-9]", "", host.lower().replace("www.", "").rsplit(".", 1)[0])
    initials = "".join(w[0] for w in re.sub(r"[^a-z ]", " ", company.lower()).split() if w not in ("of", "the", "and", "us"))
    if any(len(w) >= 3 and w in flat for w in words[:2]):
        return True
    if len(initials) >= 3 and initials in flat:
        return True
    t = title.lower()
    return len(words) >= 2 and all(w in t for w in words[:2])


def find_website(company, city=""):
    """Open-source web search (ddgs) across several engines. Returns the first result that belongs to
    the company and is not a directory or job board; '' when nothing trustworthy is found."""
    try:
        from ddgs import DDGS
    except ImportError:
        return ""
    query = f"{company} {city} official website"
    for backend in SEARCH_BACKENDS:
        try:
            results = DDGS(timeout=15).text(query, max_results=8, backend=backend)
        except Exception as e:  # engine blocked, timed out or unsupported: try the next one
            print(f"  search [{backend}] failed for {company}: {str(e)[:70]}")
            continue
        for r in results or []:
            u = r.get("href") or r.get("url") or ""
            host = urlparse(u).netloc.lower()
            if host and not any(b in host for b in NOT_A_SITE) and name_matches(company, host, r.get("title", "")):
                return f"{urlparse(u).scheme}://{host}"
    return ""


def crawl_site(base, fetcher, max_pages=8):
    base = base.rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    host = urlparse(base).netloc
    queue, done = [base], []
    emails, people, counts, strong, src = [], {}, Counter(), set(), {}
    guessed = False
    while queue and len(done) < max_pages:
        url = queue.pop(0)
        if url in done:
            continue
        html = fetcher.get(url)
        done.append(url)
        if html:
            r = parse_page(html)
            for e in r["emails"]:
                if e not in emails:
                    emails.append(e); src[e] = url
            for p in r["phones"]:
                counts[p] += 1; src.setdefault(p, url)
            strong |= set(r["strong_phones"])
            for n, t in r["people"].items():
                people.setdefault(n, t)
            for h in r["links"]:
                u = urljoin(url, h).split("#")[0].rstrip("/")
                if urlparse(u).netloc.replace("www.", "") == host.replace("www.", "") and u not in done and u not in queue:
                    queue.append(u)
            # contact/careers pages first
            queue.sort(key=lambda u: 0 if re.search(r"contact", u, re.I) else 1 if re.search(r"career|job|team|leader|about", u, re.I) else 2)
        if not queue and not guessed:  # home page gave no links (JS site or blocked): try common paths
            guessed = True
            queue = [base + p for p in GUESS]
    ph, em = best_phone(counts, strong), best_email(emails, host)
    if not ph and not em and hasattr(fetcher, "render"):  # nothing in the plain HTML: try a real browser once
        for url in [base] + [u for u in done if re.search(r"contact", u, re.I)][:1] or [base]:
            html = fetcher.render(url)
            if not html:
                continue
            r = parse_page(html)
            for e in r["emails"]:
                if e not in emails:
                    emails.append(e); src[e] = url
            for p in r["phones"]:
                counts[p] += 1; src.setdefault(p, url)
            strong |= set(r["strong_phones"])
            for n, t in r["people"].items():
                people.setdefault(n, t)
        ph, em = best_phone(counts, strong), best_email(emails, host)
    return {"website": base, "phone": ph, "email": em, "phone_src": src.get(ph, ""), "email_src": src.get(em, ""),
            "all_emails": emails[:8], "all_phones": [p for p, _ in counts.most_common(5)],
            "people": people, "pages": len(done), "local": bool(ph) and ph[1:4] in LOCAL_AREA}


EMPTY = {"website": "", "phone": "", "email": "", "people": {}, "all_emails": [], "all_phones": [], "pages": 0, "local": False}


def enrich(company, city, website, fetcher, trusted=False):
    """Website (given, else searched) -> crawled contacts. A given website that does not look like the
    company's own (e.g. a manufacturer's site on a dealer's posting) is ignored and searched instead."""
    site = website if website and (trusted or name_matches(company, urlparse(website if "//" in website else "//" + website).netloc)) else ""
    site = site or find_website(company, city)
    if not site:
        return {**EMPTY, "note": "website not found"}
    try:
        return crawl_site(site, fetcher)
    except Exception as e:
        return {**EMPTY, "website": site, "note": f"crawl error: {str(e)[:60]}"}
