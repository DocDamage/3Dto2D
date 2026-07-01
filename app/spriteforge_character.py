#!/usr/bin/env python3
"""Character pack and multi-action batch helpers for SpriteForge Studio.

The goal is to keep WAN prompts, seeds, reference art, palettes, and actions organized
so a character does not drift wildly across idle/walk/attack/runnning clips.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from PIL import Image, ImageDraw

from spriteforge_utils import safe_name

ROOT = Path(__file__).resolve().parent
DEFAULT_ACTIONS = ["idle", "walk", "run", "attack_light", "attack_heavy", "hurt", "death"]
DEFAULT_DIRECTIONS = ["right"]


def split_csv(value: Optional[str], default: List[str]) -> List[str]:
    if not value:
        return list(default)
    return [x.strip() for x in value.split(",") if x.strip()]


def palette_from_image(path: Path, colors: int = 8) -> List[str]:
    img = Image.open(path).convert("RGBA")
    # Ignore transparent pixels, downsize for speed.
    img.thumbnail((192, 192), Image.Resampling.LANCZOS)
    pixels = []
    pixel_list = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    for r, g, b, a in pixel_list:
        if a > 64:
            pixels.append((r, g, b))
    if not pixels:
        pixels = [(r, g, b) for r, g, b, a in pixel_list]
    work = Image.new("RGB", (len(pixels), 1))
    work.putdata(pixels)
    q = work.quantize(colors=min(colors, max(1, len(set(pixels)))), method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    used = sorted(q.getcolors() or [], reverse=True)
    out: List[str] = []
    for _count, idx in used[:colors]:
        i = idx * 3
        if i + 2 < len(pal):
            out.append("#%02X%02X%02X" % (pal[i], pal[i + 1], pal[i + 2]))
    return out


def write_palette_image(colors: List[str], out: Path, cell: int = 48) -> None:
    if not colors:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (cell * len(colors), cell), "white")
    draw = ImageDraw.Draw(img)
    for i, hx in enumerate(colors):
        draw.rectangle((i * cell, 0, (i + 1) * cell, cell), fill=hx)
    img.save(out)


def build_prompt_pack(action: str, direction: str, character: str, style: str, background: str) -> Dict[str, Any]:
    try:
        import spriteforge_prompts as prompts
        return prompts.build_prompt(action=action, direction=direction, character=character, style=style, background=background)
    except Exception:
        positive = f"{character}, professional appealing character design, heroic adult proportions, distinctive outfit, strong shape language, {action} animation, {direction} view, {style}, locked camera, centered, {background}, full body game sprite, clean silhouette"
        negative = "camera movement, zoom, cuts, close up, motion blur, changing outfit, changing identity, complex background, text, subtitles, watermark, deformed body, extra limbs, missing limbs, bad anatomy, childlike drawing, amateur doodle, crude sketch, messy linework, ugly face, muddy colors"
        return {"positive": positive, "negative": negative}


def make_command(job: Dict[str, Any]) -> str:
    args = [
        "python", "spriteforge_unified.py", "generate-sprite", "--start-comfy",
        "--mode", job.get("mode", "t2v"),
        "--profile", job.get("profile", "rtx3060_12gb"),
        "--action", job["action"],
        "--direction", job["direction"],
        "--seed", str(job["seed"]),
        "--output-prefix", job.get("output_prefix", f"SpriteForge/{job['character_slug']}_{job['action']}_{job['direction']}"),
    ]
    if job.get("character"):
        args += ["--character", job["character"]]
    if job.get("style"):
        args += ["--style", job["style"]]
    if job.get("background"):
        args += ["--background", job["background"]]
    if job.get("reference_image"):
        args += ["--reference-image", job["reference_image"]]
    if job.get("workflow"):
        args += ["--workflow", job["workflow"]]
    return " ".join('"' + a + '"' if " " in str(a) else str(a) for a in args)


def cmd_create(args: argparse.Namespace) -> None:
    slug = safe_name(args.name)
    out = Path(args.output or (ROOT / "characters" / slug)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    refs_dir = out / "references"
    refs_dir.mkdir(exist_ok=True)

    ref_rel = None
    palette: List[str] = []
    if args.reference_image:
        src = Path(args.reference_image).resolve()
        if not src.exists():
            raise FileNotFoundError(src)
        dest = refs_dir / src.name
        shutil.copy2(src, dest)
        ref_rel = str(dest.relative_to(out)).replace("\\", "/")
        palette = palette_from_image(dest, colors=args.palette_colors)
        write_palette_image(palette, out / "palette.png")

    actions = split_csv(args.actions, DEFAULT_ACTIONS)
    directions = split_csv(args.directions, DEFAULT_DIRECTIONS)
    seed_base = int(args.seed if args.seed >= 0 else random.randint(100000, 999999999))
    profile = {
        "schema": "spriteforge.character.v1",
        "name": args.name,
        "slug": slug,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "description": args.description,
        "style": args.style,
        "background": args.background,
        "reference_image": ref_rel,
        "palette": palette,
        "identity_rules": [
            "preserve face, clothing, proportions, silhouette, and palette across every action",
            "locked orthographic-like camera, no zoom, no cuts, no background changes",
            "single full body character only, centered, readable silhouette",
        ],
        "negative_identity": "changing outfit, changing face, changing body proportions, morphing, extra characters, camera motion, zoom, cuts, closeup, text, watermark",
        "actions": actions,
        "directions": directions,
        "seed_base": seed_base,
        "recommended_local_profile": args.profile,
    }
    (out / "character_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

    jobs = []
    n = 0
    for action in actions:
        for direction in directions:
            prompt = build_prompt_pack(action, direction, args.description, args.style, args.background)
            seed = seed_base + n * 9973
            jobs.append({
                "character_slug": slug,
                "character": args.description,
                "style": args.style,
                "background": args.background,
                "action": action,
                "direction": direction,
                "mode": args.mode,
                "profile": args.profile,
                "seed": seed,
                "reference_image": str((out / ref_rel).resolve()) if ref_rel and args.reference_absolute else (str(out / ref_rel) if ref_rel else None),
                "positive": prompt.get("positive"),
                "negative": prompt.get("negative"),
                "output_prefix": f"SpriteForge/{slug}_{action}_{direction}",
            })
            n += 1

    batch = {"schema": "spriteforge.action_batch.v1", "character_profile": "character_profile.json", "jobs": jobs}
    (out / "action_batch.json").write_text(json.dumps(batch, indent=2), encoding="utf-8")

    bat_lines = ["@echo off", "cd /d \"%~dp0\"", "cd ..\\..", "call .venv\\Scripts\\activate.bat", ""]
    for job in jobs:
        bat_lines.append("echo Running " + job["action"] + " " + job["direction"])
        bat_lines.append(make_command(job))
        bat_lines.append("if errorlevel 1 pause")
        bat_lines.append("")
    (out / "run_action_batch.bat").write_text("\n".join(bat_lines), encoding="utf-8")

    notes = f"""# {args.name} Character Pack

Use this folder as the identity source for consistent sprite actions.

Files:

- `character_profile.json` — identity, palette, and rules
- `action_batch.json` — machine-readable action plan
- `run_action_batch.bat` — sequential local generation commands
- `palette.png` — extracted palette if a reference image was supplied

Recommended process:

1. Generate `idle` first.
2. Pick the best seed/reference result.
3. Reuse that seed family for walk/run/attack.
4. Run QA on every output.
5. Fix or regenerate clips that fail silhouette/loop/foot-drift checks.
"""
    (out / "README_CHARACTER_PACK.md").write_text(notes, encoding="utf-8")
    print(f"Character pack: {out}")
    print(f"Batch file: {out / 'run_action_batch.bat'}")


def cmd_batch(args: argparse.Namespace) -> None:
    profile_path = Path(args.profile).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    base = profile_path.parent
    actions = split_csv(args.actions, profile.get("actions") or DEFAULT_ACTIONS)
    directions = split_csv(args.directions, profile.get("directions") or DEFAULT_DIRECTIONS)
    out = Path(args.output or (base / f"batch_{time.strftime('%Y%m%d_%H%M%S')}")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    seed_base = int(args.seed if args.seed >= 0 else profile.get("seed_base", random.randint(100000, 999999999)))
    ref = profile.get("reference_image")
    ref_path = str((base / ref).resolve()) if ref else None
    jobs = []
    n = 0
    for action in actions:
        for direction in directions:
            job = {
                "character_slug": profile.get("slug", safe_name(profile.get("name", "character"))),
                "character": profile.get("description"),
                "style": args.style or profile.get("style"),
                "background": args.background or profile.get("background"),
                "action": action,
                "direction": direction,
                "mode": args.mode,
                "profile": args.local_profile or profile.get("recommended_local_profile", "rtx3060_12gb"),
                "seed": seed_base + n * 9973,
                "reference_image": ref_path,
                "output_prefix": f"SpriteForge/{profile.get('slug','character')}_{action}_{direction}",
            }
            jobs.append(job)
            n += 1
    (out / "action_batch.json").write_text(json.dumps({"schema": "spriteforge.action_batch.v1", "jobs": jobs}, indent=2), encoding="utf-8")
    bat = ["@echo off", "cd /d \"%~dp0\"", "cd ..\\..", "call .venv\\Scripts\\activate.bat", ""]
    for job in jobs:
        bat.append("echo Running " + job["action"] + " " + job["direction"])
        bat.append(make_command(job))
        bat.append("if errorlevel 1 pause")
        bat.append("")
    (out / "run_action_batch.bat").write_text("\n".join(bat), encoding="utf-8")
    print(f"Batch plan: {out / 'action_batch.json'}")
    print(f"Batch runner: {out / 'run_action_batch.bat'}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge character consistency packs")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("create", help="Create a character consistency pack")
    s.add_argument("--name", required=True)
    s.add_argument("--description", required=True)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--style", default="polished 2D game sprite, professional character design, crisp cel-shaded edges, consistent palette")
    s.add_argument("--background", default="plain bright green background")
    s.add_argument("--actions", default=",".join(DEFAULT_ACTIONS))
    s.add_argument("--directions", default=",".join(DEFAULT_DIRECTIONS))
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="rtx3060_12gb")
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--palette-colors", type=int, default=8)
    s.add_argument("--reference-absolute", action="store_true", help="Write absolute reference image path in generated batch jobs")
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_create)

    s = sub.add_parser("batch", help="Generate a fresh batch plan from an existing character_profile.json")
    s.add_argument("--profile", required=True)
    s.add_argument("--actions", default=None)
    s.add_argument("--directions", default=None)
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--local-profile", default=None)
    s.add_argument("--style", default=None)
    s.add_argument("--background", default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_batch)
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
