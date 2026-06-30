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

def cmd_status(args: argparse.Namespace) -> None:
    cfg = load_config()
    print("SpriteForge Unified v12 status")
    print(f"Root: {ROOT}")
    print(f"ComfyUI: {cfg.comfy_dir} {'[OK]' if cfg.comfy_dir.exists() else '[missing]'}")
    print(f"Comfy output: {cfg.comfy_output} {'[OK]' if cfg.comfy_output.exists() else '[missing]'}")
    print(f"Sprite output: {cfg.sprite_output}")
    print(f"Comfy API: {cfg.base_url} {'[running]' if is_comfy_running(cfg) else '[not running]'}")
    print(f"Profiles: {', '.join(sorted(cfg.raw.get('profiles', {}).keys())) or '[none]'}")

    for exe in ["git", "nvidia-smi", "blender", "ffmpeg"]:
        found = which(exe)
        print(f"{exe}: {found or '[not found in PATH]'}")

    if which("nvidia-smi"):
        run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv"], check=False)

    cn = cfg.comfy_dir / "custom_nodes"
    for name in ["comfyui-manager", "ComfyUI-WanVideoWrapper", "ComfyUI-VideoHelperSuite"]:
        p = cn / name
        print(f"custom_nodes/{name}: {'[OK]' if p.exists() else '[missing]'} {git_rev(p) or ''}")

    for sub in ["diffusion_models", "text_encoders", "vae", "clip_vision", "checkpoints"]:
        d = cfg.comfy_dir / "models" / sub
        count = len(list(d.glob("*.safetensors"))) if d.exists() else 0
        print(f"models/{sub}: {count} safetensors")


def cmd_doctor(args: argparse.Namespace) -> None:
    cfg = load_config()
    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(ROOT),
        "platform": platform.platform(),
        "python": sys.version,
        "checks": [],
    }

    def check(name: str, ok: bool, detail: str = "", severity: str = "info") -> None:
        if ok:
            status = "OK"
        elif severity == "error":
            status = "FAIL"
        elif severity == "warn":
            status = "WARN"
        else:
            status = "INFO"
        print(f"[{status}] {name}: {detail}")
        report["checks"].append({"name": name, "ok": ok, "detail": detail, "severity": severity, "status": status})

    config_path = ROOT / "config" / "spriteforge_config.json"
    check("config", config_path.exists(), str(config_path), "error")
    usage = shutil.disk_usage(ROOT)
    free_gb = usage.free / (1024**3)
    check("free disk at SpriteForge root", free_gb >= 20, f"{free_gb:.1f} GB free", "warn")

    for exe in ["git", "nvidia-smi", "blender", "ffmpeg"]:
        found = which(exe)
        required = exe in {"git", "nvidia-smi"}
        check(f"PATH executable: {exe}", bool(found), found or "not found", "error" if required else "info")

    if which("nvidia-smi"):
        rc, out = capture(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"], timeout=20)
        report["nvidia_smi"] = out.strip()
        check("NVIDIA GPU query", rc == 0, out.strip().splitlines()[0] if out.strip() else "no output", "error")
        import re as _re
        m = _re.search(r"(\d+)\s*MiB", out)
        if m:
            total_mib = int(m.group(1))
            check("VRAM target", total_mib >= 11000, f"{total_mib} MiB detected", "warn")

    check("ComfyUI folder", cfg.comfy_dir.exists(), str(cfg.comfy_dir), "error")
    check("ComfyUI main.py", (cfg.comfy_dir / "main.py").exists(), str(cfg.comfy_dir / "main.py"), "error")
    check("ComfyUI output folder", cfg.comfy_output.exists(), str(cfg.comfy_output), "warn")
    check("ComfyUI API running", is_comfy_running(cfg), cfg.base_url, "warn")

    cn = cfg.comfy_dir / "custom_nodes"
    for name in ["ComfyUI-WanVideoWrapper", "ComfyUI-VideoHelperSuite"]:
        check(f"custom node: {name}", (cn / name).exists(), str(cn / name), "warn")
    check("optional custom node manager", (cn / "comfyui-manager").exists(), str(cn / "comfyui-manager"), "info")

    manifest_path = model_manifest_path(args.manifest)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = model_manifest_files(cfg, manifest)
        report["models"] = rows
        for row in rows:
            check(f"model: {row['filename']}", row["exists"], row["dest"], "error")
    else:
        check("model manifest", False, str(manifest_path), "error")

    workflow_path = workflow_resolve(args.workflow, cfg, profile=args.profile, tier=getattr(args, "tier", None))
    wf_ok = validate_workflow_file(workflow_path, print_errors=False)
    check("API workflow JSON/link sanity", wf_ok, str(workflow_path), "error")

    if is_comfy_running(cfg):
        try:
            obj = api_get(cfg.base_url + "/object_info", timeout=10)
            required = cfg.raw.get("diagnostics", {}).get("required_native_wan_nodes", [])
            for node_name in required:
                check(f"Comfy node available: {node_name}", node_name in obj, "from /object_info", "error")
        except Exception as exc:
            check("Comfy /object_info", False, str(exc), "warn")

    out_dir = ROOT / "output" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"doctor_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Doctor report: {report_path}")


# ── Install ─────────────────────────────────────────────

def cmd_install_spriteforge(args: argparse.Namespace) -> None:
    venv = ROOT / ".venv"
    py = ensure_venv(venv, args.python)
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    install_requirements(py, ROOT / "requirements.txt")
    print(f"SpriteForge Python ready: {py}")


def cmd_install_all(args: argparse.Namespace) -> None:
    cfg = load_config()
    tier = getattr(args, "model_tier", None) or "safe"
    manifest_list = [args.manifest] if getattr(args, "manifest", None) else manifests_for_install_tier(cfg, tier)
    print("=" * 72)
    print("SpriteForge full installer v12")
    print("This installs/updates ComfyUI, WAN/video nodes, and ComfyUI Manager.")
    print(f"Model install tier: {tier}")
    if not manifest_list:
        print("Model downloads: skipped for this tier.")
    else:
        print("Model manifests to verify/download:")
        for m in manifest_list:
            print(f"  - {m}")
    print("=" * 72)

    marker_dir = ROOT / "state"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / "auto_wan_install_v12_done.json"

    cmd_install_spriteforge(argparse.Namespace(python=args.python))

    if not getattr(args, "skip_hardware_apply", False):
        try:
            run([sys.executable, str(ROOT / "spriteforge_hardware.py"), "apply"], check=False)
        except Exception as exc:
            print(f"[WARN] Hardware advisor apply step skipped: {exc}")

    if getattr(args, "snapshot", False):
        try:
            run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "snapshot", "--name", "before-auto-install-v12"], check=False)
        except Exception as exc:
            print(f"[WARN] Could not create snapshot before install: {exc}")

    cmd_install_comfy(argparse.Namespace(
        python=args.python,
        torch_index=args.torch_index,
        skip_torch=args.skip_torch,
        nodes=True,
        manager=True,
    ))

    downloaded_manifests: List[str] = []
    if not getattr(args, "skip_models", False):
        for manifest in manifest_list:
            cmd_download_wan_native(argparse.Namespace(
                manifest=manifest,
                force=args.force_models,
                dry_run=False,
                allow_heavy=getattr(args, "allow_heavy_models", False),
            ))
            downloaded_manifests.append(str(manifest))
        for manifest in manifest_list:
            cmd_model_report(argparse.Namespace(manifest=manifest, json=True))

    if not getattr(args, "skip_doctor", False):
        try:
            first_manifest = manifest_list[0] if manifest_list else None
            cmd_doctor(argparse.Namespace(
                manifest=first_manifest or "model_manifests/wan21_t2v_1_3b_native.json",
                workflow=None,
                profile="auto",
                tier="wan21_safe" if tier in {"safe", "recommended", "default"} else "wan22_5b",
            ))
        except Exception as exc:
            print(f"[WARN] Doctor failed, but installation finished enough to inspect manually: {exc}")

    marker.write_text(json.dumps({
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": args.python,
        "torch_index": args.torch_index,
        "model_tier": tier,
        "manifests": downloaded_manifests,
        "models_skipped": bool(getattr(args, "skip_models", False)),
    }, indent=2), encoding="utf-8")

    print("=" * 72)
    print("SpriteForge v12 install complete.")
    print("Next step: launch ComfyUI, then run a debug sprite generation.")
    print("=" * 72)


def cmd_install_comfy(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not which("git"):
        raise RuntimeError("Git is required. Install Git for Windows, then run this again.")

    git_clone_or_pull("https://github.com/Comfy-Org/ComfyUI.git", cfg.comfy_dir)
    py = ensure_venv(cfg.comfy_dir / ".venv", args.python)
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])

    if not args.skip_torch:
        if args.torch_index.lower() == "cu130":
            run([str(py), "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--extra-index-url", "https://download.pytorch.org/whl/cu130"])
        elif args.torch_index.lower() == "cu126":
            run([str(py), "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu126"])
        elif args.torch_index.lower() == "cu121":
            run([str(py), "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu121"])
        else:
            raise RuntimeError("Unsupported --torch-index. Use cu130, cu126, cu121, or --skip-torch.")

    install_requirements(py, cfg.comfy_dir / "requirements.txt")

    if args.nodes:
        cmd_install_nodes(argparse.Namespace(manager=args.manager))

    print("ComfyUI install/update complete.")


def cmd_install_nodes(args: argparse.Namespace) -> None:
    cfg = load_config()
    cn = cfg.comfy_dir / "custom_nodes"
    cn.mkdir(parents=True, exist_ok=True)
    py = comfy_python(cfg)
    nodes = [
        ("https://github.com/kijai/ComfyUI-WanVideoWrapper.git", cn / "ComfyUI-WanVideoWrapper"),
        ("https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", cn / "ComfyUI-VideoHelperSuite"),
    ]
    for url, dest in nodes:
        install_node(url, dest, py)
        if dest.name == "ComfyUI-WanVideoWrapper":
            install_wanvideo_optional_requirements(dest, py)
    if getattr(args, "manager", False):
        install_node("https://github.com/Comfy-Org/ComfyUI-Manager.git", cn / "comfyui-manager", py)
    print("WAN/Video custom nodes install/update complete.")


def cmd_install_manager(args: argparse.Namespace) -> None:
    cfg = load_config()
    cn = cfg.comfy_dir / "custom_nodes"
    cn.mkdir(parents=True, exist_ok=True)
    install_node("https://github.com/Comfy-Org/ComfyUI-Manager.git", cn / "comfyui-manager", comfy_python(cfg))
    print("ComfyUI Manager installed/updated in custom_nodes/comfyui-manager")


# ── ComfyUI process control ─────────────────────────────

def cmd_launch_comfy(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not cfg.comfy_dir.exists():
        raise RuntimeError("ComfyUI is not installed yet. Run install-comfy first.")
    py = comfy_python(cfg)
    listen = cfg.raw.get("comfy", {}).get("listen", "127.0.0.1")
    port = str(cfg.raw.get("comfy", {}).get("port", 8188))
    extra = list(cfg.raw.get("comfy", {}).get("extra_args", []))
    if args.extra:
        extra += args.extra
    cmd = [str(py), "main.py", "--listen", str(listen), "--port", port] + extra
    print("Starting ComfyUI. Close this window or press Ctrl+C to stop it.")
    print(f"Open: http://{cfg.host}:{cfg.port}")
    run(cmd, cwd=cfg.comfy_dir, check=False)


def cmd_open_comfy(args: argparse.Namespace) -> None:
    cfg = load_config()
    webbrowser.open(cfg.base_url)
    print(cfg.base_url)


# ── WAN generation ──────────────────────────────────────

def cmd_submit_wan(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not is_comfy_running(cfg):
        raise RuntimeError(f"ComfyUI is not running at {cfg.base_url}. Launch it first.")
    queue_wan_prompt(args, cfg)


# ── Generate sprite (WAN + convert pipeline) ────────────

def cmd_generate_sprite(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not is_comfy_running(cfg):
        start_comfy_background(cfg)
        if not wait_for_comfy(cfg, timeout=180.0):
            raise RuntimeError("ComfyUI did not start within 180 seconds.")
    resp, patched, queued_path = queue_wan_prompt(args, cfg)
    prompt_id = resp.get("prompt_id") if isinstance(resp, dict) else None
    if not prompt_id:
        raise RuntimeError("Got no prompt_id from ComfyUI. Check logs.")
    entry_time = time.time()

    entry = wait_for_history(cfg, prompt_id, timeout=float(getattr(args, "timeout", 600) or 600), poll_seconds=10.0)
    outputs = output_files_from_history(cfg, entry)
    if not outputs:
        raise RuntimeError("No output files found in ComfyUI history entry.")
    video = wait_for_existing_output(outputs, stable_seconds=3.0) or find_newest_video(
        cfg.comfy_output, after_time=entry_time, prefix_hint=patched.get("_spriteforge", {}).get("output_prefix")
    )
    if video is None:
        raise RuntimeError("Could not locate a stable output video.")

    sprite_dir = Path(args.output or f"output/wan_sprite_{time.strftime('%Y%m%d_%H%M%S')}")
    sprite_cmd = build_sprite_args(video, sprite_dir.resolve(), cfg, getattr(args, "sprite_extra_args", None))
    run(sprite_cmd)
    write_run_manifest(prompt_id, patched, resp, outputs, video, sprite_dir)
    print(f"Sprite output: {sprite_dir}")


# ── Watch output ────────────────────────────────────────

def cmd_watch_output(args: argparse.Namespace) -> None:
    cfg = load_config()
    watch_dir = Path(args.folder or cfg.comfy_output)
    poll = float(getattr(args, "poll_seconds", 3) or 3)
    stable = float(getattr(args, "stable_seconds", 3) or 3)
    last_time = time.time()
    seen: set[Path] = set()

    print(f"Watching {watch_dir} for new videos. Press Ctrl+C to stop.")
    while True:
        try:
            vid = find_newest_video(watch_dir, after_time=last_time)
            if vid and vid not in seen:
                seen.add(vid)
                stamp = time.strftime("%Y%m%d_%H%M%S")
                out_dir = Path(args.output) if args.output else (ROOT / "output" / f"watch_{stamp}")
                cmd = build_sprite_args(vid, out_dir, cfg)
                print(f"New video: {vid.name} → {out_dir}")
                run(cmd)
                last_time = time.time()
            time.sleep(poll)
        except KeyboardInterrupt:
            print("Stopped.")
            return


# ── Convert video ───────────────────────────────────────

def cmd_convert_video(args: argparse.Namespace) -> None:
    cfg = load_config()
    input_video = Path(args.input)
    output_dir = Path(args.output or f"output/convert_{time.strftime('%Y%m%d_%H%M%S')}")
    cmd = build_sprite_args(input_video, output_dir.resolve(), cfg, getattr(args, "extra", None))
    run(cmd)
    print(f"Converted to sprite: {output_dir}")


# ── Model download ──────────────────────────────────────

def cmd_download_wan_native(args: argparse.Namespace) -> None:
    cfg = load_config()
    manifest_path = model_manifest_path(getattr(args, "manifest", None))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if not manifest:
        raise FileNotFoundError(f"Model manifest not found: {manifest_path}")
    rows = model_manifest_files(cfg, manifest)
    print(f"Manifest: {manifest_path.name} ({len(rows)} files)")

    for row in rows:
        dest = Path(row["dest"])
        if row["exists"] and not getattr(args, "force", False):
            print(f"  [OK] {row['filename']}")
            continue
        if getattr(args, "dry_run", False):
            print(f"  [DRY RUN] Would download {row['filename']} from {row['repo_id']}")
            continue
        repo = row["repo_id"] or manifest.get("repo_id")
        from huggingface_hub import hf_hub_download
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            hf_hub_download(repo_id=repo, filename=row["filename"], local_dir=dest.parent.parent, local_dir_use_symlinks=False)
            print(f"  [DONE] {row['filename']}")
        except Exception as exc:
            print(f"  [FAIL] {row['filename']}: {exc}")


def cmd_model_report(args: argparse.Namespace) -> None:
    cfg = load_config()
    manifest_path = model_manifest_path(getattr(args, "manifest", None))
    if not manifest_path.exists():
        raise FileNotFoundError(f"Model manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = model_manifest_files(cfg, manifest)
    present = sum(1 for r in rows if r["exists"])
    total = len(rows)
    if getattr(args, "json", False):
        print(json.dumps({"manifest": str(manifest_path), "total": total, "present": present, "files": rows}, indent=2))
    else:
        print(f"{manifest_path.name}: {present}/{total} model files present")
        for row in rows:
            status = "OK" if row["exists"] else "MISSING"
            size = f"{row['size_bytes']/1024**3:.1f} GB" if row["size_bytes"] else ""
            print(f"  [{status}] {row['filename']} {size}".strip())


def cmd_model_tiers(args: argparse.Namespace) -> None:
    cfg = load_config()
    info = model_tiers_info(cfg)
    for key, data in sorted(info.items()):
        print(f"  {key}: {data['label']} | VRAM min: {data.get('vram_min_gb', '?')} GB | Disk: {data.get('disk_gb', '?')} GB")
    print(f"\nDefault: {cfg.raw.get('default_model_tier', 'wan21_safe')}")


def cmd_download_model_tier(args: argparse.Namespace) -> None:
    cfg = load_config()
    tier = getattr(args, "tier", "safe")
    manifests = manifests_for_install_tier(cfg, tier)
    if not manifests:
        print(f"No model downloads needed for tier '{tier}'.")
        return
    for manifest in manifests:
        cmd_download_wan_native(argparse.Namespace(
            manifest=manifest,
            force=getattr(args, "force", False),
            dry_run=False,
            allow_heavy=getattr(args, "allow_heavy", False),
        ))


# ── QA report ───────────────────────────────────────────

def cmd_qa_report(args: argparse.Namespace) -> None:
    from services.qa_threshold_service import resolve_qa_thresholds, threshold_cli_args

    input_val = getattr(args, "input", getattr(args, "sprite_dir", None))
    if not input_val:
        raise ValueError("Either --input or --sprite-dir must be provided.")
        
    sprite_dir = Path(input_val)
    if not sprite_dir.is_absolute():
        sprite_dir = ROOT / sprite_dir
    thresholds = resolve_qa_thresholds(ROOT, sprite_dir, getattr(args, "qa_preset", "auto"))
    if getattr(args, "loop_rmse_threshold", None) is not None:
        thresholds["loop_rmse_threshold"] = float(args.loop_rmse_threshold)
    if getattr(args, "foot_drift_threshold", None) is not None:
        thresholds["foot_drift_threshold"] = float(args.foot_drift_threshold)
    if getattr(args, "center_drift_threshold", None) is not None:
        thresholds["center_drift_threshold"] = float(args.center_drift_threshold)
    cmd = [
        sys.executable,
        str(ROOT / "spriteforge_qc.py"),
        "report",
        "--input",
        str(input_val),
        "--duplicate-threshold",
        str(getattr(args, "duplicate_threshold", 1.25)),
    ] + threshold_cli_args(thresholds)
    if getattr(args, "output", None):
        cmd += ["--output", args.output]
    run(cmd)


# ── Misc ────────────────────────────────────────────────

def cmd_open_model_pages(args: argparse.Namespace) -> None:
    urls = [
        "https://comfyanonymous.github.io/ComfyUI_examples/wan/",
        "https://docs.comfy.org/tutorials/video/wan/wan2_2",
        "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/main/split_files/diffusion_models",
        "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/diffusion_models",
        "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/vae",
        "https://github.com/kijai/ComfyUI-WanVideoWrapper",
    ]
    for u in urls:
        webbrowser.open(u)
        print(u)


def cmd_validate_workflow(args: argparse.Namespace) -> None:
    cfg = load_config()
    path = workflow_resolve(args.workflow, cfg, profile=args.profile, tier=getattr(args, "tier", None))
    ok = validate_workflow_file(path, print_errors=True)
    if args.check_nodes and is_comfy_running(cfg):
        obj = api_get(cfg.base_url + "/object_info", timeout=10)
        wf = json.loads(path.read_text(encoding="utf-8"))
        classes = sorted({v.get("class_type") for k, v in wf.items() if isinstance(v, dict) and not str(k).startswith("_")})
        for cls in classes:
            exists = cls in obj
            ok = ok and exists
            print(f"{'[OK]' if exists else '[MISSING]'} Comfy node class: {cls}")
    elif args.check_nodes:
        print("ComfyUI is not running, so node-class validation was skipped.")
    if not ok:
        raise RuntimeError("Workflow validation failed.")


def cmd_queue_status(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not is_comfy_running(cfg):
        raise RuntimeError(f"ComfyUI is not running at {cfg.base_url}")
    for endpoint in ["/queue", "/history"]:
        try:
            data = api_get(cfg.base_url + endpoint, timeout=10)
            print(endpoint)
            print(json.dumps(data, indent=2)[: args.max_chars])
        except Exception as exc:
            print(f"Could not read {endpoint}: {exc}")


def cmd_history(args: argparse.Namespace) -> None:
    cfg = load_config()
    entry = history_entry(cfg, args.prompt_id)
    if not entry:
        raise RuntimeError(f"No history entry for prompt id {args.prompt_id}")
    files = output_files_from_history(cfg, entry)
    print(json.dumps(entry, indent=2)[: args.max_chars])
    print("\nResolved output files:")
    for p in files:
        print(f" - {p} {'[exists]' if p.exists() else '[missing]'}")


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