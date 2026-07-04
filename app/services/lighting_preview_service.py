#!/usr/bin/env python3
"""Bake lighting preview animations from SpriteForge sprite folders."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image, ImageChops

from services.animated_export_service import load_sprite_animation_frames
from services.sprite_video_loader import ensure_dir

LIGHTING_PREVIEW_SCHEMA = "spriteforge.lighting_preview.v1"


def _clamp_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def _light_frame(image: Image.Image, light_x: float, light_y: float, intensity: float, ambient: float) -> Image.Image:
    frame = image.convert("RGBA")
    width, height = frame.size
    shade = Image.new("L", frame.size, int(max(0.0, min(1.0, ambient)) * 255))
    pixels = shade.load()
    cx = ((light_x + 1.0) / 2.0) * max(1, width - 1)
    cy = ((light_y + 1.0) / 2.0) * max(1, height - 1)
    radius = max(1.0, (width * width + height * height) ** 0.5)
    for y in range(height):
        for x in range(width):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / radius
            falloff = max(0.0, 1.0 - dist)
            value = ambient + falloff * intensity
            pixels[x, y] = int(max(0.0, min(2.0, value)) / 2.0 * 255)
    lit = ImageChops.multiply(frame.convert("RGB"), shade.convert("RGB")).convert("RGBA")
    lit.putalpha(frame.getchannel("A"))
    return lit


def _load_map_frame_files(sprite_dir: Path, folder_name: str) -> list[Image.Image]:
    folder = sprite_dir / folder_name
    if not folder.exists():
        return []
    files = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".png", ".webp"})
    return [Image.open(path).convert("RGBA") for path in files]


def _load_map_sheet_frames(sprite_dir: Path, meta: Dict[str, Any], filename: str, count: int) -> list[Image.Image]:
    path = sprite_dir / filename
    if not path.exists():
        return []
    sheet = Image.open(path).convert("RGBA")
    frame_meta = meta.get("frames") if isinstance(meta.get("frames"), list) else []
    fw = int(meta.get("frame_width", 0) or 0)
    fh = int(meta.get("frame_height", 0) or 0)
    columns = max(1, int(meta.get("columns", 1) or 1))
    frames: list[Image.Image] = []
    for index in range(count):
        frame = frame_meta[index] if index < len(frame_meta) and isinstance(frame_meta[index], dict) else {
            "x": (index % columns) * fw,
            "y": (index // columns) * fh,
            "w": fw,
            "h": fh,
        }
        x = int(frame.get("x", 0) or 0)
        y = int(frame.get("y", 0) or 0)
        w = int(frame.get("w", fw) or fw)
        h = int(frame.get("h", fh) or fh)
        frames.append(sheet.crop((x, y, x + w, y + h)))
    return frames


def _load_lighting_map_frames(sprite_dir: Path, meta: Dict[str, Any], count: int) -> Dict[str, list[Image.Image]]:
    return {
        "normal": _load_map_frame_files(sprite_dir, "frames_normal") or _load_map_sheet_frames(sprite_dir, meta, "sheet_normal.png", count),
        "specular": _load_map_frame_files(sprite_dir, "frames_specular") or _load_map_sheet_frames(sprite_dir, meta, "sheet_specular.png", count),
        "ao": _load_map_frame_files(sprite_dir, "frames_ao") or _load_map_sheet_frames(sprite_dir, meta, "sheet_ao.png", count),
    }


def _map_light_frame(
    image: Image.Image,
    normal: Image.Image,
    specular: Optional[Image.Image],
    ao: Optional[Image.Image],
    light_x: float,
    light_y: float,
    intensity: float,
    ambient: float,
    specular_power: float = 0.35,
) -> Image.Image:
    base = image.convert("RGBA")
    size = base.size
    normal = normal.convert("RGBA").resize(size, Image.Resampling.NEAREST)
    specular = specular.convert("RGBA").resize(size, Image.Resampling.NEAREST) if specular else None
    ao = ao.convert("RGBA").resize(size, Image.Resampling.NEAREST) if ao else None

    sprite = np.asarray(base).astype(np.float32)
    normal_arr = np.asarray(normal).astype(np.float32)
    nx = normal_arr[:, :, 0] / 127.5 - 1.0
    ny = normal_arr[:, :, 1] / 127.5 - 1.0
    nz = normal_arr[:, :, 2] / 127.5 - 1.0
    nlen = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    nx /= nlen
    ny /= nlen
    nz /= nlen

    lz = 0.75
    llen = max((light_x * light_x + light_y * light_y + lz * lz) ** 0.5, 1e-6)
    lx = light_x / llen
    ly = light_y / llen
    lz = lz / llen
    dot = np.maximum(0.0, nx * lx + ny * ly + nz * lz)
    spec_mask = (np.asarray(specular)[:, :, 0].astype(np.float32) / 255.0) if specular else 1.0
    ao_mask = (np.asarray(ao)[:, :, 0].astype(np.float32) / 255.0) if ao else 1.0
    shine = np.power(dot, 18.0) * specular_power * spec_mask
    shade = ambient * ao_mask + dot * intensity + shine

    out = sprite.copy()
    out[:, :, 0:3] = np.clip(sprite[:, :, 0:3] * shade[:, :, None], 0, 255)
    out[:, :, 3] = sprite[:, :, 3]
    return Image.fromarray(out.astype(np.uint8), mode="RGBA")


def export_lighting_preview_gif(
    sprite_dir: Path,
    output: Optional[Path] = None,
    light_x: float = 0.35,
    light_y: float = -0.45,
    intensity: float = 1.15,
    ambient: float = 0.35,
) -> Dict[str, Any]:
    sprite_dir = Path(sprite_dir)
    frames, meta = load_sprite_animation_frames(sprite_dir)
    fps = _clamp_float(meta.get("fps", 12.0), 12.0, 1.0, 60.0)
    lx = _clamp_float(light_x, 0.35, -1.0, 1.0)
    ly = _clamp_float(light_y, -0.45, -1.0, 1.0)
    power = _clamp_float(intensity, 1.15, 0.0, 2.0)
    base = _clamp_float(ambient, 0.35, 0.0, 1.0)
    out_path = Path(output) if output else sprite_dir / "lighting_preview.gif"
    ensure_dir(out_path.parent)
    map_frames = _load_lighting_map_frames(sprite_dir, meta, len(frames))
    normal_frames = map_frames["normal"]
    specular_frames = map_frames["specular"]
    ao_frames = map_frames["ao"]
    map_aware = len(normal_frames) >= len(frames)
    rendered = []
    for index, frame in enumerate(frames):
        if map_aware:
            rendered.append(_map_light_frame(
                frame.image,
                normal_frames[index],
                specular_frames[index] if index < len(specular_frames) else None,
                ao_frames[index] if index < len(ao_frames) else None,
                lx,
                ly,
                power,
                base,
            ))
        else:
            rendered.append(_light_frame(frame.image, lx, ly, power, base))
    duration_ms = max(16, int(round(1000 / fps)))
    rendered[0].save(
        out_path,
        save_all=True,
        append_images=rendered[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        transparency=0,
    )
    manifest_path = out_path.with_suffix(".lighting_preview.json")
    manifest = {
        "schema": LIGHTING_PREVIEW_SCHEMA,
        "file": out_path.name,
        "source_sprite": str(sprite_dir),
        "animation": str(meta.get("animation", "animation")),
        "frame_count": len(rendered),
        "fps": fps,
        "duration_seconds": round(len(rendered) / fps, 4),
        "light": {
            "x": lx,
            "y": ly,
            "intensity": power,
            "ambient": base,
        },
        "lighting_maps": {
            "schema": "spriteforge.lighting_maps.v1",
            "normal": {
                "available": bool(normal_frames),
                "source": "frames_normal or sheet_normal.png",
                "frame_count": len(normal_frames),
            },
            "specular": {
                "available": bool(specular_frames),
                "source": "frames_specular or sheet_specular.png",
                "frame_count": len(specular_frames),
            },
            "ao": {
                "available": bool(ao_frames),
                "source": "frames_ao or sheet_ao.png",
                "frame_count": len(ao_frames),
            },
            "server_bake": "normal_specular_ao" if map_aware else "radial_fallback",
        },
        "rendering": {
            "schema": "spriteforge.lighting_preview_render.v1",
            "normal_compositing": map_aware,
            "specular_compositing": map_aware and bool(specular_frames),
            "ao_compositing": map_aware and bool(ao_frames),
            "texture_filter": "nearest",
        },
        "engine_ready": {
            "godot": True,
            "web": True,
            "notes": "Preview GIF is a baked lighting reference; keep sheet_normal.png for runtime lighting in engines that support normals.",
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "path": str(out_path),
        "manifest_path": str(manifest_path),
        "frame_count": len(rendered),
        "fps": fps,
        "schema": LIGHTING_PREVIEW_SCHEMA,
    }
