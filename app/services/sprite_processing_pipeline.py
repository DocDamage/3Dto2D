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
    apply_chroma_key, apply_pixel_art_background_removal, try_rembg, try_birefnet, apply_pixeloe_pixelization,
    fit_native_pixel_palette, apply_native_pixel_cleanup, add_outline, solidify_transparent_rgb
)
from services.sprite_alpha_tools import refine_alpha_edges
from services.sprite_frame_norm import normalize_frames, apply_frame_sequence_ops
from services.sprite_interpolation import interpolate_frames
from services.sprite_temporal_matting import stabilize_temporal_alpha
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
    matting_engine: str = "chroma",
    temporal_alpha_stabilize: bool = False,
    temporal_alpha_strength: float = 0.55,
    alpha_refine: bool = False,
    alpha_refine_radius: int = 1,
    pixelize: bool = False,
    pixelize_scale: int = 4,
    pixel_cleanup: bool = False,
    pixel_cleanup_colors: int = 24,
    pixel_cleanup_dither: bool = False,
    pixel_cleanup_dither_mode: str = "none",
    pixel_cleanup_palette: Optional[str] = None,
    generate_normal_maps: bool = False,
    normal_map_engine: str = "height",
    interpolate_fps: Optional[float] = None,
    interpolation_engine: str = "blend",
    interpolation_skip_pixel_art: bool = False,
    interpolation_skip_impact_frames: bool = False,
    interpolation_skip_patterns: Optional[str] = None,
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
        if matting_engine == "birefnet":
            img = try_birefnet(img)
        elif matting_engine == "pixel-art":
            img = apply_pixel_art_background_removal(img, tolerance=key_tolerance, alpha_threshold=alpha_threshold)
        elif matting_engine == "rembg" or rembg:
            img = try_rembg(img)

        if key_color is not None:
            img = apply_chroma_key(img, key_color, key_tolerance, key_feather)

        if alpha_refine:
            img = refine_alpha_edges(img, radius=alpha_refine_radius)

        if pixelize:
            img = apply_pixeloe_pixelization(img, pixel_size=pixelize_scale)

        if outline_width > 0:
            img = add_outline(img, outline_width, outline_color)
        processed.append(FrameItem(img, item.name, item.source_index))

    if temporal_alpha_stabilize:
        processed = stabilize_temporal_alpha(processed, strength=temporal_alpha_strength)

    effective_pixel_dither_mode = str(pixel_cleanup_dither_mode or "none").lower().replace("_", "-")
    if pixel_cleanup_dither and effective_pixel_dither_mode == "none":
        effective_pixel_dither_mode = "floyd-steinberg"

    if pixel_cleanup:
        parsed_palette = SpriteService.parse_palette(pixel_cleanup_palette or "")
        if parsed_palette:
            native_palette = parsed_palette
            palette_source = pixel_cleanup_palette
        else:
            native_palette = fit_native_pixel_palette(
                [item.image for item in processed],
                colors=pixel_cleanup_colors,
                alpha_threshold=alpha_threshold,
            )
            palette_source = "learned-oklab"
        processed = [
            FrameItem(
                apply_native_pixel_cleanup(
                    item.image,
                    colors=pixel_cleanup_colors,
                    alpha_threshold=alpha_threshold,
                    dither=pixel_cleanup_dither,
                    dither_mode=effective_pixel_dither_mode,
                    palette=native_palette,
                ),
                item.name,
                item.source_index,
            )
            for item in processed
        ]

    pixel_art_active = bool(pixelize or pixel_cleanup or matting_engine == "pixel-art")
    hold_patterns = []
    if interpolation_skip_impact_frames:
        from services.sprite_interpolation import DEFAULT_IMPACT_PATTERNS

        hold_patterns.extend(DEFAULT_IMPACT_PATTERNS)
    if interpolation_skip_patterns:
        hold_patterns.extend([part.strip() for part in interpolation_skip_patterns.split(",") if part.strip()])

    processed, output_fps, interpolation_info = interpolate_frames(
        processed,
        fps,
        interpolate_fps,
        engine=interpolation_engine,
        hold_all_transitions=bool(interpolation_skip_pixel_art and pixel_art_active),
        hold_name_patterns=hold_patterns,
    )
    fps = output_fps

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
        "alpha_refine": bool(alpha_refine),
        "alpha_refine_radius": alpha_refine_radius if alpha_refine else 0,
        "temporal_alpha_stabilize": bool(temporal_alpha_stabilize),
        "temporal_alpha_strength": temporal_alpha_strength if temporal_alpha_stabilize else 0,
        "pixel_cleanup": {
            "enabled": bool(pixel_cleanup),
            "colors": pixel_cleanup_colors if pixel_cleanup else 0,
            "dither": bool(pixel_cleanup and effective_pixel_dither_mode != "none"),
            "dither_mode": effective_pixel_dither_mode if pixel_cleanup else "none",
            "palette": palette_source if pixel_cleanup else None,
        },
        "normal_map_engine": normal_map_engine if generate_normal_maps else None,
        "matting_engine": matting_engine,
        "interpolation": interpolation_info,
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

    if generate_normal_maps:
        from services.sprite_normal_map import SpriteNormalMapService
        normal_frames = []
        specular_frames = []
        ao_frames = []
        height_frames = []
        for item in normalized:
            norm_img, spec_img, ao_img = SpriteNormalMapService.generate_maps(item.image, engine=normal_map_engine)
            height_img = SpriteNormalMapService.generate_height_map(item.image, engine=normal_map_engine)
            normal_frames.append(FrameItem(norm_img, f"{item.name}_normal", item.source_index))
            specular_frames.append(FrameItem(spec_img, f"{item.name}_specular", item.source_index))
            ao_frames.append(FrameItem(ao_img, f"{item.name}_ao", item.source_index))
            height_frames.append(FrameItem(height_img, f"{item.name}_height", item.source_index))

        normal_sheet, _, _, _ = pack_sheet(normal_frames, cols, spacing, margin, power_of_two)
        normal_sheet.save(output / "sheet_normal.png")

        specular_sheet, _, _, _ = pack_sheet(specular_frames, cols, spacing, margin, power_of_two)
        specular_sheet.save(output / "sheet_specular.png")

        ao_sheet, _, _, _ = pack_sheet(ao_frames, cols, spacing, margin, power_of_two)
        ao_sheet.save(output / "sheet_ao.png")

        height_sheet, _, _, _ = pack_sheet(height_frames, cols, spacing, margin, power_of_two)
        height_sheet.save(output / "sheet_height.png")

        if save_processed_frames:
            save_png_sequence(normal_frames, output / "frames_normal")
            save_png_sequence(specular_frames, output / "frames_specular")
            save_png_sequence(ao_frames, output / "frames_ao")
            save_png_sequence(height_frames, output / "frames_height")

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
        matting_engine=getattr(args, "matting_engine", "chroma"),
        temporal_alpha_stabilize=getattr(args, "temporal_alpha_stabilize", False),
        temporal_alpha_strength=getattr(args, "temporal_alpha_strength", 0.55),
        alpha_refine=getattr(args, "alpha_refine", False),
        alpha_refine_radius=getattr(args, "alpha_refine_radius", 1),
        pixelize=getattr(args, "pixelize", False),
        pixelize_scale=getattr(args, "pixelize_scale", 4),
        pixel_cleanup=getattr(args, "pixel_cleanup", False),
        pixel_cleanup_colors=getattr(args, "pixel_cleanup_colors", 24),
        pixel_cleanup_dither=getattr(args, "pixel_cleanup_dither", False),
        pixel_cleanup_dither_mode=getattr(args, "pixel_cleanup_dither_mode", "none"),
        pixel_cleanup_palette=getattr(args, "pixel_cleanup_palette", None),
        generate_normal_maps=getattr(args, "generate_normal_maps", False),
        normal_map_engine=getattr(args, "normal_map_engine", "height"),
        interpolate_fps=getattr(args, "interpolate_fps", None),
        interpolation_engine=getattr(args, "interpolation_engine", "blend"),
        interpolation_skip_pixel_art=getattr(args, "interpolation_skip_pixel_art", False),
        interpolation_skip_impact_frames=getattr(args, "interpolation_skip_impact_frames", False),
        interpolation_skip_patterns=getattr(args, "interpolation_skip_patterns", None),
    )
