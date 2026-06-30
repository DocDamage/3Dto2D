#!/usr/bin/env python3
"""SpriteForge final polish utilities.

Modularized to keep LOC under 500. Core logic is moved to services.final_service.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from spriteforge_utils import save_json, load_json
from services.final_service import (
    ROOT, OUTPUT, RELEASES,
    find_sprite_dirs, recommended_next_step,
    selected_sprite_dirs, project_release_metadata,
    make_release_readme, check_release_quality_gates,
    all_sprite_records, rel, safe_name
)

# Wrapper functions to support direct test patching and mocking
def preflight_data() -> Dict[str, Any]:
    from services.final_service import preflight_data as _impl
    return _impl()

def sprite_record(folder: Path) -> Dict[str, Any]:
    from services.final_service import sprite_record as _impl
    return _impl(folder)

def get_project_quality_gates(sprite_dir: Path) -> Dict[str, Any]:
    from services.final_service import get_project_quality_gates as _impl
    return _impl(sprite_dir)

def cmd_next(args: argparse.Namespace) -> None:
    data = recommended_next_step()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"Recommended next step: {data['step']}")
        print(data["reason"])
        print(f"Action key: {data['action']}")

def cmd_preflight(args: argparse.Namespace) -> None:
    data = preflight_data()
    outdir = Path(args.output or (OUTPUT / "diagnostics"))
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = outdir / f"preflight_{stamp}.json"
    html_path = outdir / f"preflight_{stamp}.html"
    save_json(json_path, data)
    
    from services.final_service import render_preflight_html
    html_path.write_text(render_preflight_html(data), encoding="utf-8")
    print(f"Preflight JSON: {json_path}")
    print(f"Preflight HTML: {html_path}")
    print(f"Recommended next step: {data['checks']['next_step']['step']}")
    if args.open:
        from services.open_path_service import open_path
        open_path(html_path)

def cmd_release(args: argparse.Namespace) -> None:
    sprites = selected_sprite_dirs(args)
    if not sprites:
        raise SystemExit("No sprite outputs found. Pass --sprite-dir, --root, or --project.")
        
    gate = check_release_quality_gates(sprites)
    for err in gate["errors"]:
        print(f"ERROR (Quality Gate): {err}", file=sys.stderr)
    for warn in gate["warnings"]:
        print(f"WARNING (Quality Gate): {warn}", file=sys.stderr)
        
    if not gate["ok"] and getattr(args, "strict", False):
        raise SystemExit("Release build blocked by quality gate errors under strict mode.")
        
    name = safe_name(args.name or (Path(args.project).stem if args.project else "spriteforge_release"))
    created = dt.datetime.now().isoformat(timespec="seconds")
    outroot = Path(args.output or (RELEASES / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}"))
    if not outroot.is_absolute():
        outroot = ROOT / outroot
    if outroot.exists() and not args.force:
        raise SystemExit(f"Release folder exists. Use --force to overwrite: {outroot}")
    if outroot.exists():
        shutil.rmtree(outroot)
    (outroot / "sprites").mkdir(parents=True)
    (outroot / "engine").mkdir()
    (outroot / "preflight").mkdir()
    records = []
    for folder in sprites:
        dest = outroot / "sprites" / folder.name
        shutil.copytree(folder, dest, ignore=shutil.ignore_patterns("*.tmp", "__pycache__"))
        rec = sprite_record(folder)
        rec["release_path"] = rel(dest)
        records.append(rec)
        meta = load_json(folder / "sheet.json", {}) or {}
        notes = [
            f"# {folder.name}", "",
            f"Frame size: {meta.get('frame_width','?')}x{meta.get('frame_height','?')}",
            f"Frames: {meta.get('frame_count','?')}",
            f"FPS: {meta.get('fps','?')}",
            f"Columns: {meta.get('columns','?')}",
            f"Rows: {meta.get('rows','?')}", "",
            "Godot: set hframes=Columns and vframes=Rows.",
            "Unity: slice sheet.png by Frame size.",
        ]
        (outroot / "engine" / f"{folder.name}_import_notes.md").write_text("\n".join(notes)+"\n", encoding="utf-8")
    preflight = preflight_data()
    save_json(outroot / "preflight" / "preflight.json", preflight)
    from services.final_service import render_preflight_html
    (outroot / "preflight" / "preflight.html").write_text(render_preflight_html(preflight), encoding="utf-8")
    manifest = {
        "schema": "spriteforge_release_v12",
        "name": name,
        "created_at": created,
        "sprite_count": len(records),
        "sprites": records,
        "root": str(ROOT.resolve()),
        **project_release_metadata(args.project),
    }
    save_json(outroot / "manifest.json", manifest)
    (outroot / "README.md").write_text(make_release_readme(name, records, created), encoding="utf-8")
    if args.zip:
        zip_path = outroot.with_suffix(".zip")
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in outroot.rglob("*"):
                zf.write(p, p.relative_to(outroot.parent))
        print(f"Release folder: {outroot}")
        print(f"Release zip: {zip_path}")
    else:
        print(f"Release folder: {outroot}")

def cmd_dashboard(args: argparse.Namespace) -> None:
    data = preflight_data()
    records = all_sprite_records(500)
    out = Path(args.output or (OUTPUT / "_studio_dashboard" / "index.html"))
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    from services.final_service import render_dashboard_html
    out.write_text(render_dashboard_html(records, data), encoding="utf-8")
    print(f"Dashboard: {out}")
    if args.open:
        from services.open_path_service import open_path
        open_path(out)

def cmd_open_latest(args: argparse.Namespace) -> None:
    sprites = find_sprite_dirs()
    if not sprites:
        print("No sprite outputs found.")
        return
    latest = sprites[0]
    print(latest)
    if args.open:
        from services.open_path_service import open_path
        open_path(latest)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge final polish tools")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("next", help="Print the recommended next step")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("preflight", help="Create final all-in-one setup/status report")
    s.add_argument("--output", default=None)
    s.add_argument("--open", action="store_true")
    s.set_defaults(func=cmd_preflight)

    s = sub.add_parser("dashboard", help="Create standalone asset dashboard HTML")
    s.add_argument("--output", default=None)
    s.add_argument("--open", action="store_true")
    s.set_defaults(func=cmd_dashboard)

    s = sub.add_parser("release", help="Package finished sprites into a release folder/zip")
    s.add_argument("--name", default=None)
    s.add_argument("--sprite-dir", action="append", default=[])
    s.add_argument("--root", default=None)
    s.add_argument("--project", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--zip", action="store_true")
    s.add_argument("--force", action="store_true")
    s.add_argument("--strict", action="store_true")
    s.set_defaults(func=cmd_release)

    s = sub.add_parser("latest", help="Print/open latest sprite output")
    s.add_argument("--open", action="store_true")
    s.set_defaults(func=cmd_open_latest)
    return p

def main(argv: Optional[Sequence[str]] = None) -> int:
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
