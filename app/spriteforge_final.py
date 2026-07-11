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

RELEASE_TARGETS: Dict[str, Dict[str, Any]] = {
    "godot": {
        "label": "Godot",
        "workflow": "AnimatedSprite2D grid animation",
        "asset_root": "res://art/sprites",
        "summary": "Grid-slice each sheet for an AnimatedSprite2D animation.",
        "steps": [
            "Copy each packaged sprite folder into `res://art/sprites/`.",
            "Import `sheet.png` with nearest-neighbor filtering and no mipmaps.",
            "Create SpriteFrames, set horizontal/vertical frames from `columns`/`rows`, and add frames in row-major order.",
            "Set the animation speed from `fps` in `sheet.json` and enable looping only when the source animation loops.",
        ],
        "settings": {
            "node": "AnimatedSprite2D",
            "texture_filter": "nearest",
            "mipmaps": False,
            "frame_order": "row-major",
            "grid_fields": ["columns", "rows"],
        },
    },
    "unity": {
        "label": "Unity",
        "workflow": "Multiple Sprite import and AnimationClip",
        "asset_root": "Assets/Sprites",
        "summary": "Slice each sheet as multiple sprites and build an AnimationClip.",
        "steps": [
            "Copy each packaged sprite folder into `Assets/Sprites/`.",
            "Set Texture Type to Sprite (2D and UI), Sprite Mode to Multiple, Filter Mode to Point, and Compression to None.",
            "Slice by the `frame_width` and `frame_height` grid in `sheet.json`, preserving row-major frame order.",
            "Build an AnimationClip at the listed `fps`; turn Loop Time on only when the source animation loops.",
        ],
        "settings": {
            "texture_type": "Sprite (2D and UI)",
            "sprite_mode": "Multiple",
            "filter_mode": "Point",
            "compression": "None",
            "frame_order": "row-major",
            "grid_fields": ["frame_width", "frame_height"],
        },
    },
    "unreal": {
        "label": "Unreal Engine",
        "workflow": "Paper2D Sprite and Flipbook",
        "asset_root": "/Game/Sprites",
        "summary": "Extract Paper2D sprites from the grid and assemble a Flipbook.",
        "steps": [
            "Enable the Paper2D plugin, then import each `sheet.png` under `/Game/Sprites/`.",
            "Apply Paper2D texture settings, use nearest filtering, and disable mip generation for crisp pixel art.",
            "Extract sprites with a grid sized from `frame_width` and `frame_height` in `sheet.json`, in row-major order.",
            "Create a PaperFlipbook and set Frames Per Second from the packaged `fps` value.",
        ],
        "settings": {
            "plugin": "Paper2D",
            "asset_type": "PaperFlipbook",
            "texture_filter": "Nearest",
            "mip_gen_settings": "NoMipmaps",
            "frame_order": "row-major",
            "grid_fields": ["frame_width", "frame_height"],
        },
    },
    "png": {
        "label": "PNG Images",
        "workflow": "Engine-neutral image handoff",
        "asset_root": "art/sprites",
        "summary": "Use the transparent PNG sheets directly, with JSON metadata as an optional slicing reference.",
        "steps": [
            "Copy `sheet.png` (and `preview.gif` when present) from each packaged sprite folder.",
            "Keep alpha transparency intact and resize only by whole-number multiples with nearest-neighbor sampling.",
            "Use `frame_width`, `frame_height`, `columns`, and `rows` from `sheet.json` when individual frames are needed.",
            "Preserve row-major frame order and the listed `fps` when handing the images to another animation tool.",
        ],
        "settings": {
            "primary_asset": "sheet.png",
            "color_mode": "RGBA",
            "resampling": "nearest-neighbor",
            "frame_order": "row-major",
            "metadata_optional": True,
        },
    },
    "web": {
        "label": "Web",
        "workflow": "Canvas or CSS spritesheet animation",
        "asset_root": "public/sprites",
        "summary": "Animate each PNG sheet in Canvas or CSS using the packaged grid and timing metadata.",
        "steps": [
            "Copy each packaged sprite folder into your site's static asset directory, such as `public/sprites/`.",
            "Load `sheet.png` and `sheet.json`; advance frames in row-major order using `1000 / fps` milliseconds per frame.",
            "For Canvas, draw the source rectangle from `frame_width` and `frame_height`; disable image smoothing.",
            "For CSS, set `image-rendering: pixelated` and move `background-position` by whole frame dimensions.",
        ],
        "settings": {
            "runtime": "Canvas 2D or CSS",
            "image_rendering": "pixelated",
            "canvas_image_smoothing": False,
            "frame_order": "row-major",
            "timing_formula_ms": "1000 / fps",
        },
    },
}


def _release_target(value: Any) -> tuple[str, Dict[str, Any]]:
    target = str(value or "godot").strip().lower()
    if target not in RELEASE_TARGETS:
        allowed = ", ".join(sorted(RELEASE_TARGETS))
        raise SystemExit(f"Unsupported release target. Choose one of: {allowed}.")
    return target, RELEASE_TARGETS[target]


def _target_guide_markdown(target: str, spec: Dict[str, Any]) -> str:
    settings = []
    for key, value in spec["settings"].items():
        rendered = json.dumps(value) if isinstance(value, (list, dict, bool)) else str(value)
        settings.append(f"- `{key}`: `{rendered}`")
    steps = [f"{index}. {step}" for index, step in enumerate(spec["steps"], 1)]
    return "\n".join([
        f"# {spec['label']} release guide",
        "",
        f"This package was prepared for **{spec['label']}** (`{target}`).",
        f"Workflow: {spec['workflow']}.",
        f"Suggested asset root: `{spec['asset_root']}`.",
        "",
        "## Import steps",
        "",
        *steps,
        "",
        "## Recommended settings",
        "",
        *settings,
        "",
        "## Source contract",
        "",
        "Every folder under `sprites/` keeps the original `sheet.png` and `sheet.json`. "
        "The JSON metadata is authoritative for frame size, grid dimensions, frame count, and FPS.",
        "",
    ])


def _sprite_target_notes(folder: Path, meta: Dict[str, Any], target: str, spec: Dict[str, Any]) -> str:
    lines = [
        f"# {folder.name}",
        "",
        f"Release target: {spec['label']} (`{target}`)",
        f"Workflow: {spec['workflow']}",
        f"Suggested asset root: `{spec['asset_root']}`",
        "",
        "## Sprite grid",
        "",
        f"- Frame size: {meta.get('frame_width', '?')}x{meta.get('frame_height', '?')}",
        f"- Frames: {meta.get('frame_count', '?')}",
        f"- FPS: {meta.get('fps', '?')}",
        f"- Columns: {meta.get('columns', '?')}",
        f"- Rows: {meta.get('rows', '?')}",
        "- Frame order: row-major (left to right, then top to bottom)",
        "",
        f"## {spec['label']} steps",
        "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(spec["steps"], 1))
    lines.extend(["", "See `TARGET_GUIDE.md` in this directory for the package-wide handoff.", ""])
    return "\n".join(lines)

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
    target, target_spec = _release_target(getattr(args, "target", "godot"))
        
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
        notes = _sprite_target_notes(folder, meta, target, target_spec)
        (outroot / "engine" / f"{folder.name}_import_notes.md").write_text(notes, encoding="utf-8")
    target_guide = "engine/TARGET_GUIDE.md"
    (outroot / target_guide).write_text(_target_guide_markdown(target, target_spec), encoding="utf-8")
    preflight = preflight_data()
    save_json(outroot / "preflight" / "preflight.json", preflight)
    from services.final_service import render_preflight_html
    (outroot / "preflight" / "preflight.html").write_text(render_preflight_html(preflight), encoding="utf-8")
    handoff = {
        "schema": "spriteforge.release_handoff.v1",
        "consumer_target": target,
        "target_guidance": {
            "path": target_guide,
            "label": target_spec["label"],
            "workflow": target_spec["workflow"],
            "summary": target_spec["summary"],
        },
        "quality_gate": gate,
        "strict_mode": bool(getattr(args, "strict", False)),
        "preflight": {
            "json": "preflight/preflight.json",
            "html": "preflight/preflight.html",
            "generated_at": preflight.get("generated_at", ""),
            "next_step": (preflight.get("checks") or {}).get("next_step", {}),
        },
        "engine_import": {
            "notes_dir": "engine",
            "target": target,
            "target_label": target_spec["label"],
            "guidance": target_guide,
            "workflow": target_spec["workflow"],
            "asset_root": target_spec["asset_root"],
            "steps": list(target_spec["steps"]),
            "settings": dict(target_spec["settings"]),
            "godot": "Use each sprite sheet.json columns/rows for hframes/vframes and keep texture filtering nearest.",
            "unity": "Import sheet.png as Sprite Mode Multiple, slice by frame_width x frame_height, and build clips at sheet.json fps.",
        },
        "sprites_dir": "sprites",
        "zip_exclusion_policy": "SpriteForge excludes restricted/heavy files from release zips via is_release_excluded.",
    }
    manifest = {
        "schema": "spriteforge_release_v12",
        "name": name,
        "created_at": created,
        "consumer_target": target,
        "sprite_count": len(records),
        "sprites": records,
        "handoff": handoff,
        "root": str(ROOT.resolve()),
        **project_release_metadata(args.project),
    }
    save_json(outroot / "manifest.json", manifest)
    (outroot / "README.md").write_text(
        make_release_readme(name, records, created, target=target, target_label=target_spec["label"]),
        encoding="utf-8",
    )
    if args.zip:
        zip_path = outroot.with_suffix(".zip")
        if zip_path.exists():
            zip_path.unlink()
        from spriteforge_utils import is_release_excluded, audit_dir_exclusions
        violations = audit_dir_exclusions(outroot)
        manifest["handoff"]["zip"] = {
            "path": rel(zip_path),
            "excluded_count": len(violations),
            "excluded_paths": violations,
        }
        save_json(outroot / "manifest.json", manifest)
        if violations:
            print(f"AUDIT WARNING: Excluding {len(violations)} restricted/heavy files from release zip: {violations}", file=sys.stderr)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in outroot.rglob("*"):
                if p.is_file():
                    if not is_release_excluded(p, outroot):
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
    s.add_argument(
        "--target",
        choices=sorted(RELEASE_TARGETS),
        default="godot",
        help="Consumer handoff target (default: godot)",
    )
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
