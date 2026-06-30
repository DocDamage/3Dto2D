from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict

from services.shell_service import which, run, git_rev, capture
from services.wan_generation_service import is_comfy_running, api_get, history_entry, output_files_from_history
from services.model_install_service import model_manifest_path, model_manifest_files, workflow_resolve
from services.comfy_workflow_service import validate_workflow_file

ROOT = Path(__file__).resolve().parent.parent

def cmd_status(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
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
    from spriteforge_commands import load_config
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


def cmd_validate_workflow(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
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
    from spriteforge_commands import load_config
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
    from spriteforge_commands import load_config
    cfg = load_config()
    entry = history_entry(cfg, args.prompt_id)
    if not entry:
        raise RuntimeError(f"No history entry for prompt id {args.prompt_id}")
    files = output_files_from_history(cfg, entry)
    print(json.dumps(entry, indent=2)[: args.max_chars])
    print("\nResolved output files:")
    for p in files:
        print(f" - {p} {'[exists]' if p.exists() else '[missing]'}")


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
