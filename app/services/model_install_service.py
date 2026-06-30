#!/usr/bin/env python3
"""Model installation, manifest handling, and tier management."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from .config_service import ConfigService
    from . import comfy_workflow_service as wf_svc
except ImportError:
    from config_service import ConfigService  # type: ignore
    import comfy_workflow_service as wf_svc  # type: ignore


ROOT = Path(__file__).resolve().parent.parent

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


def normalize_model_tier(cfg: dict, tier: Optional[str]) -> str:
    raw = (tier or cfg.raw.get("default_model_tier") or "wan21_safe").strip().lower()
    key = MODEL_TIER_ALIASES.get(raw, raw)
    tiers = cfg.raw.get("model_tiers", {})
    if key not in tiers:
        raise KeyError(f"Unknown model tier '{tier}'. Available: {', '.join(sorted(tiers))}")
    return key


def tier_config(cfg: dict, tier: Optional[str]) -> Dict[str, Any]:
    key = normalize_model_tier(cfg, tier)
    data = dict(cfg.raw.get("model_tiers", {}).get(key, {}))
    data["key"] = key
    return data


def manifests_for_install_tier(cfg: dict, tier: Optional[str]) -> List[str]:
    raw = (tier or "safe").strip().lower()
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
    out = []
    seen = set()
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def merged_wan_defaults(cfg: dict, profile: Optional[str], mode: Optional[str] = None, tier: Optional[str] = None) -> Dict[str, Any]:
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


def workflow_resolve(path: Optional[str], cfg: dict, profile: Optional[str] = None, mode: Optional[str] = None, tier: Optional[str] = None) -> Path:
    wd = merged_wan_defaults(cfg, profile, mode=mode, tier=tier)
    p = Path(path or wd.get("api_workflow", "workflows/wan21_t2v_1_3b_native_api.json"))
    if not p.is_absolute():
        p = ROOT / p
    return p


def model_manifest_path(path: Optional[str]) -> Path:
    p = Path(path or "model_manifests/wan21_t2v_1_3b_native.json")
    if not p.is_absolute():
        p = ROOT / p
    return p


def model_manifest_files(cfg: dict, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
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


def git_rev(path: Path) -> Optional[str]:
    if not (path / ".git").exists():
        return None
    try:
        p = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(path), capture_output=True, text=True, timeout=20)
        return (p.stdout or "").strip() if p.returncode == 0 else None
    except Exception:
        return None


def model_tiers_info(cfg: dict) -> Dict[str, Any]:
    tiers = cfg.raw.get("model_tiers", {})
    result = {}
    for key, data in sorted(tiers.items()):
        result[key] = {
            "label": data.get("label", key),
            "description": data.get("description", ""),
            "modes": data.get("modes", []),
            "default_profile": data.get("default_profile", ""),
            "manifest": data.get("manifest", ""),
            "vram_min_gb": data.get("vram_min_gb"),
            "disk_gb": data.get("disk_gb"),
        }
    return result


def stage_file_to_comfy_input(cfg: dict, file_path: str, subfolder: str = "SpriteForge") -> str:
    src = Path(file_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    dest_dir = cfg.comfy_input / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return f"{subfolder}/{src.name}".replace("\\", "/")