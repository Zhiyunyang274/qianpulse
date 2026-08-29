#!/usr/bin/env bash
set -euo pipefail

SERVER_PORT="${PORT:-8501}"
exec streamlit run app.py --server.address 0.0.0.0 --server.port "$SERVER_PORT"
