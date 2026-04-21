@echo off
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

set "PYTHON_EXE="
REM Prefer full path first: works when py.exe and python are not on PATH.
for %%V in (312 313 311) do if not defined PYTHON_EXE (
  set "TRY_EXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
  if exist "!TRY_EXE!" (
    "!TRY_EXE!" -c "import sys" >nul 2>&1 && set "PYTHON_EXE=!TRY_EXE!"
  )
)
if not defined PYTHON_EXE where py >nul 2>&1 && py -3 -c "import sys" >nul 2>&1 && set "PYTHON_EXE=py -3"
if not defined PYTHON_EXE where python >nul 2>&1 && python -c "import sys" >nul 2>&1 && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
  echo Could not find Python. Install Python 3.12+ or add it to PATH, then retry.
  exit /b 1
)

echo Using Python: %PYTHON_EXE%
%PYTHON_EXE% -m pip install -r "app\requirements.txt"
if errorlevel 1 (
  echo Failed to install dependencies.
  exit /b 1
)

set "ICON_ARG="
if exist "%PROJECT_ROOT%\app_icon.ico" (
  set "ICON_ARG=--icon ""%PROJECT_ROOT%\app_icon.ico"""
)

%PYTHON_EXE% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name GUTTSJobRunner ^
  --version-file "%PROJECT_ROOT%\build_config\version_info.txt" ^
  %ICON_ARG% ^
  --collect-all jobspy ^
  --collect-all pandas ^
  --collect-all numpy ^
  --collect-all tls_client ^
  app\gutts_job_runner.py

if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo.
echo Build complete: "%PROJECT_ROOT%\dist\GUTTSJobRunner.exe"
endlocal
