#!/usr/bin/env bash
set -euo pipefail

DIR="/opt/flitecraft-HPD-Integration/scripts"

"$DIR/stop_server.sh" || true
"$DIR/install_dependencies.sh"
"$DIR/install_service.sh"
"$DIR/start_server.sh"
"$DIR/validate_service.sh"

echo "[Reinstall] Completed."


