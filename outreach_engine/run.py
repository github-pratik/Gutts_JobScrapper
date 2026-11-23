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
        j["level"] = quality.level(j["title"])
        if j["level"] not in cfg["levels"] or not quality.is_fresh(j.get("posted", ""), today, cfg["max_days_old"]):
            continue
        cos.setdefault(norm(j["company"]), {"company": j["company"], "jobs": [], "website": ""})["jobs"].append(j)
        if j.get("website"):
            cos[norm(j["company"])]["website"] = j["website"]
    return cos


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
        co["jobs"] = [j for j in co["jobs"] if j["live"] != "Expired"]
        if not co["jobs"]:
            return None
        city = co["jobs"][0]["location"].split(",")[0]
        e = contacts.enrich(co["company"], city, known.get(norm(co["company"])) or co["website"], f)
        titles = " ".join(j["title"] for j in co["jobs"])
        ppl = "; ".join(f"{n} ({t})" for n, t in list(e["people"].items())[:5])
        posted = [x for x in {j.get("emails", "") for j in co["jobs"]} if x]
        co.update(industry=quality.sector(co["company"], titles), trade=quality.trade(titles, co["company"]),
                  phone=e["phone"], email=e["email"] or (posted[0].split(",")[0] if posted else ""), website=e["website"],
                  all_phones=e["all_phones"], all_emails=e["all_emails"],
                  notes="; ".join(x for x in [ppl, e.get("note", "")] if x))
        print(f"    {co['company'][:40]:40} phone={'Y' if co['phone'] else '-'} email={'Y' if co['email'] else '-'} jobs={len(co['jobs'])}")
        return co

    with ThreadPoolExecutor(cfg["workers"]) as ex:
        done = [c for c in ex.map(work, order) if c]

    print("3/4 Writing workbook")
    path = out / f"GUTTS_Call_Sheet_{today}.xlsx"
    sheet.build(done, str(path), today)
    with open(out / f"postings_{today}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["company", "industry", "trade", "phone", "email", "website", "title", "level", "location", "url", "source", "posting"])
        for c in done:
            for j in c["jobs"]:
                w.writerow([c["company"], c["industry"], c["trade"], c["phone"], c["email"], c["website"], j["title"], j["level"], j["location"], j["url"], j["source"], j["live"]])

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
