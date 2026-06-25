#!/usr/bin/env python3
"""SpriteForge animation-pack and atlas tools.

Adds production-level organization on top of one-off sprite sheets:
- create a character action/direction manifest
- generate prompts and posepacks for each action
- collect finished sprite outputs into a pack index
- run QA across the whole pack
- pack multiple animation sheets into one atlas + JSON
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image

ROOT = Path(__file__).resolve().parent

try:
    from spriteforge_prompts import ACTION_TEMPLATES, DIRECTIONS, build_prompt, make_posepack, DEFAULT_CHARACTER, DEFAULT_STYLE, DEFAULT_BACKGROUND
except Exception:
    ACTION_TEMPLATES = {}
    DIRECTIONS = {}
    DEFAULT_CHARACTER = "single full body original game character, consistent outfit, clean silhouette"
    DEFAULT_STYLE = "2D game sprite animation, crisp edges, readable silhouette"
    DEFAULT_BACKGROUND = "plain bright green chroma key background"
    build_prompt = None
    make_posepack = None


def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "spriteforge_pack"


def parse_csv(value: str, allowed: Optional[Iterable[str]] = None) -> List[str]:
    items = [x.strip() for x in value.split(",") if x.strip()]
    if allowed is not None:
        allowed_set = set(allowed)
        bad = [x for x in items if x not in allowed_set]
        if bad:
            raise ValueError(f"Unsupported values {bad}. Allowed: {', '.join(sorted(allowed_set))}")
    return items


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_meta(sprite_dir: Path) -> Dict[str, Any]:
    path = sprite_dir / "sheet.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_sprite_dir"] = str(sprite_dir)
    return data


def find_sprite_dirs(root: Path) -> List[Path]:
    if (root / "sheet.json").exists():
        return [root]
    return sorted({p.parent for p in root.rglob("sheet.json")})


def project_metadata_for_output(out: Path) -> Dict[str, str]:
    """Attach project identity when the pack is created inside a project root."""
    for parent in [out, *out.parents]:
        manifest = parent / "spriteforge_project.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            try:
                project_path = manifest.resolve().relative_to(ROOT.resolve()).as_posix()
                project_root = parent.resolve().relative_to(ROOT.resolve()).as_posix()
            except ValueError:
                project_path = str(manifest.resolve()).replace("\\", "/")
                project_root = str(parent.resolve()).replace("\\", "/")
            return {
                "project_name": str(data.get("name") or parent.name),
                "project_path": project_path,
                "project_root": project_root,
            }
    return {}


def default_frame_count(action: str) -> int:
    spec = ACTION_TEMPLATES.get(action, {}) if isinstance(ACTION_TEMPLATES, dict) else {}
    return int(spec.get("frames", 24))


def cmd_init(args: argparse.Namespace) -> None:
    if build_prompt is None:
        raise RuntimeError("spriteforge_prompts.py could not be imported")
    actions = parse_csv(args.actions, ACTION_TEMPLATES.keys())
    directions = parse_csv(args.directions, DIRECTIONS.keys())
    pack_name = safe_name(args.name or "character_pack")
    out = Path(args.output or (ROOT / "output" / "packs" / pack_name)).resolve()
    prompts_dir = out / "prompts"
    poses_dir = out / "posepacks"
    expected_dir = out / "sprites"
    ensure_dir(prompts_dir); ensure_dir(poses_dir); ensure_dir(expected_dir)

    entries: List[Dict[str, Any]] = []
    for action in actions:
        for direction in directions:
            key = f"{action}_{direction}"
            prompt_path = prompts_dir / f"{key}.json"
            prompt = build_prompt(
                action=action,
                direction=direction,
                character=args.character,
                style=args.style,
                background=args.background,
                extra=args.extra,
                reference=args.reference,
                pose_guided=args.pose_guided,
            )
            write_json(prompt_path, prompt)
            posepack_path = None
            if args.posepacks:
                posepack_path = poses_dir / key
                frames = int(prompt.get("recommended_frames", default_frame_count(action)))
                make_posepack(action, direction, frames, args.pose_size, posepack_path)
            entries.append({
                "key": key,
                "action": action,
                "direction": direction,
                "prompt_path": str(prompt_path.relative_to(out)),
                "posepack_path": str(posepack_path.relative_to(out)) if posepack_path else None,
                "expected_video_name": f"{key}.mp4",
                "expected_sprite_dir": str((expected_dir / key).relative_to(out)),
                "status": "planned",
            })

    manifest = {
        "schema": "spriteforge_pack.v1",
        "pack_name": pack_name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "character": args.character,
        "style": args.style,
        "background": args.background,
        "actions": actions,
        "directions": directions,
        "entries": entries,
        **project_metadata_for_output(out),
        "notes": [
            "Generate videos/sprites for each entry, then run pack-collect or pack-atlas.",
            "Use prompt_path and posepack_path with exported ComfyUI API workflows.",
        ],
    }
    write_json(out / "pack_manifest.json", manifest)
    (out / "README_PACK.md").write_text(make_pack_readme(manifest), encoding="utf-8")
    print(f"Created pack manifest: {out / 'pack_manifest.json'}")
    print(f"Entries: {len(entries)}")


def make_pack_readme(manifest: Dict[str, Any]) -> str:
    rows = []
    for e in manifest.get("entries", []):
        rows.append(f"| {e['action']} | {e['direction']} | `{e['prompt_path']}` | `{e.get('posepack_path') or ''}` | `{e['expected_sprite_dir']}` |")
    return """# SpriteForge Character Pack

This folder is a production plan for a multi-action, multi-direction character sprite pack.

| Action | Direction | Prompt | Posepack | Sprite output |
|---|---|---|---|---|
""" + "\n".join(rows) + "\n\nRun QA after each generated sprite and then build an atlas.\n"


def cmd_collect(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    sprite_dirs = find_sprite_dirs(root)
    entries = []
    for sd in sprite_dirs:
        try:
            meta = load_meta(sd)
        except Exception:
            continue
        entries.append({
            "name": str(meta.get("animation") or sd.name),
            "sprite_dir": str(sd),
            "sheet": str(sd / meta.get("image", "sheet.png")),
            "frame_count": int(meta.get("frame_count", 0)),
            "fps": float(meta.get("fps", 12)),
            "frame_width": int(meta.get("frame_width", 0)),
            "frame_height": int(meta.get("frame_height", 0)),
            "columns": int(meta.get("columns", 0)),
            "rows": int(meta.get("rows", 0)),
        })
    out = Path(args.output or (root / "pack_index.json")).resolve()
    pack = {
        "schema": "spriteforge_pack_index.v1",
        "root": str(root),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(entries),
        "entries": entries,
    }
    write_json(out, pack)
    write_pack_html(pack, out.with_suffix(".html"))
    print(f"Collected {len(entries)} sprite outputs")
    print(f"Index: {out}")
    print(f"HTML: {out.with_suffix('.html')}")


def write_pack_html(pack: Dict[str, Any], path: Path) -> None:
    import html
    rows = []
    base = path.parent
    for e in pack.get("entries", []):
        sheet = Path(e["sheet"])
        try:
            rel = sheet.relative_to(base).as_posix()
        except Exception:
            rel = sheet.as_posix()
        rows.append(
            f"<tr><td>{html.escape(e['name'])}</td><td>{e['frame_count']}</td><td>{e['fps']}</td>"
            f"<td>{e['frame_width']}x{e['frame_height']}</td><td><img src='{html.escape(rel)}'></td></tr>"
        )
    txt = """<!doctype html><html><head><meta charset='utf-8'><title>SpriteForge Pack</title>
<style>body{font-family:Arial,sans-serif;margin:28px} table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px} img{max-width:360px;background:#222}</style>
</head><body><h1>SpriteForge Pack Index</h1>
""" + f"<p>Root: <code>{html.escape(pack.get('root',''))}</code></p><table><tr><th>Name</th><th>Frames</th><th>FPS</th><th>Cell</th><th>Sheet</th></tr>" + "".join(rows) + "</table></body></html>"
    path.write_text(txt, encoding="utf-8")


def shelf_pack(sizes: Sequence[Tuple[int, int]], max_width: int, padding: int) -> Tuple[List[Tuple[int, int]], Tuple[int, int]]:
    x = y = 0
    row_h = 0
    positions: List[Tuple[int, int]] = []
    atlas_w = 0
    for w, h in sizes:
        if x > 0 and x + w > max_width:
            x = 0
            y += row_h + padding
            row_h = 0
        positions.append((x, y))
        x += w + padding
        row_h = max(row_h, h)
        atlas_w = max(atlas_w, x)
    atlas_h = y + row_h
    return positions, (max(1, atlas_w - padding), max(1, atlas_h))


def cmd_atlas(args: argparse.Namespace) -> None:
    sprite_dirs: List[Path] = []
    for item in args.sprite_dir or []:
        sprite_dirs.extend(find_sprite_dirs(Path(item).resolve()))
    if args.root:
        sprite_dirs.extend(find_sprite_dirs(Path(args.root).resolve()))
    # Deduplicate while preserving order.
    seen = set(); unique: List[Path] = []
    for sd in sprite_dirs:
        r = sd.resolve()
        if r not in seen:
            seen.add(r); unique.append(r)
    if not unique:
        raise RuntimeError("No sprite outputs found. Use --root or --sprite-dir.")

    metas = [load_meta(sd) for sd in unique]
    sheets = [Image.open(Path(m["_sprite_dir"]) / m.get("image", "sheet.png")).convert("RGBA") for m in metas]
    sizes = [img.size for img in sheets]
    positions, atlas_size = shelf_pack(sizes, args.max_width, args.padding)
    atlas = Image.new("RGBA", atlas_size, (0, 0, 0, 0))

    animations: Dict[str, Any] = {}
    for meta, sheet, (ox, oy) in zip(metas, sheets, positions):
        atlas.alpha_composite(sheet, (ox, oy))
        name = safe_name(str(meta.get("animation") or Path(meta["_sprite_dir"]).name))
        frames = []
        for fr in meta.get("frames", []):
            frames.append({
                "index": int(fr.get("index", len(frames))),
                "name": fr.get("name", f"{name}_{len(frames):04d}"),
                "x": int(fr.get("x", 0)) + ox,
                "y": int(fr.get("y", 0)) + oy,
                "w": int(fr.get("w", meta.get("frame_width", 0))),
                "h": int(fr.get("h", meta.get("frame_height", 0))),
                "duration_ms": int(fr.get("duration_ms", round(1000 / float(meta.get("fps", 12))))),
            })
        animations[name] = {
            "source_sprite_dir": meta["_sprite_dir"],
            "fps": float(meta.get("fps", 12)),
            "frame_width": int(meta.get("frame_width", 0)),
            "frame_height": int(meta.get("frame_height", 0)),
            "frame_count": int(meta.get("frame_count", len(frames))),
            "frames": frames,
        }

    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out / "atlas.png")
    data = {
        "schema": "spriteforge_atlas.v1",
        "image": "atlas.png",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "width": atlas.width,
        "height": atlas.height,
        "animation_count": len(animations),
        "animations": animations,
    }
    write_json(out / "atlas.json", data)
    write_atlas_notes(out / "ATLAS_NOTES.md", data)
    print(f"Atlas: {out / 'atlas.png'}")
    print(f"Metadata: {out / 'atlas.json'}")
    print(f"Animations: {len(animations)}")


def write_atlas_notes(path: Path, data: Dict[str, Any]) -> None:
    lines = ["# SpriteForge Atlas", "", "Generated atlas animations:", ""]
    for name, anim in data.get("animations", {}).items():
        lines.append(f"- `{name}`: {anim['frame_count']} frames, {anim['fps']} FPS, cell {anim['frame_width']}x{anim['frame_height']}")
    lines.append("\nUse `atlas.json` to map each animation frame to `atlas.png` regions.")
    path.write_text("\n".join(lines), encoding="utf-8")


def cmd_qa(args: argparse.Namespace) -> None:
    # Use the production QC module when available. It writes per-sprite HTML reports
    # and returns score/status summaries.
    from spriteforge_quality import quality_report
    root = Path(args.root).resolve()
    sprite_dirs = find_sprite_dirs(root)
    reports = []
    qroot = Path(args.output).resolve() if args.output else root / "pack_quality"
    qroot.mkdir(parents=True, exist_ok=True)
    for sd in sprite_dirs:
        try:
            rep = quality_report(sd, qroot / sd.name, None)
            reports.append({
                "sprite_dir": str(sd),
                "score": rep.get("score", 0),
                "grade": rep.get("grade"),
                "status": rep.get("status", rep.get("grade")),
                "summary": rep.get("summary", {}),
                "suggestions": rep.get("suggestions", []),
                "report_html": str((qroot / sd.name / "quality_report.html")),
            })
        except Exception as exc:
            reports.append({"sprite_dir": str(sd), "score": 0, "status": "error", "error": str(exc)})
    avg = sum(float(r.get("score", 0)) for r in reports) / max(1, len(reports))
    data = {
        "schema": "spriteforge_pack_quality.v1",
        "root": str(root),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "average_score": round(avg, 2),
        "count": len(reports),
        "reports": reports,
    }
    out = qroot / "pack_quality.json"
    write_json(out, data)
    write_pack_quality_html(data, qroot / "pack_quality.html")
    print(f"Average score: {data['average_score']} / 100 across {len(reports)} sprites")
    print(f"Report: {out}")

def write_pack_quality_html(data: Dict[str, Any], path: Path) -> None:
    import html
    rows = []
    for r in data.get("reports", []):
        rows.append(f"<tr><td>{html.escape(Path(r['sprite_dir']).name)}</td><td>{r.get('score')}</td><td>{html.escape(str(r.get('status')))}</td><td>{html.escape('; '.join(r.get('suggestions', [])[:2]))}</td></tr>")
    txt = f"""<!doctype html><html><head><meta charset='utf-8'><title>SpriteForge Pack QA</title>
<style>body{{font-family:Arial,sans-serif;margin:28px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:6px}}</style>
</head><body><h1>SpriteForge Pack QA</h1><p>Average score: <b>{data.get('average_score')}</b> / 100</p>
<table><tr><th>Sprite</th><th>Score</th><th>Status</th><th>Notes</th></tr>{''.join(rows)}</table></body></html>"""
    path.write_text(txt, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge character pack and atlas tools")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="Create a character pack manifest, prompts, and optional posepacks")
    s.add_argument("--name", default="character_pack")
    s.add_argument("--character", default=DEFAULT_CHARACTER)
    s.add_argument("--style", default=DEFAULT_STYLE)
    s.add_argument("--background", default=DEFAULT_BACKGROUND)
    s.add_argument("--extra", default="")
    s.add_argument("--actions", default="idle,walk,run,attack_light,hurt,death")
    s.add_argument("--directions", default="front,right,back,left")
    s.add_argument("--output", default=None)
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--posepacks", action="store_true")
    s.add_argument("--pose-size", type=int, default=512)
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("collect", help="Collect sprite outputs under a folder into pack_index.json")
    s.add_argument("--root", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_collect)

    s = sub.add_parser("atlas", help="Build one atlas.png + atlas.json from many SpriteForge outputs")
    s.add_argument("--root", default=None)
    s.add_argument("--sprite-dir", action="append", default=[])
    s.add_argument("--output", required=True)
    s.add_argument("--max-width", type=int, default=4096)
    s.add_argument("--padding", type=int, default=4)
    s.set_defaults(func=cmd_atlas)

    s = sub.add_parser("qa", help="Run QA across all sprite outputs under a folder")
    s.add_argument("--root", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_qa)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
