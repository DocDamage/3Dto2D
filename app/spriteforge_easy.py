#!/usr/bin/env python3
"""
SpriteForge Easy Mode GUI.

This is a thin, user-friendly launcher over spriteforge_unified.py and spriteforge.py.
It avoids requiring the user to type CLI commands for normal use.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
EASY_CONFIG_PATH = ROOT / "config" / "easy_mode.json"
PRESETS_PATH = ROOT / "config" / "easy_presets.json"
VIDEO_EXTS = ("*.mp4", "*.webm", "*.mov", "*.mkv", "*.avi", "*.m4v")
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
DROP_VIDEOS_DIR = ROOT / "01_DROP_VIDEOS_HERE"
IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")

# ── Extracted services ──────────────────────────────────
from services.easy_command_runner import CommandRunner
from services.easy_helpers import (
    python_preference, resolve_root_path, open_path,
    is_comfy_running, short_path, find_recent_sprite_outputs,
    nvidia_summary, pycmd,
)
from services.easy_actions_mixin import EasyActionsMixin
from services.easy_ui_mixin import EasyUiMixin
from services.easy_ui_tabs_mixin import EasyUiTabsMixin
from spriteforge_utils import load_json, save_json, get_app_version, apply_dark_theme
from spriteforge_utils import PYTHON


class EasyApp(EasyUiMixin, EasyUiTabsMixin, EasyActionsMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        DROP_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        version = get_app_version()
        self.title(f"SpriteForge Studio {version} - Easy Mode")
        self.geometry("1180x780")
        self.minsize(980, 680)

        # Apply dark theme
        apply_dark_theme(self)

        self.cfg = load_json(CONFIG_PATH, {})
        self.presets = load_json(PRESETS_PATH, {})
        self.easy = load_json(EASY_CONFIG_PATH, {})
        self.runner = CommandRunner(self)
        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.selected_sprite_dir: Optional[Path] = None

        self.vars: Dict[str, tk.Variable] = {}
        self._build_ui()
        self.after(100, self._pump_log)
        self.after(250, self.refresh_status)
        self.after(300, self.refresh_outputs)

        if "--smoke-test" in sys.argv:
            print("SpriteForge Easy Mode smoke test OK")
            self.destroy()

    # ---------- UI helpers ----------
    def v(self, name: str, default: str = "") -> tk.StringVar:
        value = str(self.easy.get(name, default))
        var = tk.StringVar(value=value)
        self.vars[name] = var
        return var

    def boolv(self, name: str, default: bool = False) -> tk.BooleanVar:
        value = bool(self.easy.get(name, default))
        var = tk.BooleanVar(value=value)
        self.vars[name] = var
        return var

    def save_easy_settings(self) -> None:
        data = load_json(EASY_CONFIG_PATH, {})
        for k, var in self.vars.items():
            try:
                data[k] = var.get()
            except Exception:
                pass
        save_json(EASY_CONFIG_PATH, data)
        self.easy = data



def main() -> int:
    if "--smoke-test" in sys.argv:
        print("SpriteForge Easy Mode smoke test OK")
        return 0
    app = EasyApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
