#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$ROOT_DIR/.venv"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

PORT="${PORT:-8002}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  LOCAL_PYTHON="${MOVIS_PYTHON:-}"
  if [ -z "$LOCAL_PYTHON" ]; then
    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
        LOCAL_PYTHON="$candidate"
        break
      fi
    done
  fi
  if [ -z "$LOCAL_PYTHON" ]; then
    printf '%s\n' 'GoonToThis requires Python 3.10 or newer. Set MOVIS_PYTHON to a compatible executable.' >&2
    exit 1
  fi
  "$LOCAL_PYTHON" -m venv "$VENV_DIR"
elif ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  printf '%s\n' 'The existing .venv uses Python older than 3.10. Recreate it with ./run-local.sh after moving or removing .venv.' >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

printf '\nGoonToThis local test server:\n'
printf '  http://127.0.0.1:%s\n\n' "$PORT"

cd "$ROOT_DIR"
PORT="$PORT" "$VENV_DIR/bin/python" app.py
