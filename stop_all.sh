#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"

stop_pid_file() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"

  if [ ! -f "$pid_file" ]; then
    printf '%s pid file not found.\n' "$name"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"

  if kill -0 "$pid" >/dev/null 2>&1; then
    printf 'Stopping %s process: %s\n' "$name" "$pid"
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  else
    printf '%s process is not running.\n' "$name"
  fi

  rm -f "$pid_file"
}

stop_port() {
  local port="$1"

  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi

  local pids
  pids="$(lsof -ti "tcp:$port" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    return
  fi

  printf 'Cleaning port %s processes: %s\n' "$port" "$pids"
  for pid in $pids; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}

printf '\n========================================\n'
printf 'Stopping Agent for Exam\n'
printf '========================================\n\n'

stop_pid_file "backend"
stop_pid_file "frontend"
stop_port "8000"
stop_port "5173"

printf '\nStopped.\n'
