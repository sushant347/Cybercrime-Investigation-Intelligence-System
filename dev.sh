#!/usr/bin/env bash
# CIIS local development launcher.
#
#   ./dev.sh            same as `up` (start the full project)
#   ./dev.sh up         API :8001 + web :5173 + engines, together (Ctrl-C stops both)
#   ./dev.sh setup      (re)create both venvs + frontend deps + seed the DB
#   ./dev.sh api        just the Django REST API on :8001  (override: CIIS_API_PORT)
#   ./dev.sh web        just the Vite dev server on :5173  (proxies /api -> :8001)
#   ./dev.sh threat ... run the phishing/threat engine CLI in its own venv
#   ./dev.sh reset-db   wipe the platform DB and re-seed demo users
#   ./dev.sh doctor     print the detected toolchain + what is/ isn't set up
#
# WHAT "THE FULL PROJECT" IS
#   The Django API (ciis_api) is the hub. It imports four forensic engines
#   IN-PROCESS via api/engine.py, so starting the API starts them too:
#       - evidence_ocr_engine        (OCR / evidence pipeline)
#       - evidence_correlation_engine
#       - timeline_reconstruction
#       - report generation
#   `up` therefore launches: API (+ those 4 engines) + the React/Vite frontend,
#   with the full pipeline enabled (CIIS_RUN_FULL_PIPELINE=1).
#
#   The threat_intelligence_system is the ONE engine that cannot share the
#   platform venv: paddlepaddle (OCR) needs numpy<2 while the threat ML stack
#   needs numpy>=2. It gets its own venv (.venv-threat). Run it standalone with
#   `./dev.sh threat <url>`, or opt into in-API ML scoring by exporting
#   CIIS_ML_THREAT_INTEL=1 (only meaningful in a venv built for it).
#
# `up` is self-bootstrapping: if the venvs / node_modules / DB are missing it
# runs `setup` for you first, so a fresh clone comes up with a single command.
#
# QUICK START FOR SOMEONE NEW TO THE REPO
#   1. Install Python 3.12+ (https://python.org/downloads) and Node.js 20+
#      (https://nodejs.org) if you don't already have them.
#   2. git clone <repo>, cd into it.
#   3. Run:  ./dev.sh
#   That single command creates both venvs, installs every Python/npm
#   dependency, sets up the database, and starts the app. First run takes
#   several minutes (downloads ~500MB of ML/CV packages); every run after
#   that starts in seconds. Open http://localhost:5173 once it's ready.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(pwd)"

# --------------------------------------------------------------- configuration
PLATFORM_VENV="${CIIS_PLATFORM_VENV:-.venv-platform}"
THREAT_VENV="${CIIS_THREAT_VENV:-.venv-threat}"

# 8000 is left alone on purpose: other local projects commonly bind it, and the
# Vite proxy would then silently forward /api to the wrong application.
export CIIS_API_PORT="${CIIS_API_PORT:-8001}"
export WEB_PORT="${WEB_PORT:-5173}"

# Make the engine roots explicit so the API finds every engine regardless of cwd.
export CIIS_ENGINE_ROOT="${CIIS_ENGINE_ROOT:-$ROOT/evidence_ocr_engine}"
export CIIS_THREAT_INTEL_ROOT="${CIIS_THREAT_INTEL_ROOT:-$ROOT/threat_intelligence_system}"
# Run the complete OCR->correlation->timeline->report pipeline on upload/analyze.
export CIIS_RUN_FULL_PIPELINE="${CIIS_RUN_FULL_PIPELINE:-1}"

# ------------------------------------------------------------------ toolchains
# Portable Python discovery. The engines require >=3.12 (macOS system python is
# 3.9). Honour CIIS_PYTHON, else pick the first interpreter that is >=3.12.
py_ok() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' >/dev/null 2>&1; }
find_python() {
  if [ -n "${CIIS_PYTHON:-}" ]; then echo "$CIIS_PYTHON"; return; fi
  for c in python3.14 python3.13 python3.12 python3 python \
           /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
    if command -v "$c" >/dev/null 2>&1 && py_ok "$c"; then command -v "$c"; return; fi
  done
  echo ""   # nothing suitable
}

# venv layout differs by platform: POSIX uses bin/, Windows (Git Bash) Scripts/.
venv_py() {
  local v="$1"
  if   [ -x "$v/bin/python" ];        then echo "$v/bin/python"
  elif [ -x "$v/Scripts/python.exe" ];then echo "$v/Scripts/python.exe"
  elif [ -x "$v/bin/python3" ];       then echo "$v/bin/python3"
  else echo "$v/bin/python"; fi   # default; existence checked by caller
}

require_python() {
  local p; p="$(find_python)"
  if [ -z "$p" ]; then
    echo "ERROR: need Python >=3.12 but none found." >&2
    echo "       Install it, or set CIIS_PYTHON=/path/to/python3.12" >&2
    exit 1
  fi
  echo "$p"
}

# ----------------------------------------------------------------------- setup
setup() {
  local PY; PY="$(require_python)"
  echo ">> Using Python: $PY ($("$PY" --version 2>&1))"

  echo ">> [1/4] platform venv ($PLATFORM_VENV): OCR + API + correlation/timeline/report"
  "$PY" -m venv "$PLATFORM_VENV"
  local ppy; ppy="$(venv_py "$PLATFORM_VENV")"
  "$ppy" -m pip install -q --upgrade pip setuptools wheel
  "$ppy" -m pip install -q \
    -r evidence_ocr_engine/requirements.txt \
    -r ciis_api/requirements.txt \
    reportlab python-dateutil

  echo ">> [2/4] threat venv ($THREAT_VENV): phishing/threat ML stack (separate numpy major)"
  "$PY" -m venv "$THREAT_VENV"
  local tpy; tpy="$(venv_py "$THREAT_VENV")"
  "$tpy" -m pip install -q --upgrade pip setuptools wheel
  "$tpy" -m pip install -q -r threat_intelligence_system/requirements.txt

  echo ">> [3/4] frontend deps (npm ci)"
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found. Install Node.js (https://nodejs.org) and re-run ./dev.sh" >&2
    exit 1
  fi
  # `npm ci` wipes node_modules and installs exactly what package-lock.json
  # pins -- a plain `npm install` on top of a stale/partial node_modules
  # (e.g. left over from switching branches) can silently produce a broken
  # dependency tree that only fails later, inside Vite, with a confusing
  # esbuild "Failed to resolve entry" error.
  ( cd ciis_frontend && (npm ci || { echo ">> npm ci failed (lockfile out of sync?) -- falling back to npm install"; rm -rf node_modules; npm install; } ) )

  echo ">> [4/4] database migrate + seed demo users"
  reset_db

  echo "Setup complete. Run: ./dev.sh up"
}

# Decide whether a first-run bootstrap is needed before `up`.
need_setup() {
  [ -x "$(venv_py "$PLATFORM_VENV")" ] || return 0
  [ -d "ciis_frontend/node_modules" ] || return 0
  [ -f "ciis_api/ciis_platform.sqlite3" ] || return 0
  return 1
}

# --------------------------------------------------------------------- db / run
reset_db() {
  local ppy; ppy="$(venv_py "$ROOT/$PLATFORM_VENV")"   # absolute, survives the subshell cd
  ( cd ciis_api \
      && "$ppy" manage.py migrate \
      && "$ppy" manage.py seed_demo )
}

api() {
  local ppy; ppy="$ROOT/${PLATFORM_VENV}"; ppy="$(venv_py "$ppy")"
  cd ciis_api && exec "$ppy" manage.py runserver "$CIIS_API_PORT"
}

web() {
  cd ciis_frontend && exec npm run dev -- --port "$WEB_PORT"
}

# Run the standalone threat engine in its own venv, e.g.
#   ./dev.sh threat https://paypal-login-security.xyz/login
threat() {
  local tpy; tpy="$ROOT/${THREAT_VENV}"; tpy="$(venv_py "$tpy")"
  if [ ! -x "$tpy" ]; then
    echo "ERROR: threat venv missing. Run ./dev.sh setup first." >&2; exit 1
  fi
  ( cd threat_intelligence_system && exec "$tpy" cli.py "$@" )
}

up() {
  if need_setup; then
    echo ">> First run detected (missing venv / node_modules / DB) — bootstrapping..."
    setup
  fi
  echo ">> Starting CIIS full stack:"
  echo "     API     http://localhost:$CIIS_API_PORT   (+ OCR/correlation/timeline/report engines)"
  echo "     Web     http://localhost:$WEB_PORT"
  echo "     Ctrl-C stops everything."

  ( api ) &  local api_pid=$!
  ( web ) &  local web_pid=$!
  # Kill the whole process group of each child so runserver/vite children die too.
  trap 'kill "$api_pid" "$web_pid" 2>/dev/null; wait 2>/dev/null' INT TERM
  wait
}

doctor() {
  local PY; PY="$(find_python)"
  echo "CIIS doctor"
  echo "  repo root        : $ROOT"
  echo "  python (>=3.12)  : ${PY:-NOT FOUND}"
  [ -n "$PY" ] && echo "  python version   : $("$PY" --version 2>&1)"
  echo "  platform venv    : $([ -x "$(venv_py "$PLATFORM_VENV")" ] && echo present || echo MISSING) ($PLATFORM_VENV)"
  echo "  threat venv      : $([ -x "$(venv_py "$THREAT_VENV")" ] && echo present || echo MISSING) ($THREAT_VENV)"
  echo "  frontend deps    : $([ -d ciis_frontend/node_modules ] && echo present || echo MISSING)"
  echo "  platform DB      : $([ -f ciis_api/ciis_platform.sqlite3 ] && echo present || echo MISSING)"
  echo "  API port         : $CIIS_API_PORT"
  echo "  web port         : $WEB_PORT"
  echo "  full pipeline    : CIIS_RUN_FULL_PIPELINE=$CIIS_RUN_FULL_PIPELINE"
  echo "  ML threat intel  : CIIS_ML_THREAT_INTEL=${CIIS_ML_THREAT_INTEL:-0}"
}

case "${1:-up}" in
  setup)    setup ;;
  api)      api ;;
  web)      web ;;
  up)       up ;;
  threat)   shift; threat "$@" ;;
  reset-db) reset_db ;;
  doctor)   doctor ;;
  *) echo "usage: $0 {up|setup|api|web|threat|reset-db|doctor}" >&2; exit 1 ;;
esac
