from __future__ import annotations

import argparse
import os
import platform
import sys
import time
import json
from pathlib import Path
from typing import List, Optional

from services.shell_service import ensure_venv, git_clone_or_pull, install_requirements, run
from services.model_install_service import manifests_for_install_tier

ROOT = Path(__file__).resolve().parent.parent

def venv_python(venv: Path) -> Path:
    from spriteforge_commands import venv_python as _vp
    return _vp(venv)


def comfy_python(cfg: spriteforge_commands.Config) -> Path:
    from spriteforge_commands import comfy_python as _cp
    return _cp(cfg)


def install_node(url: str, dest: Path, py: Path) -> None:
    git_clone_or_pull(url, dest)
    install_requirements(py, dest / "requirements.txt", optional=True)


def install_wanvideo_optional_requirements(dest: Path, py: Path) -> None:
    install_requirements(py, dest / "fantasyportrait" / "requirements.txt", optional=True)
    sage_packages = ["sageattention"]
    if platform.system().lower() == "windows":
        sage_packages.insert(0, "triton-windows<3.8")
    run([str(py), "-m", "pip", "install", *sage_packages], check=False)


def cmd_install_spriteforge(args: argparse.Namespace) -> None:
    py = ensure_venv(ROOT / ".venv", args.python)
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    install_requirements(py, ROOT / "requirements.txt")
    print(f"SpriteForge Python ready: {py}")


def cmd_install_all(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config, cmd_doctor
    from services.model_commands import cmd_download_wan_native, cmd_model_report
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
    from spriteforge_commands import load_config
    from services.shell_service import which
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
    from spriteforge_commands import load_config
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
    from spriteforge_commands import load_config
    cfg = load_config()
    cn = cfg.comfy_dir / "custom_nodes"
    cn.mkdir(parents=True, exist_ok=True)
    install_node("https://github.com/Comfy-Org/ComfyUI-Manager.git", cn / "comfyui-manager", comfy_python(cfg))
    print("ComfyUI Manager installed/updated in custom_nodes/comfyui-manager")
