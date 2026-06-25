#!/usr/bin/env python3
"""Local hardware advisor for SpriteForge/ComfyUI/WAN settings."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "spriteforge_config.json"


def capture(cmd, timeout=15):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def parse_nvidia_smi() -> Dict[str, Any]:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "error": "nvidia-smi not found in PATH"}
    rc, out = capture(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"])
    if rc != 0:
        return {"available": False, "error": out.strip()}
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            try:
                total = int(float(parts[1]))
                free = int(float(parts[2]))
            except Exception:
                total = free = 0
            gpus.append({"name": parts[0], "memory_total_mib": total, "memory_free_mib": free, "driver_version": parts[3]})
    return {"available": bool(gpus), "gpus": gpus, "raw": out}


def recommendation(total_mib: int) -> Dict[str, Any]:
    gb = total_mib / 1024
    if gb >= 48:
        return {
            "tier": "heavy_local",
            "profile": "quality_local",
            "wan_path": "Wan 14B/I2V/VACE may be realistic locally depending on workflow/offload.",
            "sprite_defaults": {"cell_size": "768x768", "fps": 12, "frames": 49},
        }
    if gb >= 24:
        return {
            "tier": "cloud_or_24gb_local",
            "profile": "i2v_cloud_24gb_plus",
            "wan_path": "Wan 2.2 TI2V-5B style paths are in 24GB-class territory with offload; 14B still prefers much more VRAM.",
            "sprite_defaults": {"cell_size": "512x512", "fps": 12, "frames": 33},
        }
    if gb >= 11:
        return {
            "tier": "rtx3060_12gb",
            "profile": "rtx3060_12gb",
            "wan_path": "Use Wan 2.1 T2V 1.3B locally. Treat I2V/VACE/14B as cloud jobs.",
            "sprite_defaults": {"cell_size": "512x512", "fps": 12, "frames": 33},
        }
    if gb >= 8:
        return {
            "tier": "low_vram_8gb",
            "profile": "sprite_fast",
            "wan_path": "Try smaller/quantized/offloaded workflows only; keep clips short and resolution low.",
            "sprite_defaults": {"cell_size": "384x384", "fps": 8, "frames": 17},
        }
    return {
        "tier": "not_recommended_for_local_wan",
        "profile": "debug",
        "wan_path": "Use cloud for WAN; local machine can still convert videos to spritesheets.",
        "sprite_defaults": {"cell_size": "256x256", "fps": 8, "frames": 17},
    }


def cmd_report(args: argparse.Namespace) -> None:
    info = parse_nvidia_smi()
    best = None
    if info.get("gpus"):
        best = max(info["gpus"], key=lambda g: g.get("memory_total_mib", 0))
        rec = recommendation(int(best.get("memory_total_mib", 0)))
    else:
        rec = recommendation(0)
    report = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "nvidia_smi": info,
        "selected_gpu": best,
        "recommendation": rec,
        "notes": [
            "Speccy may misreport RTX 3060 VRAM as 4095MB; nvidia-smi is the value that matters.",
            "Keep WAN clips short for sprite work. Consistency beats resolution.",
        ],
    }
    out = Path(args.output or (ROOT / "output" / "diagnostics" / f"hardware_advisor_{time.strftime('%Y%m%d_%H%M%S')}.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote: {out}")


def cmd_apply(args: argparse.Namespace) -> None:
    if not CONFIG.exists():
        raise FileNotFoundError(CONFIG)
    info = parse_nvidia_smi()
    best = max(info.get("gpus", []), key=lambda g: g.get("memory_total_mib", 0), default={"memory_total_mib": 0})
    rec = recommendation(int(best.get("memory_total_mib", 0)))
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    sd = cfg.setdefault("sprite_defaults", {})
    sd.update({
        "fps": rec["sprite_defaults"]["fps"],
        "cell_size": rec["sprite_defaults"]["cell_size"],
    })
    cfg.setdefault("hardware_advisor", {})["last_recommendation"] = rec
    cfg["hardware_advisor"]["last_applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    backup = CONFIG.with_suffix(".json.bak_" + time.strftime("%Y%m%d_%H%M%S"))
    CONFIG.replace(backup)
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Backed up config: {backup}")
    print(f"Applied sprite defaults for tier: {rec['tier']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge hardware advisor")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("report")
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_report)
    s = sub.add_parser("apply", help="Back up config and apply recommended sprite defaults")
    s.set_defaults(func=cmd_apply)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
