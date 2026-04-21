import csv
import html
import re
import socket
import sys
import time
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(r"C:\Users\ppshp\Desktop\JOB")
SOURCE_CSV = ROOT / "Master Employer List - Final(Sheet2).csv"
SEED_CSV = ROOT / "company_job_pages_batch1.csv"
OUTPUT_RESEARCH_CSV = ROOT / "company_job_pages_all.csv"
OUTPUT_MASTER_CSV = ROOT / "Master Employer List - Final(Sheet2)-with-job-pages.csv"
OUTPUT_MASTER_XLSX = ROOT / "Master Employer List - Final(Sheet2)-with-job-pages.xlsx"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "aol.com",
    "icloud.com",
    "msn.com",
    "live.com",
    "verizon.net",
    "comcast.net",
}
GENERIC_JOB_BOARDS = {
    "indeed.com",
    "simplyhired.com",
    "ziprecruiter.com",
    "glassdoor.com",
    "monster.com",
    "linkedin.com",
}
KEYWORDS = [
    "careers",
    "career",
    "jobs",
    "job",
    "employment",
    "join-our-team",
    "join our team",
    "work-with-us",
    "opportunities",
    "apply",
    "open positions",
]
JOB_HOST_HINTS = [
    "greenhouse.io",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "myworkdayjobs.com",
    "ultipro.com",
    "ukg.com",
    "adp.com",
    "paylocity.com",
    "icims.com",
    "bamboohr.com",
    "applicantpro.com",
    "taleo.net",
    "smartrecruiters.com",
    "ashbyhq.com",
]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self._current_href: Optional[str] = None
        self._current_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "a":
            attr_map = dict(attrs)
            self._current_href = attr_map.get("href")
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href is not None:
            text = " ".join(part.strip() for part in self._current_text if part.strip()).strip()
            self.links.append((self._current_href, html.unescape(text)))
            self._current_href = None
            self._current_text = []


def fetch_url(url: str, timeout: int = 12) -> Tuple[Optional[str], Optional[str]]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return final_url, None
            body = resp.read(600_000)
            charset = "utf-8"
            match = re.search(r"charset=([a-zA-Z0-9_-]+)", content_type)
            if match:
                charset = match.group(1)
            try:
                text = body.decode(charset, errors="replace")
            except LookupError:
                text = body.decode("utf-8", errors="replace")
            return final_url, text
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError):
        return None, None


def extract_links(base_url: str, html_text: str) -> List[Tuple[str, str]]:
    parser = LinkParser()
    parser.feed(html_text)
    links = []
    for href, text in parser.links:
        if not href:
            continue
        absolute = urljoin(base_url, href)
        links.append((absolute, text.strip()))
    return links


def score_link(url: str, text: str, company: str, official_domain: Optional[str]) -> int:
    url_l = url.lower()
    text_l = text.lower()
    score = 0
    for keyword in KEYWORDS:
        if keyword in url_l:
            score += 6
        if keyword in text_l:
            score += 5
    if any(host in url_l for host in JOB_HOST_HINTS):
        score += 7
    if official_domain:
        host = urlparse(url_l).netloc.replace("www.", "")
        if official_domain in host:
            score += 4
    if company.lower().split(",")[0] in text_l:
        score += 2
    if "mailto:" in url_l or "tel:" in url_l:
        score -= 10
    if any(nope in url_l for nope in ["/privacy", "/contact", "/about", "/blog", "/news", "/product"]):
        score -= 3
    return score


def normalize_domain(email_text: str) -> str:
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", str(email_text or ""), flags=re.I)
    for email_addr in emails:
        domain = email_addr.strip().lower().split("@", 1)[1]
        if domain and domain not in FREE_EMAIL_DOMAINS:
            return domain
    return ""


def read_source_rows() -> List[Dict[str, str]]:
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def unique_companies(rows: List[Dict[str, str]]) -> List[str]:
    seen = OrderedDict()
    for row in rows:
        company = (row.get("Company") or "").strip()
        if company and company != "-":
            seen.setdefault(company, None)
    return list(seen.keys())


def company_domain_map(rows: List[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in rows:
        company = (row.get("Company") or "").strip()
        if not company or company == "-" or company in out:
            continue
        domain = normalize_domain(row.get("Email") or "")
        out[company] = domain
    return out


def load_seed_data() -> Dict[str, Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    for path in [SEED_CSV, OUTPUT_RESEARCH_CSV]:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            company = row.get("Company")
            if company:
                merged[company] = row
    return merged


def load_existing_research() -> Dict[str, Dict[str, str]]:
    return {}


def looks_like_jobs_page(url: str) -> bool:
    url_l = url.lower()
    return any(keyword.replace(" ", "-") in url_l or keyword in url_l for keyword in KEYWORDS) or any(
        host in url_l for host in JOB_HOST_HINTS
    )


def search_duckduckgo(company: str, official_domain: str) -> Optional[str]:
    queries = []
    if official_domain:
        queries.append(f'site:{official_domain} careers jobs')
        queries.append(f'site:{official_domain} employment')
    queries.append(f'"{company}" careers jobs official')
    queries.append(f'"{company}" employment official')

    for query in queries:
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        final_url, html_text = fetch_url(search_url, timeout=15)
        if not final_url or not html_text:
            continue
        links = extract_links(final_url, html_text)
        candidates = []
        for link, text in links:
            parsed = urlparse(link)
            if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
                qs = parse_qs(parsed.query)
                uddg = qs.get("uddg", [""])[0]
                if uddg:
                    link = unquote(uddg)
            host = urlparse(link).netloc.lower().replace("www.", "")
            if host in GENERIC_JOB_BOARDS:
                continue
            score = score_link(link, text, company, official_domain)
            if official_domain:
                if official_domain not in host and not any(job_host in host for job_host in JOB_HOST_HINTS):
                    continue
            if score >= 8:
                candidates.append((score, link))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
    return None


def probe_common_paths(domain: str) -> Optional[str]:
    candidates = [
        "/careers",
        "/careers/",
        "/jobs",
        "/jobs/",
        "/employment",
        "/employment/",
        "/join-our-team",
        "/join-our-team/",
        "/about/careers",
        "/about-us/careers",
    ]
    for prefix in [f"https://{domain}", f"https://www.{domain}", f"http://{domain}", f"http://www.{domain}"]:
        for path in candidates:
            url = prefix + path
            final_url, html_text = fetch_url(url, timeout=10)
            if final_url and (html_text is not None or looks_like_jobs_page(final_url)):
                return final_url
    return None


def find_jobs_page(company: str, domain: str) -> Tuple[str, str, str]:
    if domain:
        for home in [f"https://{domain}", f"https://www.{domain}", f"http://{domain}", f"http://www.{domain}"]:
            final_url, html_text = fetch_url(home)
            if not final_url:
                continue
            if html_text:
                links = extract_links(final_url, html_text)
                scored = []
                for link, text in links:
                    score = score_link(link, text, company, domain)
                    if score >= 8:
                        scored.append((score, link, text))
                if scored:
                    scored.sort(reverse=True)
                    top_score, top_link, top_text = scored[0]
                    if any(host in top_link for host in JOB_HOST_HINTS):
                        return top_link, "Verified careers page", "Official site links to an external job application system."
                    if domain in urlparse(top_link).netloc.replace("www.", ""):
                        return top_link, "Verified careers page", "Official company site careers/jobs page."
                    return top_link, "Likely careers page", f'Best careers-related link found from official site: {top_text or top_link}'
            common = probe_common_paths(domain)
            if common:
                return common, "Likely careers page", "Common careers/jobs path found on the likely official domain."

        search_hit = search_duckduckgo(company, domain)
        if search_hit:
            return search_hit, "Likely careers page", "Found via targeted web search using the likely official domain."

        return "", "No clear public careers page found", "Could not verify a public careers/jobs page on the likely official site."

    search_hit = search_duckduckgo(company, domain)
    if search_hit:
        return search_hit, "Likely careers page", "Found via web search because the sheet did not provide a reliable company domain."

    return "", "No clear public careers page found", "The sheet did not provide a reliable domain, and a public careers page could not be verified."


def save_research_rows(rows: List[Dict[str, str]]) -> None:
    fields = ["Company", "JobsOrCareersPage", "Status", "Notes"]
    with OUTPUT_RESEARCH_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_outputs() -> None:
    source_rows = read_source_rows()
    companies = unique_companies(source_rows)
    domains = company_domain_map(source_rows)
    seed = load_seed_data()
    existing = load_existing_research()

    results: List[Dict[str, str]] = []
    for idx, company in enumerate(companies, start=1):
        if company in existing:
            row = existing[company]
            results.append(
                {
                    "Company": company,
                    "JobsOrCareersPage": row.get("JobsOrCareersPage", ""),
                    "Status": row.get("Status", ""),
                    "Notes": row.get("Notes", ""),
                }
            )
            continue

        if company in seed:
            row = seed[company]
            results.append(
                {
                    "Company": company,
                    "JobsOrCareersPage": row.get("JobsOrCareersPage", ""),
                    "Status": row.get("Status", ""),
                    "Notes": row.get("Notes", ""),
                }
            )
            save_research_rows(results)
            continue

        domain = domains.get(company, "")
        page, status, notes = find_jobs_page(company, domain)
        result = {
            "Company": company,
            "JobsOrCareersPage": page,
            "Status": status,
            "Notes": notes,
        }
        results.append(result)
        print(f"[{idx}/{len(companies)}] {company} -> {status} -> {page or 'N/A'}", flush=True)
        save_research_rows(results)
        time.sleep(0.4)

    save_research_rows(results)

    research_map = {row["Company"]: row for row in results}
    merged_rows = []
    for row in source_rows:
        company = (row.get("Company") or "").strip()
        job_row = research_map.get(company, {})
        merged_rows.append(
            {
                "Name": row.get("Name", ""),
                "Company": row.get("Company", ""),
                "Title": row.get("Title", ""),
                "Email": row.get("Email", ""),
                "Phone": row.get("Phone", ""),
                "Location": row.get("Location", ""),
                "JobsOrCareersPage": job_row.get("JobsOrCareersPage", ""),
                "JobsPageStatus": job_row.get("Status", ""),
                "JobsPageNotes": job_row.get("Notes", ""),
            }
        )

    pd.DataFrame(merged_rows).to_csv(OUTPUT_MASTER_CSV, index=False)
    pd.DataFrame(merged_rows).to_excel(OUTPUT_MASTER_XLSX, index=False)


if __name__ == "__main__":
    try:
        build_outputs()
    except KeyboardInterrupt:
        sys.exit(130)
