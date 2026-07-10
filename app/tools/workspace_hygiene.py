#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parents[2]


def directory_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    if not path.exists():
        return total
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def git_storage_report(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "count-objects", "-vH"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (result.stdout or result.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable: {exc}"


def build_report(root: Path = REPO_ROOT) -> Dict[str, Any]:
    targets = [".git", "app/vendor", "app/input", "output", "dist_release.zip"]
    sizes = {}
    for name in targets:
        target = root / name
        if not target.exists():
            continue
        size = directory_size(target)
        sizes[name] = {"bytes": size, "gb": round(size / (1024 ** 3), 2)}
    return {
        "root": str(root),
        "sizes": sizes,
        "git": git_storage_report(root),
        "recommendations": [
            "Keep ComfyUI/models outside synced source trees and set SPRITEFORGE_COMFYUI_DIR and SPRITEFORGE_COMFYUI_OUTPUT.",
            "Back up and inspect dangling Git objects before running git gc --prune.",
            "Keep release ZIPs in artifact storage instead of the source workspace.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only SpriteForge workspace storage report")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Workspace: {report['root']}")
        for name, row in report["sizes"].items():
            print(f"  {name}: {row['gb']:.2f} GB")
        print("\nGit object report:\n" + report["git"])
        print("\nRecommendations:")
        for recommendation in report["recommendations"]:
            print(f"  - {recommendation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
