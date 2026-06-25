#!/usr/bin/env python3
"""Prompt and pose-pack helpers for SpriteForge Studio v5.

This module is intentionally model/workflow agnostic. It creates:
- strong sprite-action prompts for WAN/ComfyUI
- OpenPose-style guide frame sequences for common sprite actions
- prompt packs you can reuse from the GUI/CLI
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent

DIRECTIONS = {
    "front": "front view, character facing camera",
    "back": "back view, character facing away from camera",
    "left": "left side view, character facing left",
    "right": "right side view, character facing right",
    "three_quarter": "three quarter view, slight turn, readable silhouette",
}

ACTION_TEMPLATES: Dict[str, Dict[str, object]] = {
    "idle": {
        "motion": "idle breathing loop, subtle weight shift, hands steady, feet planted",
        "frames": 24,
        "pose": "idle",
    },
    "walk": {
        "motion": "clean walk cycle loop, alternating legs, stable torso, readable foot contact poses",
        "frames": 32,
        "pose": "walk",
    },
    "run": {
        "motion": "run cycle loop, stronger forward lean, clear leg extension, stable character identity",
        "frames": 24,
        "pose": "run",
    },
    "attack_light": {
        "motion": "light melee attack animation, anticipation, fast strike, follow through, return to idle pose",
        "frames": 24,
        "pose": "attack_light",
    },
    "attack_heavy": {
        "motion": "heavy attack animation, large windup, powerful strike, recovery, readable silhouette",
        "frames": 32,
        "pose": "attack_heavy",
    },
    "cast": {
        "motion": "magic casting animation, hands raise, energy gesture, controlled recovery, feet planted",
        "frames": 32,
        "pose": "cast",
    },
    "jump": {
        "motion": "jump animation, crouch anticipation, takeoff, airborne pose, landing recovery",
        "frames": 24,
        "pose": "jump",
    },
    "hurt": {
        "motion": "hurt reaction animation, quick recoil, torso bends back, returns to stance",
        "frames": 16,
        "pose": "hurt",
    },
    "death": {
        "motion": "death animation, character collapses clearly, no camera movement, final pose held",
        "frames": 40,
        "pose": "death",
    },
}

DEFAULT_CHARACTER = "single full body original game character, consistent face, consistent outfit, clean silhouette"
DEFAULT_STYLE = "2D game sprite animation, crisp edges, readable silhouette, production sprite sheet style"
DEFAULT_BACKGROUND = "plain bright green chroma key background, evenly lit, no shadows on background"
DEFAULT_NEGATIVE = (
    "camera movement, zoom, cuts, close up, motion blur, changing outfit, changing identity, changing face, "
    "extra limbs, missing limbs, deformed body, broken hands, bad anatomy, inconsistent silhouette, complex background, "
    "text, subtitles, watermark, logo, blur, low quality, flicker, frame jump, occlusion, cropped body"
)


def build_prompt(
    action: str,
    direction: str = "right",
    character: str = DEFAULT_CHARACTER,
    style: str = DEFAULT_STYLE,
    background: str = DEFAULT_BACKGROUND,
    extra: str = "",
    reference: bool = False,
    pose_guided: bool = False,
) -> Dict[str, object]:
    if action not in ACTION_TEMPLATES:
        raise KeyError(f"Unknown action '{action}'. Available: {', '.join(sorted(ACTION_TEMPLATES))}")
    if direction not in DIRECTIONS:
        raise KeyError(f"Unknown direction '{direction}'. Available: {', '.join(sorted(DIRECTIONS))}")

    spec = ACTION_TEMPLATES[action]
    modifiers = [
        str(character).strip(),
        str(spec["motion"]),
        DIRECTIONS[direction],
        "locked orthographic-feeling camera, no camera movement, character centered, full body visible, feet visible",
        "loopable animation, first frame and final frame compatible, stable scale, stable ground position",
        str(style).strip(),
        str(background).strip(),
    ]
    if reference:
        modifiers.append("preserve the supplied character reference image identity, outfit, proportions, palette, and silhouette")
    if pose_guided:
        modifiers.append("follow the supplied pose guide sequence closely while preserving character identity")
    if extra.strip():
        modifiers.append(extra.strip())
    positive = ", ".join(m for m in modifiers if m)
    return {
        "action": action,
        "direction": direction,
        "positive": positive,
        "negative": DEFAULT_NEGATIVE,
        "recommended_frames": int(spec["frames"]),
        "recommended_fps": 12,
        "pose_template": str(spec["pose"]),
    }


# Very small stick figure system: normalized joints in a 0..1 box.
JOINTS = ["head", "neck", "pelvis", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_hand", "r_hand", "l_knee", "r_knee", "l_foot", "r_foot"]
BONES = [
    ("head", "neck"), ("neck", "pelvis"),
    ("neck", "l_shoulder"), ("l_shoulder", "l_elbow"), ("l_elbow", "l_hand"),
    ("neck", "r_shoulder"), ("r_shoulder", "r_elbow"), ("r_elbow", "r_hand"),
    ("pelvis", "l_knee"), ("l_knee", "l_foot"),
    ("pelvis", "r_knee"), ("r_knee", "r_foot"),
]


def _base_pose() -> Dict[str, Tuple[float, float]]:
    return {
        "head": (0.50, 0.16), "neck": (0.50, 0.28), "pelvis": (0.50, 0.55),
        "l_shoulder": (0.42, 0.31), "r_shoulder": (0.58, 0.31),
        "l_elbow": (0.38, 0.45), "r_elbow": (0.62, 0.45),
        "l_hand": (0.36, 0.58), "r_hand": (0.64, 0.58),
        "l_knee": (0.43, 0.73), "r_knee": (0.57, 0.73),
        "l_foot": (0.42, 0.91), "r_foot": (0.58, 0.91),
    }


def action_pose(action: str, frame: int, total: int, direction: str = "right") -> Dict[str, Tuple[float, float]]:
    p = _base_pose()
    t = (frame / max(1, total)) * math.tau
    side = -1 if direction == "left" else 1

    if action == "idle":
        bob = math.sin(t) * 0.015
        for k, (x, y) in list(p.items()):
            p[k] = (x, y + bob)
        p["l_hand"] = (0.35, 0.58 + bob * 0.5)
        p["r_hand"] = (0.65, 0.58 - bob * 0.5)

    elif action in {"walk", "run"}:
        amp = 0.12 if action == "walk" else 0.17
        lean = 0.04 * side if action == "run" else 0.015 * side
        for k, (x, y) in list(p.items()):
            p[k] = (x + lean * (1.0 - y), y + math.sin(t) * 0.01)
        leg = math.sin(t) * amp
        arm = -math.sin(t) * amp * 0.9
        p["l_knee"] = (0.43 + leg * side, 0.73)
        p["l_foot"] = (0.42 + leg * 1.6 * side, 0.91)
        p["r_knee"] = (0.57 - leg * side, 0.73)
        p["r_foot"] = (0.58 - leg * 1.6 * side, 0.91)
        p["l_elbow"] = (0.38 + arm * side, 0.45)
        p["l_hand"] = (0.36 + arm * 1.3 * side, 0.58)
        p["r_elbow"] = (0.62 - arm * side, 0.45)
        p["r_hand"] = (0.64 - arm * 1.3 * side, 0.58)

    elif action in {"attack_light", "attack_heavy"}:
        phase = frame / max(1, total - 1)
        windup = math.sin(min(phase, 0.45) / 0.45 * math.pi) if phase < 0.45 else 0
        strike = max(0.0, math.sin((phase - 0.35) / 0.35 * math.pi)) if phase < 0.70 else 0
        recover = max(0.0, 1.0 - (phase - 0.70) / 0.30) if phase >= 0.70 else 1.0
        reach = (0.10 if action == "attack_light" else 0.18) * strike * side
        back = (0.08 if action == "attack_light" else 0.14) * windup * side
        p["r_shoulder"] = (0.58 + reach * 0.3 - back * 0.4, 0.31)
        p["r_elbow"] = (0.62 + reach - back, 0.42 - 0.07 * windup)
        p["r_hand"] = (0.64 + reach * 2.0 - back * 1.3, 0.54 - 0.10 * windup)
        p["l_hand"] = (0.38 - reach * 0.3, 0.56)
        p["pelvis"] = (0.50 + reach * 0.15, 0.55)

    elif action == "cast":
        phase = frame / max(1, total - 1)
        raise_amt = math.sin(min(1.0, phase / 0.5) * math.pi / 2)
        p["l_elbow"] = (0.37, 0.42 - 0.12 * raise_amt)
        p["r_elbow"] = (0.63, 0.42 - 0.12 * raise_amt)
        p["l_hand"] = (0.42, 0.52 - 0.25 * raise_amt)
        p["r_hand"] = (0.58, 0.52 - 0.25 * raise_amt)

    elif action == "jump":
        phase = frame / max(1, total - 1)
        lift = max(0.0, math.sin(phase * math.pi)) * 0.24
        crouch = max(0.0, math.sin(min(phase, 0.25) / 0.25 * math.pi)) * 0.07 if phase < 0.25 else 0
        for k, (x, y) in list(p.items()):
            p[k] = (x, y - lift + crouch)
        p["l_knee"] = (0.45, 0.76 - lift + crouch)
        p["r_knee"] = (0.55, 0.76 - lift + crouch)
        p["l_hand"] = (0.34, 0.47 - lift)
        p["r_hand"] = (0.66, 0.47 - lift)

    elif action == "hurt":
        phase = frame / max(1, total - 1)
        recoil = math.sin(phase * math.pi) * 0.12 * side
        for k, (x, y) in list(p.items()):
            p[k] = (x - recoil * (1.0 - y), y)
        p["head"] = (p["head"][0] - recoil * 0.8, p["head"][1])
        p["r_hand"] = (0.66 - recoil, 0.50)

    elif action == "death":
        phase = frame / max(1, total - 1)
        fall = min(1.0, phase * 1.4)
        # Rotate figure toward the floor in a crude, readable way.
        cx, cy = 0.50, 0.78
        angle = fall * (math.pi / 2) * side
        for k, (x, y) in list(p.items()):
            dx, dy = x - cx, y - cy
            rx = cx + dx * math.cos(angle) - dy * math.sin(angle)
            ry = cy + dx * math.sin(angle) + dy * math.cos(angle)
            p[k] = (rx, min(0.93, ry + fall * 0.05))

    return p


def _project(pt: Tuple[float, float], size: int, margin: int) -> Tuple[int, int]:
    x, y = pt
    return (int(margin + x * (size - 2 * margin)), int(margin + y * (size - 2 * margin)))


def draw_pose_frame(action: str, frame: int, total: int, direction: str, size: int, bg: Tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    pts = action_pose(action, frame, total, direction)
    margin = int(size * 0.08)

    # Ground line helps with foot locking when used visually as a guide.
    ground_y = int(size * 0.92)
    d.line([(int(size * 0.16), ground_y), (int(size * 0.84), ground_y)], fill=(80, 80, 80), width=max(1, size // 160))

    # Bone colors roughly separate limbs for visual clarity.
    for a, b in BONES:
        pa, pb = _project(pts[a], size, margin), _project(pts[b], size, margin)
        d.line([pa, pb], fill=(255, 255, 255), width=max(2, size // 64))
        d.line([pa, pb], fill=(40, 190, 255), width=max(1, size // 96))
    for name in JOINTS:
        x, y = _project(pts[name], size, margin)
        r = max(3, size // 64)
        color = (255, 220, 60) if name in {"head", "neck", "pelvis"} else (255, 80, 80)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    return img


def make_posepack(action: str, direction: str, frames: int, size: int, output: Path, bg: Tuple[int, int, int] = (0, 0, 0)) -> Dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    frame_dir = output / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(frames):
        img = draw_pose_frame(action, i, frames, direction, size, bg)
        p = frame_dir / f"pose_{i:04d}.png"
        img.save(p)
        paths.append(str(p))
    contact = make_contact_sheet([Path(p) for p in paths], size)
    contact_path = output / "pose_contact_sheet.png"
    contact.save(contact_path)
    meta = {
        "action": action,
        "direction": direction,
        "frames": frames,
        "size": size,
        "fps": 12,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "frames_dir": str(frame_dir),
        "contact_sheet": str(contact_path),
        "files": paths,
    }
    (output / "posepack.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def make_contact_sheet(paths: Sequence[Path], cell: int) -> Image.Image:
    imgs = [Image.open(p).convert("RGB") for p in paths]
    n = len(imgs)
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)
    thumb = max(96, min(192, cell // 2))
    sheet = Image.new("RGB", (cols * thumb, rows * thumb), (20, 20, 20))
    for i, img in enumerate(imgs):
        im = img.resize((thumb, thumb), Image.Resampling.LANCZOS)
        sheet.paste(im, ((i % cols) * thumb, (i // cols) * thumb))
    return sheet


def cmd_build(args: argparse.Namespace) -> None:
    data = build_prompt(
        action=args.action,
        direction=args.direction,
        character=args.character,
        style=args.style,
        background=args.background,
        extra=args.extra,
        reference=args.reference,
        pose_guided=args.pose_guided,
    )
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Wrote prompt pack: {out}")
    print("\nPOSITIVE:\n" + str(data["positive"]))
    print("\nNEGATIVE:\n" + str(data["negative"]))
    print(f"\nRecommended: {data['recommended_frames']} frames at {data['recommended_fps']} FPS")


def cmd_posepack(args: argparse.Namespace) -> None:
    spec = ACTION_TEMPLATES.get(args.action, {})
    frames = args.frames or int(spec.get("frames", 24))
    output = Path(args.output or (ROOT / "output" / "posepacks" / f"{args.action}_{args.direction}_{time.strftime('%Y%m%d_%H%M%S')}"))
    meta = make_posepack(args.action, args.direction, frames, args.size, output)
    print(json.dumps(meta, indent=2))


def cmd_list(args: argparse.Namespace) -> None:
    print("Actions:")
    for k, v in ACTION_TEMPLATES.items():
        print(f" - {k}: {v['motion']} ({v['frames']} frames)")
    print("\nDirections:")
    for k, v in DIRECTIONS.items():
        print(f" - {k}: {v}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge prompt and pose-pack builder")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("build", help="Build a WAN sprite-action prompt")
    s.add_argument("--action", required=True, choices=sorted(ACTION_TEMPLATES))
    s.add_argument("--direction", default="right", choices=sorted(DIRECTIONS))
    s.add_argument("--character", default=DEFAULT_CHARACTER)
    s.add_argument("--style", default=DEFAULT_STYLE)
    s.add_argument("--background", default=DEFAULT_BACKGROUND)
    s.add_argument("--extra", default="")
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("posepack", help="Create OpenPose-style guide frames for a sprite action")
    s.add_argument("--action", required=True, choices=sorted(ACTION_TEMPLATES))
    s.add_argument("--direction", default="right", choices=sorted(DIRECTIONS))
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--size", type=int, default=512)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_posepack)

    s = sub.add_parser("list", help="List supported actions and directions")
    s.set_defaults(func=cmd_list)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
