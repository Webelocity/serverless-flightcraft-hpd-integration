#!/usr/bin/env bash
set -euo pipefail

APP_NAME="flitecraft-hpd"
APP_DIR="/opt/flitecraft-HPD-Integration"
VENV_DIR="$APP_DIR/venv"
USER_TO_RUN="root"

SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

echo "[Service] Installing systemd service $APP_NAME ..."

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=HPD Pricing Scheduler (FastAPI)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${USER_TO_RUN}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=DISABLE_INTERNAL_SCHEDULER=false
EnvironmentFile=-/etc/sysconfig/${APP_NAME}
ExecStart=${VENV_DIR}/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/var/log/flitecraft-hpd/app.log
StandardError=append:/var/log/flitecraft-hpd/app.err.log

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable ${APP_NAME}.service

echo "[Service] Installed and enabled ${APP_NAME}.service"


