#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "EDEN's local Python environment is missing."
  echo "Run:  python3 -m venv .venv"
  echo "Then: .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi
exec .venv/bin/python run.py "$@"

