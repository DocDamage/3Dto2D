from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from services.easy_helpers import (
    python_preference,
    resolve_root_path,
    is_comfy_running,
    short_path,
    find_recent_sprite_outputs,
    open_path,
    pycmd,
    nvidia_summary,
    load_thumbnail,
)
from spriteforge_utils import load_json, save_json
from spriteforge_utils import PYTHON

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
EASY_CONFIG_PATH = ROOT / "config" / "easy_mode.json"
DROP_VIDEOS_DIR = ROOT / "01_DROP_VIDEOS_HERE"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")

class EasyActionsMixin:
    def pycmd(self, *args: str) -> List[str]:
        return pycmd(*args)

    def save_easy_settings(self) -> None:
        data = load_json(EASY_CONFIG_PATH, {})
        for k, var in self.vars.items():
            try:
                data[k] = var.get()
            except Exception:
                pass
        save_json(EASY_CONFIG_PATH, data)
        self.easy = data

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
            nvidia = nvidia_summary()
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

    def load_thumbnail(self, folder: Path) -> Optional[Any]:
        if not hasattr(self, "_thumb_cache"):
            self._thumb_cache = {}
        return load_thumbnail(folder, self._thumb_cache)

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

    def browse_video_file(self) -> None:
        from spriteforge_easy import VIDEO_EXTS
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
