from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from services.config_service import ConfigService, load_json

ROOT = Path(__file__).resolve().parent.parent


def _addon_registry() -> Dict[str, Any]:
    return load_json(ROOT / "config" / "model_addons.json", {"addons": []}) or {"addons": []}


def _addon_by_id(addon_id: str) -> Dict[str, Any]:
    for addon in _addon_registry().get("addons", []):
        if str(addon.get("id")) == addon_id:
            return addon
    raise ValueError(f"Unknown model add-on: {addon_id}")


def _target_dir(dest_subdir: str) -> Path:
    if dest_subdir == "workflows":
        return ROOT / "workflows"
    return ConfigService.get_path("paths.comfyui_dir") / "models" / dest_subdir


def cmd_download_model_addon(args: argparse.Namespace) -> None:
    from huggingface_hub import hf_hub_download, snapshot_download

    addon = _addon_by_id(str(args.addon))
    repo_id = str(addon.get("repo_id") or "").strip()
    if not repo_id:
        raise ValueError(f"Model add-on {addon.get('id')} does not define repo_id")

    print(f"Model add-on: {addon.get('label') or addon.get('id')}")
    print(f"Hugging Face repo: {repo_id}")
    print(f"Base model: {addon.get('base_model') or 'unknown'}")

    files = addon.get("files") or []
    for item in files:
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        dest_subdir = str(item.get("dest_subdir") or addon.get("dest_subdir") or "loras")
        target = _target_dir(dest_subdir)
        target.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {filename} -> {target}")
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=target,
            local_dir_use_symlinks=False,
            force_download=bool(getattr(args, "force", False)),
        )
        print(f"[DONE] {filename}")

    patterns = [str(p) for p in addon.get("file_patterns", []) if str(p).strip()]
    if patterns:
        dest_subdir = str(addon.get("dest_subdir") or "loras")
        target = _target_dir(dest_subdir)
        target.mkdir(parents=True, exist_ok=True)
        print(f"Downloading patterns {patterns} -> {target}")
        snapshot_download(
            repo_id=repo_id,
            allow_patterns=patterns,
            local_dir=target,
            local_dir_use_symlinks=False,
            force_download=bool(getattr(args, "force", False)),
        )
        print("[DONE] Pattern download complete")

    if not files and not patterns:
        raise ValueError(f"Model add-on {addon.get('id')} does not define downloadable files")

    print("Model add-on install complete.")
