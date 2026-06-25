#!/usr/bin/env python3
"""SpriteForge production helpers v6.

Thin production layer around the core SpriteForge tools:
- project manifests
- multi-action/view batch plans
- prompt and posepack generation
- quality reports
- atlas packing
- engine atlas helper export
- environment lockfiles
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import spriteforge_prompts as prompts

ROOT = Path(__file__).resolve().parent
DEFAULT_ACTIONS = ["idle", "walk", "run", "attack_light", "attack_heavy", "jump", "hurt", "death"]
DEFAULT_VIEWS = ["right"]


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "spriteforge"


def split_csv(value: Optional[str], default: Sequence[str]) -> List[str]:
    if not value:
        return list(default)
    return [x.strip() for x in value.split(",") if x.strip()]


def run(cmd: Sequence[str], check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    print("$ " + " ".join(f'\"{c}\"' if " " in str(c) else str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=check, cwd=str(cwd or ROOT))


def run_shell(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    print("$ " + cmd, flush=True)
    return subprocess.run(cmd, shell=True, check=check, cwd=str(ROOT))


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def project_root_from_name(name: str) -> Path:
    return ROOT / "projects" / safe_name(name)


def project_path(path_or_dir: str) -> Path:
    p = Path(path_or_dir)
    if not p.is_absolute():
        p = ROOT / p
    if p.is_dir():
        return p / "project.spriteforge.json"
    return p


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def cmd_project_init(args: argparse.Namespace) -> None:
    root = Path(args.output).resolve() if args.output else project_root_from_name(args.name).resolve()
    actions = split_csv(args.actions, DEFAULT_ACTIONS)
    views = split_csv(args.views or args.direction, DEFAULT_VIEWS)
    for sub in ["prompts", "posepacks", "sprites", "atlas", "batch", "qa", "qc", "references", "workflows", "renders", "engine"]:
        (root / sub).mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "spriteforge_project_v6",
        "name": args.name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "character": args.character,
        "style": args.style,
        "background": args.background,
        "direction": views[0],
        "views": views,
        "actions": actions,
        "default_profile": args.profile,
        "default_mode": args.mode,
        "default_fps": args.fps,
        "default_cell_size": args.cell_size,
        "reference_image": args.reference_image or "",
        "paths": {
            "root": str(root),
            "prompts": str(root / "prompts"),
            "posepacks": str(root / "posepacks"),
            "sprites": str(root / "sprites"),
            "atlas": str(root / "atlas"),
            "batch": str(root / "batch"),
            "qa": str(root / "qa"),
            "references": str(root / "references"),
            "workflows": str(root / "workflows"),
            "engine": str(root / "engine"),
        },
    }
    out = root / "project.spriteforge.json"
    write_json(out, data)
    (root / "README.md").write_text(f"# {args.name}\n\nSpriteForge v6 production project.\n", encoding="utf-8")
    print(f"Project: {out}")


def load_project(path: str) -> Dict[str, Any]:
    p = project_path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    return read_json(p)


def q(s: str) -> str:
    return '"' + str(s).replace('"', '\\"') + '"'


def argv_to_bat(argv: Sequence[str]) -> str:
    return " ".join(q(a) if any(ch.isspace() for ch in str(a)) else str(a) for a in argv)


def make_generate_argv(project: Dict[str, Any], action: str, view: str, prompt: Dict[str, Any], posepack: Optional[Path], args: argparse.Namespace) -> List[str]:
    argv = [
        sys.executable,
        str(ROOT / "spriteforge_unified.py"),
        "generate-sprite",
        "--start-comfy",
        "--mode", args.mode or project.get("default_mode", "t2v"),
        "--profile", args.profile or project.get("default_profile", "rtx3060_12gb"),
        "--action", action,
        "--direction", view,
        "--prompt", str(prompt.get("positive", "")),
        "--negative", str(prompt.get("negative", "")),
        "--frames", str(args.frames or prompt.get("recommended_frames") or 33),
    ]
    if args.width:
        argv += ["--width", str(args.width)]
    if args.height:
        argv += ["--height", str(args.height)]
    if args.steps:
        argv += ["--steps", str(args.steps)]
    if args.seed is not None:
        argv += ["--seed", str(args.seed)]
    ref = args.reference_image or project.get("reference_image") or ""
    if ref:
        argv += ["--reference-image", str(ref)]
    if posepack:
        argv += ["--posepack", str(posepack)]
    return argv


def cmd_batch_plan(args: argparse.Namespace) -> None:
    project_file = project_path(args.project)
    project = read_json(project_file)
    root = Path(project["paths"]["root"]).resolve()
    actions = split_csv(args.actions, project.get("actions", DEFAULT_ACTIONS))
    views = split_csv(args.views, project.get("views", [project.get("direction", "right")]))
    prompt_dir = Path(project["paths"].get("prompts", root / "prompts"))
    pose_dir = Path(project["paths"].get("posepacks", root / "posepacks"))
    sprite_dir = Path(project["paths"].get("sprites", root / "sprites"))
    batch_dir = Path(project["paths"].get("batch", root / "batch"))
    prompt_dir.mkdir(parents=True, exist_ok=True)
    pose_dir.mkdir(parents=True, exist_ok=True)
    sprite_dir.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    actions_compat: List[Dict[str, Any]] = []
    commands_bat: List[str] = []
    for action in actions:
        for view in views:
            slug = safe_name(f"{action}_{view}")
            prompt_pack = prompts.build_prompt(
                action=action,
                direction=view,
                character=project.get("character", prompts.DEFAULT_CHARACTER),
                style=project.get("style", prompts.DEFAULT_STYLE),
                background=project.get("background", prompts.DEFAULT_BACKGROUND),
                reference=bool(args.reference or args.reference_image or project.get("reference_image")),
                pose_guided=bool(args.pose_guided),
            )
            prompt_path = prompt_dir / f"{slug}.prompt.json"
            write_json(prompt_path, prompt_pack)
            posepack_path: Optional[Path] = None
            if args.pose_guided:
                frames = int(args.frames or prompt_pack.get("recommended_frames", 24))
                posepack_path = pose_dir / slug
                prompts.make_posepack(action, view, frames, 512, posepack_path)
            out_sprite = sprite_dir / slug
            generate_argv = make_generate_argv(project, action, view, prompt_pack, posepack_path, args)
            commands_bat.append(argv_to_bat(generate_argv))
            item = {
                "id": slug,
                "action": action,
                "view": view,
                "prompt_file": str(prompt_path),
                "posepack": str(posepack_path) if posepack_path else None,
                "sprite_dir": str(out_sprite),
                "recommended_frames": prompt_pack.get("recommended_frames"),
                "recommended_fps": prompt_pack.get("recommended_fps", project.get("default_fps", 12)),
                "commands": {
                    "generate_argv": generate_argv,
                    "generate_bat": argv_to_bat(generate_argv),
                    "qa_argv": [sys.executable, str(ROOT / "spriteforge_unified.py"), "qa", "--sprite-dir", str(out_sprite)],
                },
            }
            items.append(item)
            actions_compat.append({
                "action": action,
                "direction": view,
                "prompt_file": str(prompt_path),
                "posepack": str(posepack_path) if posepack_path else None,
                "recommended_frames": prompt_pack.get("recommended_frames"),
                "commands": [argv_to_bat(generate_argv)],
            })

    plan = {
        "schema": "spriteforge_batch_plan_v6",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project": str(project_file),
        "project_root": str(root),
        "profile": args.profile or project.get("default_profile", "rtx3060_12gb"),
        "mode": args.mode or project.get("default_mode", "t2v"),
        "pose_guided": bool(args.pose_guided),
        "items": items,
        "actions": actions_compat,
        "next_steps": [
            "Run prompts/poses stage only to verify assets.",
            "Preview generation commands with --stage generate --dry-run.",
            "Run one action first before executing the entire batch.",
            "Run QA on every output before atlas packing.",
        ],
    }
    out = Path(args.output).resolve() if args.output else batch_dir / "batch_plan.json"
    write_json(out, plan)
    # Also write legacy name for old BATs/modules.
    write_json(batch_dir / "production_plan.json", plan)
    bat = batch_dir / "RUN_GENERATE_COMMANDS.bat"
    bat.write_text("@echo off\ncd /d " + q(str(ROOT)) + "\n" + "\n".join(commands_bat) + "\npause\n", encoding="utf-8")
    print(f"Batch plan: {out}")
    print(f"Legacy copy: {batch_dir / 'production_plan.json'}")
    print(f"Run commands: {bat}")
    print(f"Planned {len(items)} action/view jobs.")


def cmd_run_batch(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = ROOT / plan_path
    if plan_path.is_dir():
        if (plan_path / "batch_plan.json").exists():
            plan_path = plan_path / "batch_plan.json"
        else:
            plan_path = plan_path / "production_plan.json"
    plan = read_json(plan_path)
    items = plan.get("items") or []
    if not items and plan.get("actions"):
        for e in plan["actions"]:
            items.append({
                "id": safe_name(f"{e.get('action')}_{e.get('direction','right')}"),
                "action": e.get("action"),
                "view": e.get("direction", "right"),
                "prompt_file": e.get("prompt_file"),
                "posepack": e.get("posepack"),
                "commands": {"generate_bat": e.get("commands", [""])[0]},
            })
    stages = ["prompts", "poses", "generate", "qa"] if args.stage == "all" else [args.stage]
    for item in items:
        print(f"\n[{item.get('id')}]", flush=True)
        for stage in stages:
            if stage == "prompts":
                p = item.get("prompt_file")
                print(f"prompt: {p} {'OK' if p and Path(p).exists() else 'MISSING'}")
            elif stage == "poses":
                p = item.get("posepack")
                if p:
                    print(f"posepack: {p} {'OK' if Path(p).exists() else 'MISSING'}")
                else:
                    print("posepack: none")
            elif stage == "generate":
                argv = item.get("commands", {}).get("generate_argv")
                bat = item.get("commands", {}).get("generate_bat")
                if args.execute:
                    if argv:
                        run(argv, check=not args.continue_on_error)
                    elif bat:
                        run_shell(bat, check=not args.continue_on_error)
                else:
                    print("DRY RUN: " + (bat or argv_to_bat(argv or [])))
            elif stage == "qa":
                qa = item.get("commands", {}).get("qa_argv")
                if qa and args.execute:
                    run(qa, check=False)
                else:
                    print("QA command: " + argv_to_bat(qa or []))


def cmd_qa(args: argparse.Namespace) -> None:
    run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", args.sprite_dir] + (["--output", args.output] if args.output else []), check=False)


def expand_inputs(inputs: List[str]) -> List[Path]:
    paths: List[Path] = []
    for item in inputs:
        matches = glob.glob(item)
        if not matches:
            matches = glob.glob(str(ROOT / item))
        if matches:
            paths.extend(Path(m) for m in matches)
        else:
            paths.append(Path(item))
    out: List[Path] = []
    seen = set()
    for p in paths:
        p = p.resolve()
        if p.is_file() and p.name == "sheet.json":
            p = p.parent
        if (p / "sheet.json").exists() and str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out


def cmd_atlas(args: argparse.Namespace) -> None:
    sprites = expand_inputs(args.inputs)
    if not sprites:
        raise RuntimeError("No atlas inputs found. Add folders containing sheet.json.")
    cmd = [sys.executable, str(ROOT / "spriteforge_atlas.py"), "atlas", "--output", args.output, "--sprites"] + [str(p) for p in sprites]
    if args.columns:
        cmd += ["--columns", str(args.columns)]
    if args.cell_size:
        cmd += ["--cell-size", args.cell_size]
    if args.name:
        cmd += ["--name", args.name]
    run(cmd)


def cmd_export_atlas_engine(args: argparse.Namespace) -> None:
    atlas_dir = Path(args.atlas_dir)
    if not atlas_dir.is_absolute():
        atlas_dir = ROOT / atlas_dir
    if not (atlas_dir / "atlas.json").exists():
        raise FileNotFoundError(atlas_dir / "atlas.json")
    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = ROOT / out
        out.mkdir(parents=True, exist_ok=True)
        for name in ["atlas.png", "atlas.json", "GodotAtlasPlayer.gd", "SpriteForgeAtlasPlayer.cs", "atlas_report.html"]:
            src = atlas_dir / name
            if src.exists():
                shutil.copy2(src, out / name)
        print(f"Copied atlas engine helpers to: {out}")
    else:
        print("Atlas engine helpers already exist here:")
        print(atlas_dir / "GodotAtlasPlayer.gd")
        print(atlas_dir / "SpriteForgeAtlasPlayer.cs")
        print("Copy atlas.png + atlas.json + the matching helper into your engine project.")


def git_rev(path: Path) -> Optional[str]:
    if not (path / ".git").exists():
        return None
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(path), text=True).strip()
    except Exception:
        return None


def cmd_lock_env(args: argparse.Namespace) -> None:
    lock_dir = Path(args.output).resolve() if args.output else ROOT / "output" / "env_locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    try:
        pip_freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    except Exception as exc:
        pip_freeze = f"pip freeze failed: {exc}"
    repo_paths = [ROOT, ROOT / "vendor" / "ComfyUI", ROOT / "ComfyUI"]
    for candidate in [ROOT / "vendor" / "ComfyUI" / "custom_nodes", ROOT / "ComfyUI" / "custom_nodes"]:
        if candidate.exists():
            repo_paths += list(candidate.glob("*"))
    repos = [{"path": str(p), "rev": git_rev(p)} for p in repo_paths if p.exists()]
    data = {
        "schema": "spriteforge_environment_lock_v6",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "pip_freeze": pip_freeze.splitlines(),
        "repos": repos,
    }
    out = lock_dir / f"environment_lock_{time.strftime('%Y%m%d_%H%M%S')}.json"
    write_json(out, data)
    print(f"Environment lock: {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge production helpers v6")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("project-init")
    s.add_argument("--name", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--character", required=True)
    s.add_argument("--style", default="clean 2D game sprite, crisp outline")
    s.add_argument("--background", default=prompts.DEFAULT_BACKGROUND)
    s.add_argument("--direction", default="right")
    s.add_argument("--views", default=None)
    s.add_argument("--actions", default=",".join(DEFAULT_ACTIONS))
    s.add_argument("--profile", default="rtx3060_12gb")
    s.add_argument("--mode", default="t2v")
    s.add_argument("--fps", type=int, default=12)
    s.add_argument("--cell-size", default="512x512")
    s.add_argument("--reference-image", default="")
    s.set_defaults(func=cmd_project_init)

    s = sub.add_parser("batch-plan")
    s.add_argument("--project", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--actions", default=None)
    s.add_argument("--views", default=None)
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--reference", action="store_true")
    s.add_argument("--reference-image", default="")
    s.add_argument("--profile", default=None)
    s.add_argument("--mode", default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--steps", type=int, default=None)
    s.add_argument("--seed", default=None)
    s.set_defaults(func=cmd_batch_plan)

    s = sub.add_parser("run-batch")
    s.add_argument("--plan", required=True)
    s.add_argument("--stage", required=True, choices=["prompts", "poses", "generate", "qa", "all"])
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--execute", action="store_true")
    s.add_argument("--continue-on-error", action="store_true")
    s.set_defaults(func=cmd_run_batch)

    s = sub.add_parser("qa")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_qa)

    s = sub.add_parser("atlas")
    s.add_argument("--inputs", nargs="+", required=True)
    s.add_argument("--output", required=True)
    s.add_argument("--columns", type=int, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--name", default="spriteforge_atlas")
    s.set_defaults(func=cmd_atlas)

    s = sub.add_parser("export-atlas-engine")
    s.add_argument("--atlas-dir", required=True)
    s.add_argument("--engine", choices=["godot", "unity"], default="godot")
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_export_atlas_engine)

    s = sub.add_parser("lock-env")
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_lock_env)
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
