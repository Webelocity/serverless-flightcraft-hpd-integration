#!/usr/bin/env bash
set -euo pipefail

APP_NAME="flitecraft-hpd"

echo "[Stop] Stopping service ${APP_NAME} if running..."
if systemctl list-units --full -all | grep -q "${APP_NAME}.service"; then
    systemctl stop ${APP_NAME}.service || true
else
    echo "[Stop] Service ${APP_NAME} not installed; skipping stop"
fi

echo "[Stop] Done."


