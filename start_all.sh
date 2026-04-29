#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
PID_DIR="$ROOT_DIR/.pids"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="5173"
AFE_RELOAD="${AFE_RELOAD:-0}"
OPENED_TERMINAL_WINDOWS=0

mkdir -p "$LOG_DIR" "$PID_DIR"

print_header() {
  printf '\n========================================\n'
  printf 'Starting Agent for Exam\n'
  printf '========================================\n\n'
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

is_port_in_use() {
  local port="$1"
  if command_exists lsof; then
    lsof -ti "tcp:$port" >/dev/null 2>&1
  else
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-30}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf '%s is ready: %s\n' "$name" "$url"
      return 0
    fi
    sleep 1
  done

  printf 'Timed out waiting for %s: %s\n' "$name" "$url" >&2
  return 1
}

shell_join() {
  local joined=""
  local arg
  for arg in "$@"; do
    printf -v joined '%s %q' "$joined" "$arg"
  done
  printf '%s' "${joined# }"
}

escape_applescript_string() {
  sed 's/\\/\\\\/g; s/"/\\"/g'
}

run_in_terminal() {
  local command="$1"
  local escaped
  escaped="$(printf '%s' "$command" | escape_applescript_string)"
  osascript -e "tell application \"Terminal\" to do script \"$escaped\""
  OPENED_TERMINAL_WINDOWS=1
}

ensure_backend_env() {
  if ! command_exists python3; then
    printf 'python3 was not found. Please install Python 3.10 or newer, then rerun this script.\n' >&2
    exit 1
  fi

  if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    printf 'Python 3.10 or newer is required. Current version: ' >&2
    python3 --version >&2
    printf 'Install a newer Python from https://www.python.org/downloads/macos/ or with Homebrew: brew install python\n' >&2
    exit 1
  fi

  if [ ! -x "$BACKEND_DIR/venv/bin/python" ]; then
    printf 'Creating backend virtual environment...\n'
    python3 -m venv "$BACKEND_DIR/venv"
  fi

  if ! "$BACKEND_DIR/venv/bin/python" -c "import fastapi, uvicorn, markdown, playwright" >/dev/null 2>&1; then
    printf 'Installing backend dependencies...\n'
    "$BACKEND_DIR/venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
  fi

  printf 'Ensuring Playwright Chromium is installed...\n'
  "$BACKEND_DIR/venv/bin/python" -m playwright install chromium >/dev/null 2>&1 || {
    printf 'Playwright Chromium install failed. Try rerunning with a stable network, or run manually:\n' >&2
    printf '  cd %s && source venv/bin/activate && python -m playwright install chromium\n' "$BACKEND_DIR" >&2
    exit 1
  }
}

ensure_frontend_env() {
  if ! command_exists npm; then
    printf 'npm was not found. Please install Node.js with npm, then rerun this script.\n' >&2
    exit 1
  fi

  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    printf 'Installing frontend dependencies...\n'
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

start_backend() {
  if is_port_in_use "$BACKEND_PORT"; then
    printf 'Backend port %s is already in use. Skipping backend start.\n' "$BACKEND_PORT"
    return
  fi

  printf 'Starting backend server...\n'
  (
    cd "$BACKEND_DIR"
    backend_args=(app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT")
    if [ "$AFE_RELOAD" = "1" ]; then
      backend_args=(app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT")
    fi

    nohup venv/bin/python -m uvicorn "${backend_args[@]}" > "$LOG_DIR/backend.log" 2>&1 &
    backend_pid=$!
    echo "$backend_pid" > "$PID_DIR/backend.pid"
    disown "$backend_pid" 2>/dev/null || true
  )
}

start_frontend() {
  if is_port_in_use "$FRONTEND_PORT"; then
    printf 'Frontend port %s is already in use. Skipping frontend start.\n' "$FRONTEND_PORT"
    return
  fi

  printf 'Starting frontend server...\n'
  (
    cd "$FRONTEND_DIR"
    nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
      > "$LOG_DIR/frontend.log" 2>&1 &
    frontend_pid=$!
    echo "$frontend_pid" > "$PID_DIR/frontend.pid"
    disown "$frontend_pid" 2>/dev/null || true
  )
}

start_backend_terminal() {
  if is_port_in_use "$BACKEND_PORT"; then
    printf 'Backend port %s is already in use. Skipping backend start.\n' "$BACKEND_PORT"
    return
  fi

  printf 'Opening backend terminal window...\n'
  backend_args=(python -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT")
  if [ "$AFE_RELOAD" = "1" ]; then
    backend_args=(python -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT")
  fi

  run_in_terminal "cd $(shell_join "$BACKEND_DIR") && source venv/bin/activate && $(shell_join "${backend_args[@]}")"
}

start_frontend_terminal() {
  if is_port_in_use "$FRONTEND_PORT"; then
    printf 'Frontend port %s is already in use. Skipping frontend start.\n' "$FRONTEND_PORT"
    return
  fi

  printf 'Opening frontend terminal window...\n'
  frontend_args=(npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT")
  run_in_terminal "cd $(shell_join "$FRONTEND_DIR") && $(shell_join "${frontend_args[@]}")"
}

start_terminal_services() {
  start_backend_terminal
  start_frontend_terminal
}

should_open_terminal() {
  [ "$(uname -s)" = "Darwin" ] && command_exists osascript
}

print_header
ensure_backend_env
ensure_frontend_env

if should_open_terminal; then
  start_terminal_services
else
  start_backend
  start_frontend
fi

wait_for_url "http://$BACKEND_HOST:$BACKEND_PORT/health" "Backend"
wait_for_url "http://$FRONTEND_HOST:$FRONTEND_PORT/" "Frontend"

printf '\n========================================\n'
printf 'Startup completed!\n'
printf '========================================\n\n'
printf 'Backend server:  http://localhost:%s\n' "$BACKEND_PORT"
printf 'Frontend server: http://localhost:%s\n' "$FRONTEND_PORT"
printf 'API docs:        http://localhost:%s/docs\n' "$BACKEND_PORT"
printf '\n'
if [ "$OPENED_TERMINAL_WINDOWS" = "1" ]; then
  printf 'Logs are shown in the opened Terminal windows.\n'
else
  printf 'Logs:\n'
  printf '%s\n' "- $LOG_DIR/backend.log"
  printf '%s\n' "- $LOG_DIR/frontend.log"
fi
printf '\n'
printf 'Stop services with: ./stop_all.sh\n'
