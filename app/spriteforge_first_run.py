#!/usr/bin/env python3
"""Beginner-first setup wizard for SpriteForge."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import tkinter as tk

from spriteforge_utils import get_app_version, apply_dark_theme

ROOT = Path(__file__).resolve().parent
PY = str((ROOT / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else (ROOT / ".venv" / "bin" / "python"))
if not Path(PY).exists():
    PY = sys.executable
CONFIG = ROOT / "config" / "spriteforge_config.json"


class Wizard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        version = get_app_version()
        self.title(f"SpriteForge Studio {version} - First Run Wizard")
        self.geometry("980x720")
        self.minsize(860, 620)
        apply_dark_theme(self)
        self.proc: subprocess.Popen | None = None
        self.create_widgets()
        self.log("Welcome. Start with 'Run Preflight Check'. The installer now automatically downloads the Wan 2.1 1.3B model set when you run full setup.")

    def create_widgets(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Label(self, text="SpriteForge First Run", font=("Segoe UI", 18, "bold"))
        header.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 4))
        sub = ttk.Label(self, text="Guided setup, recovery, and validation. Use this when installing for the first time or when something breaks.")
        sub.grid(row=0, column=1, sticky="e", padx=16, pady=(14, 4))

        left = ttk.Frame(self, padding=12)
        left.grid(row=1, column=0, sticky="ns")
        right = ttk.Frame(self, padding=(0, 12, 12, 12))
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        buttons = [
            ("1. Run Preflight Check", self.preflight),
            ("2. Install / Repair Python Deps", lambda: self.run_cmd("Install/Repair Python Deps", [PY, "-m", "pip", "install", "-r", "requirements.txt"])),
            ("3. Install Everything + Auto-Download WAN Models", lambda: self.run_cmd("Install Everything + WAN Models", [PY, "spriteforge_unified.py", "install-all"])),
            ("4. Repair / Resume WAN Model Download", lambda: self.run_cmd("Repair WAN Models", [PY, "spriteforge_unified.py", "download-wan-native"])),
            ("5. Validate / Doctor", lambda: self.run_cmd("Doctor", [PY, "spriteforge_unified.py", "doctor"])),
            ("6. Make No-GPU Demo Sprite", lambda: self.run_cmd("No-GPU Demo", [PY, "spriteforge_demo.py"], self.open_outputs)),
            ("Open Easy Mode", self.open_easy),
            ("Open Outputs Folder", self.open_outputs),
            ("Collect Support Bundle", lambda: self.run_cmd("Support Bundle", [PY, "spriteforge_support_bundle.py"])),
            ("Open Troubleshooting Docs", self.open_docs),
        ]
        for i, (text, cmd) in enumerate(buttons):
            b = ttk.Button(left, text=text, command=cmd, width=34)
            b.grid(row=i, column=0, sticky="ew", pady=4)

        ttk.Separator(left).grid(row=len(buttons), column=0, sticky="ew", pady=10)
        self.run_all_btn = ttk.Button(left, text="One-Click Setup + Demo", command=self.one_click_setup)
        self.run_all_btn.grid(row=len(buttons)+1, column=0, sticky="ew", pady=4)
        ttk.Button(left, text="Reset First-Run Marker", command=self.reset_marker).grid(row=len(buttons)+2, column=0, sticky="ew", pady=4)

        self.logbox = ScrolledText(right, wrap="word", font=("Consolas", 10), bg="#121212", fg="#e0e0e0", insertbackground="#e0e0e0", bd=0, highlightthickness=1, highlightbackground="#3a3a3a", highlightcolor="#00adb5")
        self.logbox.grid(row=0, column=0, sticky="nsew")
        self.progress = ttk.Progressbar(right, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 0))

    def log(self, msg: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.logbox.insert("end", f"[{stamp}] {msg}\n")
        self.logbox.see("end")
        self.update_idletasks()

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def run_cmd(self, title: str, cmd: list[str], on_done=None) -> None:
        if self.proc is not None:
            messagebox.showwarning("Busy", "A command is already running.")
            return
        self.log(f"\n=== {title} ===")
        self.log("$ " + " ".join(cmd))
        self.set_busy(True)

        def worker() -> None:
            try:
                self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                assert self.proc.stdout is not None
                for line in self.proc.stdout:
                    self.after(0, self.log, line.rstrip())
                code = self.proc.wait()
                self.after(0, self.log, f"=== finished: exit {code} ===")
                if code == 0 and on_done:
                    self.after(0, on_done)
            except Exception as exc:
                self.after(0, self.log, f"ERROR: {exc}")
            finally:
                self.proc = None
                self.after(0, self.set_busy, False)

        threading.Thread(target=worker, daemon=True).start()

    def preflight(self) -> None:
        self.log("\n=== Preflight Check ===")
        checks: list[tuple[str, str, str]] = []
        # writable
        try:
            p = ROOT / "logs" / "preflight_write_test.tmp"
            p.parent.mkdir(exist_ok=True)
            p.write_text("ok", encoding="utf-8")
            p.unlink()
            checks.append(("PASS", "Folder is writable", str(ROOT)))
        except Exception as exc:
            checks.append(("FAIL", "Folder is not writable", str(exc)))
        # Python
        checks.append(("PASS", "Python", sys.version.split()[0]))
        # Git
        git = shutil.which("git")
        checks.append(("PASS" if git else "WARN", "Git", git or "Not found. Needed for ComfyUI install/update."))
        # NVIDIA
        nvsmi = shutil.which("nvidia-smi")
        if nvsmi:
            try:
                out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True, timeout=15)
                checks.append(("PASS", "NVIDIA GPU", out.strip().replace("\n", " | ")))
            except Exception as exc:
                checks.append(("WARN", "NVIDIA GPU", f"nvidia-smi exists but failed: {exc}"))
        else:
            checks.append(("WARN", "NVIDIA GPU", "nvidia-smi not found. Install/update NVIDIA driver if WAN will run locally."))
        # Disk
        total, used, free = shutil.disk_usage(ROOT)
        free_gb = free / (1024**3)
        status = "PASS" if free_gb >= 50 else "WARN"
        checks.append((status, "Disk free", f"{free_gb:.1f} GB free. 50+ GB recommended for ComfyUI + models."))
        # venv deps
        for mod in ["PIL", "numpy", "cv2", "imageio", "huggingface_hub"]:
            try:
                __import__(mod)
                checks.append(("PASS", f"Python module: {mod}", "installed"))
            except Exception:
                checks.append(("WARN", f"Python module: {mod}", "missing; click Install / Repair Python Deps"))
        # Config/model checks
        comfy_dir = ROOT / "vendor" / "ComfyUI"
        checks.append(("PASS" if comfy_dir.exists() else "WARN", "ComfyUI folder", str(comfy_dir) if comfy_dir.exists() else "not installed yet"))
        required_models = [
            ROOT / "vendor" / "ComfyUI" / "models" / "text_encoders" / "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            ROOT / "vendor" / "ComfyUI" / "models" / "vae" / "wan_2.1_vae.safetensors",
            ROOT / "vendor" / "ComfyUI" / "models" / "diffusion_models" / "wan2.1_t2v_1.3B_fp16.safetensors",
        ]
        present = sum(1 for p in required_models if p.exists())
        checks.append(("PASS" if present == len(required_models) else "WARN", "WAN 2.1 1.3B models", f"{present}/{len(required_models)} files found"))
        # ComfyUI running
        try:
            with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=1.0) as r:
                checks.append(("PASS", "ComfyUI server", f"running, HTTP {getattr(r, 'status', 200)}"))
        except Exception:
            checks.append(("WARN", "ComfyUI server", "not running. Launch it after setup."))

        for status, name, detail in checks:
            self.log(f"{status:4} | {name:28} | {detail}")
        self.log("Preflight complete. WARN is not always fatal; FAIL needs fixing.")

    def one_click_setup(self) -> None:
        if self.proc is not None:
            return
        if not messagebox.askyesno("One-Click Setup", "This can download/update ComfyUI and large WAN model files. Continue?"):
            return
        steps = [
            ("Install/Repair Python Deps", [PY, "-m", "pip", "install", "-r", "requirements.txt"]),
            ("Install Everything + Auto-Download WAN Models", [PY, "spriteforge_unified.py", "install-all"]),
            ("Doctor", [PY, "spriteforge_unified.py", "doctor"]),
            ("No-GPU Demo", [PY, "spriteforge_demo.py"]),
        ]
        self.set_busy(True)

        def worker() -> None:
            for title, cmd in steps:
                self.after(0, self.log, f"\n=== {title} ===")
                self.after(0, self.log, "$ " + " ".join(cmd))
                try:
                    cp = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    assert cp.stdout is not None
                    for line in cp.stdout:
                        self.after(0, self.log, line.rstrip())
                    code = cp.wait()
                    self.after(0, self.log, f"=== {title} exit {code} ===")
                    if code != 0:
                        self.after(0, self.log, "Stopping one-click setup because this step failed. Use Collect Support Bundle if needed.")
                        break
                except Exception as exc:
                    self.after(0, self.log, f"ERROR: {exc}")
                    break
            self.after(0, self.set_busy, False)

        threading.Thread(target=worker, daemon=True).start()

    def open_easy(self) -> None:
        (ROOT / ".first_run_complete").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        subprocess.Popen([PY, "spriteforge_easy.py"], cwd=str(ROOT))
        self.destroy()

    def open_outputs(self) -> None:
        out = ROOT / "output"
        out.mkdir(exist_ok=True)
        self.open_path(out)

    def open_docs(self) -> None:
        self.open_path(ROOT / "docs")

    def open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.log(f"Could not open {path}: {exc}")

    def reset_marker(self) -> None:
        try:
            (ROOT / ".first_run_complete").unlink(missing_ok=True)
            self.log("First-run marker reset.")
        except Exception as exc:
            self.log(f"Could not reset marker: {exc}")


if __name__ == "__main__":
    Wizard().mainloop()
