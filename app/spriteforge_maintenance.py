#!/usr/bin/env python3
"""ComfyUI snapshot, safe update, and rollback helper."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
SNAP_ROOT = ROOT / "snapshots"


def load_config() -> Dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    return p


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = False) -> Tuple[int, str]:
    print("$ " + " ".join(cmd) + (f" (cwd={cwd})" if cwd else ""))
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    out = (p.stdout or "") + (p.stderr or "")
    if out.strip():
        print(out.strip())
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return p.returncode, out


def git_info(path: Path) -> Dict:
    info = {"path": str(path), "exists": path.exists(), "is_git": (path / ".git").exists()}
    if not info["is_git"]:
        return info
    fields = {
        "rev": ["git", "rev-parse", "HEAD"],
        "short_rev": ["git", "rev-parse", "--short", "HEAD"],
        "branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        "remote": ["git", "remote", "get-url", "origin"],
        "status": ["git", "status", "--porcelain"],
    }
    for k, cmd in fields.items():
        rc, out = run(cmd, cwd=path)
        info[k] = out.strip() if rc == 0 else None
    return info


def custom_node_dirs(comfy: Path) -> List[Path]:
    cn = comfy / "custom_nodes"
    if not cn.exists():
        return []
    return [p for p in sorted(cn.iterdir()) if p.is_dir() and not p.name.startswith(".")]


def snapshot_data() -> Dict:
    cfg = load_config()
    comfy = resolve(cfg["paths"]["comfyui_dir"])
    repos = [git_info(comfy)] + [git_info(p) for p in custom_node_dirs(comfy)]
    py = sys.executable
    rc, freeze = run([py, "-m", "pip", "freeze"])
    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(ROOT),
        "comfyui_dir": str(comfy),
        "repos": repos,
        "pip_freeze": freeze.splitlines() if rc == 0 else [],
        "config": cfg,
    }


def cmd_snapshot(args: argparse.Namespace) -> None:
    SNAP_ROOT.mkdir(parents=True, exist_ok=True)
    sid = args.name or time.strftime("snapshot_%Y%m%d_%H%M%S")
    out = SNAP_ROOT / sid
    out.mkdir(parents=True, exist_ok=True)
    data = snapshot_data()
    (out / "snapshot.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    if args.copy_config:
        shutil.copy2(CONFIG_PATH, out / "spriteforge_config.json")
    print(f"Snapshot: {out}")


def cmd_list(args: argparse.Namespace) -> None:
    if not SNAP_ROOT.exists():
        print("No snapshots yet.")
        return
    for p in sorted(SNAP_ROOT.iterdir()):
        js = p / "snapshot.json"
        if not js.exists():
            continue
        data = json.loads(js.read_text(encoding="utf-8"))
        print(f"{p.name}: {data.get('created_at')}  {data.get('comfyui_dir')}")


def load_snapshot(name: str) -> Dict:
    path = Path(name)
    if not path.is_absolute():
        path = SNAP_ROOT / name / "snapshot.json"
    if path.is_dir():
        path = path / "snapshot.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_rollback(args: argparse.Namespace) -> None:
    data = load_snapshot(args.snapshot)
    for repo in data.get("repos", []):
        path = Path(repo.get("path", ""))
        rev = repo.get("rev")
        if not repo.get("is_git") or not path.exists() or not rev:
            print(f"Skipping non-git/missing repo: {path}")
            continue
        if args.dry_run:
            print(f"Would rollback {path} to {rev}")
            continue
        run(["git", "fetch", "--all"], cwd=path)
        run(["git", "checkout", rev], cwd=path, check=True)
    print("Rollback complete. Restart ComfyUI after rollback.")


def update_repo(path: Path) -> None:
    if not (path / ".git").exists():
        print(f"Skipping non-git repo: {path}")
        return
    # Refuse to pull over local uncommitted edits unless forced.
    rc, status = run(["git", "status", "--porcelain"], cwd=path)
    if status.strip():
        print(f"WARNING: {path} has local changes. Skipping update for safety.")
        return
    run(["git", "pull", "--ff-only"], cwd=path)


def cmd_safe_update(args: argparse.Namespace) -> None:
    # Always snapshot before touching anything.
    sid = time.strftime("before_update_%Y%m%d_%H%M%S")
    cmd_snapshot(argparse.Namespace(name=sid, copy_config=True))
    cfg = load_config()
    comfy = resolve(cfg["paths"]["comfyui_dir"])
    targets = [comfy]
    if args.custom_nodes:
        targets.extend(custom_node_dirs(comfy))
    for path in targets:
        update_repo(path)
    print(f"Safe update finished. Pre-update snapshot: {sid}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge ComfyUI maintenance")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("snapshot")
    s.add_argument("--name", default=None)
    s.add_argument("--copy-config", action="store_true", default=True)
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("list")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("rollback")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_rollback)

    s = sub.add_parser("safe-update")
    s.add_argument("--custom-nodes", action="store_true", help="Also update git-based custom nodes")
    s.set_defaults(func=cmd_safe_update)
    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
