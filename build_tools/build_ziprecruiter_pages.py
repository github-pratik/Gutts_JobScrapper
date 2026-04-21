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
SOURCE_CSV = ROOT / "Master Employer List - Final(Sheet2)-with-job-pages.csv"
RESEARCH_CSV = ROOT / "company_ziprecruiter_pages.csv"
OUTPUT_CSV = ROOT / "ZipRecruiter Leads.csv"
OUTPUT_XLSX = ROOT / "ZipRecruiter Leads.xlsx"
OUTPUT_SHEET_NAME = "ZipRecruiter Leads"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
ZIPRECRUITER_HOSTS = {"ziprecruiter.com", "www.ziprecruiter.com"}


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


def fetch_url(url: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str]]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return final_url, None
            body = resp.read(400_000)
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


def normalize_company(company: str) -> str:
    company = re.sub(r"\s+", " ", str(company or "").strip())
    return company


def company_query_variants(company: str) -> List[str]:
    normalized = normalize_company(company)
    stripped = re.sub(r"[^A-Za-z0-9 ]+", " ", normalized)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    variants = OrderedDict()
    for value in [normalized, stripped]:
        if value:
            variants[value] = None
    return list(variants.keys())


def is_ziprecruiter_url(url: str) -> bool:
    return urlparse(url).netloc.lower() in ZIPRECRUITER_HOSTS


def score_ziprecruiter_link(url: str, text: str, company: str) -> int:
    if not is_ziprecruiter_url(url):
        return -999

    url_l = url.lower()
    text_l = text.lower()
    company_l = company.lower()
    score = 0

    if "/jobs/" in url_l or "/jobs-" in url_l:
        score += 8
    if "/c/" in url_l or "/cmp/" in url_l:
        score += 6
    if company_l in text_l:
        score += 10
    for token in re.findall(r"[a-z0-9]+", company_l):
        if len(token) >= 4 and token in text_l:
            score += 2

    return score


def search_ziprecruiter(company: str) -> Optional[str]:
    for variant in company_query_variants(company):
        query = f'site:ziprecruiter.com "{variant}"'
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        final_url, html_text = fetch_url(search_url, timeout=10)
        if not final_url or not html_text:
            continue

        candidates = []
        for link, text in extract_links(final_url, html_text):
            parsed = urlparse(link)
            if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
                qs = parse_qs(parsed.query)
                uddg = qs.get("uddg", [""])[0]
                if uddg:
                    link = unquote(uddg)

            score = score_ziprecruiter_link(link, text, variant)
            if score >= 8:
                candidates.append((score, link))

        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]

    return None


def read_source_rows() -> List[Dict[str, str]]:
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def unique_companies(rows: List[Dict[str, str]]) -> List[str]:
    seen = OrderedDict()
    for row in rows:
        company = normalize_company(row.get("Company", ""))
        if company and company != "-":
            seen.setdefault(company, None)
    return list(seen.keys())


def load_existing_research() -> Dict[str, Dict[str, str]]:
    if not RESEARCH_CSV.exists():
        return {}
    with RESEARCH_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {normalize_company(row.get("Company", "")): row for row in rows if row.get("Company")}


def save_research_rows(rows: List[Dict[str, str]]) -> None:
    fields = ["Company", "ZipRecruiterPage", "ZipRecruiterStatus", "ZipRecruiterNotes"]
    with RESEARCH_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def find_ziprecruiter_page(company: str) -> Tuple[str, str, str]:
    page = search_ziprecruiter(company)
    if page:
        return page, "ZipRecruiter page found", "Found through a targeted web search for public ZipRecruiter results."
    return "", "No clear ZipRecruiter page found", "No public ZipRecruiter result was found for this company."


def build_outputs() -> None:
    source_rows = read_source_rows()
    companies = unique_companies(source_rows)
    existing = load_existing_research()

    results: List[Dict[str, str]] = []
    for idx, company in enumerate(companies, start=1):
        if company in existing:
            results.append(existing[company])
            continue

        page, status, notes = find_ziprecruiter_page(company)
        result = {
            "Company": company,
            "ZipRecruiterPage": page,
            "ZipRecruiterStatus": status,
            "ZipRecruiterNotes": notes,
        }
        results.append(result)
        print(f"[{idx}/{len(companies)}] {company} -> {status} -> {page or 'N/A'}", flush=True)
        save_research_rows(results)
        time.sleep(0.2)

    save_research_rows(results)

    research_map = {row["Company"]: row for row in results}
    merged_rows = []
    for row in source_rows:
        company = normalize_company(row.get("Company", ""))
        zip_row = research_map.get(company, {})
        merged = dict(row)
        merged["ZipRecruiterPage"] = zip_row.get("ZipRecruiterPage", "")
        merged["ZipRecruiterStatus"] = zip_row.get("ZipRecruiterStatus", "")
        merged["ZipRecruiterNotes"] = zip_row.get("ZipRecruiterNotes", "")
        merged_rows.append(merged)

    output_df = pd.DataFrame(merged_rows)
    output_df.to_csv(OUTPUT_CSV, index=False)
    output_df.to_excel(OUTPUT_XLSX, index=False, sheet_name=OUTPUT_SHEET_NAME)


if __name__ == "__main__":
    try:
        build_outputs()
    except KeyboardInterrupt:
        sys.exit(130)
