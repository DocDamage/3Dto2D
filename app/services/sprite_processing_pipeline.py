from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from PIL import Image

from services.sprite_service import SpriteService
from services.sprite_video_loader import FrameItem, ensure_dir, save_png_sequence
from services.sprite_chroma_alpha import (
    apply_chroma_key, try_rembg, add_outline, solidify_transparent_rgb
)
from services.sprite_frame_norm import normalize_frames, apply_frame_sequence_ops
from services.sprite_sheet_service import (
    pack_sheet, write_metadata, write_aseprite_json,
    make_preview_gif, make_contact_sheet,
    write_godot_notes, write_report
)

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

    write_godot_notes(output / "godot_notes.txt", result.frame_count, result.columns, result.rows, result.fps, result.cell_size)

    if report:
        write_report(output / "report.html", result.sheet_path.name, output, result.frame_count, fps, final_cell, cols, rows, extra)

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
