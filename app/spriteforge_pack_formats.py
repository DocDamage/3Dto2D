#!/usr/bin/env python3
"""Extra atlas/export formats for SpriteForge spritesheets."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def load_meta(sprite_dir: Path) -> Dict[str, Any]:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def frame_name(meta: Dict[str, Any], i: int) -> str:
    anim = str(meta.get("animation", "anim"))
    return f"{anim}_{i:04d}.png"


def texturepacker_json(meta: Dict[str, Any], image_name: str = "sheet.png") -> Dict[str, Any]:
    fw, fh = int(meta["frame_width"]), int(meta["frame_height"])
    frames: Dict[str, Any] = {}
    for i in range(int(meta["frame_count"])):
        fr = meta.get("frames", [])[i] if i < len(meta.get("frames", [])) else {
            "x": (i % int(meta.get("columns", 1))) * fw,
            "y": (i // int(meta.get("columns", 1))) * fh,
            "w": fw,
            "h": fh,
        }
        frames[frame_name(meta, i)] = {
            "frame": {"x": int(fr["x"]), "y": int(fr["y"]), "w": fw, "h": fh},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": fw, "h": fh},
            "sourceSize": {"w": fw, "h": fh},
            "duration": int(fr.get("duration_ms", round(1000 / float(meta.get("fps", 12))))),
        }
    return {
        "frames": frames,
        "meta": {
            "app": "SpriteForge Studio",
            "version": "6",
            "image": image_name,
            "format": "RGBA8888",
            "size": {"w": int(meta.get("columns", 1)) * fw, "h": int(meta.get("rows", 1)) * fh},
            "scale": "1",
        },
    }


def phaser_json(meta: Dict[str, Any], image_name: str = "sheet.png") -> Dict[str, Any]:
    # Phaser accepts TexturePacker-style hash atlases. Keep format explicit.
    data = texturepacker_json(meta, image_name=image_name)
    data["meta"]["type"] = "TexturePackerJSONHash"
    return data


def pixijs_json(meta: Dict[str, Any], image_name: str = "sheet.png") -> Dict[str, Any]:
    data = texturepacker_json(meta, image_name=image_name)
    data["animations"] = {
        str(meta.get("animation", "anim")): [frame_name(meta, i) for i in range(int(meta["frame_count"]))]
    }
    return data


def css_export(meta: Dict[str, Any], image_name: str = "sheet.png") -> str:
    anim = str(meta.get("animation", "anim")).replace(" ", "_")
    fw, fh = int(meta["frame_width"]), int(meta["frame_height"])
    fps = float(meta.get("fps", 12))
    count = int(meta["frame_count"])
    duration = max(0.001, count / fps)
    return f"""/* SpriteForge CSS sprite animation */
.sprite-{anim} {{
  width: {fw}px;
  height: {fh}px;
  background-image: url('{image_name}');
  background-repeat: no-repeat;
  image-rendering: pixelated;
  animation: spriteforge-{anim} {duration:.3f}s steps({count}) infinite;
}}

@keyframes spriteforge-{anim} {{
  from {{ background-position: 0 0; }}
  to {{ background-position: -{fw * count}px 0; }}
}}
"""


def cmd_export(args: argparse.Namespace) -> None:
    sprite_dir = Path(args.sprite_dir).resolve()
    meta = load_meta(sprite_dir)
    out_dir = Path(args.output).resolve() if args.output else sprite_dir / "atlas_exports"
    ensure_dir(out_dir)
    image_name = args.image_name or "sheet.png"
    if args.copy_image:
        shutil.copy2(sprite_dir / meta.get("image", "sheet.png"), out_dir / image_name)
    if args.format == "texturepacker":
        data = texturepacker_json(meta, image_name)
        out = out_dir / "texturepacker.json"
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    elif args.format == "phaser":
        data = phaser_json(meta, image_name)
        out = out_dir / "phaser_atlas.json"
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    elif args.format == "pixijs":
        data = pixijs_json(meta, image_name)
        out = out_dir / "pixijs_spritesheet.json"
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    elif args.format == "css":
        out = out_dir / "sprite.css"
        out.write_text(css_export(meta, image_name), encoding="utf-8")
    else:
        raise ValueError(args.format)
    print(f"Exported {args.format}: {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export extra SpriteForge atlas formats")
    s = p.add_subparsers(dest="command", required=True)
    e = s.add_parser("export")
    e.add_argument("--sprite-dir", required=True)
    e.add_argument("--format", required=True, choices=["texturepacker", "phaser", "pixijs", "css"])
    e.add_argument("--output", default=None)
    e.add_argument("--image-name", default=None)
    e.add_argument("--copy-image", action="store_true")
    e.set_defaults(func=cmd_export)
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
