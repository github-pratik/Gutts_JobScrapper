# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

GUTTS Job Runner — a job scraping tool for **Ground Up Trade & Talent Solutions** (Fairfax, VA), a workforce development company placing entry-level Plumbing/HVAC candidates with employers in Northern Virginia and the DC metro. The scraper surfaces relevant open roles so GUTTS staff can identify placement opportunities.

## Commands

Install dependencies (run from project root):
```bash
python -m pip install -r app/requirements.txt
```

Run the Streamlit web app:
```bash
python -m streamlit run app/web_app.py
# or on Windows:
run_web_app.bat
```

Run the Tkinter desktop GUI:
```bash
python app/gutts_job_runner.py
```

Run the scraper from the command line (no UI):
```bash
python app/jobspy_scrape.py
python app/jobspy_scrape.py --sites indeed linkedin --results-wanted 30 --hours-old 168
```

Run tests:
```bash
python -m unittest tests/test_jobspy_scrape.py
# single test:
python -m unittest tests.test_jobspy_scrape.JobspyScrapeTests.test_build_curated_jobs_schema
```

Build the Windows `.exe`:
```bash
build_tools/build_exe.bat
# outputs: dist/GUTTSJobRunner.exe
```

Deploy (Render reads `render.yaml` automatically on push):
```
startCommand: streamlit run app/web_app.py --server.address 0.0.0.0 --server.port $PORT
```

## Architecture

### Module responsibilities

**`app/jobspy_scrape.py`** — core engine, no UI dependencies.
- `ScrapeConfig` dataclass holds all scrape parameters with GUTTS-tuned defaults.
- `run_gutts_scrape(config, log)` is the single entry point called by all UIs. It runs one or two scrape passes, curates/filters results, validates links, dedupes, and writes CSV.
- `build_curated_jobs()` maps raw `jobspy` columns → a curated 14-column schema (`job_title`, `company`, `source_site`, `posted_date`, `location`, `work_type`, `experience`, `salary`, `skills`, `summary`, `job_url`, `link_status`, `search_query`, `scraped_at`).
- `apply_structured_filters()` does post-scrape filtering against `ScrapeConfig` fields (include/exclude keywords, must-have skills, experience range, work modes).
- `validate_job_link()` does a HEAD (then GET fallback) HTTP check on each `job_url`; results are `live`, `dead`, or `unknown`.

**`app/web_app.py`** — Streamlit UI. All state lives in `st.session_state` (initialized in `init_state()`). Presets (search presets + parameter presets) are applied via `apply_search_preset()` / `apply_parameter_preset()`. `effective_terms()` composes the final query strings from session state before passing to `run_gutts_scrape`.

**`app/gutts_job_runner.py`** — Tkinter desktop GUI. Mirrors web_app.py's preset logic but runs the scrape in a background thread (via `threading.Thread`) to keep the UI responsive, streaming log lines back through a `queue.Queue`.

### Data flow

```
User input (UI or CLI args)
  → ScrapeConfig
  → run_gutts_scrape()
      → run_one_scrape() [calls jobspy.scrape_jobs()]  ×1 or ×2 passes
      → sort_by_recency()
      → build_curated_jobs()       # column mapping
      → apply_structured_filters() # keyword / skill / experience / work-mode
      → enforce_recency()          # strict day-age cutoff
      → validate_job_link()        # per-row HTTP check (slow)
      → apply_link_status_filter()
      → dedupe_jobs()
      → write CSV
```

### Search query design

Two constant query strings are defined in `jobspy_scrape.py` (`GUTTS_DEFAULT_SEARCH`, `GUTTS_SECOND_PASS_SEARCH`) and duplicated in both UI files as Fairfax-specific variants. The web app adds `STRICT_ENTRY_EXCLUSIONS` and `EMPLOYMENT_TARGET_TERMS` modifiers that are appended to the base query at run time via `effective_terms()`. When editing queries, keep negative terms (`-software -developer -IT`) present to suppress non-trade results.

### Key constraints

- `validate_job_link()` makes one HTTP request per result row and is the dominant performance cost. LinkedIn and some boards return 403/429, which maps to `unknown` rather than `dead`.
- `linkedin_fetch_description=True` is off by default — it significantly slows scrapes and increases LinkedIn rate-limit risk.
- Tests in `tests/` use `sys.path.insert` to import from `app/` — there is no package structure or `setup.py`.
- CSV outputs are gitignored; never commit scraped data.

## Key files for business context

- `docs/GUTTS_COMPANY_CONTEXT.md` — detailed company background for understanding why search queries are tuned the way they are.
- `build_config/GUTTSJobRunner.spec` — PyInstaller spec for the Windows executable build.

## Development conventions

From the project's established Cursor skills (`.cursor/skills/`):

### Python standards
- Python 3.11+ idioms; type hints on all public functions.
- Prefer `pathlib` over raw string paths (already enforced throughout).
- Use dataclasses for structured domain objects (`ScrapeConfig` is the pattern to follow).
- Keep functions small with explicit side effects — no hidden globals or mutable module state.
- Implement the smallest correct change; avoid refactoring beyond what the task requires.

### Testing
- Framework: stdlib `unittest` (no pytest). Tests live in `tests/` and add `app/` to `sys.path` manually.
- Cover: happy path, `None`/empty input, bad types, and exception paths.
- Don't modify existing tests to make them pass — fix the code instead.

### Debugging approach
- Reproduce reliably before changing anything.
- Isolate by layer: is it the scrape call, the curation step, the filter, or the link validator?
- Form a specific hypothesis before touching code ("the `date_posted` column is missing because `glassdoor` returns a different field name").
- Fix the root cause, not the symptom.

### When iterating on failures
- Fix one error at a time, re-run tests after each fix.
- Never add `# noqa`, `# type: ignore`, or broad `except Exception: pass` to silence errors — fix the actual problem.
- If after several attempts nothing improves, stop and report what's blocking rather than making more speculative changes.

### Monitoring the running app
- Watch the Streamlit terminal for `Traceback`, `Error:`, or `streamlit.errors` patterns.
- The Streamlit server hot-reloads on file save — after a fix, check the terminal for "Rerunning..." and confirm no new errors appear.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
