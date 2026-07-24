#!/usr/bin/env bash
# CIIS local development launcher.
#
#   ./dev.sh setup      recreate both venvs + frontend deps from scratch
#   ./dev.sh api        Django REST API on :8001  (override: CIIS_API_PORT)
#   ./dev.sh web        Vite dev server on :5173 (proxies /api -> :8001)
#   ./dev.sh up         api + web together (Ctrl-C stops both)
#   ./dev.sh reset-db   wipe the platform DB and re-seed demo users
#
# Two venvs are intentional: the OCR engine (paddlepaddle) and the threat
# intelligence ML stack pin incompatible numpy majors, so they cannot share one.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PY=/opt/homebrew/bin/python3.12   # engines require >=3.12; macOS system python is 3.9
PLATFORM_VENV=.venv-platform
THREAT_VENV=.venv-threat

# 8000 is left alone on purpose: other local projects commonly bind it, and the
# Vite proxy would then silently forward /api to the wrong application.
export CIIS_API_PORT="${CIIS_API_PORT:-8001}"

setup() {
  "$PY" -m venv "$PLATFORM_VENV"
  "$PLATFORM_VENV/bin/python" -m pip install -q --upgrade pip setuptools wheel
  "$PLATFORM_VENV/bin/python" -m pip install -q \
    -r evidence_ocr_engine/requirements.txt \
    -r ciis_api/requirements.txt \
    reportlab python-dateutil

  "$PY" -m venv "$THREAT_VENV"
  "$THREAT_VENV/bin/python" -m pip install -q --upgrade pip setuptools wheel
  "$THREAT_VENV/bin/python" -m pip install -q -r threat_intelligence_system/requirements.txt

  (cd ciis_frontend && npm install)
  reset_db
  echo "Setup complete. Run: ./dev.sh up"
}

reset_db() {
  (cd ciis_api \
    && ../"$PLATFORM_VENV"/bin/python manage.py migrate \
    && ../"$PLATFORM_VENV"/bin/python manage.py seed_demo)
}

api() { cd ciis_api && exec ../"$PLATFORM_VENV"/bin/python manage.py runserver "$CIIS_API_PORT"; }
web() { cd ciis_frontend && exec npm run dev; }

up() {
  ( api ) & local api_pid=$!
  ( web ) & local web_pid=$!
  trap 'kill $api_pid $web_pid 2>/dev/null' INT TERM
  wait
}

case "${1:-up}" in
  setup)    setup ;;
  api)      api ;;
  web)      web ;;
  up)       up ;;
  reset-db) reset_db ;;
  *) echo "usage: $0 {setup|api|web|up|reset-db}" >&2; exit 1 ;;
esac
