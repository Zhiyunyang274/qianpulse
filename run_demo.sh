#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Creating .venv …"
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import streamlit, numpy, scipy, plotly" >/dev/null 2>&1; then
  echo "Installing Python dependencies …"
  .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/streamlit run app.py "$@"
