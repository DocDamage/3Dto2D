#!/usr/bin/env python3
"""SpriteForge reproducibility and regression manifest tools."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HASH_EXTS = {".json", ".png", ".gif", ".mp4", ".webm", ".py", ".bat", ".md", ".txt"}


def sha256(path: Path, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def capture(cmd: List[str], cwd: Optional[Path] = None, timeout: float = 15) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def git_rev(path: Path) -> Optional[str]:
    if not (path / ".git").exists():
        return None
    rc, out = capture(["git", "rev-parse", "HEAD"], cwd=path)
    return out.strip() if rc == 0 else None


def build_manifest(root: Path, output: Path, include_all: bool = False) -> Path:
    root = root.resolve()
    files: List[Dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if not include_all and p.suffix.lower() not in HASH_EXTS:
            continue
        try:
            rel = p.relative_to(root).as_posix()
            files.append({"path": rel, "size": p.stat().st_size, "sha256": sha256(p)})
        except Exception:
            pass
    data: Dict[str, Any] = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(root),
        "platform": platform.platform(),
        "python": sys.version,
        "files": files,
        "git": {},
    }
    for sub in [root, root / "vendor" / "ComfyUI", root / "vendor" / "ComfyUI" / "custom_nodes" / "ComfyUI-WanVideoWrapper", root / "vendor" / "ComfyUI" / "custom_nodes" / "ComfyUI-VideoHelperSuite"]:
        rev = git_rev(sub)
        if rev:
            data["git"][str(sub)] = rev
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Manifest: {output}")
    print(f"Files hashed: {len(files)}")
    return output


def compare_manifests(a: Path, b: Path, output: Optional[Path]) -> Dict[str, Any]:
    ma = json.loads(a.read_text(encoding="utf-8"))
    mb = json.loads(b.read_text(encoding="utf-8"))
    da = {x["path"]: x for x in ma.get("files", [])}
    db = {x["path"]: x for x in mb.get("files", [])}
    added = sorted(set(db) - set(da))
    removed = sorted(set(da) - set(db))
    changed = sorted(k for k in set(da) & set(db) if da[k].get("sha256") != db[k].get("sha256"))
    report = {"a": str(a), "b": str(b), "added": added, "removed": removed, "changed": changed, "changed_count": len(changed)}
    print(json.dumps(report, indent=2))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Compare report: {output}")
    return report


def cmd_manifest(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root / "output" / "repro" / f"manifest_{time.strftime('%Y%m%d_%H%M%S')}.json"
    build_manifest(root, output, include_all=args.all)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    compare_manifests(Path(args.a).resolve(), Path(args.b).resolve(), Path(args.output).resolve() if args.output else None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge reproducibility manifest tools")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("manifest")
    s.add_argument("--root", default=".")
    s.add_argument("--output", default=None)
    s.add_argument("--all", action="store_true", help="Hash all file types instead of common project artifacts only")
    s.set_defaults(func=cmd_manifest)
    s = sub.add_parser("compare")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_compare)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
