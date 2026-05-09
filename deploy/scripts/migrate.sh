#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/sqlmon}"
BACKEND_DIR="${BACKEND_DIR:-${APP_HOME}/backend}"
VENV_DIR="${VENV_DIR:-${APP_HOME}/venv}"

cd "${BACKEND_DIR}"

exec "${VENV_DIR}/bin/alembic" upgrade head
