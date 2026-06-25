#!/usr/bin/env python3
"""Tkinter launcher for SpriteForge Studio."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText  # In case it is used or needed

from spriteforge_utils import load_json, save_json, app_python, PYTHON, get_app_version, apply_dark_theme

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"


def load_config():
    return load_json(CONFIG_PATH, {})


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        version = get_app_version()
        self.title(f"SpriteForge Studio {version} - ComfyUI + WAN + Production Sprites")
        self.geometry("1080x760")
        apply_dark_theme(self)
        self.proc = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self.cfg = load_config()
        self.create_ui()
        self.after(100, self.drain_log)

    def create_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.setup_tab = ttk.Frame(nb, padding=10)
        self.gen_tab = ttk.Frame(nb, padding=10)
        self.convert_tab = ttk.Frame(nb, padding=10)
        self.prod_tab = ttk.Frame(nb, padding=10)
        self.log_tab = ttk.Frame(nb, padding=10)
        nb.add(self.setup_tab, text="Setup / Doctor / Launch")
        nb.add(self.gen_tab, text="WAN → Sprite")
        nb.add(self.convert_tab, text="Convert / Watch / Blender")
        nb.add(self.prod_tab, text="Production / QA / Atlas")
        nb.add(self.log_tab, text="Log")

        self.build_setup_tab()
        self.build_gen_tab()
        self.build_convert_tab()
        self.build_prod_tab()
        self.build_log_tab()

    def build_setup_tab(self):
        row = 0
        ttk.Label(
            self.setup_tab,
            text="One local tool: install/manage ComfyUI, install WAN/video nodes, download model files, launch ComfyUI, diagnose the setup, and build sprite sheets.",
            wraplength=980,
        ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 10))
        row += 1
        buttons = [
            ("Install SpriteForge Python deps", ["install-spriteforge"]),
            ("Install/Update ComfyUI + WAN Nodes", ["install-comfy", "--nodes"]),
            ("Install/Update WAN Nodes Only", ["install-nodes"]),
            ("Install/Update ComfyUI Manager", ["install-manager"]),
            ("Download Native Wan 2.1 1.3B Model Files", ["download-wan-native"]),
            ("Download Native Wan 2.1 I2V Manifest Files", ["download-wan-native", "--manifest", "model_manifests/wan21_i2v_480p_14b_native.json"]),
            ("Snapshot ComfyUI Before Updates", ["snapshot"]),
            ("Safe Update ComfyUI + Custom Nodes", ["safe-update", "--custom-nodes"]),
            ("Write Cloud GPU Plan", ["cloud-plan"]),
            ("Check Status", ["status"]),
            ("Run Doctor", ["doctor"]),
            ("Validate Included Workflow", ["validate-workflow"]),
            ("Check Model Files", ["model-report"]),
            ("Open Model Download Pages", ["open-model-pages"]),
        ]
        for label, cmd in buttons:
            ttk.Button(self.setup_tab, text=label, command=lambda c=cmd: self.run_cli(c)).grid(row=row, column=0, sticky="ew", pady=4, padx=4)
            row += 1

        ttk.Separator(self.setup_tab).grid(row=1, column=1, rowspan=12, sticky="ns", padx=18)
        ttk.Button(self.setup_tab, text="Launch ComfyUI", command=self.launch_comfy_window).grid(row=1, column=2, sticky="ew", pady=4)
        ttk.Button(self.setup_tab, text="Open ComfyUI in Browser", command=lambda: self.run_cli(["open-comfy"])).grid(row=2, column=2, sticky="ew", pady=4)
        ttk.Button(self.setup_tab, text="ComfyUI Queue / History", command=lambda: self.run_cli(["queue-status"])).grid(row=3, column=2, sticky="ew", pady=4)
        ttk.Button(self.setup_tab, text="Stop launched process", command=self.stop_proc).grid(row=4, column=2, sticky="ew", pady=4)

        ttk.Label(self.setup_tab, text="Default managed ComfyUI folder:").grid(row=6, column=2, sticky="w", pady=(20, 0))
        ttk.Label(self.setup_tab, text=str(ROOT / self.cfg["paths"]["comfyui_dir"]), foreground="gray").grid(row=7, column=2, sticky="w")
        ttk.Label(
            self.setup_tab,
            text="v6 adds sprite QA scoring, repair, character pack manifests, multi-animation atlases, Godot AnimatedSprite2D export, Unity animation clip helpers, and the v5 exact ComfyUI prompt_id tracking.",
            wraplength=460,
            foreground="gray",
        ).grid(row=9, column=2, sticky="w", pady=(20, 0))

        for c in range(3):
            self.setup_tab.columnconfigure(c, weight=1)

    def build_gen_tab(self):
        self.prompt = tk.Text(self.gen_tab, height=7, wrap="word")
        self.prompt.insert(
            "1.0",
            "single full body character walking cycle, side view, locked camera, no zoom, centered, plain bright green background, game sprite animation, clean silhouette",
        )
        self.negative = tk.Text(self.gen_tab, height=4, wrap="word")
        self.negative.insert(
            "1.0",
            "camera movement, zoom, cuts, close up, motion blur, changing outfit, changing identity, complex background, text, subtitles, watermark, deformed body, extra limbs, low quality",
        )

        profiles = sorted(self.cfg.get("profiles", {}).keys()) or ["rtx3060_12gb"]
        self.profile = tk.StringVar(value="rtx3060_12gb" if "rtx3060_12gb" in profiles else profiles[0])
        self.mode = tk.StringVar(value="t2v")
        self.action = tk.StringVar(value="walk")
        self.direction = tk.StringVar(value="right")
        self.reference_image = tk.StringVar(value="")
        ttk.Label(self.gen_tab, text="WAN mode").grid(row=0, column=0, sticky="w")
        ttk.Combobox(self.gen_tab, textvariable=self.mode, values=["t2v", "i2v", "vace", "custom"], width=12, state="readonly").grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(self.gen_tab, text="Profile").grid(row=0, column=2, sticky="w")
        ttk.Combobox(self.gen_tab, textvariable=self.profile, values=profiles, width=18, state="readonly").grid(row=0, column=3, sticky="w", padx=4)
        ttk.Button(self.gen_tab, text="Apply profile defaults", command=self.apply_profile).grid(row=0, column=4, sticky="w", padx=4)

        ttk.Label(self.gen_tab, text="Action").grid(row=1, column=0, sticky="w")
        ttk.Combobox(self.gen_tab, textvariable=self.action, values=["idle","walk","run","attack_light","attack_heavy","cast","jump","hurt","death"], width=16, state="readonly").grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(self.gen_tab, text="Direction").grid(row=1, column=2, sticky="w")
        ttk.Combobox(self.gen_tab, textvariable=self.direction, values=["front","back","left","right","three_quarter"], width=16, state="readonly").grid(row=1, column=3, sticky="w", padx=4)
        ttk.Button(self.gen_tab, text="Build prompt from action", command=self.build_prompt_from_action).grid(row=1, column=4, sticky="w", padx=4)

        ttk.Label(self.gen_tab, text="Reference image for I2V/reference mode").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(self.gen_tab, textvariable=self.reference_image).grid(row=2, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.gen_tab, text="Browse", command=lambda: self.pick_file(self.reference_image, [("Image", "*.png *.jpg *.jpeg *.webp")])).grid(row=2, column=4, sticky="w", padx=4)

        ttk.Label(self.gen_tab, text="Positive prompt").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.prompt.grid(row=4, column=0, columnspan=5, sticky="nsew", pady=(0, 8))
        ttk.Label(self.gen_tab, text="Negative prompt").grid(row=5, column=0, sticky="w")
        self.negative.grid(row=6, column=0, columnspan=5, sticky="nsew", pady=(0, 8))

        defaults = self.current_defaults()
        self.width = tk.StringVar(value=str(defaults.get("width", 832)))
        self.height = tk.StringVar(value=str(defaults.get("height", 480)))
        self.frames = tk.StringVar(value=str(defaults.get("frames", 33)))
        self.steps = tk.StringVar(value=str(defaults.get("steps", 24)))
        self.cfgscale = tk.StringVar(value=str(defaults.get("cfg", 6)))
        self.seed = tk.StringVar(value="-1")

        fields = [("Width", self.width), ("Height", self.height), ("Frames", self.frames), ("Steps", self.steps), ("CFG", self.cfgscale), ("Seed", self.seed)]
        for i, (lab, var) in enumerate(fields):
            ttk.Label(self.gen_tab, text=lab).grid(row=7, column=i % 3, sticky="w", padx=4)
            ttk.Entry(self.gen_tab, textvariable=var, width=12).grid(row=8, column=i % 3, sticky="w", padx=4)

        ttk.Button(self.gen_tab, text="Submit WAN workflow only", command=self.submit_wan).grid(row=9, column=0, sticky="ew", padx=4, pady=12)
        ttk.Button(self.gen_tab, text="Generate WAN → exact history output → build spritesheet", command=self.generate_sprite).grid(row=9, column=1, columnspan=2, sticky="ew", padx=4, pady=12)
        ttk.Button(self.gen_tab, text="Make posepack for action", command=self.make_posepack).grid(row=9, column=3, sticky="ew", padx=4, pady=12)
        ttk.Button(self.gen_tab, text="Run Doctor first", command=lambda: self.run_cli(["doctor", "--profile", self.profile.get()])).grid(row=9, column=4, sticky="ew", padx=4, pady=12)
        ttk.Label(
            self.gen_tab,
            text="Use t2v/debug first. I2V/reference mode uses a heavier WAN model and is better as a cloud/offload job. Posepacks are guide assets; real pose control still needs a pose-capable exported ComfyUI workflow.",
            wraplength=980,
            foreground="gray",
        ).grid(row=10, column=0, columnspan=5, sticky="w")

        self.gen_tab.rowconfigure(4, weight=1)
        self.gen_tab.columnconfigure(0, weight=1)
        self.gen_tab.columnconfigure(1, weight=1)
        self.gen_tab.columnconfigure(2, weight=1)
        self.gen_tab.columnconfigure(3, weight=1)

    def build_prompt_from_action(self):
        args = ["build-prompt", "--action", self.action.get(), "--direction", self.direction.get()]
        if self.reference_image.get():
            args.append("--reference")
        self.run_cli(args)

    def make_posepack(self):
        self.run_cli(["make-posepack", "--action", self.action.get(), "--direction", self.direction.get(), "--frames", self.frames.get(), "--size", "512"])

    def current_defaults(self):
        d = dict(self.cfg.get("wan_defaults", {}))
        d.update(self.cfg.get("profiles", {}).get(self.profile.get() if hasattr(self, "profile") else "rtx3060_12gb", {}))
        return d

    def apply_profile(self):
        d = self.current_defaults()
        self.width.set(str(d.get("width", 832)))
        self.height.set(str(d.get("height", 480)))
        self.frames.set(str(d.get("frames", 33)))
        self.steps.set(str(d.get("steps", 24)))
        self.cfgscale.set(str(d.get("cfg", 6)))

    def build_convert_tab(self):
        self.video_path = tk.StringVar()
        self.watch_folder = tk.StringVar(value=str(ROOT / self.cfg["paths"]["comfyui_output"]))
        self.blend_path = tk.StringVar()

        row = 0
        ttk.Label(self.convert_tab, text="Convert existing WAN/ComfyUI video").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Entry(self.convert_tab, textvariable=self.video_path).grid(row=row, column=0, sticky="ew", padx=4)
        ttk.Button(self.convert_tab, text="Browse video", command=lambda: self.pick_file(self.video_path, [("Video", "*.mp4 *.webm *.mov *.mkv *.avi")])).grid(row=row, column=1, padx=4)
        ttk.Button(self.convert_tab, text="Convert video", command=self.convert_video).grid(row=row, column=2, padx=4)
        row += 1

        ttk.Separator(self.convert_tab).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(self.convert_tab, text="Watch ComfyUI output folder and auto-convert new videos").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Entry(self.convert_tab, textvariable=self.watch_folder).grid(row=row, column=0, sticky="ew", padx=4)
        ttk.Button(self.convert_tab, text="Browse folder", command=lambda: self.pick_folder(self.watch_folder)).grid(row=row, column=1, padx=4)
        ttk.Button(self.convert_tab, text="Start watcher", command=self.watch_output).grid(row=row, column=2, padx=4)
        row += 1

        ttk.Separator(self.convert_tab).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(self.convert_tab, text="Blender orthographic render from .blend, then pack spritesheet").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Entry(self.convert_tab, textvariable=self.blend_path).grid(row=row, column=0, sticky="ew", padx=4)
        ttk.Button(self.convert_tab, text="Browse .blend", command=lambda: self.pick_file(self.blend_path, [("Blender", "*.blend")])).grid(row=row, column=1, padx=4)
        ttk.Button(self.convert_tab, text="Run Blender BAT", command=self.run_blender_bat).grid(row=row, column=2, padx=4)
        row += 1

        self.convert_tab.columnconfigure(0, weight=1)


    def build_prod_tab(self):
        self.pack_name = tk.StringVar(value="hero_pack")
        self.pack_character = tk.StringVar(value="single full body original game character, consistent outfit, clean silhouette")
        self.pack_root = tk.StringVar(value=str(ROOT / "output" / "packs" / "hero_pack"))
        self.qa_sprite_dir = tk.StringVar(value="")
        self.repair_output = tk.StringVar(value="")
        self.atlas_root = tk.StringVar(value=str(ROOT / "output" / "packs" / "hero_pack"))
        self.atlas_output = tk.StringVar(value=str(ROOT / "output" / "packs" / "hero_pack" / "atlas"))
        self.engine_sprite_dir = tk.StringVar(value="")
        self.engine_project = tk.StringVar(value="")
        self.engine_choice = tk.StringVar(value="godot")
        self.godot_mode = tk.StringVar(value="animatedsprite2d")

        row = 0
        ttk.Label(
            self.prod_tab,
            text="Production helpers: build action/direction pack plans, QA generated sprites, repair jitter/clipping, pack atlases, and export Godot/Unity helpers.",
            wraplength=980,
        ).grid(row=row, column=0, columnspan=5, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(self.prod_tab, text="Pack name").grid(row=row, column=0, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.pack_name).grid(row=row, column=1, sticky="ew", padx=4)
        ttk.Label(self.prod_tab, text="Character").grid(row=row, column=2, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.pack_character).grid(row=row, column=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Create pack prompts + posepacks", command=self.create_pack).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1

        ttk.Label(self.prod_tab, text="Pack/root folder").grid(row=row, column=0, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.pack_root).grid(row=row, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Browse", command=lambda: self.pick_folder(self.pack_root)).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1

        ttk.Button(self.prod_tab, text="Collect pack index", command=self.collect_pack).grid(row=row, column=0, sticky="ew", padx=4, pady=8)
        ttk.Button(self.prod_tab, text="Run pack QA", command=self.pack_quality).grid(row=row, column=1, sticky="ew", padx=4, pady=8)
        ttk.Button(self.prod_tab, text="Build atlas", command=self.build_atlas).grid(row=row, column=2, sticky="ew", padx=4, pady=8)
        ttk.Button(self.prod_tab, text="Open pack folder", command=lambda: webbrowser.open(Path(self.pack_root.get()).resolve().as_uri())).grid(row=row, column=3, sticky="ew", padx=4, pady=8)
        row += 1

        ttk.Separator(self.prod_tab).grid(row=row, column=0, columnspan=5, sticky="ew", pady=12)
        row += 1
        ttk.Label(self.prod_tab, text="QA / repair one SpriteForge output folder").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Entry(self.prod_tab, textvariable=self.qa_sprite_dir).grid(row=row, column=0, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Browse sprite folder", command=lambda: self.pick_folder(self.qa_sprite_dir)).grid(row=row, column=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Run QA", command=self.run_qa).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1
        ttk.Label(self.prod_tab, text="Repair output optional").grid(row=row, column=0, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.repair_output).grid(row=row, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Repair bottom-center", command=self.repair_sprite).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1

        ttk.Separator(self.prod_tab).grid(row=row, column=0, columnspan=5, sticky="ew", pady=12)
        row += 1
        ttk.Label(self.prod_tab, text="Atlas root folder").grid(row=row, column=0, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.atlas_root).grid(row=row, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Browse", command=lambda: self.pick_folder(self.atlas_root)).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1
        ttk.Label(self.prod_tab, text="Atlas output folder").grid(row=row, column=0, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.atlas_output).grid(row=row, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Build atlas", command=self.build_atlas).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1

        ttk.Separator(self.prod_tab).grid(row=row, column=0, columnspan=5, sticky="ew", pady=12)
        row += 1
        ttk.Label(self.prod_tab, text="Export one sprite output to engine").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Entry(self.prod_tab, textvariable=self.engine_sprite_dir).grid(row=row, column=0, columnspan=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Browse sprite folder", command=lambda: self.pick_folder(self.engine_sprite_dir)).grid(row=row, column=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Export", command=self.export_engine).grid(row=row, column=4, sticky="ew", padx=4)
        row += 1
        ttk.Label(self.prod_tab, text="Project folder optional").grid(row=row, column=0, sticky="w")
        ttk.Entry(self.prod_tab, textvariable=self.engine_project).grid(row=row, column=1, sticky="ew", padx=4)
        ttk.Combobox(self.prod_tab, textvariable=self.engine_choice, values=["godot", "unity"], width=10, state="readonly").grid(row=row, column=2, sticky="ew", padx=4)
        ttk.Combobox(self.prod_tab, textvariable=self.godot_mode, values=["animatedsprite2d", "sprite2d"], width=18, state="readonly").grid(row=row, column=3, sticky="ew", padx=4)
        ttk.Button(self.prod_tab, text="Browse project", command=lambda: self.pick_folder(self.engine_project)).grid(row=row, column=4, sticky="ew", padx=4)

        for c in range(5):
            self.prod_tab.columnconfigure(c, weight=1)

    def create_pack(self):
        root = Path(self.pack_root.get()).resolve()
        self.run_cli([
            "pack-init", "--name", self.pack_name.get(),
            "--character", self.pack_character.get(),
            "--output", str(root),
            "--actions", "idle,walk,run,attack_light,hurt,death",
            "--directions", "front,right,back,left",
            "--pose-guided", "--posepacks",
        ])

    def collect_pack(self):
        self.run_cli(["pack-collect", "--root", self.pack_root.get()])

    def pack_quality(self):
        self.run_cli(["pack-quality", "--root", self.pack_root.get()])

    def run_qa(self):
        if not self.qa_sprite_dir.get():
            messagebox.showerror("Missing sprite folder", "Choose a SpriteForge output folder containing sheet.json.")
            return
        self.run_cli(["quality", "--sprite-dir", self.qa_sprite_dir.get()])

    def repair_sprite(self):
        if not self.qa_sprite_dir.get():
            messagebox.showerror("Missing sprite folder", "Choose a SpriteForge output folder containing sheet.json.")
            return
        args = ["repair-sprite", "--sprite-dir", self.qa_sprite_dir.get(), "--anchor", "bottom-center", "--pad", "8", "--drop-loop-duplicate"]
        if self.repair_output.get():
            args += ["--output", self.repair_output.get()]
        self.run_cli(args)

    def build_atlas(self):
        self.run_cli(["pack-atlas", "--root", self.atlas_root.get(), "--output", self.atlas_output.get()])

    def export_engine(self):
        if not self.engine_sprite_dir.get():
            messagebox.showerror("Missing sprite folder", "Choose a SpriteForge output folder containing sheet.json.")
            return
        args = ["export-engine", "--engine", self.engine_choice.get(), "--sprite-dir", self.engine_sprite_dir.get()]
        if self.engine_project.get():
            args += ["--project", self.engine_project.get()]
        if self.engine_choice.get() == "godot":
            args += ["--godot-mode", self.godot_mode.get()]
        self.run_cli(args)

    def build_log_tab(self):
        self.log = tk.Text(self.log_tab, wrap="word", bg="#111", fg="#ddd", insertbackground="#ddd")
        self.log.pack(fill="both", expand=True)

    def log_line(self, text: str):
        self.log_q.put(text)

    def drain_log(self):
        try:
            while True:
                msg = self.log_q.get_nowait()
                self.log.insert("end", msg)
                self.log.see("end")
        except queue.Empty:
            pass
        self.after(100, self.drain_log)

    def run_cli(self, args):
        cmd = [sys.executable, str(ROOT / "spriteforge_unified.py")] + list(args)
        self.run_process(cmd, cwd=ROOT)

    def run_process(self, cmd, cwd=None):
        def worker():
            self.log_line("\n$ " + " ".join(map(str, cmd)) + "\n")
            try:
                proc = subprocess.Popen(cmd, cwd=str(cwd or ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                self.proc = proc
                assert proc.stdout is not None
                for line in proc.stdout:
                    self.log_line(line)
                rc = proc.wait()
                self.log_line(f"\n[exit {rc}]\n")
            except Exception as e:
                self.log_line(f"\nERROR: {e}\n")
        threading.Thread(target=worker, daemon=True).start()

    def launch_comfy_window(self):
        self.run_cli(["launch-comfy"])

    def stop_proc(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.log_line("\nSent terminate signal.\n")

    def submit_wan(self):
        self.run_cli(self.wan_args("submit-wan"))

    def generate_sprite(self):
        self.run_cli(self.wan_args("generate-sprite") + ["--start-comfy"])

    def wan_args(self, command):
        args = [
            command,
            "--mode", self.mode.get(),
            "--profile", self.profile.get(),
            "--action", self.action.get(),
            "--direction", self.direction.get(),
            "--prompt", self.prompt.get("1.0", "end").strip(),
            "--negative", self.negative.get("1.0", "end").strip(),
            "--width", self.width.get(),
            "--height", self.height.get(),
            "--frames", self.frames.get(),
            "--steps", self.steps.get(),
            "--cfg", self.cfgscale.get(),
            "--seed", self.seed.get(),
        ]
        if self.reference_image.get():
            args += ["--reference-image", self.reference_image.get()]
        return args

    def convert_video(self):
        if not self.video_path.get():
            messagebox.showerror("Missing video", "Choose a video first.")
            return
        self.run_cli(["convert-video", "--input", self.video_path.get()])

    def watch_output(self):
        self.run_cli(["watch-output", "--folder", self.watch_folder.get(), "--pattern", "*.webm"])

    def run_blender_bat(self):
        if not self.blend_path.get():
            messagebox.showerror("Missing .blend", "Choose a .blend file first.")
            return
        bat = ROOT / "blender_ortho_here.bat"
        self.run_process([str(bat), self.blend_path.get()], cwd=ROOT)

    def pick_file(self, var, filetypes):
        f = filedialog.askopenfilename(filetypes=filetypes)
        if f:
            var.set(f)

    def pick_folder(self, var):
        f = filedialog.askdirectory()
        if f:
            var.set(f)


if __name__ == "__main__":
    app = Studio()
    app.mainloop()
