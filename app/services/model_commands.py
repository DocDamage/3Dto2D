from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

from services.model_install_service import (
    model_manifest_files,
    model_manifest_path,
    model_tiers_info,
    manifests_for_install_tier,
)

def cmd_download_wan_native(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
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
    from spriteforge_commands import load_config
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
    from spriteforge_commands import load_config
    cfg = load_config()
    info = model_tiers_info(cfg)
    for key, data in sorted(info.items()):
        print(f"  {key}: {data['label']} | VRAM min: {data.get('vram_min_gb', '?')} GB | Disk: {data.get('disk_gb', '?')} GB")
    print(f"\nDefault: {cfg.raw.get('default_model_tier', 'wan21_safe')}")


def cmd_download_model_tier(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
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
