#!/usr/bin/env python3
"""
SpriteForge Unified v12: local orchestrator for ComfyUI + WAN + sprite conversion.

This package does not bundle ComfyUI repositories or WAN model weights. It manages
local installs, launches ComfyUI, submits WAN workflows, tracks the exact ComfyUI
prompt_id through /history, then converts the generated video into a sprite sheet.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
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
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

from services.config_service import ConfigService
from services.comfy_service import ComfyService
from services.model_service import ModelService
from services.job_service import JobService
from services.sprite_service import SpriteService
from services.export_service import ExportService


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
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    return Config(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))


MODEL_TIER_ALIASES = {
    "safe": "wan21_safe",
    "recommended": "wan21_safe",
    "default": "wan21_safe",
    "wan21": "wan21_safe",
    "wan2.1": "wan21_safe",
    "wan21_safe": "wan21_safe",
    "advanced": "wan22_5b",
    "better": "wan22_5b",
    "wan22": "wan22_5b",
    "wan2.2": "wan22_5b",
    "wan22_5b": "wan22_5b",
    "5b": "wan22_5b",
    "cloud": "wan22_14b_cloud",
    "wan22_14b": "wan22_14b_cloud",
    "wan22_14b_cloud": "wan22_14b_cloud",
}


def normalize_model_tier(cfg: Config, tier: Optional[str]) -> str:
    raw = (tier or cfg.raw.get("default_model_tier") or "wan21_safe").strip().lower()
    key = MODEL_TIER_ALIASES.get(raw, raw)
    tiers = cfg.raw.get("model_tiers", {})
    if key not in tiers:
        raise KeyError(f"Unknown model tier '{tier}'. Available: {', '.join(sorted(tiers))}")
    return key


def tier_config(cfg: Config, tier: Optional[str]) -> Dict[str, Any]:
    key = normalize_model_tier(cfg, tier)
    data = dict(cfg.raw.get("model_tiers", {}).get(key, {}))
    data["key"] = key
    return data


def manifests_for_install_tier(cfg: Config, tier: Optional[str]) -> List[str]:
    raw = (tier or "safe").strip().lower()
    # Installer tiers: safe = only the low-risk model; advanced/all = safe plus Wan2.2 5B.
    if raw in {"none", "skip", "cloud", "wan22_14b_cloud"}:
        return []
    if raw in {"advanced", "all", "all_local", "both", "wan21_plus_wan22", "wan2.2", "wan22", "better"}:
        keys = ["wan21_safe", "wan22_5b"]
    elif raw in {"wan22_only", "wan22_5b_only", "5b_only"}:
        keys = ["wan22_5b"]
    else:
        keys = [normalize_model_tier(cfg, raw)]
    paths = []
    for key in keys:
        manifest = cfg.raw.get("model_tiers", {}).get(key, {}).get("manifest")
        if manifest:
            paths.append(str(manifest))
    # dedupe while preserving order
    out = []
    seen = set()
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def merged_wan_defaults(cfg: Config, profile: Optional[str], mode: Optional[str] = None, tier: Optional[str] = None) -> Dict[str, Any]:
    wd: Dict[str, Any] = dict(cfg.raw.get("wan_defaults", {}))
    tc: Dict[str, Any] = {}
    if tier or not mode or mode == "auto":
        tc = tier_config(cfg, tier)
    effective_mode = mode if mode and mode != "auto" else tc.get("mode") or "t2v"
    wd["mode"] = effective_mode
    mode_defaults = cfg.raw.get("wan_modes", {}).get(effective_mode, {})
    wd.update(mode_defaults)
    if tc:
        wd.update(tc.get("defaults", {}))
        wd["model_tier"] = tc.get("key")
        wd["model_tier_label"] = tc.get("label")
    effective_profile = profile
    if not effective_profile or effective_profile == "auto":
        effective_profile = tc.get("default_profile") or cfg.raw.get("default_profile") or "rtx3060_12gb"
    if effective_profile and effective_profile != "auto":
        profiles = cfg.raw.get("profiles", {})
        if effective_profile not in profiles:
            raise KeyError(f"Unknown profile '{effective_profile}'. Available: {', '.join(sorted(profiles))}")
        wd.update(profiles[effective_profile])
        wd["profile"] = effective_profile
    return wd


def print_cmd(cmd: Sequence[str], cwd: Optional[Path] = None) -> None:
    where = f" (cwd={cwd})" if cwd else ""
    print("$ " + " ".join(f'\"{c}\"' if " " in str(c) else str(c) for c in cmd) + where, flush=True)


def run(cmd: Sequence[str], cwd: Optional[Path] = None, check: bool = True, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    print_cmd(cmd, cwd)
    return subprocess.run(list(map(str, cmd)), cwd=str(cwd) if cwd else None, check=check, env=env)


def capture(cmd: Sequence[str], cwd: Optional[Path] = None, timeout: float = 20.0) -> Tuple[int, str]:
    try:
        p = subprocess.run(list(map(str, cmd)), cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def which(exe: str) -> Optional[str]:
    return shutil.which(exe)


def python_launcher(prefer: str = "3.12") -> List[str]:
    """Return a Windows-friendly Python launcher command."""
    if os.name == "nt" and which("py"):
        for ver in [prefer, "3.13", "3.12", "3.11", ""]:
            cmd = ["py"] + ([f"-{ver}"] if ver else []) + ["-c", "import sys; print(sys.version)"]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                return ["py"] + ([f"-{ver}"] if ver else [])
            except Exception:
                pass
    return [sys.executable]


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv(venv: Path, prefer_python: str = "3.12") -> Path:
    py = venv_python(venv)
    if py.exists():
        return py
    venv.parent.mkdir(parents=True, exist_ok=True)
    run(python_launcher(prefer_python) + ["-m", "venv", str(venv)])
    return py


def comfy_python(cfg: Config) -> Path:
    # Manual install venv inside ComfyUI.
    p = cfg.comfy_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if p.exists():
        return p
    # Official Windows portable layouts.
    p2 = cfg.comfy_dir.parent / "python_embeded" / "python.exe"
    if p2.exists():
        return p2
    p3 = cfg.comfy_dir / "python_embeded" / "python.exe"
    if p3.exists():
        return p3
    return Path(sys.executable)


def git_clone_or_pull(url: str, dest: Path) -> None:
    if dest.exists() and (dest / ".git").exists():
        run(["git", "pull", "--ff-only"], cwd=dest, check=False)
    elif dest.exists() and any(dest.iterdir()):
        tmp = dest.parent / f".{dest.name}_clone_{int(time.time())}"
        print(f"Repairing non-git folder by cloning into a temporary directory: {tmp}")
        run(["git", "clone", url, str(tmp)])
        try:
            shutil.copytree(tmp, dest, dirs_exist_ok=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", url, str(dest)])


def git_rev(path: Path) -> Optional[str]:
    if not (path / ".git").exists():
        return None
    rc, out = capture(["git", "rev-parse", "--short", "HEAD"], cwd=path)
    return out.strip() if rc == 0 else None


def install_requirements(py: Path, req: Path, optional: bool = False) -> None:
    if req.exists():
        run([str(py), "-m", "pip", "install", "-r", str(req)], check=not optional)
    elif not optional:
        raise FileNotFoundError(req)


def api_get(url: str, timeout: float = 5.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
        try:
            return json.loads(data)
        except Exception:
            return data


def api_post_json(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode("utf-8")
        return json.loads(txt) if txt else {}


def is_comfy_running(cfg: Config) -> bool:
    try:
        api_get(cfg.base_url + "/system_stats", timeout=2.0)
        return True
    except Exception:
        return False


def wait_for_comfy(cfg: Config, timeout: float = 180.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_comfy_running(cfg):
            return True
        time.sleep(2)
    return False


def model_manifest_path(path: Optional[str]) -> Path:
    p = Path(path or "model_manifests/wan21_t2v_1_3b_native.json")
    if not p.is_absolute():
        p = ROOT / p
    return p


def model_manifest_files(cfg: Config, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    models_root = cfg.comfy_dir / "models"
    out = []
    default_repo = manifest.get("repo_id")
    for item in manifest.get("files", []):
        dest = models_root / item["dest_subdir"] / item["filename"]
        row = dict(item)
        row["repo_id"] = row.get("repo_id") or default_repo
        row["dest"] = str(dest)
        row["exists"] = dest.exists()
        row["size_bytes"] = dest.stat().st_size if dest.exists() else 0
        out.append(row)
    return out


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

    check("config", CONFIG_PATH.exists(), str(CONFIG_PATH), "error")
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
        m = re.search(r"(\d+)\s*MiB", out)
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


def cmd_install_spriteforge(args: argparse.Namespace) -> None:
    venv = ROOT / ".venv"
    py = ensure_venv(venv, args.python)
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    install_requirements(py, ROOT / "requirements.txt")
    print(f"SpriteForge Python ready: {py}")


def cmd_install_all(args: argparse.Namespace) -> None:
    """One-step installer: SpriteForge deps, ComfyUI, WAN nodes, Manager, and selected model tier."""
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


def install_node(url: str, dest: Path, py: Path) -> None:
    git_clone_or_pull(url, dest)
    install_requirements(py, dest / "requirements.txt", optional=True)


def install_wanvideo_optional_requirements(dest: Path, py: Path) -> None:
    install_requirements(py, dest / "fantasyportrait" / "requirements.txt", optional=True)
    sage_packages = ["sageattention"]
    if platform.system().lower() == "windows":
        sage_packages.insert(0, "triton-windows<3.8")
    run([str(py), "-m", "pip", "install", *sage_packages], check=False)


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


def start_comfy_background(cfg: Config, extra: Optional[List[str]] = None) -> subprocess.Popen:
    py = comfy_python(cfg)
    listen = cfg.raw.get("comfy", {}).get("listen", "127.0.0.1")
    port = str(cfg.raw.get("comfy", {}).get("port", 8188))
    extra_args = list(cfg.raw.get("comfy", {}).get("extra_args", [])) + list(extra or [])
    cmd = [str(py), "main.py", "--listen", str(listen), "--port", port] + extra_args
    print_cmd(cmd, cfg.comfy_dir)
    return subprocess.Popen(cmd, cwd=str(cfg.comfy_dir))


def cmd_open_comfy(args: argparse.Namespace) -> None:
    cfg = load_config()
    webbrowser.open(cfg.base_url)
    print(cfg.base_url)


def workflow_resolve(path: Optional[str], cfg: Config, profile: Optional[str] = None, mode: Optional[str] = None, tier: Optional[str] = None) -> Path:
    wd = merged_wan_defaults(cfg, profile, mode=mode, tier=tier)
    p = Path(path or wd.get("api_workflow", "workflows/wan21_t2v_1_3b_native_api.json"))
    if not p.is_absolute():
        p = ROOT / p
    return p


def node_inputs_by_id_or_class(out: Dict[str, Any], node_id: Optional[str], classes: Sequence[str]) -> Tuple[str, Dict[str, Any]]:
    if node_id and node_id in out:
        return node_id, out[node_id].setdefault("inputs", {})
    for cls in classes:
        for k, v in sorted(out.items(), key=lambda kv: str(kv[0])):
            if isinstance(v, dict) and v.get("class_type") == cls:
                return k, v.setdefault("inputs", {})
    raise KeyError(f"Workflow is missing node id={node_id!r} or classes={list(classes)}")


def clip_text_nodes(out: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if "6" in out and "7" in out:
        return out["6"].setdefault("inputs", {}), out["7"].setdefault("inputs", {})
    nodes = []
    for k, v in out.items():
        if isinstance(v, dict) and v.get("class_type") == "CLIPTextEncode":
            nodes.append((str(k), v.setdefault("inputs", {})))
    nodes.sort(key=lambda kv: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", kv[0])])
    if len(nodes) < 2:
        raise KeyError("Workflow needs at least two CLIPTextEncode nodes for positive and negative prompts")
    return nodes[0][1], nodes[1][1]


def set_input(inputs: Dict[str, Any], key_options: Sequence[str], value: Any) -> bool:
    for key in key_options:
        if key in inputs:
            inputs[key] = value
            return True
    return False


def spriteforge_prompt_from_args(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Build a prompt from action/direction fields if the user did not type one."""
    action = getattr(args, "action", None)
    if not action:
        return None
    try:
        import spriteforge_prompts as prompts  # local module
        return prompts.build_prompt(
            action=action,
            direction=getattr(args, "direction", "right") or "right",
            character=getattr(args, "character", None) or prompts.DEFAULT_CHARACTER,
            style=getattr(args, "style", None) or prompts.DEFAULT_STYLE,
            background=getattr(args, "background", None) or prompts.DEFAULT_BACKGROUND,
            extra=getattr(args, "extra_prompt", None) or "",
            reference=bool(getattr(args, "reference_image", None)),
            pose_guided=bool(getattr(args, "pose_action", None) or getattr(args, "posepack", None)),
        )
    except Exception as exc:
        print(f"Could not build action prompt: {exc}")
        return None


def stage_file_to_comfy_input(cfg: Config, file_path: str, subfolder: str = "SpriteForge") -> str:
    src = Path(file_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    dest_dir = cfg.comfy_input / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return f"{subfolder}/{src.name}".replace("\\", "/")


def find_nodes_feeding_into(workflow: Dict[str, Any], target_classes: set) -> set:
    feeding_ids = set()
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        if cls in target_classes:
            for val in node.get("inputs", {}).values():
                if isinstance(val, list) and len(val) == 2:
                    source_id = str(val[0])
                    feeding_ids.add(source_id)
    return feeding_ids


def patch_workflow_images(workflow: Dict[str, Any], reference_image_name: Optional[str], style_image_name: Optional[str]) -> Tuple[int, int]:
    ip_clip_classes = {
        "IPAdapterApply", "IPAdapterApplyAdvanced", "IPAdapter", "IPAdapterAdvanced",
        "IPAdapterEncoder", "CLIPVisionEncode", "PrepImageForClipVision", "IPAdapterFaceID"
    }
    style_source_ids = find_nodes_feeding_into(workflow, ip_clip_classes)
    if style_source_ids:
        style_source_ids = style_source_ids.union(find_nodes_feeding_into(workflow, {
            workflow[sid].get("class_type") for sid in style_source_ids if sid in workflow
        }))
        
    style_count = 0
    ref_count = 0
    
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        if cls in {"LoadImage", "LoadImageMask", "LoadImageUpload"}:
            inputs = node.setdefault("inputs", {})
            if style_image_name and node_id in style_source_ids:
                inputs["image"] = style_image_name
                if "upload" in inputs:
                    inputs["upload"] = "image"
                style_count += 1
            elif reference_image_name:
                inputs["image"] = reference_image_name
                if "upload" in inputs:
                    inputs["upload"] = "image"
                ref_count += 1
                
    if style_image_name and style_count == 0:
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") in {"LoadImage", "LoadImageMask", "LoadImageUpload"}:
                inputs = node.setdefault("inputs", {})
                inputs["image"] = style_image_name
                style_count += 1
                break
                
    return ref_count, style_count


def patch_clip_vision_nodes(workflow: Dict[str, Any], clip_vision: Optional[str]) -> int:
    if not clip_vision:
        return 0
    count = 0
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "CLIPVisionLoader":
            inputs = node.setdefault("inputs", {})
            if set_input(inputs, ["clip_name", "model_name", "clip_vision_name"], clip_vision):
                count += 1
    return count


def patch_posepack_nodes(workflow: Dict[str, Any], posepack_path: str) -> int:
    """Best-effort patch for user-exported pose workflows.

    Different custom nodes use different class/input names, so this sets common
    folder/path fields when they exist. If none exist, the posepack still gets
    recorded in the run manifest and prompt text.
    """
    pp = Path(posepack_path)
    frame_dir = pp / "frames" if pp.is_dir() and (pp / "frames").exists() else pp
    count = 0
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        cls = str(node.get("class_type", "")).lower()
        if "pose" in cls or "image" in cls or "video" in cls or "vhs" in cls:
            for key in ["directory", "image_dir", "folder", "path", "input_dir", "frame_dir"]:
                if key in inputs:
                    inputs[key] = str(frame_dir)
                    count += 1
            for key in ["image", "start_image"]:
                if key in inputs and frame_dir.is_dir():
                    first = sorted(frame_dir.glob("*.png"))[:1]
                    if first:
                        inputs[key] = str(first[0])
                        count += 1
    return count


def maybe_create_posepack(args: argparse.Namespace) -> Optional[Path]:
    if getattr(args, "posepack", None):
        return Path(args.posepack).resolve()
    action = getattr(args, "pose_action", None)
    if not action:
        return None
    try:
        import spriteforge_prompts as prompts
        spec = prompts.ACTION_TEMPLATES.get(action, {})
        frames = int(getattr(args, "pose_frames", None) or getattr(args, "frames", None) or spec.get("frames", 24))
        direction = getattr(args, "pose_direction", None) or getattr(args, "direction", "right") or "right"
        out = ROOT / "output" / "posepacks" / f"{action}_{direction}_{time.strftime('%Y%m%d_%H%M%S')}"
        prompts.make_posepack(action, direction, frames, int(getattr(args, "pose_size", 512) or 512), out)
        print(f"Posepack created: {out}")
        return out
    except Exception as exc:
        print(f"Could not create posepack: {exc}")
        return None


def patch_wan_workflow(prompt: Dict[str, Any], args: argparse.Namespace, cfg: Config) -> Dict[str, Any]:
    out = json.loads(json.dumps(prompt))
    requested_mode = getattr(args, "mode", "auto") or "auto"
    wd = merged_wan_defaults(cfg, getattr(args, "profile", None), mode=requested_mode, tier=getattr(args, "tier", None))
    mode = wd.get("mode") or ("t2v" if requested_mode == "auto" else requested_mode)

    prompt_pack = spriteforge_prompt_from_args(args)
    positive = args.prompt or (prompt_pack or {}).get("positive") or (
        "single full body original game character walking cycle, professional appealing character design, heroic adult proportions, "
        "clear readable face, distinctive outfit, strong shape language, cohesive color palette, side view, locked orthographic camera, "
        "centered, full body visible, plain bright green background, high quality 2D game sprite animation, crisp cel-shaded edges, clean silhouette"
    )
    negative = args.negative or (prompt_pack or {}).get("negative") or (
        "camera movement, zoom, cuts, close up, motion blur, changing outfit, changing identity, complex background, text, subtitles, "
        "watermark, deformed body, extra limbs, missing limbs, bad anatomy, childlike drawing, amateur doodle, crude sketch, scribbles, "
        "messy linework, ugly face, melted face, lumpy body, shapeless outfit, muddy colors, low quality"
    )

    pos_inputs, neg_inputs = clip_text_nodes(out)
    pos_inputs["text"] = positive
    neg_inputs["text"] = negative

    _, unet = node_inputs_by_id_or_class(out, "37", ["UNETLoader", "UNETLoaderGGUF"])
    set_input(unet, ["unet_name", "model_name", "ckpt_name"], args.model or wd.get("model", "wan2.1_t2v_1.3B_fp16.safetensors"))

    _, clip = node_inputs_by_id_or_class(out, "38", ["CLIPLoader", "DualCLIPLoader", "WanTextEncoderLoader"])
    set_input(clip, ["clip_name", "text_encoder_name", "model_name"], args.text_encoder or wd.get("text_encoder", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"))

    _, vae = node_inputs_by_id_or_class(out, "39", ["VAELoader"])
    set_input(vae, ["vae_name"], args.vae or wd.get("vae", "wan_2.1_vae.safetensors"))

    try:
        _, latent = node_inputs_by_id_or_class(out, "40", ["EmptyHunyuanLatentVideo", "Wan22ImageToVideoLatent", "EmptyWanVideoLatent", "EmptyLatentVideo", "EmptyLatentImage"])
    except KeyError:
        _, latent = node_inputs_by_id_or_class(out, "50", ["Wan22ImageToVideoLatent", "WanImageToVideo", "WanVaceToVideo", "WanReferenceToVideo"])
    set_input(latent, ["width"], int(args.width or wd.get("width", 832)))
    set_input(latent, ["height"], int(args.height or wd.get("height", 480)))
    if getattr(args, "preview", False):
        set_input(latent, ["length", "frames", "num_frames", "video_length"], 1)
    else:
        set_input(latent, ["length", "frames", "num_frames", "video_length"], int(args.frames or wd.get("frames", 33)))
    set_input(latent, ["batch_size"], 1)

    # Reference image and style reference image mode
    staged_reference = None
    staged_style = None
    if getattr(args, "reference_image", None):
        staged_reference = stage_file_to_comfy_input(cfg, args.reference_image)
    if getattr(args, "style_image", None):
        staged_style = stage_file_to_comfy_input(cfg, args.style_image)
        
    if staged_reference or staged_style:
        ref_patched, style_patched = patch_workflow_images(out, staged_reference, staged_style)
        print(f"Workflow image patching results: main reference patched = {ref_patched}, style reference patched = {style_patched}")

    clip_vision_name = getattr(args, "clip_vision", None) or wd.get("clip_vision")
    patched_clip_vision = patch_clip_vision_nodes(out, clip_vision_name)
    if patched_clip_vision:
        print(f"Patched CLIP vision nodes: {patched_clip_vision} -> {clip_vision_name}")

    posepack_path = maybe_create_posepack(args)
    patched_pose = 0
    if posepack_path:
        patched_pose = patch_posepack_nodes(out, str(posepack_path))
        print(f"Posepack available: {posepack_path} (patched {patched_pose} workflow fields)")

    seed = int(args.seed)
    if seed < 0:
        seed = random.randint(1, 2**48 - 1)
    _, sampler = node_inputs_by_id_or_class(out, "3", ["KSampler", "KSamplerAdvanced"])
    set_input(sampler, ["seed", "noise_seed"], seed)
    steps = int(args.steps or wd.get("steps", 30))
    if getattr(args, "preview", False):
        steps = min(steps, 10)
    set_input(sampler, ["steps"], steps)
    set_input(sampler, ["cfg", "guidance_scale"], float(args.cfg or wd.get("cfg", 6)))
    set_input(sampler, ["sampler_name", "sampler"], args.sampler or wd.get("sampler", "uni_pc"))
    set_input(sampler, ["scheduler"], args.scheduler or wd.get("scheduler", "simple"))

    try:
        _, sampling = node_inputs_by_id_or_class(out, "48", ["ModelSamplingSD3", "ModelSamplingAuraFlow", "ModelSamplingFlux"])
        set_input(sampling, ["shift"], float(args.shift or wd.get("shift", 8)))
    except KeyError:
        pass

    save_id, save = node_inputs_by_id_or_class(out, "47", ["SaveWEBM", "SaveVideo", "VHS_VideoCombine", "VideoCombine", "SaveAnimatedWEBP", "SaveImage"])
    prefix = args.output_prefix or wd.get("output_prefix", "SpriteForge/wan_sprite")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    prefix = prefix.rstrip("/") + f"_{stamp}"
    set_input(save, ["filename_prefix", "filename", "prefix"], prefix)
    set_input(save, ["fps", "frame_rate"], int(args.video_fps or wd.get("fps", 12)))

    out["_spriteforge"] = {
        "generated_at": stamp,
        "output_prefix": prefix,
        "seed": seed,
        "profile": wd.get("profile") or getattr(args, "profile", None),
        "model_tier": wd.get("model_tier") or getattr(args, "tier", None),
        "model_tier_label": wd.get("model_tier_label"),
        "mode": mode,
        "action": getattr(args, "action", None),
        "direction": getattr(args, "direction", None),
        "reference_image": staged_reference,
        "posepack": str(posepack_path) if posepack_path else None,
        "pose_nodes_patched": patched_pose if posepack_path else 0,
        "save_node": save_id,
        "workflow_patch_version": 11,
    }
    return out


def submit_prompt(cfg: Config, prompt: Dict[str, Any], client_id: Optional[str] = None) -> Any:
    payload: Dict[str, Any] = {"prompt": {k: v for k, v in prompt.items() if not str(k).startswith("_")}}
    if client_id:
        payload["client_id"] = client_id
    return api_post_json(cfg.base_url + "/prompt", payload, timeout=60.0)


def queue_wan_prompt(args: argparse.Namespace, cfg: Config) -> Tuple[Dict[str, Any], Dict[str, Any], Path]:
    workflow_path = workflow_resolve(args.workflow, cfg, profile=getattr(args, "profile", None), mode=getattr(args, "mode", "auto"), tier=getattr(args, "tier", None))
    prompt = json.loads(workflow_path.read_text(encoding="utf-8"))
    patched = patch_wan_workflow(prompt, args, cfg)

    queued_dir = ROOT / "output" / "queued_workflows"
    queued_dir.mkdir(parents=True, exist_ok=True)
    queued_path = queued_dir / f"wan_api_{time.strftime('%Y%m%d_%H%M%S')}.json"
    queued_path.write_text(json.dumps(patched, indent=2), encoding="utf-8")
    print(f"Saved patched API workflow: {queued_path}")

    resp = submit_prompt(cfg, patched, client_id=f"spriteforge-{os.getpid()}")
    prompt_id = resp.get("prompt_id") if isinstance(resp, dict) else None
    print("Queued ComfyUI prompt:")
    print(json.dumps(resp, indent=2))
    print(f"Output prefix: {patched.get('_spriteforge', {}).get('output_prefix')}")
    if prompt_id:
        print(f"Prompt ID: {prompt_id}")
    return resp, patched, queued_path


def cmd_submit_wan(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not is_comfy_running(cfg):
        raise RuntimeError(f"ComfyUI is not running at {cfg.base_url}. Launch it first.")
    queue_wan_prompt(args, cfg)


def history_entry(cfg: Config, prompt_id: str) -> Optional[Dict[str, Any]]:
    url = cfg.base_url + "/history/" + urllib.parse.quote(prompt_id)
    data = api_get(url, timeout=10)
    if isinstance(data, dict):
        if prompt_id in data:
            return data[prompt_id]
        # Some builds may return the entry directly.
        if "outputs" in data or "status" in data:
            return data
    return None


def wait_for_history(cfg: Config, prompt_id: str, timeout: float, poll_seconds: float) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last_status = "queued"
    while time.time() < deadline:
        entry = history_entry(cfg, prompt_id)
        if entry:
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = str(status.get("status_str", "")).lower()
            completed = bool(status.get("completed"))
            if status_str and status_str != last_status:
                print(f"ComfyUI status: {status_str}")
                last_status = status_str
            if completed or status_str in {"success", "completed"} or entry.get("outputs"):
                if status_str in {"error", "failed"}:
                    raise RuntimeError(f"ComfyUI prompt failed: {json.dumps(status, indent=2)}")
                return entry
            if status_str in {"error", "failed"}:
                raise RuntimeError(f"ComfyUI prompt failed: {json.dumps(status, indent=2)}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Prompt {prompt_id} was not completed before timeout.")


def recursive_file_records(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        if "filename" in obj and isinstance(obj.get("filename"), str):
            yield obj
        for v in obj.values():
            yield from recursive_file_records(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from recursive_file_records(v)


def resolve_comfy_record(cfg: Config, rec: Dict[str, Any]) -> Path:
    typ = str(rec.get("type", "output")).lower()
    if typ == "input":
        base = cfg.comfy_input
    elif typ == "temp":
        base = cfg.comfy_temp
    else:
        base = cfg.comfy_output
    sub = str(rec.get("subfolder") or "")
    return base / sub / str(rec["filename"])


def output_files_from_history(cfg: Config, entry: Dict[str, Any]) -> List[Path]:
    paths: List[Path] = []
    for rec in recursive_file_records(entry.get("outputs", entry)):
        p = resolve_comfy_record(cfg, rec)
        if p.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS:
            paths.append(p)
    # Dedupe while preserving order.
    seen = set()
    deduped = []
    for p in paths:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def stable_file(path: Path, stable_seconds: float) -> bool:
    try:
        s1 = path.stat().st_size
        time.sleep(stable_seconds)
        s2 = path.stat().st_size
        return s1 > 0 and s1 == s2
    except FileNotFoundError:
        return False


def wait_for_existing_output(paths: Sequence[Path], stable_seconds: float, timeout: float = 120.0) -> Optional[Path]:
    deadline = time.time() + timeout
    videos = [p for p in paths if p.suffix.lower() in VIDEO_EXTS]
    images = [p for p in paths if p.suffix.lower() in IMAGE_EXTS]
    candidates = videos or images
    while time.time() < deadline:
        for p in candidates:
            if p.exists() and stable_file(p, stable_seconds):
                return p
        time.sleep(2)
    return None


def find_newest_video(folder: Path, after_time: float, prefix_hint: Optional[str] = None) -> Optional[Path]:
    if not folder.exists():
        return None
    candidates = []
    hint = Path(prefix_hint).name.lower() if prefix_hint else None
    for p in folder.rglob("*"):
        if p.suffix.lower() not in VIDEO_EXTS:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_mtime < after_time:
            continue
        rank = 1
        if hint and hint not in p.stem.lower():
            rank = 0
        candidates.append((rank, st.st_mtime, p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def build_sprite_args(input_video: Path, output_dir: Path, cfg: Config, extra: Optional[List[str]] = None) -> List[str]:
    sd = cfg.raw.get("sprite_defaults", {})
    cmd = [sys.executable, str(ROOT / "spriteforge.py"), "video", "--input", str(input_video), "--output", str(output_dir)]
    cmd += ["--fps", str(sd.get("fps", 12))]
    if sd.get("cell_size"):
        cmd += ["--cell-size", str(sd.get("cell_size"))]
    if sd.get("key_color"):
        cmd += ["--key-color", str(sd.get("key_color"))]
    cmd += ["--key-tolerance", str(sd.get("key_tolerance", 45))]
    cmd += ["--anchor", str(sd.get("anchor", "bottom-center"))]
    cmd += ["--pad", str(sd.get("pad", 24))]
    cmd += ["--solidify", str(sd.get("solidify", 2))]
    if sd.get("drop_loop_duplicate", True):
        cmd += ["--drop-loop-duplicate"]
    if sd.get("preview_gif", True):
        cmd += ["--preview-gif"]
    if sd.get("report", True):
        cmd += ["--report"]
    if extra:
        cmd += extra
    return cmd


def write_run_manifest(prompt_id: Optional[str], patched: Dict[str, Any], response: Dict[str, Any], outputs: Sequence[Path], chosen: Optional[Path], sprite_dir: Optional[Path]) -> Path:
    runs_dir = ROOT / "output" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stem = prompt_id or time.strftime("%Y%m%d_%H%M%S")
    path = runs_dir / f"run_{stem}.json"
    data = {
        "prompt_id": prompt_id,
        "response": response,
        "spriteforge": patched.get("_spriteforge", {}),
        "history_outputs": [str(p) for p in outputs],
        "chosen_output": str(chosen) if chosen else None,
        "sprite_dir": str(sprite_dir) if sprite_dir else None,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Run manifest: {path}")
    return path


def cmd_generate_sprite(args: argparse.Namespace) -> None:
    cfg = load_config()
    comfy_proc: Optional[subprocess.Popen] = None
    started_at = time.time()

    if not is_comfy_running(cfg):
        if not args.start_comfy:
            raise RuntimeError(f"ComfyUI is not running at {cfg.base_url}. Use --start-comfy or launch it first.")
        comfy_proc = start_comfy_background(cfg)
        if not wait_for_comfy(cfg, timeout=args.comfy_timeout):
            raise RuntimeError("ComfyUI did not become ready before timeout.")

    response, patched, _queued_path = queue_wan_prompt(args, cfg)
    prompt_id = str(response.get("prompt_id")) if isinstance(response, dict) and response.get("prompt_id") else None
    prefix_hint = patched.get("_spriteforge", {}).get("output_prefix")

    outputs: List[Path] = []
    chosen: Optional[Path] = None

    if prompt_id and not args.no_history:
        print("Waiting for exact ComfyUI prompt history output...")
        entry = wait_for_history(cfg, prompt_id, timeout=args.timeout, poll_seconds=args.poll_seconds)
        outputs = output_files_from_history(cfg, entry)
        print("History outputs:")
        for p in outputs:
            print(f" - {p}")
        chosen = wait_for_existing_output(outputs, args.stable_seconds, timeout=180)

    if not chosen and not args.no_folder_fallback:
        print("Falling back to folder scan for newest matching video...")
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            candidate = find_newest_video(cfg.comfy_output, started_at, prefix_hint)
            if candidate and stable_file(candidate, args.stable_seconds):
                chosen = candidate
                break
            time.sleep(args.poll_seconds)

    if not chosen:
        write_run_manifest(prompt_id, patched, response if isinstance(response, dict) else {}, outputs, None, None)
        raise RuntimeError("No completed ComfyUI video was found. Check ComfyUI queue/history and run doctor.")

    if getattr(args, "preview", False):
        name = chosen.stem + "_preview"
        out_dir = cfg.sprite_output / name
        out_dir.mkdir(parents=True, exist_ok=True)
        dest_preview = out_dir / "preview_image.png"
        shutil.copy2(chosen, dest_preview)
        write_run_manifest(prompt_id, patched, response if isinstance(response, dict) else {}, outputs, chosen, out_dir)
        print(f"Generated preview image: {dest_preview}")
        if comfy_proc and args.stop_comfy:
            comfy_proc.terminate()
        return

    name = chosen.stem + "_sprite"
    out_dir = cfg.sprite_output / name
    extra = []
    if getattr(args, "fps", None) is not None:
        extra += ["--fps", str(args.fps)]
    if getattr(args, "cell_size", None):
        extra += ["--cell-size", str(args.cell_size)]
    if getattr(args, "key_color", None):
        extra += ["--key-color", str(args.key_color)]
    if getattr(args, "resolutions", None):
        extra += ["--resolutions", str(args.resolutions)]
    if getattr(args, "power_of_two", False):
        extra.append("--power-of-two")
    run(build_sprite_args(chosen, out_dir, cfg, extra=extra))
    if getattr(args, "quality_check", False):
        qc_extra = []
        if getattr(args, "qa_threshold_loop_rmse", None) is not None:
            qc_extra += ["--loop-rmse-threshold", str(args.qa_threshold_loop_rmse)]
        if getattr(args, "qa_threshold_foot_drift", None) is not None:
            qc_extra += ["--foot-drift-threshold", str(args.qa_threshold_foot_drift)]
        if getattr(args, "qa_threshold_center_drift", None) is not None:
            qc_extra += ["--center-drift-threshold", str(args.qa_threshold_center_drift)]
        run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", str(out_dir)] + qc_extra, check=False)
    write_run_manifest(prompt_id, patched, response if isinstance(response, dict) else {}, outputs, chosen, out_dir)
    print(f"Generated sprite output: {out_dir}")

    if comfy_proc and args.stop_comfy:
        comfy_proc.terminate()


def cmd_watch_output(args: argparse.Namespace) -> None:
    cfg = load_config()
    out = Path(args.output) if args.output else cfg.sprite_output
    if not out.is_absolute():
        out = ROOT / out
    folder = Path(args.folder) if args.folder else cfg.comfy_output
    if not folder.is_absolute():
        folder = ROOT / folder

    sd = cfg.raw.get("sprite_defaults", {})
    cmd = [sys.executable, str(ROOT / "spriteforge.py"), "watch", "--folder", str(folder), "--output", str(out)]
    cmd += ["--pattern", args.pattern]
    cmd += ["--fps", str(args.fps or sd.get("fps", 12))]
    cmd += ["--cell-size", str(args.cell_size or sd.get("cell_size", "512x512"))]
    if args.key_color or sd.get("key_color"):
        cmd += ["--key-color", str(args.key_color or sd.get("key_color"))]
    cmd += ["--key-tolerance", str(args.key_tolerance or sd.get("key_tolerance", 45))]
    cmd += ["--anchor", str(args.anchor or sd.get("anchor", "bottom-center"))]
    cmd += ["--pad", str(args.pad if args.pad is not None else sd.get("pad", 24))]
    cmd += ["--solidify", str(args.solidify if args.solidify is not None else sd.get("solidify", 2))]
    if sd.get("drop_loop_duplicate", True):
        cmd += ["--drop-loop-duplicate"]
    if sd.get("preview_gif", True):
        cmd += ["--preview-gif"]
    if sd.get("report", True):
        cmd += ["--report"]
    run(cmd)


def cmd_convert_video(args: argparse.Namespace) -> None:
    cfg = load_config()
    input_video = Path(args.input)
    output = Path(args.output) if args.output else cfg.sprite_output / (input_video.stem + "_sprite")
    if not output.is_absolute():
        output = ROOT / output
    run(build_sprite_args(input_video, output, cfg, args.extra or []))


def cmd_download_wan_native(args: argparse.Namespace) -> None:
    cfg = load_config()
    manifest_path = model_manifest_path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("cloud_only") and not getattr(args, "allow_heavy", False):
        raise RuntimeError("This manifest is marked cloud/heavy-GPU only and is blocked from auto-download. Use --allow-heavy only if you really intend to download it.")
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except Exception as exc:
        raise RuntimeError("huggingface_hub is required. Run setup_windows.bat first, or pip install huggingface_hub.") from exc

    tmp = ROOT / "vendor" / "model_downloads" / manifest.get("preset", "wan")
    tmp.mkdir(parents=True, exist_ok=True)
    models_root = cfg.comfy_dir / "models"
    rows = model_manifest_files(cfg, manifest)
    did_anything = False
    for row in rows:
        source = row["source"]
        filename = row["filename"]
        dest = Path(row["dest"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if args.dry_run:
            print(f"Would download {source} -> {dest} ({row.get('approx_size', 'unknown size')})")
            continue
        if dest.exists() and not args.force:
            print(f"Already exists: {dest}")
            continue
        did_anything = True
        repo_id = row.get("repo_id") or manifest.get("repo_id")
        if not repo_id:
            raise RuntimeError(f"Manifest file {filename} is missing repo_id")
        print(f"Downloading {source} from {repo_id} ({row.get('approx_size', 'unknown size')})")
        local = Path(hf_hub_download(repo_id=repo_id, filename=source, local_dir=str(tmp / str(repo_id).replace('/', '__')), resume_download=True))
        print(f"Copying to {dest}")
        shutil.copy2(local, dest)
    if args.dry_run:
        print("Dry run complete. No WAN model files were downloaded.")
    elif did_anything:
        print("Model files are in place. The installer will skip these files on future runs unless --force is used.")
    else:
        print("Model files were already present. Nothing to download.")


def cmd_model_report(args: argparse.Namespace) -> None:
    cfg = load_config()
    manifest_path = model_manifest_path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = model_manifest_files(cfg, manifest)
    ok = True
    for row in rows:
        ok = ok and row["exists"]
        size = f"{row['size_bytes'] / (1024**3):.2f} GB" if row["exists"] else row.get("approx_size", "")
        print(f"{'[OK]' if row['exists'] else '[MISSING]'} {row['dest']} {size}")
    if args.json:
        out = ROOT / "output" / "diagnostics"
        out.mkdir(parents=True, exist_ok=True)
        p = out / f"model_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        p.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"JSON report: {p}")
    if not ok:
        print("Run: python spriteforge_unified.py download-wan-native")


def cmd_model_tiers(args: argparse.Namespace) -> None:
    cfg = load_config()
    print("Available SpriteForge WAN model tiers:")
    for key, data in cfg.raw.get("model_tiers", {}).items():
        manifest = data.get("manifest")
        status = "cloud/heavy" if not data.get("local_ok", False) else "local"
        print(f"\n[{key}] {data.get('label', key)}")
        print(f"  status: {status}")
        print(f"  default profile: {data.get('default_profile')}")
        print(f"  minimum/recommended VRAM: {data.get('min_vram_gb', '?')} GB")
        print(f"  manifest: {manifest or '[none]'}")
        print(f"  recommended for: {data.get('recommended_for', '')}")
        if manifest:
            mp = model_manifest_path(manifest)
            if mp.exists():
                rows = model_manifest_files(cfg, json.loads(mp.read_text(encoding='utf-8')))
                ok = sum(1 for row in rows if row['exists'])
                print(f"  files present: {ok}/{len(rows)}")


def cmd_download_model_tier(args: argparse.Namespace) -> None:
    cfg = load_config()
    manifests = manifests_for_install_tier(cfg, args.tier)
    if not manifests:
        print(f"No local downloads are configured for tier: {args.tier}")
        return
    for manifest in manifests:
        cmd_download_wan_native(argparse.Namespace(manifest=manifest, force=args.force, dry_run=args.dry_run, allow_heavy=args.allow_heavy))
    if not args.dry_run:
        for manifest in manifests:
            cmd_model_report(argparse.Namespace(manifest=manifest, json=True))


def cmd_qa_report(args: argparse.Namespace) -> None:
    from services.qa_threshold_service import resolve_qa_thresholds, threshold_cli_args

    sprite_dir = Path(args.input)
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
        args.input,
        "--duplicate-threshold",
        str(args.duplicate_threshold),
    ] + threshold_cli_args(thresholds)
    if args.output:
        cmd += ["--output", args.output]
    run(cmd)


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


def validate_workflow_file(path: Path, print_errors: bool = True) -> bool:
    ok = True
    try:
        wf = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        if print_errors:
            print(f"[FAIL] Could not load workflow: {exc}")
        return False
    node_ids = {str(k) for k in wf if not str(k).startswith("_")}
    for k, v in wf.items():
        if str(k).startswith("_"):
            continue
        if not isinstance(v, dict) or "class_type" not in v:
            ok = False
            if print_errors:
                print(f"[FAIL] Node {k} missing class_type")
            continue
        inputs = v.get("inputs", {})
        if isinstance(inputs, dict):
            for name, val in inputs.items():
                if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                    if val[0] not in node_ids:
                        ok = False
                        if print_errors:
                            print(f"[FAIL] Node {k}.{name} links to missing node {val[0]}")
    if print_errors:
        print(f"{'[OK]' if ok else '[FAIL]'} Workflow sanity: {path}")
    return ok


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Unified ComfyUI + WAN + SpriteForge tool v12")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("doctor", help="Run system, ComfyUI, model, node, and workflow diagnostics")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--workflow", default=None)
    s.add_argument("--profile", default="auto")
    s.add_argument("--tier", default="wan21_safe")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("install-spriteforge", help="Install SpriteForge local Python dependencies")
    s.add_argument("--python", default="3.12")
    s.set_defaults(func=cmd_install_spriteforge)

    s = sub.add_parser("install-all", help="Install/update SpriteForge, ComfyUI, WAN nodes, Manager, and selected WAN model tier")
    s.add_argument("--python", default="3.12")
    s.add_argument("--torch-index", default="cu126", choices=["cu130", "cu126", "cu121"])
    s.add_argument("--skip-torch", action="store_true")
    s.add_argument("--model-tier", default="safe", help="safe/recommended=Wan2.1 1.3B, advanced=Wan2.1+Wan2.2 5B, wan22_only=only Wan2.2 5B, cloud=no local model download")
    s.add_argument("--manifest", default=None, help="Legacy/manual manifest override. Usually leave empty and use --model-tier.")
    s.add_argument("--force-models", action="store_true")
    s.add_argument("--allow-heavy-models", action="store_true", help="Allow cloud/heavy manifests if explicitly requested")
    s.add_argument("--skip-models", action="store_true", help="Install ComfyUI/nodes but do not download WAN weights")
    s.add_argument("--skip-doctor", action="store_true")
    s.add_argument("--skip-hardware-apply", action="store_true")
    s.add_argument("--snapshot", action="store_true", help="Create a rollback snapshot before updating ComfyUI/custom nodes")
    s.set_defaults(func=cmd_install_all)

    s = sub.add_parser("install-comfy", help="Install/update ComfyUI and optionally WAN/video nodes")
    s.add_argument("--python", default="3.12")
    s.add_argument("--torch-index", default="cu130", choices=["cu130", "cu126", "cu121"])
    s.add_argument("--skip-torch", action="store_true")
    s.add_argument("--nodes", action="store_true", help="Also install WanVideoWrapper and VideoHelperSuite")
    s.add_argument("--manager", action="store_true", help="Also install ComfyUI Manager into custom_nodes/comfyui-manager")
    s.set_defaults(func=cmd_install_comfy)

    s = sub.add_parser("install-nodes", help="Install/update WAN and video helper ComfyUI custom nodes")
    s.add_argument("--manager", action="store_true")
    s.set_defaults(func=cmd_install_nodes)

    s = sub.add_parser("install-manager", help="Install/update ComfyUI Manager")
    s.set_defaults(func=cmd_install_manager)

    s = sub.add_parser("launch-comfy", help="Launch ComfyUI")
    s.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args passed to ComfyUI main.py")
    s.set_defaults(func=cmd_launch_comfy)

    s = sub.add_parser("open-comfy")
    s.set_defaults(func=cmd_open_comfy)

    def add_wan_args(s: argparse.ArgumentParser) -> None:
        s.add_argument("--workflow", default=None)
        s.add_argument("--tier", default=None, help="Model tier: wan21_safe, wan22_5b, or wan22_14b_cloud. Defaults to config default_model_tier. Aliases: safe, advanced, cloud.")
        s.add_argument("--mode", default="auto", choices=["auto", "t2v", "ti2v22", "i2v", "vace", "custom"], help="WAN mode. auto chooses the mode from --tier.")
        s.add_argument("--profile", default="auto", help="WAN preset. auto uses the profile recommended by --tier.")
        s.add_argument("--prompt", required=False)
        s.add_argument("--negative", default=None)
        s.add_argument("--action", default=None, help="Build prompt from sprite action: idle, walk, run, attack_light, attack_heavy, cast, jump, hurt, death")
        s.add_argument("--direction", default="right", help="Prompt direction: front, back, left, right, three_quarter")
        s.add_argument("--character", default=None, help="Character description used by automatic prompt builder")
        s.add_argument("--style", default=None)
        s.add_argument("--background", default=None)
        s.add_argument("--extra-prompt", default=None)
        s.add_argument("--reference-image", default=None, help="Image-to-video/reference image path. Patched into common LoadImage nodes.")
        s.add_argument("--clip-vision", default=None, help="CLIP vision model for I2V, default from config")
        s.add_argument("--pose-action", default=None, help="Generate a posepack for this action and attach/patch it when workflow supports pose input")
        s.add_argument("--pose-direction", default=None)
        s.add_argument("--pose-frames", type=int, default=None)
        s.add_argument("--pose-size", type=int, default=512)
        s.add_argument("--posepack", default=None, help="Existing posepack folder to attach/patch into a custom pose workflow")
        s.add_argument("--model", default=None)
        s.add_argument("--text-encoder", default=None)
        s.add_argument("--vae", default=None)
        s.add_argument("--width", type=int, default=None)
        s.add_argument("--height", type=int, default=None)
        s.add_argument("--frames", type=int, default=None)
        s.add_argument("--video-fps", type=int, default=None)
        s.add_argument("--steps", type=int, default=None)
        s.add_argument("--cfg", type=float, default=None)
        s.add_argument("--shift", type=float, default=None)
        s.add_argument("--sampler", default=None)
        s.add_argument("--scheduler", default=None)
        s.add_argument("--seed", type=int, default=-1)
        s.add_argument("--output-prefix", default=None)
        s.add_argument("--resolutions", default=None)
        s.add_argument("--preview", action="store_true")
        s.add_argument("--style-image", default=None)
        s.add_argument("--batch-size", type=int, default=None, help="VRAM fallback hint for workflows with batch controls")
        s.add_argument("--vram-fallback", default=None, help="Internal retry hint: fp8, batch, resolution, or cpu_offload")
        s.add_argument("--cpu-offload", default=None, help="Internal retry hint for CPU/offload mode")

    s = sub.add_parser("submit-wan", help="Submit the included native Wan 2.1 T2V API workflow to a running ComfyUI server")
    add_wan_args(s)
    s.set_defaults(func=cmd_submit_wan)

    s = sub.add_parser("generate-sprite", help="Submit Wan job, wait for exact ComfyUI history output, then convert to spritesheet")
    add_wan_args(s)
    s.add_argument("--start-comfy", action="store_true")
    s.add_argument("--stop-comfy", action="store_true")
    s.add_argument("--timeout", type=float, default=3600)
    s.add_argument("--comfy-timeout", type=float, default=180)
    s.add_argument("--poll-seconds", type=float, default=5)
    s.add_argument("--stable-seconds", type=float, default=5)
    s.add_argument("--no-history", action="store_true", help="Skip prompt_id /history tracking and use folder scan only")
    s.add_argument("--no-folder-fallback", action="store_true", help="Fail if prompt history does not resolve a usable output")
    s.add_argument("--quality-check", action="store_true", help="Run SpriteForge QC after converting the generated video")
    s.add_argument("--cell-size", default=None)
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--qa-threshold-loop-rmse", type=float, default=None)
    s.add_argument("--qa-threshold-foot-drift", type=float, default=None)
    s.add_argument("--qa-threshold-center-drift", type=float, default=None)
    s.add_argument("--power-of-two", action="store_true", help="Pad final sheet to power-of-two dimensions")
    s.set_defaults(func=cmd_generate_sprite)

    s = sub.add_parser("watch-output", help="Watch ComfyUI output and convert new videos into sprites")
    s.add_argument("--folder", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--pattern", default="*.webm")
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--key-tolerance", type=float, default=None)
    s.add_argument("--anchor", default=None)
    s.add_argument("--pad", type=int, default=None)
    s.add_argument("--solidify", type=int, default=None)
    s.set_defaults(func=cmd_watch_output)

    s = sub.add_parser("convert-video", help="Convert one existing video to sprites")
    s.add_argument("--input", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_convert_video)

    s = sub.add_parser("download-wan-native", help="Download model files from a selected manifest")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-heavy", action="store_true")
    s.set_defaults(func=cmd_download_wan_native)

    s = sub.add_parser("download-model-tier", help="Download a named model tier: safe, advanced, wan22_only, cloud")
    s.add_argument("--tier", default="safe")
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-heavy", action="store_true")
    s.set_defaults(func=cmd_download_model_tier)

    s = sub.add_parser("model-tiers", help="List available model tiers and local file status")
    s.set_defaults(func=cmd_model_tiers)

    s = sub.add_parser("model-report", help="Check required model files")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_model_report)

    s = sub.add_parser("open-model-pages")
    s.set_defaults(func=cmd_open_model_pages)

    s = sub.add_parser("validate-workflow", help="Validate API workflow JSON links and optionally node classes against running ComfyUI")
    s.add_argument("--workflow", default=None)
    s.add_argument("--profile", default="auto")
    s.add_argument("--tier", default="wan21_safe")
    s.add_argument("--check-nodes", action="store_true")
    s.set_defaults(func=cmd_validate_workflow)

    s = sub.add_parser("queue-status", help="Print ComfyUI queue/history summary")
    s.add_argument("--max-chars", type=int, default=8000)
    s.set_defaults(func=cmd_queue_status)

    s = sub.add_parser("history", help="Print one ComfyUI prompt history entry and resolved output files")
    s.add_argument("prompt_id")
    s.add_argument("--max-chars", type=int, default=12000)
    s.set_defaults(func=cmd_history)

    s = sub.add_parser("build-prompt", help="Build a sprite-action prompt without running WAN")
    s.add_argument("--action", required=True)
    s.add_argument("--direction", default="right")
    s.add_argument("--character", default=None)
    s.add_argument("--style", default=None)
    s.add_argument("--background", default=None)
    s.add_argument("--extra", default="")
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_prompts.py"), "build", "--action", a.action, "--direction", a.direction] + (["--character", a.character] if a.character else []) + (["--style", a.style] if a.style else []) + (["--background", a.background] if a.background else []) + (["--extra", a.extra] if a.extra else []) + (["--reference"] if a.reference else []) + (["--pose-guided"] if a.pose_guided else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("make-posepack", help="Generate OpenPose-style guide frames for a sprite action")
    s.add_argument("--action", required=True)
    s.add_argument("--direction", default="right")
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--size", type=int, default=512)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_prompts.py"), "posepack", "--action", a.action, "--direction", a.direction, "--size", str(a.size)] + (["--frames", str(a.frames)] if a.frames else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("export-engine", help="Create Godot or Unity helper files from a SpriteForge output folder")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--engine", required=True, choices=["godot", "unity", "unreal"])
    s.add_argument("--output", default=None)
    s.add_argument("--project", default=None)
    s.add_argument("--name", default=None)
    s.add_argument("--res-path", default=None)
    s.add_argument("--godot-mode", choices=["animatedsprite2d", "sprite2d"], default="animatedsprite2d")
    s.add_argument("--naming-convention", default="default")
    s.add_argument("--pivot-mode", default="bottom-center")
    s.add_argument("--ppu", type=int, default=100)
    s.add_argument("--filter-mode", default="nearest")
    s.add_argument("--loop-flag", default="true")
    s.add_argument("--import-path", default=None)
    s.add_argument("--clip-name", default=None)
    def _export_engine(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_engine_export.py"), "export", "--sprite-dir", a.sprite_dir, "--engine", a.engine]
        for name in ["output", "project", "name", "res_path", "naming_convention", "pivot_mode", "ppu", "filter_mode", "loop_flag", "import_path", "clip_name"]:
            val = getattr(a, name, None)
            if val is not None:
                cmd += [f"--{name.replace('_', '-')}", str(val)]
        if a.engine == "godot":
            cmd += ["--godot-mode", a.godot_mode]
        run(cmd)
    s.set_defaults(func=_export_engine)

    s = sub.add_parser("snapshot", help="Snapshot ComfyUI/custom-node git revisions before updates")
    s.add_argument("--name", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "snapshot"] + (["--name", a.name] if a.name else [])))

    s = sub.add_parser("safe-update", help="Snapshot first, then git-pull ComfyUI and optionally custom nodes")
    s.add_argument("--custom-nodes", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "safe-update"] + (["--custom-nodes"] if a.custom_nodes else [])))

    s = sub.add_parser("rollback", help="Rollback ComfyUI/custom-node git repos to a saved snapshot")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "rollback", "--snapshot", a.snapshot] + (["--dry-run"] if a.dry_run else [])))

    s = sub.add_parser("quality-check", help="Run QC on one SpriteForge output folder")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", a.sprite_dir] + (["--output", a.output] if a.output else []) + (["--fail-under", str(a.fail_under)] if a.fail_under is not None else []), check=False))

    s = sub.add_parser("quality-batch", help="Run QC over every SpriteForge output folder under a root")
    s.add_argument("--root", default="output")
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "batch", "--root", a.root] + (["--output", a.output] if a.output else []) + (["--fail-under", str(a.fail_under)] if a.fail_under is not None else []), check=False))

    s = sub.add_parser("atlas-build", help="Build one multi-animation atlas from multiple SpriteForge output folders")
    s.add_argument("--sprites", nargs="*", default=[])
    s.add_argument("--root", default=None, help="Discover SpriteForge outputs under this root when --sprites is omitted")
    s.add_argument("--output", required=True)
    s.add_argument("--columns", type=int, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--name", default="spriteforge_atlas")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_atlas.py"), "atlas", "--output", a.output, "--name", a.name] + (["--root", a.root] if a.root else []) + (["--columns", str(a.columns)] if a.columns else []) + (["--cell-size", a.cell_size] if a.cell_size else []) + (["--sprites"] + a.sprites if a.sprites else [])))

    s = sub.add_parser("workflow-slots", help="Inspect an exported ComfyUI API workflow and write a slot map")
    s.add_argument("--workflow", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_workflows.py"), "slots", "--workflow", a.workflow] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("workflow-patch", help="Patch a ComfyUI API workflow using detected workflow slots")
    s.add_argument("--workflow", required=True)
    s.add_argument("--mapping", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--prompt", default=None)
    s.add_argument("--negative", default=None)
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--steps", type=int, default=None)
    s.add_argument("--cfg", type=float, default=None)
    s.add_argument("--sampler", default=None)
    s.add_argument("--scheduler", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--fps", type=int, default=None)
    s.add_argument("--output-prefix", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--text-encoder", default=None)
    s.add_argument("--vae", default=None)
    s.add_argument("--clip-vision", default=None)
    def _wf_patch(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_workflows.py"), "patch", "--workflow", a.workflow]
        for name in ["mapping", "output", "prompt", "negative", "output_prefix", "reference_image", "model", "text_encoder", "vae", "clip_vision", "sampler", "scheduler"]:
            val = getattr(a, name)
            if val is not None:
                cmd += ["--" + name.replace("_", "-"), str(val)]
        for name in ["seed", "steps", "cfg", "width", "height", "frames", "fps"]:
            val = getattr(a, name)
            if val is not None:
                cmd += ["--" + name.replace("_", "-"), str(val)]
        if a.dry_run:
            cmd += ["--dry-run"]
        run(cmd)
    s.set_defaults(func=_wf_patch)

    s = sub.add_parser("production-plan", help="Create prompts/posepacks/commands for a full character action set")
    s.add_argument("--character", default=None)
    s.add_argument("--style", default=None)
    s.add_argument("--direction", default="right")
    s.add_argument("--actions", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--pose", action="store_true")
    s.add_argument("--seeds", type=int, default=1)
    def _prod(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_batch.py"), "plan", "--direction", a.direction, "--seeds", str(a.seeds)]
        if a.character: cmd += ["--character", a.character]
        if a.style: cmd += ["--style", a.style]
        if a.actions: cmd += ["--actions", a.actions]
        if a.output: cmd += ["--output", a.output]
        if a.pose: cmd += ["--pose"]
        run(cmd)
    s.set_defaults(func=_prod)

    s = sub.add_parser("cloud-package", help="Package a GPU cloud job bundle")
    s.add_argument("--prompt", required=True)
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="quality_local")
    s.add_argument("--reference-image", default=None)
    s.add_argument("--posepack", default=None)
    s.add_argument("--workflow", default=None)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_cloud.py"), "package", "--prompt", a.prompt, "--mode", a.mode, "--profile", a.profile] + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--posepack", a.posepack] if a.posepack else []) + (["--workflow", a.workflow] if a.workflow else []) + (["--output", a.output] if a.output else [])))


    s = sub.add_parser("cloud-plan", help="Write a cloud GPU setup plan without storing API keys")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_cloud.py"), "runpod-plan"] + (["--output", a.output] if a.output else [])))


    s = sub.add_parser("quality", help="Score one sprite output for jitter, loop seam, edge clipping, duplicates, and alpha problems")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--alpha-threshold", type=int, default=8)
    s.add_argument("--duplicate-threshold", type=float, default=0.006)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", a.sprite_dir] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("repair-sprite", help="Repair a sprite output by re-anchoring frames into a stable bottom-center cell")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--anchor", default="bottom-center", choices=["bottom-center", "bottom-left", "bottom-right", "center"])
    s.add_argument("--pad", type=int, default=8)
    s.add_argument("--floor-pad", type=int, default=0)
    s.add_argument("--drop-duplicates", action="store_true")
    s.add_argument("--drop-loop-duplicate", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_qc.py"), "autofix", "--input", a.sprite_dir, "--solidify", "2"] + (["--output", a.output] if a.output else []) + (["--drop-loop-duplicate"] if a.drop_loop_duplicate else []) + (["--stabilize-anchor"] if True else [])))

    s = sub.add_parser("compare-sprites", help="Compare two sprite outputs frame-by-frame")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_compare.py"), "compare", "--a", a.a, "--b", a.b] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("pack-init", help="Create a multi-action/multi-direction character pack plan with prompts and optional posepacks")
    s.add_argument("--name", default="character_pack")
    s.add_argument("--character", default="single full body original game character, professional appealing character design, heroic adult proportions, distinctive outfit, clean silhouette")
    s.add_argument("--style", default="high quality 2D game sprite animation, polished concept-art quality, crisp cel-shaded edges, readable silhouette")
    s.add_argument("--background", default="plain bright green chroma key background")
    s.add_argument("--extra", default="")
    s.add_argument("--actions", default="idle,walk,run,attack_light,hurt,death")
    s.add_argument("--directions", default="front,right,back,left")
    s.add_argument("--output", default=None)
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--posepacks", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack.py"), "init", "--name", a.name, "--character", a.character, "--style", a.style, "--background", a.background, "--extra", a.extra, "--actions", a.actions, "--directions", a.directions] + (["--output", a.output] if a.output else []) + (["--reference"] if a.reference else []) + (["--pose-guided"] if a.pose_guided else []) + (["--posepacks"] if a.posepacks else [])))

    s = sub.add_parser("pack-collect", help="Collect finished sprite outputs into a pack index")
    s.add_argument("--root", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack.py"), "collect", "--root", a.root] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("pack-atlas", help="Build one atlas.png + atlas.json from many SpriteForge sprite outputs")
    s.add_argument("--root", default=None)
    s.add_argument("--sprite-dir", action="append", default=[])
    s.add_argument("--output", required=True)
    s.add_argument("--max-width", type=int, default=4096)
    s.add_argument("--padding", type=int, default=4)
    def _pack_atlas(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_pack.py"), "atlas", "--output", a.output, "--max-width", str(a.max_width), "--padding", str(a.padding)]
        if a.root:
            cmd += ["--root", a.root]
        for sd in a.sprite_dir or []:
            cmd += ["--sprite-dir", sd]
        return run(cmd)
    s.set_defaults(func=_pack_atlas)

    s = sub.add_parser("pack-quality", help="Run quality scoring across all sprite outputs in a pack/root folder")
    s.add_argument("--root", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack.py"), "qa", "--root", a.root] + (["--output", a.output] if a.output else [])))



    s = sub.add_parser("qa-report", help="Analyze a SpriteForge output folder for loop seams, jitter, duplicates, flicker, and anchor drift")
    s.add_argument("--input", required=True, help="SpriteForge output folder or image-frame folder")
    s.add_argument("--output", default=None)
    s.add_argument("--duplicate-threshold", type=float, default=1.25)
    s.add_argument("--qa-preset", default="auto", help="Named QA preset or 'auto' to use active/project quality gates")
    s.add_argument("--loop-rmse-threshold", type=float, default=None)
    s.add_argument("--foot-drift-threshold", type=float, default=None)
    s.add_argument("--center-drift-threshold", type=float, default=None)
    s.set_defaults(func=cmd_qa_report)

    s = sub.add_parser("autofix-sprite", help="Create a stabilized fixed copy of a sprite output folder")
    s.add_argument("--input", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--drop-loop-duplicate", action="store_true")
    s.add_argument("--stabilize-anchor", action="store_true")
    s.add_argument("--deflicker", action="store_true")
    s.add_argument("--solidify", type=int, default=2)
    s.add_argument("--blend-loop-frames", type=int, default=3)
    s.add_argument("--sharpen", action="store_true", help="Sharpen sprite edges")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_qc.py"), "autofix", "--input", a.input] + (["--output", a.output] if a.output else []) + (["--drop-loop-duplicate"] if a.drop_loop_duplicate else []) + (["--stabilize-anchor"] if a.stabilize_anchor else []) + (["--deflicker"] if a.deflicker else []) + ["--solidify", str(a.solidify)] + ["--blend-loop-frames", str(a.blend_loop_frames)] + (["--sharpen"] if a.sharpen else [])))

    s = sub.add_parser("character-pack", help="Create a character consistency pack: reference, palette, identity rules, actions, and batch BAT")
    s.add_argument("--name", required=True)
    s.add_argument("--description", required=True)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--style", default="polished 2D game sprite, professional character design, crisp cel-shaded edges, consistent palette")
    s.add_argument("--background", default="plain bright green background")
    s.add_argument("--actions", default="idle,walk,run,attack_light,attack_heavy,hurt,death")
    s.add_argument("--directions", default="right")
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="rtx3060_12gb")
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_character.py"), "create", "--name", a.name, "--description", a.description, "--style", a.style, "--background", a.background, "--actions", a.actions, "--directions", a.directions, "--mode", a.mode, "--profile", a.profile, "--seed", str(a.seed)] + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("batch-actions", help="Create a sequential generation batch from a character_profile.json")
    s.add_argument("--profile", required=True, help="Path to character_profile.json")
    s.add_argument("--actions", default=None)
    s.add_argument("--directions", default=None)
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--local-profile", default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_character.py"), "batch", "--profile", a.profile, "--mode", a.mode, "--seed", str(a.seed)] + (["--actions", a.actions] if a.actions else []) + (["--directions", a.directions] if a.directions else []) + (["--local-profile", a.local_profile] if a.local_profile else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("export-atlas", help="Export TexturePacker/Phaser/PixiJS/Aseprite/CSS/XML atlas metadata")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--format", required=True, choices=["texturepacker", "phaser", "pixijs", "aseprite", "css", "xml"])
    s.add_argument("--output", default=None)
    s.add_argument("--copy-image", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack_formats.py"), "export", "--sprite-dir", a.sprite_dir, "--format", a.format] + (["--output", a.output] if a.output else []) + (["--copy-image"] if a.copy_image else [])))

    s = sub.add_parser("remote-generate", help="Submit to a remote ComfyUI server, download exact output, and optionally convert to sprite locally")
    s.add_argument("--server", required=True)
    s.add_argument("--workflow", required=True)
    s.add_argument("--prompt", required=True)
    s.add_argument("--negative", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--video-fps", type=int, default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output-prefix", default="SpriteForge/remote_sprite")
    s.add_argument("--output", default=None)
    s.add_argument("--timeout", type=float, default=7200)
    s.add_argument("--convert", action="store_true")
    s.add_argument("--cell-size", default="512x512")
    s.add_argument("--key-color", default="auto")
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_remote.py"), "generate", "--server", a.server, "--workflow", a.workflow, "--prompt", a.prompt, "--output-prefix", a.output_prefix, "--timeout", str(a.timeout), "--cell-size", a.cell_size, "--key-color", a.key_color, "--seed", str(a.seed)] + (["--negative", a.negative] if a.negative else []) + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--width", str(a.width)] if a.width else []) + (["--height", str(a.height)] if a.height else []) + (["--frames", str(a.frames)] if a.frames else []) + (["--video-fps", str(a.video_fps)] if a.video_fps else []) + (["--output", a.output] if a.output else []) + (["--convert"] if a.convert else []) + (a.extra or [])))

    s = sub.add_parser("hardware-advisor", help="Read nvidia-smi and recommend local/cloud WAN and sprite defaults")
    s.add_argument("--apply", action="store_true", help="Back up config and apply recommended sprite defaults")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_hardware.py"), "apply"] if a.apply else [sys.executable, str(ROOT / "spriteforge_hardware.py"), "report"] + (["--output", a.output] if a.output else [])))

    return p


PRODUCTION_PASSTHROUGH = {
    "project-init", "batch-plan", "run-batch", "qa", "atlas", "export-atlas-engine", "lock-env"
}

FINAL_PASSTHROUGH = {
    "next-step": "next",
    "preflight": "preflight",
    "asset-dashboard": "dashboard",
    "release-package": "release",
    "open-latest": "latest",
}

QUEUE_PASSTHROUGH = {
    "queue-create": "create",
    "queue-run": "run",
    "queue-status": "status",
    "queue-reset": "reset",
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    # Route rich subtools before argparse consumes their --flags.
    if argv and argv[0] in FINAL_PASSTHROUGH:
        mapped = FINAL_PASSTHROUGH[argv[0]]
        try:
            return run([sys.executable, str(ROOT / "spriteforge_final.py"), mapped] + argv[1:]).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if argv and argv[0] in QUEUE_PASSTHROUGH:
        mapped = QUEUE_PASSTHROUGH[argv[0]]
        try:
            return run([sys.executable, str(ROOT / "spriteforge_queue.py"), mapped] + argv[1:]).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if argv and argv[0] in PRODUCTION_PASSTHROUGH:
        try:
            return run([sys.executable, str(ROOT / "spriteforge_production.py")] + argv).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
