#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$ROOT_DIR/.venv"
PORT="${PORT:-8002}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

printf '\nGoonToThis local test server:\n'
printf '  http://127.0.0.1:%s\n\n' "$PORT"

cd "$ROOT_DIR"
PORT="$PORT" "$VENV_DIR/bin/python" app.py
