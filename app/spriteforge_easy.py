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
import urllib.request
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


from spriteforge_utils import load_json, save_json, app_python, PYTHON, get_app_version, apply_dark_theme

def python_preference() -> str:
    try:
        value = (ROOT / ".python_version").read_text(encoding="utf-8").strip()
        return value or "3.12"
    except Exception:
        return "3.12"


def resolve_root_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def open_path(path: Path) -> None:
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True) if not path.suffix else None
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def is_comfy_running(host: str = "127.0.0.1", port: int = 8188, timeout: float = 0.75) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/system_stats", timeout=timeout) as r:
            return 200 <= getattr(r, "status", 200) < 500
    except Exception:
        return False


def short_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def find_recent_sprite_outputs(limit: int = 25) -> List[Path]:
    out = ROOT / "output"
    if not out.exists():
        return []
    candidates: List[Path] = []
    for p in out.rglob("sheet.json"):
        if p.is_file():
            candidates.append(p.parent)
    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return candidates[:limit]


class CommandRunner:
    def __init__(self, app: "EasyApp"):
        self.app = app
        self.current_proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()

    def busy(self) -> bool:
        with self.lock:
            return self.current_proc is not None

    def run(self, title: str, cmd: Sequence[str], on_done: Optional[Callable[[int], None]] = None) -> None:
        self.run_sequence(title, [(title, list(cmd), True)], on_done=on_done)

    def run_sequence(self, title: str, steps: Sequence[Tuple[str, Sequence[str], bool]], on_done: Optional[Callable[[int], None]] = None) -> None:
        if self.busy():
            # If the runner is busy, offer to enqueue the jobs
            ans = messagebox.askyesno(
                "SpriteForge is busy",
                f"A task is already running.\n\nWould you like to queue '{title}' to run later?"
            )
            if ans:
                for step_title, cmd, _ in steps:
                    action = "custom"
                    direction = "none"
                    for i, arg in enumerate(cmd):
                        if arg == "--action" and i+1 < len(cmd):
                            action = cmd[i+1]
                        elif arg == "--direction" and i+1 < len(cmd):
                            direction = cmd[i+1]
                    self.app.enqueue_job(step_title, list(cmd), action=action, direction=direction)
            return

        # Reset progress bar
        self.app.progress_bar["value"] = 0
        self.app.progress_bar["maximum"] = 100

        def worker():
            final_code = 0
            self.app.log(f"\n=== {title} ===\n")
            for step_title, cmd, stop_on_fail in steps:
                self.app.set_busy(True, step_title)
                self.app.log(f"\n--- {step_title} ---\n")
                self.app.log("Command: " + subprocess.list2cmdline(list(cmd)) + "\n")
                
                # Check if dropped video file argument is missing (deleted mid-run)
                missing_arg = False
                for arg in cmd:
                    if "01_DROP_VIDEOS_HERE" in str(arg):
                        p = Path(arg)
                        if not p.exists():
                            missing_arg = True
                            self.app.log(f"ERROR: Dropped video file not found: {p}\n")
                            rc = 1
                            break
                
                if missing_arg:
                    final_code = rc
                    self.app.log(f"Step failed (missing file): {step_title}\n")
                    if stop_on_fail:
                        break
                    continue

                try:
                    proc = subprocess.Popen(
                        list(cmd),
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                    )
                    with self.lock:
                        self.current_proc = proc
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        self.app.log(line)
                    rc = proc.wait()
                except Exception as exc:
                    rc = 1
                    self.app.log(f"ERROR: {exc}\n")
                finally:
                    with self.lock:
                        self.current_proc = None
                final_code = rc
                if rc != 0:
                    self.app.log(f"Step failed with exit code {rc}: {step_title}\n")
                    if stop_on_fail:
                        break
                else:
                    self.app.log(f"Finished: {step_title}\n")
            
            self.app.after(0, lambda: self.app.set_busy(False, "Ready"))
            if on_done:
                self.app.after(0, lambda: on_done(final_code))
            self.app.after(0, self.app.refresh_status)
            self.app.after(0, self.app.refresh_outputs)

        threading.Thread(target=worker, daemon=True).start()

    def terminate(self) -> None:
        with self.lock:
            proc = self.current_proc
        if proc is None:
            return
        try:
            proc.terminate()
            self.app.log("\nStop requested. The current process was asked to terminate.\n")
        except Exception as exc:
            self.app.log(f"\nCould not terminate process: {exc}\n")


class EasyApp(tk.Tk):
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

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = ttk.Frame(self, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="SpriteForge Studio", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Easy Mode: ComfyUI + WAN + sprite sheets", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w")
        
        # Right aligned frame for status and progress bar
        right_header = ttk.Frame(header)
        right_header.grid(row=0, column=1, rowspan=2, sticky="e")
        self.busy_label = ttk.Label(right_header, text="Ready", anchor="e")
        self.busy_label.pack(side="top", anchor="e")
        self.progress_bar = ttk.Progressbar(right_header, orient="horizontal", mode="determinate", length=200)
        self.progress_bar.pack(side="top", fill="x", pady=(4, 0))

        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        self.notebook = ttk.Notebook(paned)
        paned.add(self.notebook, weight=4)

        log_frame = ttk.LabelFrame(paned, text="Activity Log")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = ScrolledText(log_frame, height=12, wrap="word", bg="#121212", fg="#e0e0e0", insertbackground="#e0e0e0", bd=0, highlightthickness=1, highlightbackground="#3a3a3a", highlightcolor="#00adb5")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        controls = ttk.Frame(log_frame)
        controls.grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(controls, text="Stop Current Task", command=self.runner.terminate).pack(side="left")
        ttk.Button(controls, text="Clear Log", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side="left", padx=6)
        ttk.Button(controls, text="Open Outputs", command=lambda: open_path(ROOT / "output")).pack(side="left", padx=6)
        paned.add(log_frame, weight=2)

        self._home_tab()
        self._setup_tab()
        self._make_sprite_tab()
        self._convert_tab()
        self._qa_export_tab()
        self._project_tab()
        self._jobs_tab()
        self._advanced_tab()

    def section(self, parent, title: str, row: int, column: int = 0, columnspan: int = 1, sticky: str = "nsew"):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.grid(row=row, column=column, columnspan=columnspan, sticky=sticky, padx=8, pady=8)
        return frame

    def make_text_row(self, parent, label: str, var: tk.StringVar, row: int, width: int = 70, browse: Optional[Callable[[], None]] = None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        if browse:
            ttk.Button(parent, text="Browse", command=browse).grid(row=row, column=2, sticky="e", padx=(6, 0))
        parent.columnconfigure(1, weight=1)
        return entry

    # ---------- Tabs ----------
    def _home_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        self.notebook.add(tab, text="Home")

        quick = self.section(tab, "Normal user path", 0, 0, 2, "ew")
        ttk.Label(quick, text="Use these buttons from left to right. The first full setup downloads large model files.").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        ttk.Button(quick, text="1. Set Up Everything", command=self.setup_everything).grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(quick, text="2. Run Health Check", command=self.run_doctor).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(quick, text="3. Make Sprite", command=lambda: self.notebook.select(self.make_sprite_tab_ref)).grid(row=1, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(quick, text="Convert Existing Video", command=lambda: self.notebook.select(self.convert_tab_ref)).grid(row=1, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(quick, text="QA / Export", command=lambda: self.notebook.select(self.qa_tab_ref)).grid(row=1, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(quick, text="Open Outputs", command=lambda: open_path(ROOT / "output")).grid(row=1, column=5, sticky="ew", padx=4, pady=4)
        for i in range(6):
            quick.columnconfigure(i, weight=1)

        status = self.section(tab, "Status", 1, 0)
        status.rowconfigure(1, weight=1)
        status.columnconfigure(0, weight=1)
        self.status_text = ScrolledText(status, height=16, wrap="word", bg="#121212", fg="#e0e0e0", insertbackground="#e0e0e0", bd=0, highlightthickness=1, highlightbackground="#3a3a3a", highlightcolor="#00adb5")
        self.status_text.grid(row=0, column=0, sticky="nsew")
        ttk.Button(status, text="Refresh Status", command=self.refresh_status).grid(row=1, column=0, sticky="w", pady=(8, 0))

        recent = self.section(tab, "Recent sprite outputs", 1, 1)
        recent.rowconfigure(0, weight=1)
        recent.columnconfigure(0, weight=1)
        
        self.recent_list = ttk.Treeview(recent, show="tree", selectmode="browse", height=13)
        self.recent_list.grid(row=0, column=0, sticky="nsew")
        self.recent_list.bind("<<TreeviewSelect>>", self._on_recent_select)
        
        sb = ttk.Scrollbar(recent, orient="vertical", command=self.recent_list.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.recent_list.configure(yscrollcommand=sb.set)
        
        btns = ttk.Frame(recent)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Open Selected", command=self.open_selected_output).pack(side="left")
        ttk.Button(btns, text="Refresh", command=self.refresh_outputs).pack(side="left", padx=6)

    def _setup_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.notebook.add(tab, text="Setup / Health")

        setup = self.section(tab, "Setup", 0, 0)
        ttk.Button(setup, text="Set Up Everything", command=self.setup_everything).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(setup, text="Install SpriteForge Only", command=self.install_spriteforge_only).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(setup, text="Install / Update ComfyUI + WAN Models", command=self.install_comfy_nodes).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(setup, text="Download WAN 2.1 1.3B Models", command=self.download_models).grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Button(setup, text="Create Desktop Shortcut", command=self.create_shortcut).grid(row=4, column=0, sticky="ew", pady=4)
        setup.columnconfigure(0, weight=1)

        health = self.section(tab, "Health / maintenance", 0, 1)
        ttk.Button(health, text="Run Health Check", command=self.run_doctor).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(health, text="Hardware Advisor", command=self.hardware_advisor).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(health, text="Launch ComfyUI", command=self.launch_comfy).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(health, text="Open ComfyUI Browser", command=self.open_comfy).grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Button(health, text="Safe Update", command=self.safe_update).grid(row=4, column=0, sticky="ew", pady=4)
        health.columnconfigure(0, weight=1)

        paths = self.section(tab, "Folders", 1, 0, 2, "ew")
        ttk.Button(paths, text="Open App Folder", command=lambda: open_path(ROOT)).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(paths, text="Open Input Folder", command=lambda: open_path(ROOT / "input")).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(paths, text="Open Output Folder", command=lambda: open_path(ROOT / "output")).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(paths, text="Open ComfyUI Folder", command=self.open_comfy_folder).grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        for i in range(4):
            paths.columnconfigure(i, weight=1)

    def _make_sprite_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        self.make_sprite_tab_ref = tab
        self.notebook.add(tab, text="Make Sprite")

        form = self.section(tab, "Generate a sprite from a text prompt", 0, 0, sticky="ew")
        self.character_var = self.v("character", "single full body original game hero, professional appealing character design, heroic adult proportions, distinctive outfit, clean silhouette")
        self.action_var = self.v("action", "idle")
        self.direction_var = self.v("direction", "front")
        self.style_var = self.v("style", "polished 2D game sprite, professional character design, crisp cel-shaded edges, readable silhouette")
        self.profile_var = self.v("profile", "wan22_5b_3060_best")
        self.extra_prompt_var = self.v("extra_prompt", "locked camera, no zoom, centered, plain bright green background")
        self.reference_image_var = self.v("reference_image", "")
        self.seed_var = self.v("seed", "-1")
        self.quality_check_var = self.boolv("quality_check", True)

        self.make_text_row(form, "Character", self.character_var, 0)
        ttk.Label(form, text="Action").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=self.action_var, values=list((self.presets.get("actions") or {}).keys()), state="readonly").grid(row=1, column=1, sticky="ew", pady=3)
        from spriteforge_prompts import DIRECTIONS
        ttk.Label(form, text="Direction").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=self.direction_var, values=list(DIRECTIONS.keys()), state="readonly").grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Profile").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=self.profile_var, values=self.presets.get("profiles", ["debug", "rtx3060_12gb"]), state="readonly").grid(row=3, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Style").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=self.style_var, values=self.presets.get("styles", []), state="normal").grid(row=4, column=1, sticky="ew", pady=3)
        self.make_text_row(form, "Extra prompt rules", self.extra_prompt_var, 5)
        self.make_text_row(form, "Reference image (optional / heavier)", self.reference_image_var, 6, browse=self.browse_reference_image)
        self.make_text_row(form, "Seed (-1 random)", self.seed_var, 7, width=20)
        ttk.Checkbutton(form, text="Run quality check after generation", variable=self.quality_check_var).grid(row=8, column=1, sticky="w", pady=6)
        ttk.Button(form, text="Generate Sprite", command=self.generate_sprite).grid(row=9, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(form, text="Build Prompt Only", command=self.build_prompt_only).grid(row=9, column=2, sticky="ew", padx=(6, 0), pady=(10, 0))

        tips = self.section(tab, "Recommended first test", 1, 0, sticky="ew")
        ttk.Label(tips, text="Start with profile=debug, action=idle, direction=front. After that works, use profile=rtx3060_12gb for real clips.").grid(row=0, column=0, sticky="w")
        ttk.Button(tips, text="Fill Safe First Test", command=self.fill_safe_test).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _convert_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        self.convert_tab_ref = tab
        self.notebook.add(tab, text="Convert Video")

        form = self.section(tab, "Convert an existing WAN / ComfyUI video into a spritesheet", 0, 0, sticky="ew")
        self.video_file_var = self.v("video_file", "")
        self.video_output_name_var = self.v("video_output_name", "")
        self.video_fps_var = self.v("video_fps", "12")
        self.cell_size_var = self.v("cell_size", "512x512")
        self.key_color_var = self.v("key_color", "auto")
        self.key_tolerance_var = self.v("key_tolerance", "45")
        self.make_text_row(form, "Video file", self.video_file_var, 0, browse=self.browse_video_file)
        self.make_text_row(form, "Output name (optional)", self.video_output_name_var, 1)
        self.make_text_row(form, "FPS", self.video_fps_var, 2, width=20)
        self.make_text_row(form, "Cell size", self.cell_size_var, 3, width=20)
        self.make_text_row(form, "Key color", self.key_color_var, 4, width=20)
        self.make_text_row(form, "Key tolerance", self.key_tolerance_var, 5, width=20)
        ttk.Button(form, text="Convert Video to Sprite", command=self.convert_video).grid(row=6, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(form, text="Inspect Video First", command=self.inspect_video).grid(row=6, column=2, sticky="ew", padx=(6, 0), pady=(10, 0))
        ttk.Button(form, text="Open Drop Folder", command=lambda: open_path(DROP_VIDEOS_DIR)).grid(row=7, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(form, text="Convert All Videos in Drop Folder", command=self.convert_drop_folder).grid(row=7, column=2, sticky="ew", padx=(6, 0), pady=(8, 0))

        note = self.section(tab, "Tip", 1, 0, sticky="ew")
        ttk.Label(note, text="Best results: generate the source video on a plain green/blue background with a locked camera and full-body character.").grid(row=0, column=0, sticky="w")

    def _qa_export_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.qa_tab_ref = tab
        self.notebook.add(tab, text="QA / Export")

        select = self.section(tab, "Select sprite output", 0, 0, 2, "ew")
        self.sprite_dir_var = self.v("sprite_dir", "")
        self.make_text_row(select, "Sprite folder", self.sprite_dir_var, 0, browse=self.browse_sprite_dir)
        ttk.Button(select, text="Use Most Recent Output", command=self.use_most_recent_output).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(select, text="Open Selected Folder", command=self.open_sprite_dir).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(8, 0))

        qa = self.section(tab, "Fix / quality", 1, 0)
        self.blend_loop_frames_var = self.v("blend_loop_frames", "3")
        ttk.Button(qa, text="Run QA Report", command=self.qa_report).grid(row=0, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(qa, text="Auto-Fix Sprite", command=self.autofix_sprite).grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(qa, text="Open report.html", command=self.open_report_html).grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        
        ttk.Label(qa, text="Loop Blend Frames:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(qa, textvariable=self.blend_loop_frames_var, width=6).grid(row=3, column=1, sticky="w", pady=4)
        
        qa.columnconfigure(0, weight=1)
        qa.columnconfigure(1, weight=1)

        export = self.section(tab, "Export", 1, 1)
        ttk.Button(export, text="Export to Godot", command=lambda: self.export_engine("godot")).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(export, text="Export to Unity", command=lambda: self.export_engine("unity")).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(export, text="Build Atlas from Output Folder", command=self.build_atlas_from_output_root).grid(row=2, column=0, sticky="ew", pady=4)
        export.columnconfigure(0, weight=1)

        # QA summary section (row 2)
        self.qa_summary_panel = self.section(tab, "QA Report Summary", 2, 0, 2, "ew")
        self.qa_summary_inner = ttk.Frame(self.qa_summary_panel)
        self.qa_summary_inner.pack(fill="both", expand=True)
        
        self.sprite_dir_var.trace_add("write", lambda *args: self.update_qa_summary())
        self.after(500, self.update_qa_summary)

    def update_qa_summary(self, folder: Path = None) -> None:
        if folder is None:
            val = self.sprite_dir_var.get().strip()
            if val:
                folder = Path(val)
                if not folder.is_absolute():
                    folder = ROOT / folder
            
        for widget in self.qa_summary_inner.winfo_children():
            widget.destroy()
            
        if not folder or not folder.exists():
            ttk.Label(self.qa_summary_inner, text="No folder selected", font=("Segoe UI", 10, "italic")).pack(anchor="w")
            return
            
        report_path = folder / "qa" / "qa_report.json"
        if not report_path.exists():
            ttk.Label(self.qa_summary_inner, text="No QA report found. Click 'Run QA Report' to analyze this sprite.", font=("Segoe UI", 10, "italic")).pack(anchor="w")
            return
            
        try:
            report = load_json(report_path)
            metrics = report.get("metrics", {})
            issues = report.get("issues", [])
            
            # Compute status
            status_text = "PASS"
            status_color = "green"
            if issues:
                has_error = any(it.get("level") == "error" for it in issues)
                status_text = "FAIL" if has_error else "WARN"
                status_color = "#ff4444" if has_error else "#ffaa00"
                
            badge_frame = ttk.Frame(self.qa_summary_inner)
            badge_frame.pack(fill="x", pady=(0, 6))
            ttk.Label(badge_frame, text="Overall QA Status: ", font=("Segoe UI", 10, "bold")).pack(side="left")
            
            badge = tk.Label(badge_frame, text=status_text, font=("Segoe UI", 10, "bold"), fg=status_color, bg="#1e1e1e")
            badge.pack(side="left")
            
            grid_frame = ttk.Frame(self.qa_summary_inner)
            grid_frame.pack(fill="x", pady=4)
            for i in range(3):
                grid_frame.columnconfigure(i, weight=1)
            
            def add_metric(label, val, row, col, unit=""):
                f = ttk.Frame(grid_frame)
                f.grid(row=row, column=col, sticky="w", padx=10, pady=2)
                ttk.Label(f, text=label, font=("Segoe UI", 9, "bold")).pack(anchor="w")
                ttk.Label(f, text=f"{val} {unit}".strip(), font=("Segoe UI", 9)).pack(anchor="w")
                
            add_metric("Loop Seam RMSE", f"{metrics.get('loop_seam_rmse', 0.0):.2f}", 0, 0)
            add_metric("Center Jitter (X stdev)", f"{metrics.get('center_x_stdev_px', 0.0):.2f}", 0, 1, "px")
            add_metric("Foot Drift (Y stdev)", f"{metrics.get('foot_y_stdev_px', 0.0):.2f}", 0, 2, "px")
            add_metric("Brightness Flicker", f"{metrics.get('brightness_stdev', 0.0):.2f}", 1, 0)
            add_metric("Duplicate Frames", f"{len(metrics.get('duplicate_frames_after_previous', []))}", 1, 1)
            add_metric("Total Issues", f"{len(issues)}", 1, 2)
            
            if issues:
                ttk.Label(self.qa_summary_inner, text="Issues / Suggestions:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
                issues_text = ScrolledText(self.qa_summary_inner, height=4, wrap="word", font=("Segoe UI", 8), bg="#121212", fg="#e0e0e0", insertbackground="#e0e0e0", bd=0, highlightthickness=1, highlightbackground="#3a3a3a", highlightcolor="#00adb5")
                issues_text.pack(fill="both", expand=True)
                for it in issues:
                    issues_text.insert(tk.END, f"• [{it.get('level').upper()}] {it.get('message')}\n")
                issues_text.config(state="disabled")
        except Exception as exc:
            ttk.Label(self.qa_summary_inner, text=f"Error reading QA report: {exc}", font=("Segoe UI", 10, "italic")).pack(anchor="w")

    def _project_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Character Pack")

        form = self.section(tab, "Create a reusable character pack", 0, 0, sticky="ew")
        self.pack_name_var = self.v("pack_name", "hero")
        self.pack_description_var = self.v("pack_description", "single full body original game hero, simple outfit, boots, clean silhouette")
        self.pack_actions_var = self.v("pack_actions", "idle,walk,run,attack_light,hurt")
        self.pack_directions_var = self.v("pack_directions", "right")
        self.pack_reference_var = self.v("pack_reference", "")
        
        self.make_text_row(form, "Pack name", self.pack_name_var, 0, width=30)
        self.make_text_row(form, "Character description", self.pack_description_var, 1)
        
        # Actions row (row 2)
        self.make_text_row(form, "Actions", self.pack_actions_var, 2)
        
        # Actions validation label (row 3)
        self.actions_warning_lbl = ttk.Label(form, text="✓ Actions valid", font=("Segoe UI", 9))
        self.actions_warning_lbl.grid(row=3, column=1, sticky="w", pady=(0, 6))
        self.pack_actions_var.trace_add("write", self._validate_pack_actions)
        
        # Subsequent fields shifted
        self.make_text_row(form, "Directions", self.pack_directions_var, 4)
        self.make_text_row(form, "Reference image optional", self.pack_reference_var, 5, browse=self.browse_pack_reference)
        ttk.Button(form, text="Create Character Pack", command=self.create_character_pack).grid(row=6, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(form, text="Build Batch Plan From Pack", command=self.build_batch_plan).grid(row=6, column=2, sticky="ew", padx=(6, 0), pady=(10, 0))
        
        # Trigger validation initially
        self._validate_pack_actions()

    def _validate_pack_actions(self, *args) -> None:
        val = self.pack_actions_var.get().strip()
        if not val:
            self.actions_warning_lbl.config(text="⚠️ Warning: Actions field cannot be blank", foreground="orange")
            return
            
        from spriteforge_prompts import ACTION_TEMPLATES
        actions = [a.strip() for a in val.split(",") if a.strip()]
        invalid = [a for a in actions if a not in ACTION_TEMPLATES]
        if invalid:
            self.actions_warning_lbl.config(
                text=f"⚠️ Unknown actions: {', '.join(invalid)}. (Standard: {', '.join(sorted(ACTION_TEMPLATES.keys()))})",
                foreground="orange"
            )
        else:
            self.actions_warning_lbl.config(text="✓ Actions valid", foreground="green")

    def _jobs_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        self.notebook.add(tab, text="Jobs Queue")
        
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top.columnconfigure(1, weight=1)
        
        ttk.Label(top, text="Select Queue: ").pack(side="left")
        self.queue_selector = ttk.Combobox(top, state="readonly", width=30)
        self.queue_selector.pack(side="left", padx=4)
        self.queue_selector.bind("<<ComboboxSelected>>", lambda e: self.refresh_jobs_status())
        
        self.jobs_summary_lbl = ttk.Label(top, text="Pending: 0 | Running: 0 | Done: 0 | Failed: 0", font=("Segoe UI", 9, "bold"))
        self.jobs_summary_lbl.pack(side="right", padx=10)
        
        tree_frame = ttk.Frame(tab)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        cols = ("id", "action", "direction", "status", "exit_code")
        self.jobs_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.jobs_tree.grid(row=0, column=0, sticky="nsew")
        
        self.jobs_tree.heading("id", text="Job ID")
        self.jobs_tree.heading("action", text="Action")
        self.jobs_tree.heading("direction", text="Direction")
        self.jobs_tree.heading("status", text="Status")
        self.jobs_tree.heading("exit_code", text="Exit Code")
        
        self.jobs_tree.column("id", width=180, anchor="w")
        self.jobs_tree.column("action", width=120, anchor="center")
        self.jobs_tree.column("direction", width=100, anchor="center")
        self.jobs_tree.column("status", width=100, anchor="center")
        self.jobs_tree.column("exit_code", width=80, anchor="center")
        
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.jobs_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.jobs_tree.configure(yscrollcommand=sb.set)
        
        btns = ttk.Frame(tab)
        btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Run Queue", command=self.run_selected_queue).pack(side="left", padx=4)
        ttk.Button(btns, text="Reset Queue", command=self.reset_selected_queue).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete Job", command=self.delete_selected_job).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=self.refresh_jobs_status).pack(side="left", padx=4)
        
        self.after(400, self.refresh_jobs_status)

    def refresh_jobs_status(self) -> None:
        jobs_dir = ROOT / "output" / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        queues = sorted([p.name for p in jobs_dir.glob("*_queue.json")])
        
        self.queue_selector["values"] = queues
        
        current = self.queue_selector.get()
        if not current and queues:
            if "gui_queue_queue.json" in queues:
                current = "gui_queue_queue.json"
            elif any(x.startswith("gui_queue") for x in queues):
                current = [x for x in queues if x.startswith("gui_queue")][0]
            else:
                current = queues[0]
            self.queue_selector.set(current)
            
        self.jobs_tree.delete(*self.jobs_tree.get_children())
        if not current:
            self.jobs_summary_lbl.config(text="No queues found.")
            return
            
        qpath = jobs_dir / current
        data = load_json(qpath, {})
        jobs = data.get("jobs", [])
        
        counts = {"pending": 0, "running": 0, "done": 0, "failed": 0, "interrupted": 0}
        for j in jobs:
            status = j.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
            self.jobs_tree.insert("", "end", iid=j.get("id"), values=(
                j.get("id"),
                j.get("action", ""),
                j.get("direction", ""),
                status.upper(),
                j.get("exit_code", "") if j.get("exit_code") is not None else "-"
            ))
            
        self.jobs_summary_lbl.config(text=f"Pending: {counts.get('pending', 0)} | Running: {counts.get('running', 0)} | Done: {counts.get('done', 0)} | Failed: {counts.get('failed', 0)}")

    def run_selected_queue(self) -> None:
        current = self.queue_selector.get()
        if not current:
            messagebox.showwarning("No queue", "Select a queue to run first.")
            return
        qpath = ROOT / "output" / "jobs" / current
        cmd = self.pycmd("spriteforge_queue.py", "run", "--queue", str(qpath), "--continue-on-error")
        
        def done(code: int):
            self.refresh_jobs_status()
            if code == 0:
                messagebox.showinfo("Queue Done", "The job queue completed successfully.")
            else:
                messagebox.showwarning("Queue Finished", "Queue completed with some failed jobs.")
                
        self.runner.run(f"Run Queue: {current}", cmd, on_done=done)

    def reset_selected_queue(self) -> None:
        current = self.queue_selector.get()
        if not current:
            return
        qpath = ROOT / "output" / "jobs" / current
        data = load_json(qpath, {})
        for j in data.get("jobs", []):
            j["status"] = "pending"
            j["started_at"] = None
            j["finished_at"] = None
            j["exit_code"] = None
        save_json(qpath, data)
        self.refresh_jobs_status()
        messagebox.showinfo("Queue Reset", f"All jobs in queue '{current}' have been reset to pending.")

    def delete_selected_job(self) -> None:
        current = self.queue_selector.get()
        if not current:
            return
        sel = self.jobs_tree.selection()
        if not sel:
            messagebox.showwarning("No job selected", "Choose a job from the list first.")
            return
        job_id = sel[0]
        qpath = ROOT / "output" / "jobs" / current
        data = load_json(qpath, {})
        jobs = data.get("jobs", [])
        new_jobs = [j for j in jobs if j.get("id") != job_id]
        data["jobs"] = new_jobs
        save_json(qpath, data)
        self.refresh_jobs_status()

    def enqueue_job(self, name: str, cmd: List[str], action: str = "custom", direction: str = "none") -> None:
        jobs_dir = ROOT / "output" / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        qpath = jobs_dir / "gui_queue_queue.json"
        
        data = load_json(qpath, None)
        if not data or "jobs" not in data:
            import datetime as dt
            data = {
                "schema": "spriteforge_queue_v12",
                "name": "gui_queue",
                "created_at": dt.datetime.now().isoformat(timespec="seconds"),
                "jobs": []
            }
            
        import datetime as dt
        idx = len(data["jobs"]) + 1
        job_id = f"{idx:03d}_{action}_{direction}_{int(time.time())}"
        
        job = {
            "id": job_id,
            "action": action,
            "direction": direction,
            "status": "pending",
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "command": cmd,
            "log": None,
        }
        data["jobs"].append(job)
        save_json(qpath, data)
        self.log(f"Enqueued job {job_id} to gui_queue_queue.json\n")
        self.refresh_jobs_status()

    def _advanced_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.notebook.add(tab, text="Advanced")

        cloud = self.section(tab, "Remote / cloud ComfyUI", 0, 0, 2, "ew")
        self.remote_server_var = self.v("remote_server", "http://YOUR_SERVER:8188")
        self.remote_workflow_var = self.v("remote_workflow", "")
        self.remote_prompt_var = self.v("remote_prompt", "single full body original game character walking cycle, professional appealing character design, heroic adult proportions, distinctive outfit, crisp cel-shaded edges, side view, plain green background")
        self.make_text_row(cloud, "Server", self.remote_server_var, 0)
        self.make_text_row(cloud, "Workflow API JSON", self.remote_workflow_var, 1, browse=self.browse_remote_workflow)
        self.make_text_row(cloud, "Prompt", self.remote_prompt_var, 2)
        ttk.Button(cloud, text="Remote Generate + Convert", command=self.remote_generate).grid(row=3, column=1, sticky="ew", pady=(10, 0))

        maint = self.section(tab, "Maintenance", 1, 0)
        ttk.Button(maint, text="Create Snapshot", command=self.snapshot).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(maint, text="Safe Update", command=self.safe_update).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(maint, text="Model Report", command=self.model_report).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(maint, text="Open Model Download Pages", command=self.open_model_pages).grid(row=3, column=0, sticky="ew", pady=4)
        maint.columnconfigure(0, weight=1)

        docs = self.section(tab, "Guides", 1, 1)
        ttk.Button(docs, text="Open End User Guide", command=lambda: open_path(ROOT / "docs" / "END_USER_GUIDE.md")).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(docs, text="Open One-Page Cheat Sheet", command=lambda: open_path(ROOT / "docs" / "ONE_PAGE_CHEAT_SHEET.md")).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(docs, text="Open Advanced README", command=lambda: open_path(ROOT / "docs" / "README_ADVANCED_v6_BASE.md")).grid(row=2, column=0, sticky="ew", pady=4)
        docs.columnconfigure(0, weight=1)

    # ---------- logging/status ----------
    def log(self, text: str) -> None:
        self.log_queue.put(text)

    def _pump_log(self) -> None:
        import re
        progress_pat1 = re.compile(r'(\d+)%\s*\|')
        progress_pat2 = re.compile(r'(?:[Ss]tep|[Ss]teps)?\s*(\d+)\s*/\s*(\d+)')
        progress_pat3 = re.compile(r'(\d+)\s*of\s*(\d+)')

        while True:
            try:
                text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)
            
            # Scan lines for progress info
            for line in text.splitlines():
                pct = None
                m1 = progress_pat1.search(line)
                if m1:
                    try:
                        pct = float(m1.group(1))
                    except ValueError:
                        pass
                else:
                    m2 = progress_pat2.search(line)
                    if m2:
                        try:
                            curr = int(m2.group(1))
                            total = int(m2.group(2))
                            if total > 0 and curr <= total:
                                pct = (curr / total) * 100.0
                        except ValueError:
                            pass
                    else:
                        m3 = progress_pat3.search(line)
                        if m3:
                            try:
                                curr = int(m3.group(1))
                                total = int(m3.group(2))
                                if total > 0 and curr <= total:
                                    pct = (curr / total) * 100.0
                            except ValueError:
                                pass
                if pct is not None:
                    self.progress_bar["value"] = pct
                    
        self.after(100, self._pump_log)

    def set_busy(self, busy: bool, label: str = "") -> None:
        self.busy_label.config(text=("Running: " + label if busy else "Ready"))
        if not busy:
            self.progress_bar["value"] = 0

    def refresh_status(self) -> None:
        self.status_text.delete("1.0", tk.END)
        self.status_text.insert(tk.END, "Refreshing system status...")

        def worker():
            cfg = load_json(CONFIG_PATH, {})
            paths = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
            comfy_dir = resolve_root_path(str(paths.get("comfyui_dir", "vendor/ComfyUI")))
            comfy_out = resolve_root_path(str(paths.get("comfyui_output", "vendor/ComfyUI/output")))
            host = str((cfg.get("comfy", {}) or {}).get("host", "127.0.0.1"))
            port = int((cfg.get("comfy", {}) or {}).get("port", 8188))
            model_manifest = load_json(ROOT / "model_manifests" / "wan21_t2v_1_3b_native.json", {})
            model_lines = []
            all_models = True
            for f in model_manifest.get("files", []):
                p = comfy_dir / "models" / f.get("dest_subdir", "") / f.get("filename", "")
                ok = p.exists()
                all_models = all_models and ok
                model_lines.append(f"  {'OK' if ok else 'MISSING'} - {f.get('filename')} {f.get('approx_size', '')}")
            venv_ok = Path(PYTHON).exists()
            comfy_ok = comfy_dir.exists()
            server_ok = is_comfy_running(host, port)
            git_ok = shutil.which("git") is not None
            nvidia = self._nvidia_summary()
            status = [
                f"Python environment: {'OK' if venv_ok else 'Missing'} ({PYTHON})",
                f"Git for Windows: {'OK' if git_ok else 'Missing'}",
                f"NVIDIA GPU: {nvidia}",
                f"ComfyUI folder: {'OK' if comfy_ok else 'Not installed'} ({short_path(comfy_dir)})",
                f"ComfyUI server: {'Running' if server_ok else 'Not running'} (http://{host}:{port})",
                f"ComfyUI output: {short_path(comfy_out)}",
                f"WAN 2.1 1.3B models: {'OK' if all_models else 'Missing files'}",
                *model_lines,
                "",
                "Recommended: first generate with profile=debug. Then use profile=rtx3060_12gb.",
            ]
            text = "\n".join(status)
            def update():
                self.status_text.delete("1.0", tk.END)
                self.status_text.insert(tk.END, text)
            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    def _nvidia_summary(self) -> str:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return "nvidia-smi not found"
        try:
            out = subprocess.check_output([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True, timeout=3, errors="replace")
            return out.strip().replace("\n", "; ") or "not detected"
        except Exception as exc:
            return f"could not read ({exc})"

    def load_thumbnail(self, folder: Path) -> Optional[Any]:
        try:
            if not hasattr(self, "_thumb_cache"):
                self._thumb_cache = {}
            if str(folder) in self._thumb_cache:
                return self._thumb_cache[str(folder)]
            
            from PIL import Image, ImageTk
            json_path = folder / "sheet.json"
            img_name = "sheet.png"
            w, h = 512, 512
            if json_path.exists():
                try:
                    meta = json.loads(json_path.read_text(encoding="utf-8"))
                    img_name = meta.get("image", "sheet.png")
                    cell = meta.get("cell_size")
                    if cell and len(cell) == 2:
                        w, h = int(cell[0]), int(cell[1])
                except Exception:
                    pass
            
            img_path = folder / img_name
            if not img_path.exists():
                img_path = folder / "sheet.png"
            if not img_path.exists():
                pngs = list(folder.glob("*.png"))
                if pngs:
                    img_path = pngs[0]
                    
            if img_path.exists():
                with Image.open(img_path) as img:
                    if img.width >= w and img.height >= h:
                        frame = img.crop((0, 0, w, h))
                    else:
                        frame = img
                    frame.thumbnail((48, 48), Image.Resampling.LANCZOS)
                    # Create transparent square background to align all thumbnails nicely
                    bg = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
                    offset = ((48 - frame.width) // 2, (48 - frame.height) // 2)
                    bg.paste(frame, offset)
                    photo = ImageTk.PhotoImage(bg)
                    self._thumb_cache[str(folder)] = photo
                    return photo
        except Exception as exc:
            print(f"Error loading thumbnail: {exc}")
        return None

    def refresh_outputs(self) -> None:
        outputs = find_recent_sprite_outputs()
        self.recent_outputs = outputs
        self.recent_list.delete(*self.recent_list.get_children())
        for p in outputs:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)) if p.exists() else ""
            display_text = f"{ts}  {short_path(p)}"
            photo = self.load_thumbnail(p)
            if photo:
                self.recent_list.insert("", "end", iid=str(p), text=display_text, image=photo)
            else:
                self.recent_list.insert("", "end", iid=str(p), text=display_text)

    def _on_recent_select(self, event=None) -> None:
        sel = self.recent_list.selection()
        if not sel:
            return
        p = Path(sel[0])
        self.selected_sprite_dir = p
        self.sprite_dir_var.set(str(p))

    # ---------- command helpers ----------
    def pycmd(self, *args: str) -> List[str]:
        return [PYTHON, *map(str, args)]

    def setup_everything(self) -> None:
        self.save_easy_settings()
        torch_index = "cu126"
        steps = [
            ("Install SpriteForge dependencies", self.pycmd("spriteforge_unified.py", "install-spriteforge", "--python", python_preference()), True),
            ("Apply hardware recommendations", self.pycmd("spriteforge_unified.py", "hardware-advisor", "--apply"), False),
            ("Install / update ComfyUI + WAN nodes + auto-download models", self.pycmd("spriteforge_unified.py", "install-all", "--python", python_preference(), "--torch-index", torch_index), True),
            ("Run health check", self.pycmd("spriteforge_unified.py", "doctor"), False),
        ]
        self.runner.run_sequence("Set Up Everything", steps)

    def install_spriteforge_only(self) -> None:
        self.runner.run("Install SpriteForge Only", self.pycmd("spriteforge_unified.py", "install-spriteforge", "--python", python_preference()))

    def install_comfy_nodes(self) -> None:
        self.runner.run("Install / Update ComfyUI + WAN Models", self.pycmd("spriteforge_unified.py", "install-all", "--python", python_preference(), "--torch-index", "cu126"))

    def download_models(self) -> None:
        self.runner.run("Download WAN Models", self.pycmd("spriteforge_unified.py", "download-wan-native"))

    def run_doctor(self) -> None:
        self.runner.run("Run Health Check", self.pycmd("spriteforge_unified.py", "doctor"))

    def hardware_advisor(self) -> None:
        self.runner.run("Hardware Advisor", self.pycmd("spriteforge_unified.py", "hardware-advisor"))

    def launch_comfy(self) -> None:
        cmd = self.pycmd("spriteforge_unified.py", "launch-comfy")
        try:
            kwargs = {"cwd": str(ROOT)}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(cmd, **kwargs)
            self.log("Launched ComfyUI in its own console window. Open http://127.0.0.1:8188 after it finishes loading.\n")
        except Exception as exc:
            messagebox.showerror("Could not launch ComfyUI", str(exc))

    def open_comfy(self) -> None:
        self.runner.run("Open ComfyUI Browser", self.pycmd("spriteforge_unified.py", "open-comfy"))

    def create_shortcut(self) -> None:
        bat = ROOT / "Create_Desktop_Shortcut.bat"
        if os.name == "nt":
            self.runner.run("Create Desktop Shortcut", [str(bat)])
        else:
            messagebox.showinfo("Desktop shortcut", "Shortcut creation is only included for Windows.")

    def open_comfy_folder(self) -> None:
        cfg = load_json(CONFIG_PATH, {})
        comfy_dir = resolve_root_path(str((cfg.get("paths", {}) or {}).get("comfyui_dir", "vendor/ComfyUI")))
        open_path(comfy_dir)

    def safe_update(self) -> None:
        if messagebox.askyesno("Safe Update", "Create a snapshot and update ComfyUI/custom nodes?"):
            self.runner.run("Safe Update", self.pycmd("spriteforge_unified.py", "safe-update", "--custom-nodes"))

    def snapshot(self) -> None:
        self.runner.run("Create Snapshot", self.pycmd("spriteforge_unified.py", "snapshot"))

    def model_report(self) -> None:
        self.runner.run("Model Report", self.pycmd("spriteforge_unified.py", "model-report"))

    def open_model_pages(self) -> None:
        self.runner.run("Open Model Download Pages", self.pycmd("spriteforge_unified.py", "open-model-pages"))

    # ---------- Make sprite ----------
    def fill_safe_test(self) -> None:
        self.character_var.set("single full body original game hero, professional appealing character design, heroic adult proportions, distinctive outfit, clean silhouette")
        self.action_var.set("idle")
        self.direction_var.set("front")
        self.profile_var.set("debug")
        self.style_var.set("polished 2D game sprite, professional character design, crisp cel-shaded edges, readable silhouette")
        self.extra_prompt_var.set("locked camera, no zoom, centered, plain bright green background")

    def browse_reference_image(self) -> None:
        file = filedialog.askopenfilename(title="Choose reference image", filetypes=[("Images", " ".join(IMAGE_EXTS)), ("All files", "*.*")])
        if file:
            self.reference_image_var.set(file)

    def generate_sprite(self) -> None:
        self.save_easy_settings()
        character = self.character_var.get().strip()
        if not character:
            messagebox.showerror("Missing character", "Type a character description first.")
            return
        cmd = self.pycmd(
            "spriteforge_unified.py", "generate-sprite",
            "--start-comfy",
            "--profile", self.profile_var.get().strip() or "debug",
            "--action", self.action_var.get().strip() or "idle",
            "--direction", self.direction_var.get().strip() or "front",
            "--character", character,
            "--style", self.style_var.get().strip() or "polished 2D game sprite, professional character design",
            "--background", "plain bright green chroma key background",
            "--extra-prompt", self.extra_prompt_var.get().strip() or "locked camera, no zoom, centered",
            "--seed", self.seed_var.get().strip() or "-1",
        )
        ref = self.reference_image_var.get().strip()
        if ref:
            cmd += ["--mode", "i2v", "--reference-image", ref]
            if self.profile_var.get() not in {"i2v_cloud_24gb_plus", "debug"}:
                self.log("Reference image mode is heavier than basic T2V. Consider a remote/cloud ComfyUI server if local generation fails.\n")
        if self.quality_check_var.get():
            cmd += ["--quality-check"]
        self.runner.run("Generate WAN Sprite", cmd)

    def build_prompt_only(self) -> None:
        self.save_easy_settings()
        out = ROOT / "output" / "prompts"
        out.mkdir(parents=True, exist_ok=True)
        name = f"prompt_{self.action_var.get()}_{int(time.time())}.json"
        cmd = self.pycmd(
            "spriteforge_unified.py", "build-prompt",
            "--action", self.action_var.get().strip() or "idle",
            "--direction", self.direction_var.get().strip() or "front",
            "--character", self.character_var.get().strip() or "single full body original game character, professional appealing character design",
            "--style", self.style_var.get().strip() or "polished 2D game sprite, professional character design",
            "--background", "plain bright green background",
            "--extra", self.extra_prompt_var.get().strip() or "locked camera, no zoom",
            "--output", str(out / name),
        )
        self.runner.run("Build Prompt Only", cmd)

    # ---------- Convert video ----------
    def browse_video_file(self) -> None:
        patterns = " ".join(VIDEO_EXTS)
        file = filedialog.askopenfilename(title="Choose video", filetypes=[("Video files", patterns), ("All files", "*.*")])
        if file:
            self.video_file_var.set(file)
            if not self.video_output_name_var.get().strip():
                self.video_output_name_var.set(Path(file).stem + "_sprite")

    def inspect_video(self) -> None:
        file = self.video_file_var.get().strip()
        if not file:
            messagebox.showerror("Missing video", "Choose a video first.")
            return
        self.runner.run("Inspect Video", self.pycmd("spriteforge.py", "inspect", "--input", file))

    def convert_video(self) -> None:
        self.save_easy_settings()
        file = self.video_file_var.get().strip()
        if not file:
            messagebox.showerror("Missing video", "Choose a video first.")
            return
        out_name = self.video_output_name_var.get().strip() or (Path(file).stem + "_sprite")
        out_dir = ROOT / "output" / out_name
        cmd = self.pycmd(
            "spriteforge.py", "video",
            "--input", file,
            "--output", str(out_dir),
            "--fps", self.video_fps_var.get().strip() or "12",
            "--cell-size", self.cell_size_var.get().strip() or "512x512",
            "--key-color", self.key_color_var.get().strip() or "auto",
            "--key-tolerance", self.key_tolerance_var.get().strip() or "45",
            "--anchor", "bottom-center",
            "--pad", "24",
            "--solidify", "2",
            "--drop-loop-duplicate",
            "--preview-gif",
            "--report",
            "--save-raw-frames",
        )
        def done(rc: int):
            if rc == 0:
                self.sprite_dir_var.set(str(out_dir))
                self.selected_sprite_dir = out_dir
        self.runner.run("Convert Video to Sprite", cmd, on_done=done)


    def convert_drop_folder(self) -> None:
        self.save_easy_settings()
        DROP_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        videos = sorted([p for p in DROP_VIDEOS_DIR.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES])
        if not videos:
            messagebox.showinfo("No dropped videos", f"Drop .mp4/.webm/.mov videos into:\n{DROP_VIDEOS_DIR}\n\nThen click this button again.")
            return
        steps = []
        for file_path in videos:
            out_dir = ROOT / "output" / (file_path.stem + "_sprite")
            cmd = self.pycmd(
                "spriteforge.py", "video",
                "--input", str(file_path),
                "--output", str(out_dir),
                "--fps", self.video_fps_var.get().strip() or "12",
                "--cell-size", self.cell_size_var.get().strip() or "512x512",
                "--key-color", self.key_color_var.get().strip() or "auto",
                "--key-tolerance", self.key_tolerance_var.get().strip() or "45",
                "--anchor", "bottom-center",
                "--pad", "24",
                "--solidify", "2",
                "--drop-loop-duplicate",
                "--preview-gif",
                "--report",
                "--save-raw-frames",
            )
            steps.append((f"Convert {file_path.name}", cmd, False))
            
        def done(code: int):
            if code == 0:
                messagebox.showinfo("Done", "All dropped videos converted successfully.")
            else:
                messagebox.showwarning("Warning", "Some video conversions failed. Please check the Activity Log.")
                
        self.runner.run_sequence("Convert Dropped Videos", steps, on_done=done)

    # ---------- QA/export ----------
    def browse_sprite_dir(self) -> None:
        d = filedialog.askdirectory(title="Choose SpriteForge output folder")
        if d:
            self.sprite_dir_var.set(d)
            self.selected_sprite_dir = Path(d)

    def selected_sprite(self) -> Optional[Path]:
        val = self.sprite_dir_var.get().strip()
        if val:
            return Path(val)
        if self.selected_sprite_dir:
            return self.selected_sprite_dir
        outputs = find_recent_sprite_outputs(1)
        return outputs[0] if outputs else None

    def use_most_recent_output(self) -> None:
        outputs = find_recent_sprite_outputs(1)
        if not outputs:
            messagebox.showinfo("No outputs", "No SpriteForge output with sheet.json was found yet.")
            return
        self.selected_sprite_dir = outputs[0]
        self.sprite_dir_var.set(str(outputs[0]))

    def open_sprite_dir(self) -> None:
        p = self.selected_sprite()
        if not p:
            messagebox.showinfo("No sprite selected", "Choose a sprite output first.")
            return
        open_path(p)

    def open_selected_output(self) -> None:
        p = self.selected_sprite()
        if p:
            open_path(p)

    def qa_report(self) -> None:
        p = self.selected_sprite()
        if not p:
            messagebox.showerror("No sprite selected", "Choose a sprite output first.")
            return
        def done(code: int):
            self.update_qa_summary(p)
            if code == 0:
                messagebox.showinfo("QA Done", "QA analysis finished. Summary loaded in panel.")
            else:
                messagebox.showerror("Error", "QA analysis failed.")
        self.runner.run("QA Report", self.pycmd("spriteforge_unified.py", "qa-report", "--input", str(p)), on_done=done)

    def autofix_sprite(self) -> None:
        p = self.selected_sprite()
        if not p:
            messagebox.showerror("No sprite selected", "Choose a sprite output first.")
            return
            
        if p.name.endswith("_fixed"):
            out = p
            ans = messagebox.askyesno(
                "Confirm Overwrite",
                f"This sprite is already an autofixed copy:\n{p.name}\n\nRunning Auto-Fix again will overwrite the existing fixed sprite. Do you want to proceed?"
            )
            if not ans:
                return
        else:
            out = p.with_name(p.name + "_fixed")
            ans = messagebox.askyesno(
                "Confirm Auto-Fix",
                f"Auto-Fix will create a stabilized copy at:\n{out.name}\n\nDo you want to proceed?"
            )
            if not ans:
                return
                
        def done(code: int):
            if code == 0:
                messagebox.showinfo("Auto-Fix Done", f"Auto-fixed sprite saved at:\n{short_path(out)}")
            else:
                messagebox.showerror("Error", "Auto-Fix failed.")
                
        blend_frames = self.blend_loop_frames_var.get().strip() or "3"
        self.runner.run("Auto-Fix Sprite", self.pycmd(
            "spriteforge_unified.py", "autofix-sprite", "--input", str(p), "--output", str(out),
            "--stabilize-anchor", "--drop-loop-duplicate", "--deflicker", "--solidify", "2",
            "--blend-loop-frames", blend_frames
        ), on_done=done)

    def open_report_html(self) -> None:
        p = self.selected_sprite()
        if not p:
            return
        report = p / "report.html"
        if report.exists():
            open_path(report)
        else:
            messagebox.showinfo("No report", "report.html was not found. Run QA or convert/generate with report enabled.")

    def export_engine(self, engine: str) -> None:
        p = self.selected_sprite()
        if not p:
            messagebox.showerror("No sprite selected", "Choose a sprite output first.")
            return
        out = ROOT / "output" / "engine_exports" / f"{p.name}_{engine}"
        self.runner.run(f"Export to {engine.title()}", self.pycmd("spriteforge_unified.py", "export-engine", "--sprite-dir", str(p), "--engine", engine, "--output", str(out), "--name", p.name))

    def build_atlas_from_output_root(self) -> None:
        out = ROOT / "output" / "atlas" / f"atlas_{int(time.time())}"
        self.runner.run("Build Atlas", self.pycmd("spriteforge_unified.py", "atlas-build", "--root", str(ROOT / "output"), "--output", str(out), "--name", "spriteforge_atlas"))

    # ---------- Character pack ----------
    def browse_pack_reference(self) -> None:
        file = filedialog.askopenfilename(title="Choose reference image", filetypes=[("Images", " ".join(IMAGE_EXTS)), ("All files", "*.*")])
        if file:
            self.pack_reference_var.set(file)

    def create_character_pack(self) -> None:
        self.save_easy_settings()
        name = self.pack_name_var.get().strip() or "hero"
        desc = self.pack_description_var.get().strip()
        if not desc:
            messagebox.showerror("Missing description", "Type a character description first.")
            return
            
        actions_str = self.pack_actions_var.get().strip()
        if not actions_str:
            messagebox.showerror("Invalid actions", "Actions field cannot be blank.")
            return
            
        from spriteforge_prompts import ACTION_TEMPLATES
        actions = [a.strip() for a in actions_str.split(",") if a.strip()]
        invalid = [a for a in actions if a not in ACTION_TEMPLATES]
        if invalid:
            ans = messagebox.askyesno(
                "Unknown Actions",
                f"The following actions are not standard presets:\n{', '.join(invalid)}\n\nStandard actions: {', '.join(sorted(ACTION_TEMPLATES.keys()))}\n\nDo you want to continue anyway?"
            )
            if not ans:
                return

        out = ROOT / "output" / "character_packs" / name
        cmd = self.pycmd(
            "spriteforge_unified.py", "character-pack",
            "--name", name,
            "--description", desc,
            "--actions", actions_str,
            "--directions", self.pack_directions_var.get().strip() or "right",
            "--profile", self.profile_var.get().strip() or "rtx3060_12gb",
            "--output", str(out),
        )
        ref = self.pack_reference_var.get().strip()
        if ref:
            cmd += ["--reference-image", ref]
        self.runner.run("Create Character Pack", cmd)

    def build_batch_plan(self) -> None:
        profile_path = filedialog.askopenfilename(title="Choose character_profile.json", filetypes=[("Character profile", "character_profile.json"), ("JSON", "*.json"), ("All files", "*.*")], initialdir=str(ROOT / "output" / "character_packs"))
        if not profile_path:
            return
        self.runner.run("Build Batch Plan", self.pycmd("spriteforge_unified.py", "batch-actions", "--profile", profile_path, "--local-profile", self.profile_var.get().strip() or "rtx3060_12gb"))

    # ---------- Advanced / cloud ----------
    def browse_remote_workflow(self) -> None:
        file = filedialog.askopenfilename(title="Choose exported ComfyUI API workflow", filetypes=[("JSON", "*.json"), ("All files", "*.*")], initialdir=str(ROOT / "workflows"))
        if file:
            self.remote_workflow_var.set(file)

    def remote_generate(self) -> None:
        self.save_easy_settings()
        server = self.remote_server_var.get().strip()
        workflow = self.remote_workflow_var.get().strip()
        prompt = self.remote_prompt_var.get().strip()
        if not server or not workflow or not prompt:
            messagebox.showerror("Missing remote settings", "Enter server, workflow, and prompt.")
            return
        self.runner.run("Remote Generate", self.pycmd(
            "spriteforge_unified.py", "remote-generate", "--server", server, "--workflow", workflow, "--prompt", prompt,
            "--convert", "--cell-size", self.cell_size_var.get().strip() or "512x512", "--key-color", self.key_color_var.get().strip() or "auto"
        ))


def main() -> int:
    if "--smoke-test" in sys.argv:
        print("SpriteForge Easy Mode smoke test OK")
        return 0
    app = EasyApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
