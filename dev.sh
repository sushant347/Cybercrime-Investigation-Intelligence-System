#!/usr/bin/env bash
# =============================================================================
# CIIS local development launcher.
# =============================================================================
#
# NEW HERE? THIS IS THE ONLY COMMAND YOU NEED
#
#     ./dev.sh
#
# It checks your machine, installs everything, and starts the app. First run
# downloads ~500 MB of OCR/ML packages and takes 5-15 minutes; every run after
# that starts in seconds. When it is ready it prints a http://localhost:5173
# link (and opens it for you).
#
# On Windows, run it from **Git Bash** (installed with Git for Windows), not
# from cmd.exe or PowerShell. If you double-click `dev.cmd` it will find Git
# Bash and do this for you.
#
# WHAT YOU NEED INSTALLED FIRST
#   - Python 3.12 or newer   https://python.org/downloads
#       (on Windows, tick "Add python.exe to PATH" in the installer)
#   - Node.js 20 or newer    https://nodejs.org  (pick the LTS build)
#   Run `./dev.sh doctor` and it will tell you exactly what is missing.
#
# ALL COMMANDS
#   ./dev.sh            same as `up`
#   ./dev.sh up         API + web + engines together (Ctrl-C stops everything)
#   ./dev.sh setup      (re)create both venvs + frontend deps + seed the DB
#   ./dev.sh api        just the Django REST API      (port: CIIS_API_PORT)
#   ./dev.sh web        just the Vite dev server      (port: WEB_PORT)
#   ./dev.sh threat ... run the phishing/threat engine CLI in its own venv
#   ./dev.sh test       run the frontend + API test suites
#   ./dev.sh reset-db   wipe the platform DB and re-seed demo users
#   ./dev.sh doctor     print the detected toolchain + what is / isn't set up
#   ./dev.sh clean      delete both venvs and node_modules for a fresh start
#   ./dev.sh help       this text
#
# WHAT "THE FULL PROJECT" IS
#   The Django API (ciis_api) is the hub. It imports two engine roots
#   IN-PROCESS via api/engine.py, so starting the API starts them too:
#       - evidence_ocr_engine          OCR / evidence extraction
#       - evidence_correlation_engine  analysis: correlation, graph, campaigns,
#                                      suspects, timeline, analytics, reports
#   The correlation engine is the analytical core. It reads the OCR engine's
#   storage tree read-only, and loads two standalone algorithm modules itself:
#       - timeline_reconstruction      timestamp resolution + ordering
#       - threat_intelligence_system   phishing-URL classifier (optional)
#   `up` therefore launches: API (+ those engines) + the React/Vite frontend,
#   with the full pipeline enabled (CIIS_RUN_FULL_PIPELINE=1).
#
#   ("report generation/" at the repo root is a retired prototype that nothing
#   imports; reports come from the correlation engine's reporting module.)
#
#   The threat_intelligence_system is the ONE engine that cannot share the
#   platform venv: paddlepaddle (OCR) needs numpy<2 while the threat ML stack
#   needs numpy>=2. It gets its own venv (.venv-threat). Run it standalone with
#   `./dev.sh threat <url>`, or opt into in-API ML scoring by exporting
#   CIIS_ML_THREAT_INTEL=1 (only meaningful in a venv built for it).
#
# ENVIRONMENT OVERRIDES
#   CIIS_PYTHON=/path/to/python3.12   use a specific interpreter
#   CIIS_API_PORT=8001  WEB_PORT=5173 pick ports (a busy port is auto-bumped)
#   CIIS_NO_BROWSER=1                 don't open a browser window on `up`
#   CIIS_SKIP_THREAT_VENV=1           skip the heavy ML venv during setup
# =============================================================================

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(pwd)"

# --------------------------------------------------------------- presentation
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_DIM=$'\033[2m'; C_RED=$'\033[31m'; C_YEL=$'\033[33m'
  C_GRN=$'\033[32m'; C_BLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_DIM=""; C_RED=""; C_YEL=""; C_GRN=""; C_BLD=""; C_OFF=""
fi
log()  { printf '%s>>%s %s\n'  "$C_BLD" "$C_OFF" "$*"; }
ok()   { printf '%s ok %s %s\n' "$C_GRN" "$C_OFF" "$*"; }
warn() { printf '%s !! %s %s\n' "$C_YEL" "$C_OFF" "$*" >&2; }
die()  { printf '%sERROR%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }
hint() { printf '      %s%s%s\n' "$C_DIM" "$*" "$C_OFF" >&2; }

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

# ------------------------------------------------------------------- platform
# Git Bash / MSYS reports MINGW64_NT-...; that is Windows, and several things
# below (executable names, browser opener, venv layout) differ there.
case "$(uname -s 2>/dev/null || echo unknown)" in
  Linux*)                 OS=linux   ;;
  Darwin*)                OS=macos   ;;
  MINGW*|MSYS*|CYGWIN*)   OS=windows ;;
  *)                      OS=unknown ;;
esac

# npm ships as npm.cmd on Windows; `command -v npm` finds the shim in Git Bash
# but plain `npm` inside a subshell sometimes does not, so resolve it once.
find_npm() {
  if command -v npm      >/dev/null 2>&1; then command -v npm;      return; fi
  if command -v npm.cmd  >/dev/null 2>&1; then command -v npm.cmd;  return; fi
  echo ""
}

install_hint_python() {
  case "$OS" in
    macos)   hint "Install it with:  brew install python@3.12" ;;
    linux)   hint "Install it with:  sudo apt install python3.12 python3.12-venv" ;;
    windows) hint "Download it from https://python.org/downloads and TICK 'Add python.exe to PATH'." ;;
    *)       hint "Download it from https://python.org/downloads" ;;
  esac
  hint "Already installed somewhere unusual? Run: CIIS_PYTHON=/full/path/to/python ./dev.sh"
}

install_hint_node() {
  case "$OS" in
    macos) hint "Install it with:  brew install node" ;;
    linux) hint "Install it with:  sudo apt install nodejs npm   (or use nvm for a current version)" ;;
    *)     hint "Download the LTS build from https://nodejs.org" ;;
  esac
}

# ------------------------------------------------------------------ toolchains
# Portable Python discovery. The engines require >=3.12 (macOS system python is
# 3.9). Honour CIIS_PYTHON, else pick the first interpreter that is >=3.12.
py_ok() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' >/dev/null 2>&1; }
find_python() {
  if [ -n "${CIIS_PYTHON:-}" ]; then
    py_ok "$CIIS_PYTHON" && { echo "$CIIS_PYTHON"; return; }
    return
  fi
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
    if [ -n "${CIIS_PYTHON:-}" ]; then
      warn "CIIS_PYTHON=$CIIS_PYTHON is not a working Python 3.12+."
    fi
    printf '%sERROR%s Python 3.12 or newer is required, and none was found.\n' "$C_RED" "$C_OFF" >&2
    install_hint_python
    exit 1
  fi
  echo "$p"
}

node_major() {
  command -v node >/dev/null 2>&1 || { echo 0; return; }
  node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0
}

require_node() {
  local npm_bin; npm_bin="$(find_npm)"
  [ -n "$npm_bin" ] || {
    printf '%sERROR%s Node.js / npm not found.\n' "$C_RED" "$C_OFF" >&2
    install_hint_node
    exit 1
  }
  local major; major="$(node_major)"
  if [ "$major" -lt 20 ] 2>/dev/null; then
    warn "Node $(node --version 2>/dev/null) detected; this project is built against Node 20+."
    install_hint_node
  fi
  echo "$npm_bin"
}

# ------------------------------------------------------------------ networking
# Port probing goes through Python rather than lsof/netstat/ss, which are named
# and flagged differently on every platform (and absent in Git Bash).
port_busy() {
  local port="$1" py; py="$(find_python)"
  [ -n "$py" ] || return 1     # can't tell; assume free rather than block
  "$py" -c '
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(0)      # busy
finally:
    s.close()
sys.exit(1)          # free
' "$port" >/dev/null 2>&1
}

# Find the first free port at or after $1, so a leftover server from a previous
# run (or an unrelated app) never turns into a mystery blank page.
free_port_from() {
  local port="$1" tries=0
  while port_busy "$port" && [ "$tries" -lt 20 ]; do
    port=$((port + 1)); tries=$((tries + 1))
  done
  echo "$port"
}

wait_for_http() {
  local url="$1" timeout="${2:-90}" py; py="$(find_python)"
  [ -n "$py" ] || { sleep 3; return 0; }
  "$py" -c '
import sys, time, urllib.request, urllib.error
url, deadline = sys.argv[1], time.time() + float(sys.argv[2])
while time.time() < deadline:
    try:
        urllib.request.urlopen(url, timeout=2)
        sys.exit(0)
    except urllib.error.HTTPError:
        sys.exit(0)          # answered, even if 404/401 - the server is up
    except Exception:
        time.sleep(0.7)
sys.exit(1)
' "$url" "$timeout" >/dev/null 2>&1
}

open_browser() {
  [ -z "${CIIS_NO_BROWSER:-}" ] || return 0
  [ -t 1 ] || return 0
  case "$OS" in
    macos)   open "$1"        >/dev/null 2>&1 || true ;;
    windows) start "" "$1"    >/dev/null 2>&1 || true ;;
    linux)   xdg-open "$1"    >/dev/null 2>&1 || true ;;
  esac
}

# ----------------------------------------------------------------------- setup
setup() {
  local PY; PY="$(require_python)"
  local NPM; NPM="$(require_node)"
  log "Using Python: $PY ($("$PY" --version 2>&1))"
  log "Using npm:    $NPM (node $(node --version 2>/dev/null || echo '?'))"
  echo
  warn "First-time setup downloads roughly 500 MB and can take 5-15 minutes."
  hint "It is not stuck - pip is quiet while it resolves large ML wheels."
  echo

  local steps=4
  [ -n "${CIIS_SKIP_THREAT_VENV:-}" ] && steps=3

  log "[1/$steps] platform venv ($PLATFORM_VENV): OCR + API + correlation/timeline/report"
  if ! "$PY" -m venv "$PLATFORM_VENV"; then
    printf '%sERROR%s Could not create a virtualenv.\n' "$C_RED" "$C_OFF" >&2
    [ "$OS" = linux ] && hint "On Debian/Ubuntu this usually means: sudo apt install python3-venv"
    exit 1
  fi
  local ppy; ppy="$(venv_py "$PLATFORM_VENV")"
  "$ppy" -m pip install -q --upgrade pip setuptools wheel
  "$ppy" -m pip install \
    -r evidence_ocr_engine/requirements.txt \
    -r ciis_api/requirements.txt \
    reportlab python-dateutil \
    || die "Installing the platform dependencies failed (see the pip output above)."

  if [ -n "${CIIS_SKIP_THREAT_VENV:-}" ]; then
    warn "Skipping the threat venv (CIIS_SKIP_THREAT_VENV set). './dev.sh threat' will not work."
  else
    log "[2/$steps] threat venv ($THREAT_VENV): phishing/threat ML stack (separate numpy major)"
    "$PY" -m venv "$THREAT_VENV"
    local tpy; tpy="$(venv_py "$THREAT_VENV")"
    "$tpy" -m pip install -q --upgrade pip setuptools wheel
    "$tpy" -m pip install -r threat_intelligence_system/requirements.txt \
      || die "Installing the threat-intelligence dependencies failed (see the pip output above)."
  fi

  log "[$((steps - 1))/$steps] frontend deps"
  # `npm ci` wipes node_modules and installs exactly what package-lock.json
  # pins -- a plain `npm install` on top of a stale/partial node_modules
  # (e.g. left over from switching branches) can silently produce a broken
  # dependency tree that only fails later, inside Vite, with a confusing
  # esbuild "Failed to resolve entry" error.
  (
    cd ciis_frontend
    "$NPM" ci || {
      warn "npm ci failed (lockfile out of sync?) - falling back to npm install"
      rm -rf node_modules
      "$NPM" install
    }
  ) || die "Installing the frontend dependencies failed. Check your internet connection and re-run ./dev.sh setup"

  log "[$steps/$steps] database migrate + seed demo users (skipped if no database)"
  reset_db

  echo
  ok "Setup complete. Starting the app is now just: ./dev.sh"
}

# Decide whether a first-run bootstrap is needed before `up`.
need_setup() {
  local ppy; ppy="$(venv_py "$PLATFORM_VENV")"
  [ -x "$ppy" ] || return 0
  # A venv directory can exist while the install inside it failed half way,
  # which used to surface as an unexplained ImportError at runtime.
  "$ppy" -c 'import django' >/dev/null 2>&1 || return 0
  [ -d "ciis_frontend/node_modules/vite" ] || return 0
  return 1
}

# --------------------------------------------------------------------- db / run
reset_db() {
  # The platform database was removed (config.settings has DATABASES = {}):
  # there are no migrations and no seed_demo command any more, and case data
  # lives in evidence_ocr_engine/storage/ instead. Detect that build rather
  # than assuming, so this launcher keeps working either way.
  if [ ! -d "ciis_api/api/migrations" ]; then
    log "No platform database in this build - nothing to migrate or seed."
    hint "Case data lives in evidence_ocr_engine/storage/ and is managed from the app's admin screen."
    return 0
  fi
  local ppy; ppy="$(venv_py "$ROOT/$PLATFORM_VENV")"   # absolute, survives the subshell cd
  ( cd ciis_api \
      && "$ppy" manage.py migrate \
      && "$ppy" manage.py seed_demo )
}

api() {
  local ppy; ppy="$(venv_py "$ROOT/$PLATFORM_VENV")"
  [ -x "$ppy" ] || die "Platform venv missing. Run ./dev.sh setup first."
  cd ciis_api && exec "$ppy" manage.py runserver "$CIIS_API_PORT"
}

web() {
  local NPM; NPM="$(require_node)"
  [ -d ciis_frontend/node_modules ] || die "Frontend deps missing. Run ./dev.sh setup first."
  cd ciis_frontend && exec "$NPM" run dev -- --port "$WEB_PORT" --strictPort
}

# Run the standalone threat engine in its own venv, e.g.
#   ./dev.sh threat https://paypal-login-security.xyz/login
threat() {
  local tpy; tpy="$(venv_py "$ROOT/$THREAT_VENV")"
  if [ ! -x "$tpy" ]; then
    die "Threat venv missing. Run ./dev.sh setup first (without CIIS_SKIP_THREAT_VENV)."
  fi
  ( cd threat_intelligence_system && exec "$tpy" cli.py "$@" )
}

run_tests() {
  local failed=0
  local NPM; NPM="$(find_npm)"
  if [ -n "$NPM" ] && [ -d ciis_frontend/node_modules ]; then
    log "frontend tests (vitest)"
    ( cd ciis_frontend && "$NPM" test ) || failed=1
  else
    warn "Skipping frontend tests - run ./dev.sh setup first."
  fi
  local ppy; ppy="$(venv_py "$ROOT/$PLATFORM_VENV")"
  if [ -x "$ppy" ]; then
    log "API tests (pytest)"
    ( cd ciis_api && "$ppy" -m pytest -q ) || failed=1
    log "OCR engine tests (pytest)"
    ( cd evidence_ocr_engine && "$ppy" -m pytest -q ) || failed=1
    log "correlation engine tests (pytest)"
    ( cd evidence_correlation_engine && "$ppy" -m pytest -q ) || failed=1
  else
    warn "Skipping Python tests - run ./dev.sh setup first."
  fi
  [ "$failed" -eq 0 ] || die "Some tests failed (see the output above)."
  ok "All test suites passed."
}

up() {
  if need_setup; then
    log "First run detected (missing or incomplete venv / node_modules) - bootstrapping..."
    setup
    echo
  fi

  # A port left busy by a previous run is the single most common reason the
  # app "starts" but shows a blank page, so move rather than collide. The API
  # port is exported before Vite starts, which is how its /api proxy follows.
  local want_api="$CIIS_API_PORT" want_web="$WEB_PORT"
  CIIS_API_PORT="$(free_port_from "$CIIS_API_PORT")"
  WEB_PORT="$(free_port_from "$WEB_PORT")"
  export CIIS_API_PORT WEB_PORT
  [ "$CIIS_API_PORT" = "$want_api" ] || warn "Port $want_api was busy - using $CIIS_API_PORT for the API."
  [ "$WEB_PORT" = "$want_web" ]      || warn "Port $want_web was busy - using $WEB_PORT for the web app."

  echo
  log "Starting CIIS:"
  echo "     API     http://localhost:$CIIS_API_PORT   (+ OCR/correlation/timeline/report engines)"
  echo "     Web     http://localhost:$WEB_PORT"
  echo "     ${C_DIM}Ctrl-C stops everything.${C_OFF}"
  echo

  api & local api_pid=$!
  web & local web_pid=$!

  # Kill both children on Ctrl-C, and on any exit path, so a half-dead stack
  # never leaves a port bound for the next run.
  cleanup() {
    trap - INT TERM EXIT
    kill "$api_pid" "$web_pid" 2>/dev/null || true
    wait "$api_pid" "$web_pid" 2>/dev/null || true
  }
  trap cleanup INT TERM EXIT

  if wait_for_http "http://localhost:$WEB_PORT/" 120; then
    echo
    ok "CIIS is ready -> ${C_BLD}http://localhost:$WEB_PORT${C_OFF}"
    open_browser "http://localhost:$WEB_PORT/"
  else
    warn "The web server has not answered yet; watch the log above for errors."
  fi

  # Return as soon as EITHER process exits. Without this the script sat on a
  # plain `wait` while, say, a crashed API left the frontend serving a UI
  # whose every request failed - the confusing failure mode this replaces.
  # `wait -n` needs bash 4.3+; macOS still ships bash 3.2, so poll there.
  if [ "${BASH_VERSINFO[0]}" -gt 4 ] || \
     { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -ge 3 ]; }; then
    wait -n "$api_pid" "$web_pid" 2>/dev/null || true
  else
    while kill -0 "$api_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do
      sleep 1
    done
  fi

  if kill -0 "$api_pid" 2>/dev/null; then
    warn "The web server stopped. Shutting the API down too."
  else
    warn "The API stopped. Shutting the web server down too."
    hint "Scroll up for the Python traceback - that is the real error."
  fi
}

doctor() {
  local PY; PY="$(find_python)"
  local NPM; NPM="$(find_npm)"
  local ppy; ppy="$(venv_py "$PLATFORM_VENV")"
  local tpy; tpy="$(venv_py "$THREAT_VENV")"
  local problems=0

  echo "${C_BLD}CIIS doctor${C_OFF}"
  echo "  repo root        : $ROOT"
  echo "  platform         : $OS ($(uname -s 2>/dev/null || echo unknown))"

  if [ -n "$PY" ]; then
    ok "python 3.12+     : $PY ($("$PY" --version 2>&1))"
  else
    warn "python 3.12+     : NOT FOUND"; install_hint_python; problems=$((problems + 1))
  fi

  if [ -n "$NPM" ]; then
    local major; major="$(node_major)"
    if [ "$major" -ge 20 ] 2>/dev/null; then
      ok "node 20+         : $(node --version) ($NPM)"
    else
      warn "node             : $(node --version 2>/dev/null || echo '?') - 20+ expected"
      install_hint_node; problems=$((problems + 1))
    fi
  else
    warn "node / npm       : NOT FOUND"; install_hint_node; problems=$((problems + 1))
  fi

  if [ -x "$ppy" ] && "$ppy" -c 'import django' >/dev/null 2>&1; then
    ok "platform venv    : ready ($PLATFORM_VENV)"
  elif [ -x "$ppy" ]; then
    warn "platform venv    : present but incomplete - run ./dev.sh setup"; problems=$((problems + 1))
  else
    warn "platform venv    : MISSING - run ./dev.sh setup"; problems=$((problems + 1))
  fi

  if [ -x "$tpy" ]; then ok "threat venv      : present ($THREAT_VENV)"
  else echo "  threat venv      : missing (optional; only './dev.sh threat' needs it)"; fi

  if [ -d ciis_frontend/node_modules/vite ]; then ok "frontend deps    : ready"
  else warn "frontend deps    : MISSING - run ./dev.sh setup"; problems=$((problems + 1)); fi

  echo "  platform DB      : $([ -d ciis_api/api/migrations ] \
      && echo "$([ -f ciis_api/ciis_platform.sqlite3 ] && echo present || echo MISSING)" \
      || echo "n/a (no database in this build)")"
  echo "  API port         : $CIIS_API_PORT $(port_busy "$CIIS_API_PORT" && echo '(BUSY - will be auto-bumped)' || echo '(free)')"
  echo "  web port         : $WEB_PORT $(port_busy "$WEB_PORT" && echo '(BUSY - will be auto-bumped)' || echo '(free)')"
  echo "  full pipeline    : CIIS_RUN_FULL_PIPELINE=$CIIS_RUN_FULL_PIPELINE"
  echo "  ML threat intel  : CIIS_ML_THREAT_INTEL=${CIIS_ML_THREAT_INTEL:-0}"
  echo

  if [ "$problems" -eq 0 ]; then ok "Everything looks good. Run: ./dev.sh"
  else warn "$problems thing(s) need attention - see the hints above."; fi
}

clean() {
  log "Removing $PLATFORM_VENV, $THREAT_VENV and ciis_frontend/node_modules"
  rm -rf "$PLATFORM_VENV" "$THREAT_VENV" ciis_frontend/node_modules
  ok "Clean. The next ./dev.sh will rebuild everything from scratch."
}

# Print the header comment block verbatim, so the help text and the file's own
# documentation can never drift apart.
usage() {
  awk 'NR == 1 { next }
       /^#/     { sub(/^# ?/, ""); print; next }
       { exit }' "${BASH_SOURCE[0]}"
}

case "${1:-up}" in
  setup)         setup ;;
  api)           api ;;
  web)           web ;;
  up)            up ;;
  threat)        shift; threat "$@" ;;
  test|tests)    run_tests ;;
  reset-db)      reset_db ;;
  doctor)        doctor ;;
  clean)         clean ;;
  help|-h|--help) usage ;;
  *) echo "usage: $0 {up|setup|api|web|threat|test|reset-db|doctor|clean|help}" >&2; exit 1 ;;
esac
