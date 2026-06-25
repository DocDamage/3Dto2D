#!/usr/bin/env python3
"""Production pack planner for SpriteForge actions."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import spriteforge_prompts as prompts

ROOT = Path(__file__).resolve().parent
DEFAULT_ACTIONS = ["idle", "walk", "run", "attack_light", "attack_heavy", "jump", "hurt", "death"]


def build_plan(character: str, style: str, direction: str, actions: List[str], output: Path, pose: bool, seeds: int) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    prompt_dir = output / "prompts"
    prompt_dir.mkdir(exist_ok=True)
    pose_dir = output / "posepacks"
    if pose:
        pose_dir.mkdir(exist_ok=True)

    for action in actions:
        pack = prompts.build_prompt(
            action=action,
            direction=direction,
            character=character,
            style=style,
            background=prompts.DEFAULT_BACKGROUND,
            extra="",
            reference=False,
            pose_guided=pose,
        )
        prompt_path = prompt_dir / f"{action}_{direction}.json"
        prompt_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
        posepack = None
        if pose:
            frames = int(prompts.ACTION_TEMPLATES.get(action, {}).get("frames", 24))
            posepack = pose_dir / f"{action}_{direction}"
            prompts.make_posepack(action, direction, frames, 512, posepack)
        commands = []
        for i in range(max(1, seeds)):
            seed_arg = "--seed -1" if seeds <= 1 else f"--seed {100000 + i}"
            cmd = (
                f'python spriteforge_unified.py generate-sprite --start-comfy --profile rtx3060_12gb '
                f'--action {action} --direction {direction} --character "{character}" --style "{style}" {seed_arg}'
            )
            if posepack:
                cmd += f' --posepack "{posepack}"'
            commands.append(cmd)
        entries.append({
            "action": action,
            "direction": direction,
            "prompt_file": str(prompt_path),
            "posepack": str(posepack) if posepack else None,
            "recommended_frames": prompts.ACTION_TEMPLATES.get(action, {}).get("frames", 24),
            "commands": commands,
        })

    plan = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "character": character,
        "style": style,
        "direction": direction,
        "pose_guided": pose,
        "actions": entries,
        "next_steps": [
            "Run one debug generation per action first.",
            "Convert each result to sprite sheets.",
            "Run quality-check on every output.",
            "Build atlas after all actions pass QC.",
        ],
    }
    out = output / "production_plan.json"
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (output / "RUN_COMMANDS.bat").write_text("@echo off\n" + "\n".join(cmd + "\n" for e in entries for cmd in e["commands"]) + "\npause\n", encoding="utf-8")
    print(f"Production plan: {out}")
    print(f"Run commands: {output / 'RUN_COMMANDS.bat'}")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a SpriteForge action production plan")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("plan")
    s.add_argument("--character", default=prompts.DEFAULT_CHARACTER)
    s.add_argument("--style", default=prompts.DEFAULT_STYLE)
    s.add_argument("--direction", default="right")
    s.add_argument("--actions", default=",".join(DEFAULT_ACTIONS), help="Comma-separated action list")
    s.add_argument("--output", default=None)
    s.add_argument("--pose", action="store_true")
    s.add_argument("--seeds", type=int, default=1, help="How many seed commands to generate per action")
    s.set_defaults(func=lambda a: build_plan(a.character, a.style, a.direction, [x.strip() for x in a.actions.split(',') if x.strip()], Path(a.output) if a.output else ROOT / "output" / "production_plan", a.pose, a.seeds))
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
