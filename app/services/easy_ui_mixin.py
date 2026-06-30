from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from typing import Callable, Optional

from spriteforge_utils import load_json
from services.easy_helpers import (
    resolve_root_path,
    short_path,
    open_path,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
PRESETS_PATH = ROOT / "config" / "easy_presets.json"
DROP_VIDEOS_DIR = ROOT / "01_DROP_VIDEOS_HERE"
IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")

class EasyUiMixin:
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = ttk.Frame(self, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="SpriteForge Studio", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Easy Mode: ComfyUI + WAN + sprite sheets", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w")
        
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
    def log(self, text: str) -> None:
        self.log_queue.put(text)

    def _pump_log(self) -> None:
        import re
        import queue
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

