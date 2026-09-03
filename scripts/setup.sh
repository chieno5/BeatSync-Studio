#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.10+ was not found. Install Python and retry." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 13) else 1)'; then
  echo "BeatSync Studio currently requires Python 3.10-3.12." >&2
  exit 1
fi

echo "[1/3] Creating virtual environment..."
"$PYTHON_BIN" -m venv "$PROJECT_ROOT/.venv"

echo "[2/3] Installing BeatSync Studio..."
"$PROJECT_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT_ROOT/.venv/bin/python" -m pip install -e "$PROJECT_ROOT[anime,online]"

echo "[3/3] Checking the installation..."
"$PROJECT_ROOT/.venv/bin/beatsync" doctor
