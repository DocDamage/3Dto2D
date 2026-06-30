#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/app"

PYTHON_BIN=${PYTHON:-python3}
exec "$PYTHON_BIN" spriteforge_launcher.py --wizard
