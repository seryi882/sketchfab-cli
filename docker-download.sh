#!/usr/bin/env bash
# Download a Sketchfab model using Docker (no local Python/Wine needed).
# Usage:
#   ./docker-download.sh "https://sketchfab.com/3d-models/..."
#   ./docker-download.sh --check-tools
#   ./docker-download.sh URL1 URL2
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Install: https://docs.docker.com/get-docker/"
  exit 1
fi

mkdir -p downloads

# Build image if missing
if ! docker image inspect sketchfab-cli:latest >/dev/null 2>&1; then
  echo "Building Docker image (first time may take several minutes)..."
  docker compose build
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <sketchfab-url-or-uid> [more-urls...]"
  echo "   or: $0 --check-tools"
  echo "   or: $0 --help"
  exit 1
fi

exec docker compose run --rm downloader "$@"
