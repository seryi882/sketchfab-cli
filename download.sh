#!/usr/bin/env bash
# Convenience launcher for Linux / macOS
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3 not found. Install Python 3.10+ and try again."
  exit 1
fi

if [[ ! -f tools/binz/binzDecrypt.exe ]]; then
  echo "Tools missing — running setup_tools.py ..."
  "$PY" setup_tools.py
fi

if [[ $# -eq 0 ]]; then
  exec "$PY" main.py
else
  exec "$PY" main.py "$@"
fi
