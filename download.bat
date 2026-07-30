@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set PY=py -3
) else (
  set PY=python
)

%PY% -c "import sys; print(sys.version)" >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install from https://www.python.org/downloads/
  echo Enable "Add python.exe to PATH" during setup.
  pause
  exit /b 1
)

if not exist "tools\binz\binzDecrypt.exe" (
  echo Tools missing. Running setup_tools.py ...
  %PY% setup_tools.py
  if errorlevel 1 (
    echo setup_tools.py failed.
    pause
    exit /b 1
  )
)

if "%~1"=="" (
  %PY% main.py
) else (
  %PY% main.py %*
)

echo.
pause
endlocal
