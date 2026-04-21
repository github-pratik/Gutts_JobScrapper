# Scraper_Gutts - GUTTS Job Runner

A desktop job scraping project for Ground Up Trade & Talent Solutions (GUTTS), packaged as a Windows executable for non-technical users.

## What this project does

- Provides a GUI app to run job searches across multiple job boards.
- Collects and exports job results to CSV.
- Supports configurable search keywords, location, recency, and sources.
- Can be packaged into a single-click `.exe` file for easy sharing.

## Core project files

- `app/gutts_job_runner.py` - Tkinter GUI runner application.
- `app/jobspy_scrape.py` - Scraping logic and config model.
- `app/requirements.txt` - Python dependencies.
- `build_config/GUTTSJobRunner.spec` - PyInstaller build config.
- `build_config/version_info.txt` - Windows version metadata for the `.exe`.

## Run from source

1. Install Python 3.11+ (3.12 recommended).
2. Install dependencies:
   - `python -m pip install -r app/requirements.txt`
3. Start the app:
   - `python app/gutts_job_runner.py`

## Build the executable

- Run:
  - `build_tools/build_exe.bat`
- Output:
  - `dist/GUTTSJobRunner.exe`

## Notes

- Generated outputs should stay local and are excluded from version control.
- If Windows SmartScreen appears for the `.exe`, use "More info" -> "Run anyway" for trusted internal use.
