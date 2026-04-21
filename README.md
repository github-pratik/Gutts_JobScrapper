# Scraper_Gutts - GUTTS Job Runner

A job scraping project for Ground Up Trade & Talent Solutions (GUTTS), available as both a desktop executable and a browser-based web app for non-technical users.

## What this project does

- Provides a GUI app to run job searches across multiple job boards.
- Collects and exports job results to CSV.
- Supports configurable search keywords, location, recency, and sources.
- Can be packaged into a single-click `.exe` file for easy sharing.

## Core project files

- `app/gutts_job_runner.py` - Tkinter GUI runner application.
- `app/web_app.py` - Streamlit web app for browser-based usage.
- `app/jobspy_scrape.py` - Scraping logic and config model.
- `app/requirements.txt` - Python dependencies.
- `run_web_app.bat` - One-click launcher for the Streamlit app on Windows.
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

## Run the web app (recommended for easiest usage)

- One-click on Windows:
  - `run_web_app.bat`
- Or via terminal:
  - `python -m pip install -r app/requirements.txt`
  - `python -m streamlit run app/web_app.py`

After startup, open the URL shown in terminal (usually `http://localhost:8501`).

## Deploy on Render

This repo includes `render.yaml` and `runtime.txt` for easy deployment.

1. Push this project to GitHub.
2. In Render, click **New +** -> **Blueprint**.
3. Connect your GitHub repo and select this project.
4. Render reads `render.yaml` and creates the web service automatically.
5. After deploy, open the Render URL (for example `https://gutts-job-runner.onrender.com`).

Notes:
- Free tier services can sleep when idle (first request may take longer).
- For best scrape reliability, keep the default Fairfax/LinkedIn+Indeed+ZipRecruiter presets.

## Notes

- Generated outputs should stay local and are excluded from version control.
- If Windows SmartScreen appears for the `.exe`, use "More info" -> "Run anyway" for trusted internal use.