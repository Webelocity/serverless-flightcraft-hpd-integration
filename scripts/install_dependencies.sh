#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/flitecraft-HPD-Integration"
VENV_DIR="$APP_DIR/venv"

echo "[InstallDeps] Starting dependency installation..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "[InstallDeps] python3 not found. Installing..."
    if command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y python3 python3-venv python3-pip curl
    elif command -v yum >/dev/null 2>&1; then
        yum install -y python3 python3-pip curl
        # Some distros ship venv module separately; ensure it's present
        python3 -m ensurepip || true
    else
        echo "[InstallDeps] Unsupported package manager. Please install Python 3 manually." >&2
        exit 1
    fi
else
    echo "[InstallDeps] python3 found: $(python3 --version)"
fi

mkdir -p "$APP_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "[InstallDeps] Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools

REQ_FILE=""
if [[ -f "$APP_DIR/requirements.txt" ]]; then
    REQ_FILE="$APP_DIR/requirements.txt"
elif [[ -f "$APP_DIR/requirments.txt" ]]; then
    REQ_FILE="$APP_DIR/requirments.txt"
fi

if [[ -n "$REQ_FILE" ]]; then
    echo "[InstallDeps] Installing Python dependencies from $(basename "$REQ_FILE")"
    pip install -r "$REQ_FILE"
else
    echo "[InstallDeps] No requirements file found; skipping pip install"
fi

mkdir -p /var/log/flitecraft-hpd
chown -R root:root "$APP_DIR"
chmod -R a+rX "$APP_DIR"

echo "[InstallDeps] Completed."


