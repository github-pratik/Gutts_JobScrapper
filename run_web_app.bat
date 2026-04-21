@echo off
setlocal EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

set "PYTHON_EXE="
for %%V in (312 313 311) do if not defined PYTHON_EXE (
  set "TRY_EXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
  if exist "!TRY_EXE!" set "PYTHON_EXE=!TRY_EXE!"
)
if not defined PYTHON_EXE where py >nul 2>&1 && set "PYTHON_EXE=py -3"
if not defined PYTHON_EXE where python >nul 2>&1 && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
  echo Could not find Python. Install Python 3.11+ and retry.
  exit /b 1
)

echo Using Python: %PYTHON_EXE%
%PYTHON_EXE% -m pip install -r "app\requirements.txt"
if errorlevel 1 (
  echo Failed to install dependencies.
  exit /b 1
)

echo Starting GUTTS web app...
%PYTHON_EXE% -m streamlit run "app\web_app.py"
