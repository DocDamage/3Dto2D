#!/usr/bin/env python3
"""
SpriteForge CLI command implementations — thin glue over services.

This module provides the CLI command handlers (cmd_* functions) and the CLI parser,
delegating all real logic to app/services/ modules.

┌─────────────────────────────────────────────┐
│ spriteforge_commands.py  (thin CLI glue)    │
│  - argparse CLI build_parser()              │
│  - cmd_* handlers that delegate to services │
│  - Config dataclass for convenience         │
├─────────────────────────────────────────────┤
│ services/                                   │
│  ├─ shell_service.py         (run, git, venv)│
│  ├─ model_install_service.py (tiers, install)│
│  ├─ comfy_workflow_service.py (patch, validate)│
│  └─ wan_generation_service.py (WAN, generate)│
└─────────────────────────────────────────────┘
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# ── Services ──────────────────────────────────────────────
from services.shell_service import (
    capture, ensure_venv, git_clone_or_pull, git_rev,
    install_requirements, print_cmd, python_launcher, run, venv_python as _shell_venv_python, which
)
from services.model_install_service import (
    MODEL_TIER_ALIASES,
    manifests_for_install_tier,
    merged_wan_defaults,
    model_manifest_files,
    model_manifest_path,
    model_tiers_info,
    normalize_model_tier,
    stage_file_to_comfy_input,
    tier_config,
    workflow_resolve,
)
from services.comfy_workflow_service import (
    clip_text_nodes,
    find_nodes_feeding_into,
    node_inputs_by_id_or_class,
    patch_clip_vision_nodes,
    patch_posepack_nodes,
    patch_workflow_images,
    set_input,
    validate_workflow_file,
)
from services.wan_generation_service import (
    api_get, api_post_json,
    build_sprite_args,
    find_newest_video,
    history_entry,
    is_comfy_running,
    maybe_create_posepack,
    output_files_from_history,
    patch_wan_workflow,
    queue_wan_prompt,
    resolve_comfy_record,
    recursive_file_records,
    spriteforge_prompt_from_args,
    stable_file,
    submit_prompt,
    wait_for_comfy,
    wait_for_existing_output,
    wait_for_history,
    write_run_manifest,
)
from services.model_addon_commands import cmd_download_model_addon

from services.config_service import ConfigService
from services.comfy_service import ComfyService
from services.model_service import ModelService
from services.job_service import JobService
from services.sprite_service import SpriteService
from services.export_service import ExportService
from spriteforge_utils import PYTHON


# ── Config ────────────────────────────────────────────────

@dataclass
class Config:
    raw: Dict[str, Any]

    @property
    def comfy_dir(self) -> Path:
        return self.path("paths.comfyui_dir")

    @property
    def comfy_output(self) -> Path:
        return self.path("paths.comfyui_output")

    @property
    def comfy_input(self) -> Path:
        return self.comfy_dir / "input"

    @property
    def comfy_temp(self) -> Path:
        return self.comfy_dir / "temp"

    @property
    def sprite_output(self) -> Path:
        return self.path("paths.sprite_output")

    @property
    def host(self) -> str:
        return str(self.raw.get("comfy", {}).get("host", "127.0.0.1"))

    @property
    def port(self) -> int:
        return int(self.raw.get("comfy", {}).get("port", 8188))

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def path(self, dotted: str) -> Path:
        data: Any = self.raw
        for p in dotted.split("."):
            data = data[p]
        path = Path(str(data))
        if not path.is_absolute():
            path = ROOT / path
        return path


def load_config() -> Config:
    config_path = ROOT / "config" / "spriteforge_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config: {config_path}")
    return Config(json.loads(config_path.read_text(encoding="utf-8")))


# ── ComfyUI Helpers ─────────────────────────────────────

def venv_python(venv: Path) -> Path:
    return _shell_venv_python(venv)


def comfy_python(cfg: Config) -> Path:
    p = cfg.comfy_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if p.exists():
        return p
    p2 = cfg.comfy_dir.parent / "python_embeded" / "python.exe"
    if p2.exists():
        return p2
    p3 = cfg.comfy_dir / "python_embeded" / "python.exe"
    if p3.exists():
        return p3
    return Path(sys.executable)


def start_comfy_background(cfg: Config, extra: Optional[List[str]] = None) -> subprocess.Popen:
    py = comfy_python(cfg)
    listen = cfg.raw.get("comfy", {}).get("listen", "127.0.0.1")
    port = str(cfg.raw.get("comfy", {}).get("port", 8188))
    extra_args = list(cfg.raw.get("comfy", {}).get("extra_args", [])) + list(extra or [])
    cmd = [str(py), "main.py", "--listen", str(listen), "--port", port] + extra_args
    print_cmd(cmd, cfg.comfy_dir)
    return subprocess.Popen(cmd, cwd=str(cfg.comfy_dir))


# ── Install node helpers ────────────────────────────────

def install_node(url: str, dest: Path, py: Path) -> None:
    git_clone_or_pull(url, dest)
    install_requirements(py, dest / "requirements.txt", optional=True)


def install_wanvideo_optional_requirements(dest: Path, py: Path) -> None:
    install_requirements(py, dest / "fantasyportrait" / "requirements.txt", optional=True)
    sage_packages = ["sageattention"]
    if platform.system().lower() == "windows":
        sage_packages.insert(0, "triton-windows<3.8")
    run([str(py), "-m", "pip", "install", *sage_packages], check=False)


# ═════════════════════════════════════════════════════════
#  CLI COMMAND HANDLERS
# ═════════════════════════════════════════════════════════

# ── Status / Health ─────────────────────────────────────

from services.install_commands import (
    cmd_install_spriteforge,
    cmd_install_all,
    cmd_install_comfy,
    cmd_install_nodes,
    cmd_install_manager,
)
from services.generation_commands import (
    cmd_submit_wan,
    cmd_generate_sprite,
    cmd_watch_output,
    cmd_convert_video,
)
from services.model_commands import (
    cmd_download_wan_native,
    cmd_model_report,
    cmd_model_tiers,
    cmd_download_model_tier,
    cmd_open_model_pages,
)
from services.diagnostic_commands import (
    cmd_status,
    cmd_doctor,
    cmd_validate_workflow,
    cmd_queue_status,
    cmd_history,
    cmd_qa_report,
)


def cmd_launch_comfy(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not cfg.comfy_dir.exists():
        raise RuntimeError("ComfyUI is not installed yet. Run install-comfy first.")
    py = comfy_python(cfg)
    listen = cfg.raw.get("comfy", {}).get("listen", "127.0.0.1")
    port = str(cfg.raw.get("comfy", {}).get("port", 8188))
    extra = list(cfg.raw.get("comfy", {}).get("extra_args", []))
    if getattr(args, "extra", None):
        extra += args.extra
    cmd = [str(py), "main.py", "--listen", str(listen), "--port", port] + extra
    print("Starting ComfyUI. Close this window or press Ctrl+C to stop it.")
    print(f"Open: http://{cfg.host}:{cfg.port}")
    run(cmd, cwd=cfg.comfy_dir, check=False)


def cmd_open_comfy(args: argparse.Namespace) -> None:
    cfg = load_config()
    webbrowser.open(cfg.base_url)
    print(cfg.base_url)


# ═════════════════════════════════════════════════════════
#  CLI PARSER
# ═════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spriteforge", description="SpriteForge Unified v12 — CLI")
    sub = parser.add_subparsers(dest="command", required=False)

    sp = sub.add_parser("status", help="Show system & model status")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("doctor", help="Full health/diagnostics check")
    sp.add_argument("--manifest", default=None)
    sp.add_argument("--workflow", default=None)
    sp.add_argument("--profile", default="auto")
    sp.add_argument("--tier", default=None)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("install-spriteforge", help="Install SpriteForge Python env")
    sp.add_argument("--python", default="3.12")
    sp.set_defaults(func=cmd_install_spriteforge)

    sp = sub.add_parser("install-all", help="Full install (ComfyUI + nodes + models)")
    sp.add_argument("--python", default="3.12")
    sp.add_argument("--torch-index", default="cu126")
    sp.add_argument("--skip-torch", action="store_true")
    sp.add_argument("--skip-hardware-apply", action="store_true")
    sp.add_argument("--snapshot", action="store_true")
    sp.add_argument("--model-tier", default=None)
    sp.add_argument("--manifest", default=None)
    sp.add_argument("--skip-models", action="store_true")
    sp.add_argument("--force-models", action="store_true")
    sp.add_argument("--allow-heavy-models", action="store_true")
    sp.add_argument("--skip-doctor", action="store_true")
    sp.set_defaults(func=cmd_install_all)

    sp = sub.add_parser("install-comfy", help="Install/update ComfyUI")
    sp.add_argument("--python", default="3.12")
    sp.add_argument("--torch-index", default="cu126")
    sp.add_argument("--skip-torch", action="store_true")
    sp.add_argument("--nodes", action="store_true", default=True)
    sp.add_argument("--manager", action="store_true", default=True)
    sp.set_defaults(func=cmd_install_comfy)

    sp = sub.add_parser("install-nodes", help="Install WAN custom nodes")
    sp.add_argument("--manager", action="store_true")
    sp.set_defaults(func=cmd_install_nodes)

    sp = sub.add_parser("install-manager", help="Install ComfyUI Manager")
    sp.set_defaults(func=cmd_install_manager)

    sp = sub.add_parser("launch-comfy", help="Start ComfyUI server")
    sp.add_argument("--extra", nargs="*", default=[])
    sp.set_defaults(func=cmd_launch_comfy)

    sp = sub.add_parser("open-comfy", help="Open ComfyUI in browser")
    sp.set_defaults(func=cmd_open_comfy)

    sp = sub.add_parser("submit-wan", help="Submit WAN prompt to ComfyUI")
    sp.add_argument("--workflow", default=None)
    sp.add_argument("--prompt", default=None)
    sp.add_argument("--negative", default=None)
    sp.add_argument("--mode", default="auto")
    sp.add_argument("--profile", default=None)
    sp.add_argument("--tier", default=None)
    sp.add_argument("--action", default=None)
    sp.add_argument("--direction", default="right")
    sp.add_argument("--character", default=None)
    sp.add_argument("--style", default=None)
    sp.add_argument("--background", default=None)
    sp.add_argument("--extra-prompt", default=None)
    sp.add_argument("--reference-image", default=None)
    sp.add_argument("--style-image", default=None)
    sp.add_argument("--posepack", default=None)
    sp.add_argument("--pose-action", default=None)
    sp.add_argument("--pose-frames", type=int, default=None)
    sp.add_argument("--pose-size", type=int, default=None)
    sp.add_argument("--pose-direction", default=None)
    sp.add_argument("--clip-vision", default=None)
    sp.add_argument("--seed", type=int, default=-1)
    sp.add_argument("--steps", type=int, default=None)
    sp.add_argument("--cfg", type=float, default=None)
    sp.add_argument("--sampler", default=None)
    sp.add_argument("--scheduler", default=None)
    sp.add_argument("--shift", type=float, default=None)
    sp.add_argument("--model", default=None)
    sp.add_argument("--text-encoder", default=None)
    sp.add_argument("--vae", default=None)
    sp.add_argument("--width", type=int, default=None)
    sp.add_argument("--height", type=int, default=None)
    sp.add_argument("--frames", type=int, default=None)
    sp.add_argument("--video-fps", type=int, default=None)
    sp.add_argument("--output-prefix", default=None)
    sp.add_argument("--preview", action="store_true")
    sp.set_defaults(func=cmd_submit_wan)

    sp = sub.add_parser("generate-sprite", help="Full pipeline: WAN submit + sprite conversion")
    sp.add_argument("--workflow", default=None)
    sp.add_argument("--prompt", default=None)
    sp.add_argument("--negative", default=None)
    sp.add_argument("--mode", default="auto")
    sp.add_argument("--profile", default=None)
    sp.add_argument("--tier", default=None)
    sp.add_argument("--action", default=None)
    sp.add_argument("--direction", default="right")
    sp.add_argument("--character", default=None)
    sp.add_argument("--style", default=None)
    sp.add_argument("--background", default=None)
    sp.add_argument("--extra-prompt", default=None)
    sp.add_argument("--reference-image", default=None)
    sp.add_argument("--style-image", default=None)
    sp.add_argument("--posepack", default=None)
    sp.add_argument("--pose-action", default=None)
    sp.add_argument("--pose-frames", type=int, default=None)
    sp.add_argument("--pose-size", type=int, default=None)
    sp.add_argument("--pose-direction", default=None)
    sp.add_argument("--clip-vision", default=None)
    sp.add_argument("--seed", type=int, default=-1)
    sp.add_argument("--steps", type=int, default=None)
    sp.add_argument("--cfg", type=float, default=None)
    sp.add_argument("--sampler", default=None)
    sp.add_argument("--scheduler", default=None)
    sp.add_argument("--shift", type=float, default=None)
    sp.add_argument("--model", default=None)
    sp.add_argument("--text-encoder", default=None)
    sp.add_argument("--vae", default=None)
    sp.add_argument("--width", type=int, default=None)
    sp.add_argument("--height", type=int, default=None)
    sp.add_argument("--frames", type=int, default=None)
    sp.add_argument("--video-fps", type=int, default=None)
    sp.add_argument("--output-prefix", default=None)
    sp.add_argument("--output", default=None)
    sp.add_argument("--timeout", type=float, default=600.0)
    sp.add_argument("--sprite-extra-args", nargs="*", default=None)
    sp.add_argument("--preview", action="store_true")
    sp.set_defaults(func=cmd_generate_sprite)

    sp = sub.add_parser("watch-output", help="Watch ComfyUI output for new videos and auto-convert")
    sp.add_argument("--folder", default=None)
    sp.add_argument("--output", default=None)
    sp.add_argument("--poll-seconds", type=float, default=3.0)
    sp.add_argument("--stable-seconds", type=float, default=3.0)
    sp.set_defaults(func=cmd_watch_output)

    sp = sub.add_parser("convert-video", help="Convert a video to spritesheet")
    sp.add_argument("--input", required=True)
    sp.add_argument("--output", default=None)
    sp.add_argument("--extra", nargs="*", default=None)
    sp.set_defaults(func=cmd_convert_video)

    sp = sub.add_parser("download-wan-native", help="Download WAN model files from a manifest")
    sp.add_argument("--manifest", default=None)
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--allow-heavy", action="store_true")
    sp.set_defaults(func=cmd_download_wan_native)

    sp = sub.add_parser("model-report", help="Show which model files are present")
    sp.add_argument("--manifest", default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_model_report)

    sp = sub.add_parser("model-tiers", help="List model tiers and their requirements")
    sp.set_defaults(func=cmd_model_tiers)

    sp = sub.add_parser("download-model-tier", help="Download models for a tier")
    sp.add_argument("--tier", default=None)
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--allow-heavy", action="store_true")
    sp.set_defaults(func=cmd_download_model_tier)

    sp = sub.add_parser("qa-report", help="Run QA on a sprite directory")
    sp.add_argument("--sprite-dir", required=True)
    sp.set_defaults(func=cmd_qa_report)

    sp = sub.add_parser("open-model-pages", help="Open browser tabs for WAN/ComfyUI model pages")
    sp.set_defaults(func=cmd_open_model_pages)

    sp = sub.add_parser("validate-workflow", help="Validate a workflow JSON against ComfyUI")
    sp.add_argument("--workflow", default=None)
    sp.add_argument("--profile", default=None)
    sp.add_argument("--tier", default=None)
    sp.add_argument("--check-nodes", action="store_true")
    sp.set_defaults(func=cmd_validate_workflow)

    sp = sub.add_parser("queue-status", help="Show ComfyUI queue/history status")
    sp.add_argument("--max-chars", type=int, default=4000)
    sp.set_defaults(func=cmd_queue_status)

    sp = sub.add_parser("history", help="Show ComfyUI history entry for a prompt ID")
    sp.add_argument("prompt_id")
    sp.add_argument("--max-chars", type=int, default=4000)
    sp.set_defaults(func=cmd_history)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
