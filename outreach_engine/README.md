# GUTTS Outreach Engine

Finds live entry/mid-level HVAC, plumbing and facility jobs in the DC metro, finds each employer's
phone and email from the employer's own website, and writes the weekly call sheet.

## Run it (one time setup)
1. Install Python 3.11+
2. `pip install -r outreach_engine/requirements.txt`
3. `python outreach_engine/run.py --limit 20`   (quick test)   then   `python outreach_engine/run.py`   (full run)

Output lands in `out/`: `GUTTS_Call_Sheet_<date>.xlsx`, `postings_<date>.csv`, `master.csv` (every company ever listed,
so next week only shows new ones).

## What it does
| Step | How |
|---|---|
| Job postings | JobSpy (Indeed, ZipRecruiter), public Greenhouse / Lever / Workable boards, optional Adzuna + USAJobs APIs |
| Fit filter | Keeps trade titles in VA/MD/DC, tags Entry / Mid, drops Senior, staffing agencies and postings older than 14 days |
| Live check | Opens every posting; 404 or "expired / filled" text = dropped. Blocked check = "Unverified" |
| Website | Uses the site from the posting, else a DuckDuckGo search (ddgs) |
| Contacts | Scrapling crawls home, contact, about, team, careers pages: tel: links, mailto:, structured data, Cloudflare-hidden emails, named managers |
| Sheet | Company row + posting sub-rows, dropdowns, "Where Hiring Is" tab, Contact History, All Employers |

## Optional free keys (set as environment variables or GitHub secrets, never in files)
`ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (developer.adzuna.com)  |  `USAJOBS_API_KEY`, `USAJOBS_EMAIL` (developer.usajobs.gov)

## Change what it searches
Edit `config.yaml`: locations, search terms, levels, employer career boards, known websites.

## Limits (by design)
- Business main lines and business emails only. No personal cell numbers.
- Respects each website's robots.txt and pauses between pages. No logins, no CAPTCHA bypass, no LinkedIn.
- Job boards can block or change; a blocked source is skipped and the run continues.

## Saving to SharePoint (optional)
Set these in the GitHub repo and each run saves a new dated sheet into the folder (it never overwrites a sheet people
have typed in) and keeps `_engine/master.csv` there so only new companies appear each week.
- Secrets: `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`
- Variables: `SHAREPOINT_SITE_URL`, `SHAREPOINT_FOLDER`
