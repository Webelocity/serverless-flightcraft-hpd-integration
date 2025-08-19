#!/usr/bin/env bash
set -euo pipefail

APP_NAME="flitecraft-hpd"

echo "[Start] Starting service ${APP_NAME} ..."
systemctl start ${APP_NAME}.service
systemctl status ${APP_NAME}.service --no-pager -l || true

echo "[Start] Done."


