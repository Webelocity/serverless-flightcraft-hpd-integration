#!/usr/bin/env bash
set -euo pipefail

APP_NAME="flitecraft-hpd"
HEALTH_URL="http://127.0.0.1:8000/health"

echo "[Validate] Checking service ${APP_NAME} status and health..."

systemctl is-active --quiet ${APP_NAME}.service

# Try curl, fallback to python if curl missing
if command -v curl >/dev/null 2>&1; then
    for i in {1..30}; do
        if curl -fsS "$HEALTH_URL" | grep -q '"status"\s*:\s*"ok"'; then
            echo "[Validate] Health check passed."
            exit 0
        fi
        echo "[Validate] Waiting for health... ($i)"
        sleep 2
    done
else
    for i in {1..30}; do
        if python3 - <<'PY'
import json, sys
from urllib.request import urlopen
try:
    data = json.load(urlopen("http://127.0.0.1:8000/health"))
    ok = data.get("status") == "ok"
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
        then
            echo "[Validate] Health check passed."
            exit 0
        fi
        echo "[Validate] Waiting for health... ($i)"
        sleep 2
    done
fi

echo "[Validate] Health check failed." >&2
journalctl -u ${APP_NAME}.service -n 200 --no-pager || true
exit 1


