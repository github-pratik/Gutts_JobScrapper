"""GUTTS outreach engine.   python run.py            -> full run, writes out/GUTTS_Call_Sheet_<date>.xlsx
                            python run.py --limit 20 -> quick test on 20 companies
                            python run.py --all      -> include companies already on a past sheet"""
import argparse
import collections
import csv
import datetime
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

import contacts
import jobs as jobsrc
import quality
import sharepoint
import sheet


def norm(c):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\b(inc|llc|co|corp|company|the)\b", "", c.lower()))


def group(jobs, cfg, today):
    cos = collections.OrderedDict()
    for j in jobs:
        j["level"] = quality.level(j["title"], j.get("description", ""))
        if j["level"] not in cfg["levels"] or not quality.is_fresh(j.get("posted", ""), today, cfg["max_days_old"]):
            continue
        cos.setdefault(norm(j["company"]), {"company": j["company"], "jobs": [], "website": ""})["jobs"].append(j)
        if j.get("website"):
            cos[norm(j["company"])]["website"] = j["website"]
    return cos


def collapse(jobs):
    """One row per job title per company: the same opening posted in 14 towns becomes one line."""
    by = collections.OrderedDict()
    for j in jobs:
        by.setdefault(j["title"].lower(), []).append(j)
    out = []
    for group_ in by.values():
        first = max(group_, key=lambda j: j.get("posted", ""))
        towns = list(dict.fromkeys(t for t in (j["location"].split(",")[0].strip() for j in group_) if len(t) > 2))
        state = first["location"].split(",")[1].strip() if "," in first["location"] else ""
        loc = (first["location"] if "," in first["location"] or not towns else towns[0]) if len(towns) <= 1 else ", ".join(towns[:3]) + (f" +{len(towns) - 3} more" if len(towns) > 3 else "") + (f" ({state} area)" if state else "")
        live = "Live" if any(j["live"] == "Live" for j in group_) else first["live"]
        out.append({**first, "location": loc, "live": live, "openings": len(group_)})
    return out


BOARD_MAIL = ("monster.", "indeed.", "ziprecruiter.", "glassdoor.", "linkedin.", "icims.", "greenhouse.", "lever.co", "workday", "usajobs.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml"); ap.add_argument("--out", default="out")
    ap.add_argument("--limit", type=int); ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config)); today = datetime.date.today()
    out = Path(a.out); out.mkdir(exist_ok=True)

    print("1/4 Collecting postings")
    raw = jobsrc.collect(cfg)
    kept = jobsrc.clean(raw, cfg)
    cos = group(kept, cfg, today)
    print(f"    {len(raw)} raw -> {len(kept)} relevant -> {len(cos)} companies with entry/mid roles")

    sp = sharepoint.connect()
    master = out / "master.csv"; seen = {}
    if sp and sp.download(sharepoint.MASTER_PATH, master):
        print("    loaded master list from SharePoint")
    if master.exists():
        seen = {r["key"]: r for r in csv.DictReader(open(master))}
    if cfg.get("only_new_companies") and not a.all:
        cos = collections.OrderedDict((k, v) for k, v in cos.items() if k not in seen)
        print(f"    {len(cos)} are new (not on a past sheet)")
    # most entry-level openings first: these are the best calls
    order = sorted(cos.values(), key=lambda c: (-sum(j["level"] == "Entry" for j in c["jobs"]), -len(c["jobs"])))
    order = order[: a.limit or cfg["max_companies"]]

    print(f"2/4 Checking postings are live + finding contacts for {len(order)} companies")
    f = contacts.Fetcher(cache_dir=str(out / "cache"), delay=cfg["delay_seconds"])
    known = {norm(k): v for k, v in (cfg.get("known_websites") or {}).items()}

    def status(url):
        import requests
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"})
            return r.status_code, r.text
        except requests.RequestException:
            return None, ""  # unreachable: check_live reports this posting as Unverified

    def work(co):
        for j in co["jobs"]:
            j["live"] = quality.check_live(j, status)
        co["jobs"] = collapse([j for j in co["jobs"] if j["live"] != "Expired"])
        if not co["jobs"]:
            return None
        for j in co["jobs"]:
            j["requirements"] = quality.requirements(j.get("description", ""))
        city = co["jobs"][0]["location"].split(",")[0]
        kw = known.get(norm(co["company"]))
        e = contacts.enrich(co["company"], city, kw or co["website"], f, trusted=bool(kw))
        titles = " ".join(j["title"] for j in co["jobs"])
        people = list(e["people"].items())
        posted = [m.strip() for j in co["jobs"] for m in (j.get("emails") or "").split(",")
                  if "@" in m and not any(b in m.lower() for b in BOARD_MAIL)]
        notes = [e.get("note", "")]
        if e["phone"] and not e.get("local"):
            notes.append("Phone is a head-office line, not local - ask for the DC-area service/maintenance manager")
        if len(people) > 1:
            notes.append("Also: " + "; ".join(f"{n} ({t})" for n, t in people[1:4]))
        co.update(industry=quality.sector(co["company"], titles), trade=quality.trade(titles, co["company"]),
                  phone=e["phone"], email=e["email"] or (posted[0] if posted else ""), website=e["website"],
                  contact_name=people[0][0] if people else "", contact_title=people[0][1] if people else "",
                  all_phones=e["all_phones"], all_emails=e["all_emails"], notes="; ".join(x for x in notes if x))
        print(f"    {co['company'][:40]:40} phone={'Y' if co['phone'] else '-'} email={'Y' if co['email'] else '-'} jobs={len(co['jobs'])}")
        return co

    with ThreadPoolExecutor(cfg["workers"]) as ex:
        done = [c for c in ex.map(work, order) if c]

    print("3/4 Writing workbook")
    path = out / f"GUTTS_Call_Sheet_{today}.xlsx"
    sheet.build(done, str(path), today)
    with open(out / f"postings_{today}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["company", "industry", "trade", "phone", "email", "website", "contact", "notes", "title", "level", "location", "pay", "requirements", "posted", "url", "source", "posting"])
        for c in done:
            for j in c["jobs"]:
                w.writerow([c["company"], c["industry"], c["trade"], c["phone"], c["email"], c["website"], f"{c['contact_name']} {c['contact_title']}".strip(), c["notes"], j["title"], j["level"], j["location"], j.get("pay", ""), j["requirements"], j.get("posted", ""), j["url"], j["source"], j["live"]])

    print("4/4 Updating master list")
    for c in done:
        seen.setdefault(norm(c["company"]), dict(key=norm(c["company"]), company=c["company"], first_seen=str(today)))
        seen[norm(c["company"])].update(phone=c["phone"], email=c["email"], website=c["website"], last_seen=str(today))
    with open(master, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["key", "company", "phone", "email", "website", "first_seen", "last_seen"]); w.writeheader(); w.writerows(seen.values())
    if sp:
        link = sp.upload(path, path.name)                       # new file each week, never overwrites
        sp.upload(master, sharepoint.MASTER_PATH, overwrite=True)
        print(f"    saved to SharePoint: {link}")
    if getattr(f, "errors", None):
        (out / "fetch_errors.log").write_text("\n".join(f.errors))
        print(f"    {len(f.errors)} page fetches failed (see out/fetch_errors.log)")
    n = len(done) or 1
    print(f"\nDONE  {len(done)} companies | {sum(len(c['jobs']) for c in done)} live/unverified postings | "
          f"phone {sum(bool(c['phone']) for c in done)*100//n}% | email {sum(bool(c['email']) for c in done)*100//n}%\n{path}")


if __name__ == "__main__":
    main()
