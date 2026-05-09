#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/sqlmon}"
BACKEND_DIR="${BACKEND_DIR:-${APP_HOME}/backend}"
VENV_DIR="${VENV_DIR:-${APP_HOME}/venv}"
SQLMON_API_HOST="${SQLMON_API_HOST:-127.0.0.1}"
SQLMON_API_PORT="${SQLMON_API_PORT:-8000}"

cd "${BACKEND_DIR}"

exec "${VENV_DIR}/bin/uvicorn" app.main:app \
  --host "${SQLMON_API_HOST}" \
  --port "${SQLMON_API_PORT}"
