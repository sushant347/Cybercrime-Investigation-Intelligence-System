#!/usr/bin/env bash
# =============================================================================
# CIIS local development launcher.
# =============================================================================
#
# NEW HERE? THIS IS THE ONLY COMMAND YOU NEED
#
#     ./dev.sh
#
# It checks your machine, creates/repairs every Python environment, installs
# only changed dependency sets, installs the frontend, and starts the app.
# Environments are invoked directly; you never have to activate one manually.
# First run downloads several large OCR/RAG/ML packages. Later runs skip every
# environment whose requirements have not changed.
#
# On Windows, run it from **Git Bash** (installed with Git for Windows), not
# from cmd.exe or PowerShell. If you double-click `dev.cmd` it will find Git
# Bash and do this for you.
#
# WHAT YOU NEED INSTALLED FIRST
#   - Python 3.12            https://python.org/downloads
#       (on Windows, tick "Add python.exe to PATH" in the installer)
#   - Node.js 20 or newer    https://nodejs.org  (pick the LTS build)
#   - macOS: Apple Silicon (arm64); current Paddle wheels do not support Intel
#   - Ollama                  https://ollama.com (needed for generated answers;
#                             structured RAG lookup still installs without it)
#
# ALL COMMANDS
#   ./dev.sh            same as `up`
#   ./dev.sh up         API + web + engines together (Ctrl-C stops everything)
#   ./dev.sh setup      prepare all venvs + frontend deps without starting
#   ./dev.sh api        just the Django REST API      (port: CIIS_API_PORT)
#   ./dev.sh web        just the Vite dev server      (port: WEB_PORT)
#   ./dev.sh threat ... run the phishing/threat engine CLI in its own venv
#   ./dev.sh test       run the frontend + API test suites
#   ./dev.sh reset-db   wipe the platform DB and re-seed demo users
#   ./dev.sh doctor     print the detected toolchain + what is / isn't set up
#   ./dev.sh clean      delete repo-local venvs and node_modules for a fresh start
#   ./dev.sh help       this text
#
# WHAT "THE FULL PROJECT" IS
#   The Django API (ciis_api) is the hub. It imports three engine roots
#   IN-PROCESS via api/engine.py, so starting the API starts them too:
#       - evidence_ocr_engine          OCR / evidence extraction
#       - evidence_correlation_engine  correlation, cross-case, campaigns,
#                                      suspects
#       - timeline_report_engine       timeline, graph, analytics, priority,
#                                      reports (owns the pipeline root)
#   They form a straight chain, each importing only the one before it:
#       frontend -> API -> OCR -> correlation -> timeline+report
#   The optional case assistant consumes the resulting files out-of-process:
#       pipeline artifacts -> API adapter -> standalone RAG CLI
#   It is never imported into the OCR/correlation/timeline dependency chain.
#   `up` therefore launches: API (+ those engines) + the React/Vite frontend,
#   with the full pipeline enabled (CIIS_RUN_FULL_PIPELINE=1).
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
#   CIIS_SKIP_RAG_VENV=1              skip the RAG venv during setup
#   CIIS_RAG_VENV=/short/path         override the managed RAG venv directory
#   CIIS_RAG_PYTHON=/path/to/python   use an already-managed RAG interpreter
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

# Torch wheels contain deeply nested licence files. On Windows, keeping the RAG
# environment inside an already-long repository path can exceed MAX_PATH. Use
# the short per-user local cache by default there; POSIX platforms stay local
# to the repository. CIIS_RAG_VENV always wins.
if [ -n "${CIIS_RAG_VENV:-}" ]; then
  RAG_VENV="$CIIS_RAG_VENV"
elif [ "$OS" = windows ] && [ -n "${LOCALAPPDATA:-}" ]; then
  if command -v cygpath >/dev/null 2>&1; then
    RAG_VENV="$(cygpath -u "$LOCALAPPDATA")/CIIS/venvs/rag"
  else
    RAG_VENV="$LOCALAPPDATA/CIIS/venvs/rag"
  fi
else
  RAG_VENV=".venv-rag"
fi

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
# Portable Python discovery. PaddleOCR is not yet supported on Python 3.14, so
# this project deliberately targets 3.12 rather than accepting any newer build.
py_ok() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)' >/dev/null 2>&1; }
find_python() {
  if [ -n "${CIIS_PYTHON:-}" ]; then
    py_ok "$CIIS_PYTHON" && { echo "$CIIS_PYTHON"; return; }
    return
  fi
  for c in python3.12 python3 python \
           /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
    if command -v "$c" >/dev/null 2>&1 && py_ok "$c"; then command -v "$c"; return; fi
  done
  # The Windows Python launcher is commonly available even when python.exe was
  # not added to PATH. Ask it for the concrete executable so callers can quote
  # and invoke one path normally.
  if command -v py >/dev/null 2>&1; then
    local launched
    launched="$(py -3.12 -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
    if [ -n "$launched" ] && command -v cygpath >/dev/null 2>&1; then
      launched="$(cygpath -u "$launched")"
    fi
    if [ -n "$launched" ] && py_ok "$launched"; then echo "$launched"; return; fi
  fi
  echo ""   # nothing suitable
}

require_supported_platform() {
  if [ "$OS" = macos ] && [ "$(uname -m 2>/dev/null || echo unknown)" != arm64 ]; then
    die "The OCR engine requires PaddlePaddle, whose current macOS wheel supports Apple Silicon (arm64), not Intel Macs."
  fi
}

venv_dir() {
  case "$1" in
    /*) echo "$1" ;;
    [A-Za-z]:[\\/]*)
      if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else echo "$1"; fi
      ;;
    *) echo "$ROOT/$1" ;;
  esac
}

# venv layout differs by platform: POSIX uses bin/, Windows (Git Bash) Scripts/.
venv_py() {
  local v="$1"
  if   [ -x "$v/bin/python" ];        then echo "$v/bin/python"
  elif [ -x "$v/Scripts/python.exe" ];then echo "$v/Scripts/python.exe"
  elif [ -x "$v/bin/python3" ];       then echo "$v/bin/python3"
  else echo "$v/bin/python"; fi   # default; existence checked by caller
}

configure_rag_runtime() {
  local candidate="${CIIS_RAG_PYTHON:-}"
  if [ -z "$candidate" ]; then
    candidate="$(venv_py "$(venv_dir "$RAG_VENV")")"
  fi
  if [ -x "$candidate" ] && "$candidate" -c \
      'import importlib.util,sys; sys.exit(0 if importlib.util.find_spec("chromadb") and importlib.util.find_spec("sentence_transformers") else 1)' \
      >/dev/null 2>&1; then
    # Git Bash addresses Windows drives as /c/... while the Django process is
    # native Windows Python. Passing the MSYS spelling through the environment
    # makes pathlib resolve it below the current drive (for example E:\c\...),
    # so the otherwise healthy RAG runtime appears to be missing. Export a
    # native, slash-safe drive path for the cross-process API boundary.
    if [ "$OS" = windows ] && command -v cygpath >/dev/null 2>&1; then
      candidate="$(cygpath -m "$candidate")"
    fi
    export CIIS_RAG_PYTHON="$candidate"
    return 0
  fi
  # Do not pass a stale/broken explicit interpreter to Django. The API should
  # advertise the assistant as unavailable while the core pipeline stays live.
  unset CIIS_RAG_PYTHON
  return 1
}

require_python() {
  local p; p="$(find_python)"
  if [ -z "$p" ]; then
    if [ -n "${CIIS_PYTHON:-}" ]; then
      warn "CIIS_PYTHON=$CIIS_PYTHON is not a working Python 3.12 interpreter."
    fi
    printf '%sERROR%s Python 3.12 is required, and none was found.\n' "$C_RED" "$C_OFF" >&2
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
    warn "Node $(node --version 2>/dev/null) detected; Node 20+ is required."
    install_hint_node
    exit 1
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

OLLAMA_PID=""
find_ollama() {
  if command -v ollama >/dev/null 2>&1; then command -v ollama; return; fi
  if [ "$OS" = macos ] \
     && [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
    echo "/Applications/Ollama.app/Contents/Resources/ollama"
    return
  fi
  echo ""
}

prepare_ollama() {
  [ -z "${CIIS_SKIP_RAG_VENV:-}" ] || return 0
  local ollama_bin; ollama_bin="$(find_ollama)"
  if [ -z "$ollama_bin" ]; then
    warn "Ollama is not installed; open-ended assistant answers will be unavailable."
    hint "Install it from https://ollama.com and run ./dev.sh again."
    return 0
  fi

  if ! wait_for_http "http://127.0.0.1:11434/api/tags" 2; then
    log "Starting local Ollama service"
    "$ollama_bin" serve >/dev/null 2>&1 & OLLAMA_PID=$!
    if ! wait_for_http "http://127.0.0.1:11434/api/tags" 20; then
      warn "Ollama did not start; deterministic assistant answers remain available."
      kill "$OLLAMA_PID" 2>/dev/null || true
      wait "$OLLAMA_PID" 2>/dev/null || true
      OLLAMA_PID=""
      return 0
    fi
  fi

  local model="${CIIS_RAG_OLLAMA_MODEL:-gemma3:1b}"
  if "$ollama_bin" show "$model" >/dev/null 2>&1; then
    ok "Ollama ready ($model)"
  else
    log "Downloading local assistant model: $model"
    "$ollama_bin" pull "$model" \
      || warn "Could not download $model; retry later with: ollama pull $model"
  fi
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
requirements_digest() {
  local base_python="$1"; shift
  "$base_python" -c '
import hashlib, pathlib, sys
digest = hashlib.sha256(f"python={sys.version_info[:2]}\n".encode())
for name in sys.argv[1:]:
    path = pathlib.Path(name)
    digest.update(str(path.as_posix()).encode())
    digest.update(b"\0")
    digest.update(path.read_bytes())
print(digest.hexdigest())
' "$@"
}

ensure_python_env() {
  local base_python="$1" label="$2" configured_dir="$3" probe="$4"
  shift 4
  local directory python stamp expected current
  directory="$(venv_dir "$configured_dir")"
  python="$(venv_py "$directory")"
  stamp="$directory/.ciis-requirements.sha256"
  expected="$(requirements_digest "$base_python" "$@")"
  current="$(test -f "$stamp" && tr -d '\r\n' < "$stamp" || true)"

  if [ -x "$python" ] && py_ok "$python" \
     && "$python" -c "$probe" >/dev/null 2>&1 \
     && [ "$current" = "$expected" ]; then
    ok "$label environment ready ($directory)"
    return 0
  fi

  if [ ! -x "$python" ] || ! py_ok "$python"; then
    log "Creating or repairing $label environment: $directory"
    if [ -d "$directory" ]; then
      "$base_python" -m venv --clear "$directory" \
        || die "Could not repair the $label environment at $directory."
    else
      "$base_python" -m venv "$directory" \
        || die "Could not create the $label environment at $directory."
    fi
    python="$(venv_py "$directory")"
  else
    log "$label requirements changed or the installation is incomplete."
  fi

  "$python" -m pip install -q --upgrade pip setuptools wheel
  local install_args=() requirement
  for requirement in "$@"; do install_args+=( -r "$requirement" ); done
  "$python" -m pip install "${install_args[@]}" \
    || die "Installing $label dependencies failed (see the pip output above)."
  "$python" -c "$probe" >/dev/null 2>&1 \
    || die "$label dependencies installed, but the environment validation failed."
  printf '%s\n' "$expected" > "$stamp"
  ok "$label environment installed ($directory)"
}

ensure_frontend() {
  local base_python="$1" npm_bin="$2"
  local stamp="ciis_frontend/node_modules/.ciis-package-lock.sha256"
  local expected current
  expected="$(requirements_digest "$base_python" \
    ciis_frontend/package.json ciis_frontend/package-lock.json)"
  current="$(test -f "$stamp" && tr -d '\r\n' < "$stamp" || true)"
  if [ -d ciis_frontend/node_modules/vite ] && [ "$current" = "$expected" ]; then
    ok "frontend dependencies ready"
    return 0
  fi

  log "Installing frontend dependencies"
  (
    cd ciis_frontend
    "$npm_bin" ci
  ) || die "Installing frontend dependencies failed. Check the network and that package-lock.json matches package.json."
  mkdir -p ciis_frontend/node_modules
  printf '%s\n' "$expected" > "$stamp"
  ok "frontend dependencies installed"
}

setup() {
  local PY; PY="$(require_python)"
  local NPM; NPM="$(require_node)"
  require_supported_platform
  log "Using Python: $PY ($("$PY" --version 2>&1))"
  log "Using npm:    $NPM (node $(node --version 2>/dev/null || echo '?'))"
  echo
  warn "First-time setup downloads several large OCR, RAG and ML packages."
  hint "Later runs use requirement fingerprints and skip environments that are ready."
  echo

  log "Checking platform environment: OCR + API + correlation + timeline/report"
  ensure_python_env "$PY" "platform" "$PLATFORM_VENV" \
    'import importlib.util,sys; names=("django","rest_framework","paddleocr","paddle","cv2","fitz","networkx","reportlab"); sys.exit(0 if all(importlib.util.find_spec(n) for n in names) else 1)' \
    evidence_ocr_engine/requirements.txt \
    evidence_correlation_engine/requirements.txt \
    timeline_report_engine/requirements.txt \
    ciis_api/requirements.txt \
    || die "Preparing the platform environment failed."

  if [ -n "${CIIS_SKIP_RAG_VENV:-}" ]; then
    warn "Skipping the RAG environment (CIIS_SKIP_RAG_VENV set)."
    unset CIIS_RAG_PYTHON
  elif [ -n "${CIIS_RAG_PYTHON:-}" ] && configure_rag_runtime; then
    ok "external RAG environment ready ($CIIS_RAG_PYTHON)"
  else
    unset CIIS_RAG_PYTHON
    log "Checking standalone RAG environment"
    ensure_python_env "$PY" "RAG" "$RAG_VENV" \
      'import importlib.util,sys; names=("chromadb","sentence_transformers","pytest"); sys.exit(0 if all(importlib.util.find_spec(n) for n in names) else 1)' \
      rag_assistant_engine/requirements.txt \
      rag_assistant_engine/requirements-dev.txt \
      || die "Preparing the RAG environment failed."
    configure_rag_runtime \
      || die "The managed RAG environment was installed but could not be selected."
  fi

  if [ -n "${CIIS_SKIP_THREAT_VENV:-}" ]; then
    warn "Skipping the threat venv (CIIS_SKIP_THREAT_VENV set). './dev.sh threat' will not work."
  else
    log "Checking threat-intelligence environment (separate NumPy major)"
    ensure_python_env "$PY" "threat intelligence" "$THREAT_VENV" \
      'import importlib.util,sys; names=("numpy","pandas","sklearn","xgboost","lightgbm","tldextract"); sys.exit(0 if all(importlib.util.find_spec(n) for n in names) else 1)' \
      threat_intelligence_system/requirements.txt \
      || die "Preparing the threat-intelligence environment failed."
  fi

  ensure_frontend "$PY" "$NPM"

  log "Checking platform database"
  reset_db

  echo
  ok "All required environments are ready. No manual activation is needed."
}

# --------------------------------------------------------------------- db / run
reset_db() {
  # The platform database was removed (config.settings has DATABASES = {}):
  # there are no migrations and no seed_demo command any more, and case data
  # lives in evidence_ocr_engine/storage/ instead. Inspect the actual Django
  # setting rather than the migrations directory: Python may create that
  # directory solely for __pycache__, which does not mean a database exists.
  local ppy; ppy="$(venv_py "$(venv_dir "$PLATFORM_VENV")")"
  local has_database
  has_database="$(
    cd ciis_api
    "$ppy" -c \
      'from config import settings; print("yes" if settings.DATABASES else "no")'
  )"
  if [ "$has_database" != "yes" ]; then
    log "No platform database in this build - nothing to migrate or seed."
    hint "Case data lives in evidence_ocr_engine/storage/ and is managed from the app's admin screen."
    return 0
  fi
  ( cd ciis_api \
      && "$ppy" manage.py migrate \
      && "$ppy" manage.py seed_demo )
}

api() {
  local ppy; ppy="$(venv_py "$(venv_dir "$PLATFORM_VENV")")"
  [ -x "$ppy" ] || die "Platform venv missing. Run ./dev.sh setup first."
  configure_rag_runtime || true
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
  local tpy; tpy="$(venv_py "$(venv_dir "$THREAT_VENV")")"
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
  local ppy; ppy="$(venv_py "$(venv_dir "$PLATFORM_VENV")")"
  if [ -x "$ppy" ]; then
    log "API tests (pytest)"
    ( cd ciis_api && "$ppy" -m pytest -q ) || failed=1
    log "OCR engine tests (pytest)"
    ( cd evidence_ocr_engine && "$ppy" -m pytest -q ) || failed=1
    log "correlation engine tests (pytest)"
    ( cd evidence_correlation_engine && "$ppy" -m pytest -q ) || failed=1
    log "timeline & report engine tests (pytest)"
    ( cd timeline_report_engine && "$ppy" -m pytest -q ) || failed=1
    local rpy=""
    if configure_rag_runtime; then rpy="$CIIS_RAG_PYTHON"; fi
    if [ -n "$rpy" ] && [ -x "$rpy" ]; then
      log "RAG assistant engine tests (pytest; no model download)"
      ( cd rag_assistant_engine && "$rpy" -m pytest -q ) || failed=1
    else
      warn "Skipping RAG tests - managed RAG environment is unavailable."
    fi
  else
    warn "Skipping Python tests - run ./dev.sh setup first."
  fi
  [ "$failed" -eq 0 ] || die "Some tests failed (see the output above)."
  ok "All test suites passed."
}

up() {
  # Always run the idempotent bootstrap. Ready environments are fingerprinted
  # and skipped, while missing/broken/changed ones are repaired before launch.
  setup
  echo
  prepare_ollama
  echo

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
    if [ -n "$OLLAMA_PID" ]; then kill "$OLLAMA_PID" 2>/dev/null || true; fi
    wait "$api_pid" "$web_pid" 2>/dev/null || true
    if [ -n "$OLLAMA_PID" ]; then wait "$OLLAMA_PID" 2>/dev/null || true; fi
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
  local ppy; ppy="$(venv_py "$(venv_dir "$PLATFORM_VENV")")"
  local tpy; tpy="$(venv_py "$(venv_dir "$THREAT_VENV")")"
  local problems=0

  echo "${C_BLD}CIIS doctor${C_OFF}"
  echo "  repo root        : $ROOT"
  echo "  platform         : $OS ($(uname -s 2>/dev/null || echo unknown))"

  if [ -n "$PY" ]; then
    ok "python 3.12      : $PY ($("$PY" --version 2>&1))"
  else
    warn "python 3.12      : NOT FOUND"; install_hint_python; problems=$((problems + 1))
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

  if configure_rag_runtime; then
    ok "RAG assistant    : ready ($CIIS_RAG_PYTHON)"
  else
    echo "  RAG assistant    : unavailable (optional; set CIIS_RAG_PYTHON to its Python 3.12 executable)"
  fi

  if [ -d ciis_frontend/node_modules/vite ]; then ok "frontend deps    : ready"
  else warn "frontend deps    : MISSING - run ./dev.sh setup"; problems=$((problems + 1)); fi

  echo "  platform DB      : $([ -d ciis_api/api/migrations ] \
      && echo "$([ -f ciis_api/ciis_platform.sqlite3 ] && echo present || echo MISSING)" \
      || echo "n/a (no database in this build)")"
  echo "  API port         : $CIIS_API_PORT $(port_busy "$CIIS_API_PORT" && echo '(BUSY - will be auto-bumped)' || echo '(free)')"
  echo "  web port         : $WEB_PORT $(port_busy "$WEB_PORT" && echo '(BUSY - will be auto-bumped)' || echo '(free)')"
  echo "  full pipeline    : CIIS_RUN_FULL_PIPELINE=$CIIS_RUN_FULL_PIPELINE"
  # The API defaults this to 1 (ciis_api/config/settings.py). Printing 0 as the
  # default told the operator the opposite of what the running system does.
  echo "  ML threat intel  : CIIS_ML_THREAT_INTEL=${CIIS_ML_THREAT_INTEL:-1}\
 $([ "${CIIS_ML_THREAT_INTEL:-1}" = "1" ] \
   && echo '(enabled; needs a venv with the ML stack, else falls back)' \
   || echo '(disabled)')"
  # Semantic correction uses xlm-roberta-base when transformers is importable,
  # otherwise a dictionary heuristic. Both are valid; which one ran is recorded
  # on every piece of evidence, so the operator should know which to expect.
  local ppy_probe; ppy_probe="$(venv_py "$(venv_dir "$PLATFORM_VENV")")"
  if [ -x "$ppy_probe" ]; then
    if "$ppy_probe" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('transformers') else 1)" 2>/dev/null; then
      echo "  semantic validator: xlm-roberta-base (transformers installed)"
    else
      echo "  semantic validator: heuristic (transformers not installed - optional)"
    fi
  fi
  echo

  if [ "$problems" -eq 0 ]; then ok "Everything looks good. Run: ./dev.sh"
  else warn "$problems thing(s) need attention - see the hints above."; fi
}

clean() {
  log "Removing repo-local environments and ciis_frontend/node_modules"
  rm -rf "$PLATFORM_VENV" "$THREAT_VENV" ciis_frontend/node_modules
  local rag_directory; rag_directory="$(venv_dir "$RAG_VENV")"
  case "$rag_directory" in
    "$ROOT"/*) rm -rf "$rag_directory" ;;
    *) hint "Retained external RAG environment: $rag_directory" ;;
  esac
  ok "Clean. The next ./dev.sh will rebuild everything from scratch."
}

# Print the header comment block verbatim, so the help text and the file's own
# documentation can never drift apart.
usage() {
  awk 'NR == 1 { next }
       /^#/     { sub(/^# ?/, ""); print; next }
       { exit }' "${BASH_SOURCE[0]}"
}

main() {
  case "${1:-up}" in
    setup)          setup ;;
    api)            api ;;
    web)            web ;;
    up)             up ;;
    threat)         shift; threat "$@" ;;
    test|tests)     run_tests ;;
    reset-db)       reset_db ;;
    doctor)         doctor ;;
    clean)          clean ;;
    help|-h|--help) usage ;;
    *) echo "usage: $0 {up|setup|api|web|threat|test|reset-db|doctor|clean|help}" >&2; return 1 ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
