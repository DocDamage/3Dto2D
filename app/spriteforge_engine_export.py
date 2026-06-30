#!/usr/bin/env python3
"""Direct Godot/Unity/Unreal helper export for SpriteForge spritesheets.

Modularized to keep LOC under 500. Exporters are split into services.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from services.godot_export_service import load_meta, copy_base_assets, safe_name
from services.unreal_export_service import export_unreal

# Thin wrappers to support direct patching and monkeypatching in unit tests
def export_godot(
    sprite_dir: Path, output: Optional[Path], project: Optional[Path], name: Optional[str], res_path: Optional[str], mode: str,
    naming_convention: str = "default",
    pivot_mode: str = "bottom-center",
    ppu: int = 100,
    filter_mode: str = "nearest",
    loop_flag: bool = True,
    clip_name: Optional[str] = None
) -> Path:
    from services.godot_export_service import export_godot as _impl
    return _impl(
        sprite_dir=sprite_dir, output=output, project=project, name=name, res_path=res_path, mode=mode,
        naming_convention=naming_convention, pivot_mode=pivot_mode, ppu=ppu, filter_mode=filter_mode,
        loop_flag=loop_flag, clip_name=clip_name
    )

def export_unity(
    sprite_dir: Path, output: Optional[Path], project: Optional[Path], name: Optional[str],
    naming_convention: str = "default",
    pivot_mode: str = "bottom-center",
    ppu: int = 100,
    filter_mode: str = "nearest",
    loop_flag: bool = True,
    clip_name: Optional[str] = None
) -> Path:
    from services.unity_export_service import export_unity as _impl
    return _impl(
        sprite_dir=sprite_dir, output=output, project=project, name=name,
        naming_convention=naming_convention, pivot_mode=pivot_mode, ppu=ppu, filter_mode=filter_mode,
        loop_flag=loop_flag, clip_name=clip_name
    )

def validate_export(
    sprite_dir: Path,
    engine: Optional[str] = None,
    release_zip: Optional[Path] = None,
    return_dict: bool = False,
) -> bool | Dict[str, Any]:
    from services.export_validation_service import validate_export as _impl
    return _impl(sprite_dir, engine=engine, release_zip=release_zip, return_dict=return_dict)

def cmd_export(args: argparse.Namespace) -> None:
    sprite_dir = Path(args.sprite_dir).resolve()
    output = Path(args.output).resolve() if args.output else None
    project = Path(args.project).resolve() if args.project else None
    loop_bool = getattr(args, "loop_flag", "true").lower() == "true"
    
    if args.engine == "godot":
        dest = export_godot(
            sprite_dir, output, project, args.name, args.res_path, args.godot_mode,
            naming_convention=getattr(args, "naming_convention", "default"),
            pivot_mode=getattr(args, "pivot_mode", "bottom-center"),
            ppu=getattr(args, "ppu", 100),
            filter_mode=getattr(args, "filter_mode", "nearest"),
            loop_flag=loop_bool,
            clip_name=getattr(args, "clip_name", None)
        )
    elif args.engine == "unity":
        dest = export_unity(
            sprite_dir, output, project, args.name,
            naming_convention=getattr(args, "naming_convention", "default"),
            pivot_mode=getattr(args, "pivot_mode", "bottom-center"),
            ppu=getattr(args, "ppu", 100),
            filter_mode=getattr(args, "filter_mode", "nearest"),
            loop_flag=loop_bool,
            clip_name=getattr(args, "clip_name", None)
        )
    else:
        dest = export_unreal(
            sprite_dir, output, project, args.name,
            naming_convention=getattr(args, "naming_convention", "default"),
            pivot_mode=getattr(args, "pivot_mode", "bottom-center"),
            ppu=getattr(args, "ppu", 100),
            filter_mode=getattr(args, "filter_mode", "nearest"),
            loop_flag=loop_bool,
            clip_name=getattr(args, "clip_name", None)
        )
    print(f"Exported {args.engine} helper files: {dest}")
    
    try:
        from services.plugin_manager import PluginManager
        PluginManager.trigger_hook("on_export_engine", sprite_dir=sprite_dir, engine=args.engine, dest=dest)
    except Exception:
        pass

def cmd_validate(args: argparse.Namespace) -> None:
    sprite_dir = Path(args.sprite_dir).resolve()
    engine = args.engine or None
    release_zip = Path(args.release_zip).resolve() if args.release_zip else None
    ok = validate_export(sprite_dir, engine=engine, release_zip=release_zip)
    if not ok:
        raise SystemExit(1)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export SpriteForge sheets to Godot/Unity helper files")
    sub = p.add_subparsers(dest="command", required=True)
    e = s = sub.add_parser("export")
    e.add_argument("--sprite-dir", required=True, help="Folder containing sheet.png and sheet.json")
    e.add_argument("--engine", required=True, choices=["godot", "unity", "unreal"])
    e.add_argument("--output", default=None, help="Output folder. Defaults inside the project or sprite_dir.")
    e.add_argument("--project", default=None, help="Godot or Unity project root")
    e.add_argument("--name", default=None)
    e.add_argument("--res-path", default=None, help="Godot res:// folder path, for example res://assets/sprites/hero_walk")
    e.add_argument("--godot-mode", choices=["sprite2d", "animatedsprite2d"], default="animatedsprite2d")
    e.add_argument("--naming-convention", default="default")
    e.add_argument("--pivot-mode", default="bottom-center")
    e.add_argument("--ppu", type=int, default=100)
    e.add_argument("--filter-mode", default="nearest")
    e.add_argument("--loop-flag", default="true")
    e.add_argument("--import-path", default=None)
    e.add_argument("--clip-name", default=None)
    e.set_defaults(func=cmd_export)
    v = sub.add_parser("validate", help="Validate export files for correctness")
    v.add_argument("--sprite-dir", required=True, help="Sprite output folder")
    v.add_argument("--engine", default=None, choices=["godot", "unity", "unreal"], help="Engine to check engine-specific files")
    v.add_argument("--release-zip", default=None, help="Release zip to check for completeness")
    v.set_defaults(func=cmd_validate)
    return p

def main() -> int:
    p = build_parser()
    args = p.parse_args()
    args.func(args)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
