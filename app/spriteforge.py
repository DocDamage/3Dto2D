#!/usr/bin/env python3
"""
SpriteForge v2: video/frame-folder to game-ready spritesheet converter.

Domain-split architecture:
  services/sprite_video_loader.py   — video extraction, frame loading, inspection
  services/sprite_chroma_alpha.py   — chroma key, rembg, alpha bbox, solidify, outline
  services/sprite_frame_norm.py     — frame normalization, anchor, sequence ops, diff
  services/sprite_sheet_service.py  — sheet packing, metadata, preview GIF, report

This module is a thin re-export + CLI parser. All real logic lives in services/.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageSequence, ImageFilter

try:
    import cv2
except Exception:
    cv2 = None

from services.sprite_service import SpriteService
from spriteforge_utils import natural_key

# ── Re-exports from domain services ────────────────────

from services.sprite_video_loader import (
    FrameItem, IMAGE_EXTS, VIDEO_EXTS,
    ensure_dir, load_image, extract_video_frames, load_frame_folder,
    inspect_video, inspect_frame_folder, next_power_of_two as _next_power_of_two,
    save_png_sequence,
)

from services.sprite_chroma_alpha import (
    guess_key_color_from_corners, apply_chroma_key, try_rembg,
    alpha_bbox, expand_bbox, union_bboxes,
    add_outline, solidify_transparent_rgb,
)

from services.sprite_frame_norm import (
    next_power_of_two, anchor_position, paste_fit_anchor,
    normalize_frames, frame_difference, apply_frame_sequence_ops,
)

from services.sprite_sheet_service import (
    pack_sheet, write_metadata, write_aseprite_json,
    make_preview_gif, make_contact_sheet,
    write_godot_notes as _write_godot_notes, write_report as _write_report,
)


# ── Dataclasses ──────────────────────────────────────────

@dataclass
class ProcessResult:
    output: Path
    frame_count: int
    cell_size: Tuple[int, int]
    columns: int
    rows: int
    fps: float
    sheet_path: Path
    metadata_path: Path


# ── Parsers ──────────────────────────────────────────────

def parse_size(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    value = value.lower().strip()
    if "x" not in value:
        raise argparse.ArgumentTypeError("Size must look like 512x512")
    a, b = value.split("x", 1)
    w, h = int(a), int(b)
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("Size values must be positive")
    return w, h


def parse_rgb(value: Optional[str]) -> Optional[Union[Tuple[int, int, int], str]]:
    if value is None:
        return None
    value = value.strip().lower()
    if value == "auto":
        return "auto"
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Color must be auto or R,G,B, for example 0,255,0")
    rgb = tuple(int(p) for p in parts)
    if any(v < 0 or v > 255 for v in rgb):
        raise argparse.ArgumentTypeError("RGB values must be between 0 and 255")
    return rgb


def parse_rgba(value: str) -> Tuple[int, int, int, int]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) == 3:
        parts.append("255")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Color must be R,G,B or R,G,B,A")
    rgba = tuple(int(p) for p in parts)
    if any(v < 0 or v > 255 for v in rgba):
        raise argparse.ArgumentTypeError("RGBA values must be between 0 and 255")
    return rgba


# Stub for save_png_sequence (moved to sprite_video_loader, re-exported above)
def save_png_sequence(frames, out_dir, prefix="frame"):
    from services.sprite_video_loader import save_png_sequence as _sps
    return _sps(frames, out_dir, prefix)


# ── Pipeline ─────────────────────────────────────────────

def process_common(
    frames: Sequence[FrameItem],
    output: Path,
    fps: float,
    cell_size: Optional[Tuple[int, int]],
    key_color: Optional[Union[Tuple[int, int, int], str]],
    key_tolerance: float,
    key_feather: float,
    rembg: bool,
    crop_mode: str,
    pad: int,
    alpha_threshold: int,
    columns: Optional[int],
    animation_name: str,
    preview_gif: bool,
    save_processed_frames: bool,
    anchor: str,
    ground_margin: int,
    spacing: int,
    margin: int,
    solidify: int,
    outline_width: int,
    outline_color: Tuple[int, int, int, int],
    power_of_two: bool,
    loop_mode: str,
    drop_last: bool,
    drop_loop_duplicate: bool,
    reverse: bool,
    flip_x: bool,
    flip_y: bool,
    report: bool,
    source_meta: Optional[Dict[str, Any]] = None,
    resolutions: Optional[str] = None,
    palette: Optional[List[Tuple[int, int, int]]] = None,
) -> ProcessResult:
    ensure_dir(output)

    working = apply_frame_sequence_ops(
        list(frames),
        drop_last=drop_last,
        drop_loop_duplicate=drop_loop_duplicate,
        loop_mode=loop_mode,
        reverse=reverse,
        flip_x=flip_x,
        flip_y=flip_y,
        palette=palette,
    )

    processed: List[FrameItem] = []
    for item in working:
        img = item.image.convert("RGBA")
        if key_color is not None:
            img = apply_chroma_key(img, key_color, key_tolerance, key_feather)
        if rembg:
            img = try_rembg(img)
        if outline_width > 0:
            img = add_outline(img, outline_width, outline_color)
        processed.append(FrameItem(img, item.name, item.source_index))

    normalized, final_cell, normalize_info = normalize_frames(
        processed,
        cell_size=cell_size,
        crop_mode=crop_mode,
        pad=pad,
        alpha_threshold=alpha_threshold,
        anchor=anchor,
        ground_margin=ground_margin,
    )

    if solidify > 0:
        normalized = [
            FrameItem(solidify_transparent_rgb(item.image, solidify, alpha_threshold), item.name, item.source_index)
            for item in normalized
        ]

    if save_processed_frames:
        save_png_sequence(normalized, output / "frames_processed")

    sheet, cols, rows, rects = pack_sheet(normalized, columns, spacing, margin, power_of_two)
    sheet_path = output / "sheet.png"
    sheet.save(sheet_path)

    extra = {
        "source": source_meta or {},
        "normalize": normalize_info,
        "loop_mode": loop_mode,
        "solidify": solidify,
        "outline_width": outline_width,
        "power_of_two": power_of_two,
    }

    metadata_path = output / "sheet.json"
    write_metadata(
        metadata_path,
        image_name="sheet.png",
        frames=normalized,
        rects=rects,
        cell_size=final_cell,
        columns=cols,
        rows=rows,
        fps=fps,
        animation_name=animation_name,
        spacing=spacing,
        margin=margin,
        extra=extra,
    )

    write_aseprite_json(
        output / "sheet.aseprite.json",
        image_name="sheet.png",
        frames=normalized,
        rects=rects,
        cell_size=final_cell,
        fps=fps,
        animation_name=animation_name,
    )

    if preview_gif:
        make_preview_gif(normalized, output / "preview.gif", fps)

    make_contact_sheet(normalized, output / "contact_sheet.jpg")

    result = ProcessResult(
        output=output,
        frame_count=len(normalized),
        cell_size=final_cell,
        columns=cols,
        rows=rows,
        fps=fps,
        sheet_path=sheet_path,
        metadata_path=metadata_path,
    )

    _write_godot_notes(output / "godot_notes.txt", result.frame_count, result.columns, result.rows, result.fps, result.cell_size)

    if report:
        _write_report(output / "report.html", result.sheet_path.name, output, result.frame_count, fps, final_cell, cols, rows, extra)

    # Multi-resolution output scaling
    if resolutions:
        targets = [t.strip() for t in resolutions.split(",") if t.strip()]
        for target in targets:
            try:
                if target.endswith("x"):
                    scale_factor = float(target[:-1])
                    suffix = target
                else:
                    target_size = int(target)
                    scale_factor = target_size / final_cell[0]
                    suffix = f"{target_size}"

                new_w = int(round(sheet.width * scale_factor))
                new_h = int(round(sheet.height * scale_factor))
                try:
                    from PIL import Image as PILImage
                    resample_filter = PILImage.Resampling.LANCZOS
                except AttributeError:
                    resample_filter = Image.LANCZOS

                scaled_sheet = sheet.resize((new_w, new_h), resample_filter)
                scaled_sheet_name = f"sheet_{suffix}.png"
                scaled_sheet_path = output / scaled_sheet_name
                scaled_sheet.save(scaled_sheet_path)

                scaled_rects = [
                    {
                        "x": int(round(r["x"] * scale_factor)),
                        "y": int(round(r["y"] * scale_factor)),
                        "w": int(round(r["w"] * scale_factor)),
                        "h": int(round(r["h"] * scale_factor)),
                    }
                    for r in rects
                ]
                scaled_cell = (int(round(final_cell[0] * scale_factor)), int(round(final_cell[1] * scale_factor)))
                scaled_spacing = int(round(spacing * scale_factor))
                scaled_margin = int(round(margin * scale_factor))
                scaled_extra = json.loads(json.dumps(extra)) if extra else {}

                write_metadata(
                    output / f"sheet_{suffix}.json",
                    image_name=scaled_sheet_name,
                    frames=normalized,
                    rects=scaled_rects,
                    cell_size=scaled_cell,
                    columns=cols,
                    rows=rows,
                    fps=fps,
                    animation_name=animation_name,
                    spacing=scaled_spacing,
                    margin=scaled_margin,
                    extra=scaled_extra,
                )
                write_aseprite_json(
                    output / f"sheet_{suffix}.aseprite.json",
                    image_name=scaled_sheet_name,
                    frames=normalized,
                    rects=scaled_rects,
                    cell_size=scaled_cell,
                    fps=fps,
                    animation_name=animation_name,
                )
                print(f"Exported scaled resolution target '{target}': {scaled_sheet_path}")
            except Exception as e:
                print(f"[WARN] Failed to export resolution '{target}': {e}")

    print("Done.")
    print(f"Frames: {len(normalized)}")
    print(f"Cell: {final_cell[0]}x{final_cell[1]}")
    print(f"Grid: {cols}x{rows}")
    print(f"Sheet: {sheet_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Aseprite JSON: {output / 'sheet.aseprite.json'}")
    print(f"Godot notes: {output / 'godot_notes.txt'}")
    if preview_gif:
        print(f"Preview: {output / 'preview.gif'}")
    if report:
        print(f"Report: {output / 'report.html'}")

    return result


def process_common_from_args(
    frames: Sequence[FrameItem],
    output: Path,
    fps: float,
    args: argparse.Namespace,
    source_meta: Optional[Dict[str, Any]] = None,
) -> ProcessResult:
    return process_common(
        frames=frames,
        output=output,
        fps=fps,
        cell_size=parse_size(args.cell_size),
        key_color=parse_rgb(args.key_color),
        key_tolerance=args.key_tolerance,
        key_feather=args.key_feather,
        rembg=args.rembg,
        crop_mode=args.crop_mode,
        pad=args.pad,
        alpha_threshold=args.alpha_threshold,
        columns=args.columns,
        animation_name=args.animation,
        preview_gif=args.preview_gif,
        save_processed_frames=True,
        anchor=args.anchor,
        ground_margin=args.ground_margin,
        spacing=args.spacing,
        margin=args.margin,
        solidify=args.solidify,
        outline_width=args.outline_width,
        outline_color=parse_rgba(args.outline_color),
        power_of_two=args.power_of_two,
        loop_mode=args.loop_mode,
        drop_last=args.drop_last,
        drop_loop_duplicate=args.drop_loop_duplicate,
        reverse=args.reverse,
        flip_x=args.flip_x,
        flip_y=args.flip_y,
        report=args.report,
        source_meta=source_meta,
        resolutions=getattr(args, "resolutions", None),
        palette=SpriteService.parse_palette(getattr(args, "palette", None)),
    )


# ── CLI Commands ─────────────────────────────────────────

def cmd_video(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output = Path(args.output)
    ensure_dir(output)
    frames, fps, source_meta = extract_video_frames(
        input_path=input_path,
        target_fps=args.fps,
        start_seconds=args.start,
        end_seconds=args.end,
        max_frames=args.max_frames,
        stride=args.stride,
    )
    if args.save_raw_frames:
        save_png_sequence(frames, output / "frames_raw", prefix="raw")
    process_common_from_args(frames, output, float(args.fps or fps), args, source_meta=source_meta)


def cmd_pack(args: argparse.Namespace) -> None:
    input_dir = Path(args.input)
    frames = load_frame_folder(input_dir, max_frames=args.max_frames)
    source_meta = {"source_type": "frame_folder", "source_folder": str(input_dir), "loaded_frame_count": len(frames)}
    process_common_from_args(frames, Path(args.output), float(args.fps), args, source_meta=source_meta)


def cmd_inspect(args: argparse.Namespace) -> None:
    path = Path(args.input)
    if path.is_dir():
        data = inspect_frame_folder(path)
    elif path.suffix.lower() in VIDEO_EXTS:
        data = inspect_video(path)
    else:
        raise RuntimeError("Inspect supports video files or folders of image frames.")
    text = json.dumps(data, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")


def cmd_batch(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list) or not jobs:
        raise RuntimeError("Batch config must contain a non-empty 'jobs' list.")
    for i, job in enumerate(jobs):
        print(f"\n=== Batch job {i + 1}/{len(jobs)} ===")
        mode = job.get("mode")
        if mode not in {"video", "pack"}:
            raise RuntimeError(f"Job {i + 1}: mode must be 'video' or 'pack'.")
        argv = [mode]
        for key, value in job.items():
            if key == "mode":
                continue
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    argv.append(flag)
            elif value is not None:
                argv.extend([flag, str(value)])
        parsed = build_parser().parse_args(argv)
        parsed.func(parsed)


def newest_matching_files(folder: Path, pattern: str) -> List[Path]:
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and fnmatch.fnmatch(p.name.lower(), pattern.lower())],
        key=lambda p: p.stat().st_mtime,
    )


def wait_until_file_stable(path: Path, stable_seconds: float) -> bool:
    last_size = -1
    last_change = time.time()
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        now = time.time()
        if size != last_size:
            last_size = size
            last_change = now
        if now - last_change >= stable_seconds:
            return True
        time.sleep(0.5)


def cmd_watch(args: argparse.Namespace) -> None:
    folder = Path(args.folder)
    if not folder.exists():
        raise RuntimeError(f"Watch folder does not exist: {folder}")
    out_root = Path(args.output)
    ensure_dir(out_root)
    seen = {p.resolve() for p in newest_matching_files(folder, args.pattern)}
    print(f"Watching {folder} for {args.pattern}. Press Ctrl+C to stop.")
    while True:
        try:
            files = newest_matching_files(folder, args.pattern)
            for p in files:
                rp = p.resolve()
                if rp in seen:
                    continue
                print(f"New file: {p}")
                if not wait_until_file_stable(p, args.stable_seconds):
                    continue
                seen.add(rp)
                out_dir = out_root / f"{p.stem}_sprite"
                class Obj:
                    pass
                fake = Obj()
                for k, v in vars(args).items():
                    setattr(fake, k, v)
                fake.input = str(p)
                fake.output = str(out_dir)
                fake.start = 0.0
                fake.end = None
                fake.max_frames = args.max_frames
                fake.stride = args.stride
                fake.save_raw_frames = False
                cmd_video(fake)
            time.sleep(args.poll_seconds)
        except KeyboardInterrupt:
            print("Stopped.")
            return


# ── CLI Parser ───────────────────────────────────────────

def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--output", required=True, help="Output folder")
    p.add_argument("--resolutions", default=None, help="Multi-resolution targets, comma separated. Example: 0.5x,1x,2x or 32,64,128")
    p.add_argument("--fps", type=float, default=12.0, help="Output animation FPS")
    p.add_argument("--cell-size", default=None, help="Final cell size, for example 512x512. Auto if omitted.")
    p.add_argument("--columns", type=int, default=None, help="Number of spritesheet columns. Auto if omitted.")
    p.add_argument("--animation", default="anim", help="Animation name for metadata")
    p.add_argument("--preview-gif", action="store_true", help="Export preview.gif")
    p.add_argument("--report", action="store_true", help="Export report.html and contact sheet")
    p.add_argument("--key-color", default=None, help="Chroma key color: auto or R,G,B. Example: --key-color 0,255,0")
    p.add_argument("--key-tolerance", type=float, default=45.0, help="Chroma key tolerance")
    p.add_argument("--key-feather", type=float, default=25.0, help="Soft edge width for chroma key")
    p.add_argument("--rembg", action="store_true", help="Optional AI background removal. Requires rembg + onnxruntime.")
    p.add_argument("--crop-mode", choices=["global", "per-frame", "none"], default="global", help="Canvas crop mode")
    p.add_argument("--pad", type=int, default=16, help="Padding around detected subject")
    p.add_argument("--alpha-threshold", type=int, default=8, help="Alpha threshold for subject bounds")
    p.add_argument("--anchor", choices=["center", "bottom-center", "top-center", "bottom-left", "bottom-right", "left-center", "right-center"], default="bottom-center")
    p.add_argument("--ground-margin", type=int, default=0, help="Pixels from bottom/edge when using bottom/top/side anchors")
    p.add_argument("--spacing", type=int, default=0, help="Pixels between cells in the spritesheet")
    p.add_argument("--margin", type=int, default=0, help="Outer margin around the spritesheet")
    p.add_argument("--power-of-two", action="store_true", help="Pad final sheet to power-of-two dimensions")
    p.add_argument("--solidify", type=int, default=2, help="Fill transparent RGB edge pixels to reduce filtering fringes. 0 disables.")
    p.add_argument("--outline-width", type=int, default=0, help="Optional outline width in pixels")
    p.add_argument("--outline-color", default="0,0,0,255", help="Outline color as R,G,B,A")
    p.add_argument("--palette", default=None, help="Snaps colors to a retro palette")
    p.add_argument("--loop-mode", choices=["normal", "pingpong"], default="normal", help="Loop construction mode")
    p.add_argument("--drop-last", action="store_true", help="Drop the last frame manually")
    p.add_argument("--drop-loop-duplicate", action="store_true", help="Drop last frame if it is nearly identical to the first")
    p.add_argument("--reverse", action="store_true", help="Reverse frame order")
    p.add_argument("--flip-x", action="store_true", help="Flip frames horizontally")
    p.add_argument("--flip-y", action="store_true", help="Flip frames vertically")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SpriteForge v2 spritesheet toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_video = sub.add_parser("video", help="Convert a video to spritesheet")
    add_common_args(p_video)
    p_video.add_argument("--input", required=True, help="Input video file")
    p_video.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    p_video.add_argument("--end", type=float, default=None, help="End time in seconds")
    p_video.add_argument("--max-frames", type=int, default=None, help="Maximum frames to use")
    p_video.add_argument("--stride", type=int, default=1, help="Use every Nth source frame before FPS sampling")
    p_video.add_argument("--save-raw-frames", action="store_true", help="Save raw extracted frames")
    p_video.set_defaults(func=cmd_video)

    p_pack = sub.add_parser("pack", help="Pack image frames from a folder")
    add_common_args(p_pack)
    p_pack.add_argument("--input", required=True, help="Input folder containing PNG/JPG/etc frames")
    p_pack.add_argument("--max-frames", type=int, default=None, help="Maximum frames to use")
    p_pack.set_defaults(func=cmd_pack)

    p_inspect = sub.add_parser("inspect", help="Inspect a video or frame folder and print recommended command")
    p_inspect.add_argument("--input", required=True, help="Video file or image frame folder")
    p_inspect.add_argument("--output", default=None, help="Optional JSON output path")
    p_inspect.set_defaults(func=cmd_inspect)

    p_batch = sub.add_parser("batch", help="Process multiple jobs from a JSON config")
    p_batch.add_argument("--config", required=True, help="Batch config JSON")
    p_batch.set_defaults(func=cmd_batch)

    p_watch = sub.add_parser("watch", help="Watch a folder for new videos and auto-convert them")
    add_common_args(p_watch)
    p_watch.add_argument("--folder", required=True, help="Folder to watch, e.g. ComfyUI output folder")
    p_watch.add_argument("--pattern", default="*.mp4", help="Filename pattern to watch")
    p_watch.add_argument("--poll-seconds", type=float, default=3.0)
    p_watch.add_argument("--stable-seconds", type=float, default=3.0)
    p_watch.add_argument("--max-frames", type=int, default=None)
    p_watch.add_argument("--stride", type=int, default=1)
    p_watch.set_defaults(func=cmd_watch)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())