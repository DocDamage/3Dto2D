"""SpriteForge application package.

The desktop tools and tests import modules both as top-level files from this
directory and as ``app.*`` package modules. Keep the app directory importable
for the legacy top-level module style when the package form is used first.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
APP_DIR_STR = str(APP_DIR)

if APP_DIR_STR not in sys.path:
    sys.path.insert(0, APP_DIR_STR)
