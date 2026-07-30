@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/
  pause
  exit /b 1
)

if not exist downloads mkdir downloads

docker image inspect sketchfab-cli:latest >nul 2>&1
if errorlevel 1 (
  echo Building Docker image first time, please wait...
  docker compose build
  if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
  )
)

if "%~1"=="" (
  echo Usage: docker-download.bat "https://sketchfab.com/3d-models/..."
  echo    or: docker-download.bat --check-tools
  pause
  exit /b 1
)

docker compose run --rm downloader %*
echo.
echo Done. Check the downloads\ folder.
pause
endlocal
