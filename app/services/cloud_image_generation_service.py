from __future__ import annotations

import base64
import json
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from services.sprite_chroma_alpha import apply_chroma_key, apply_native_pixel_cleanup
from services.sprite_chroma_alpha import alpha_bbox, expand_bbox
from services.sprite_frame_norm import anchor_position
from services.sprite_sheet_service import (
    make_contact_sheet,
    make_preview_gif,
    pack_sheet,
    write_godot_notes,
    write_metadata,
    write_report,
)
from services.sprite_video_loader import FrameItem, ensure_dir, save_png_sequence
from spriteforge_utils import ROOT, safe_name

DEFAULT_CONSTRAINTS = (
    "pixel art sprite, single isolated 2D game asset, flat colors, "
    "solid magenta background, centered full body, no scenery, no labels, "
    "crisp readable silhouette"
)
DEFAULT_NEGATIVE = (
    "photorealistic, soft blur, gradients, busy background, multiple characters, "
    "sprite sheet grid, text, watermark, cropped feet, floor shadow"
)
DEFAULT_KEY_COLOR = "#ff00ff"


def load_local_env(root: Path = ROOT) -> Dict[str, str]:
    """Load local key/value pairs without mutating tracked config files."""
    loaded: Dict[str, str] = {}
    for path in (root / ".env", root.parent / ".env"):
        if not path.exists() or not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
    return loaded


def resolve_api_key(provider: str) -> str:
    load_local_env()
    provider = provider.lower().strip()
    names = provider_key_names(provider)
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    raise RuntimeError(f"Missing API key for {provider}. Put it in a local .env file or process environment.")


def provider_key_names(provider: str) -> Tuple[str, ...]:
    return {
        "openai": ("OPENAI_API_KEY", "SPRITEFORGE_OPENAI_API_KEY"),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "SPRITEFORGE_GEMINI_API_KEY"),
    }.get(provider.lower().strip(), ())


def cloud_image_provider_status(provider: Optional[str] = None) -> Dict[str, Any]:
    load_local_env()
    providers = [provider.lower().strip()] if provider else ["openai", "gemini"]
    rows = {}
    for name in providers:
        key_names = provider_key_names(name)
        configured_name = next((key for key in key_names if os.environ.get(key)), "")
        rows[name] = {
            "provider": name,
            "ok": bool(configured_name),
            "configured": bool(configured_name),
            "env_names": list(key_names),
            "configured_env_name": configured_name,
            "message": "API key configured locally." if configured_name else "Missing local API key.",
        }
    return {
        "ok": True,
        "providers": rows,
        "local_env_supported": True,
        "local_env_files": [".env", "app/.env"],
    }


def hardened_prompt(user_prompt: str, constraints: str = DEFAULT_CONSTRAINTS, negative: str = DEFAULT_NEGATIVE) -> str:
    user_prompt = str(user_prompt or "").strip()
    if not user_prompt:
        raise ValueError("Prompt is required.")
    constraints = str(constraints or DEFAULT_CONSTRAINTS).strip()
    negative = str(negative or DEFAULT_NEGATIVE).strip()
    prompt = user_prompt
    if constraints and constraints.lower() not in prompt.lower():
        prompt = f"{prompt}, {constraints}"
    if negative and negative.lower() not in prompt.lower():
        prompt = f"{prompt}. Avoid: {negative}"
    return prompt


def parse_cell_size(value: str | Tuple[int, int] | None, default: Tuple[int, int] = (64, 64)) -> Tuple[int, int]:
    if isinstance(value, tuple):
        return int(value[0]), int(value[1])
    text = str(value or "").strip().lower()
    if not text:
        return default
    if "x" in text:
        left, right = text.split("x", 1)
        return max(1, int(left)), max(1, int(right))
    size = max(1, int(text))
    return size, size


def parse_key_color(value: str) -> str | Tuple[int, int, int]:
    text = str(value or "").strip()
    if text.lower() == "auto":
        return "auto"
    if text.startswith("#") and len(text) == 7:
        return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)
    if "," in text:
        parts = [int(p.strip()) for p in text.split(",")]
        if len(parts) == 3:
            return tuple(max(0, min(255, p)) for p in parts)  # type: ignore[return-value]
    return text


def _decode_b64_image(data: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(data))).convert("RGBA")


def _openai_generate(prompt: str, model: str, size: str) -> Image.Image:
    api_key = resolve_api_key("openai")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        result = client.images.generate(model=model, prompt=prompt, size=size, n=1)
        image_data = result.data[0]
        if getattr(image_data, "b64_json", None):
            return _decode_b64_image(image_data.b64_json)
        if getattr(image_data, "url", None):
            raise RuntimeError("OpenAI returned a URL image. Install SDK support for b64_json or download manually.")
    except ImportError:
        raise RuntimeError("OpenAI image generation needs the optional openai package.")
    raise RuntimeError("OpenAI response did not contain image data.")


def _gemini_generate(prompt: str, model: str, size: str) -> Image.Image:
    api_key = resolve_api_key("gemini")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        width, height = parse_cell_size(size, (1024, 1024))
        result = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1, output_mime_type="image/png"),
        )
        image = result.generated_images[0].image
        raw = getattr(image, "image_bytes", None) or image
        out = Image.open(BytesIO(raw)).convert("RGBA")
        return out.resize((width, height), Image.Resampling.LANCZOS) if out.size != (width, height) else out
    except ImportError:
        raise RuntimeError("Gemini image generation needs the optional google-genai package.")


def generate_cloud_image(provider: str, prompt: str, model: Optional[str], size: str) -> Image.Image:
    provider = provider.lower().strip()
    if provider == "openai":
        return _openai_generate(prompt, model or "gpt-image-1", size)
    if provider == "gemini":
        return _gemini_generate(prompt, model or "imagen-3.0-generate-002", size)
    raise ValueError(f"Unsupported cloud image provider: {provider}")


def _cloud_generation_contract(
    *,
    source: str,
    frame_count: int,
    constraints: str,
    negative: str,
    key_color: str,
    cell_size: Tuple[int, int],
    palette_colors: Optional[int],
) -> Dict[str, Any]:
    return {
        "schema": "spriteforge.cloud_generation_contract.v1",
        "cloud_api_opt_in": source == "cloud_api",
        "source": source,
        "request_strategy": "one_frame_per_request" if source == "cloud_api" else "local_source_images_only",
        "planned_cloud_requests": frame_count if source == "cloud_api" else 0,
        "secrets_policy": {
            "read_from_local_env": True,
            "secret_values_exposed": False,
            "secret_values_persisted": False,
            "supported_env_files": [".env", "app/.env"],
        },
        "prompt_policy": {
            "constraints": constraints,
            "negative": negative,
            "force_appended": True,
            "single_asset": "single isolated 2D game asset" in constraints,
            "sprite_sheet_disallowed": "sprite sheet grid" in negative,
        },
        "post_processing": {
            "background_to_alpha": key_color,
            "downsample_interpolation": "nearest",
            "target_cell_size": f"{cell_size[0]}x{cell_size[1]}",
            "palette_quantization": bool(palette_colors),
            "palette_colors": palette_colors,
            "grid_stitching": True,
        },
    }


def build_cloud_generation_plan(
    prompt: str,
    provider: str = "openai",
    model: Optional[str] = None,
    size: str = "1024x1024",
    cell_size: str | Tuple[int, int] = "64x64",
    frame_count: int = 1,
    frame_prompts: Optional[Sequence[str]] = None,
    source_images: Optional[Sequence[str]] = None,
    key_color: str = DEFAULT_KEY_COLOR,
    palette_colors: Optional[int] = 24,
    constraints: str = DEFAULT_CONSTRAINTS,
    negative: str = DEFAULT_NEGATIVE,
) -> Dict[str, Any]:
    """Return a secret-safe dry-run plan for cloud image sprite generation."""
    provider = provider.lower().strip()
    if provider not in {"openai", "gemini"}:
        raise ValueError(f"Unsupported cloud image provider: {provider}")
    cell = parse_cell_size(cell_size)
    source_images = list(source_images or [])
    frame_prompts = list(frame_prompts or [])
    planned_count = len(source_images) if source_images else max(1, int(frame_count))
    source = "local_images" if source_images else "cloud_api"
    prompts = []
    if not source_images:
        for idx in range(planned_count):
            pose_suffix = frame_prompts[idx] if idx < len(frame_prompts) else f"pose frame {idx + 1}"
            prompts.append(hardened_prompt(f"{prompt}, {pose_suffix}", constraints, negative))
    provider_status = cloud_image_provider_status(provider)["providers"].get(provider, {})
    return {
        "schema": "spriteforge.cloud_generation_plan.v1",
        "provider": provider,
        "model": model or ("gpt-image-1" if provider == "openai" else "imagen-3.0-generate-002"),
        "provider_configured": bool(provider_status.get("configured")),
        "configured_env_name": provider_status.get("configured_env_name", ""),
        "secret_values_exposed": False,
        "source": source,
        "source_image_count": len(source_images),
        "frame_count": planned_count,
        "generation_size": size,
        "cell_size": f"{cell[0]}x{cell[1]}",
        "key_color": key_color,
        "palette_colors": palette_colors,
        "hardened_prompts": prompts,
        "processing_steps": [
            {"name": "isolate", "detail": "Generate one isolated pose per frame."},
            {"name": "transparency", "detail": f"Remove chroma key background {key_color} into alpha."},
            {"name": "downscale", "detail": f"Resize to {cell[0]}x{cell[1]} using nearest-neighbor interpolation."},
            {"name": "palette", "detail": "Quantize to a limited palette." if palette_colors else "Keep source colors."},
            {"name": "stitch", "detail": "Pack processed frames onto a grid-aligned sprite sheet."},
        ],
        "generation_contract": _cloud_generation_contract(
            source=source,
            frame_count=planned_count,
            constraints=constraints,
            negative=negative,
            key_color=key_color,
            cell_size=cell,
            palette_colors=palette_colors,
        ),
    }


def process_cloud_frame(
    image: Image.Image,
    cell_size: Tuple[int, int],
    key_color: str = DEFAULT_KEY_COLOR,
    key_tolerance: float = 18.0,
    palette_colors: Optional[int] = 24,
    anchor: str = "bottom-center",
    ground_margin: int = 0,
) -> FrameItem:
    rgba = apply_chroma_key(image.convert("RGBA"), parse_key_color(key_color), key_tolerance, 0.0)
    bbox = alpha_bbox(rgba, threshold=8)
    cropped = rgba.crop(expand_bbox(bbox, 2, rgba.width, rgba.height)) if bbox else rgba
    cell_w, cell_h = cell_size
    scale = min(cell_w / max(1, cropped.width), cell_h / max(1, cropped.height))
    new_size = (
        max(1, min(cell_w, int(round(cropped.width * scale)))),
        max(1, min(cell_h, int(round(cropped.height * scale)))),
    )
    resized = cropped.resize(new_size, Image.Resampling.NEAREST)
    out = Image.new("RGBA", cell_size, (0, 0, 0, 0))
    out.alpha_composite(resized, anchor_position(cell_size, new_size, anchor, ground_margin))
    if palette_colors:
        out = apply_native_pixel_cleanup(out, colors=int(palette_colors), alpha_threshold=8, dither=False)
    return FrameItem(out, "cloud_frame", 0)


def _frame_cleanup_metrics(raw: Image.Image, processed: Image.Image) -> Dict[str, Any]:
    rgba = processed.convert("RGBA")
    bbox = alpha_bbox(rgba, threshold=8)
    alpha = rgba.getchannel("A")
    alpha_histogram = alpha.histogram()
    opaque_pixels = sum(alpha_histogram[9:])
    total_pixels = max(1, rgba.width * rgba.height)
    colors = rgba.convert("RGBA").getcolors(maxcolors=rgba.width * rgba.height + 1) or []
    return {
        "schema": "spriteforge.cloud_frame_cleanup.v1",
        "raw_size": f"{raw.width}x{raw.height}",
        "processed_size": f"{rgba.width}x{rgba.height}",
        "alpha_bbox": list(bbox) if bbox else [],
        "opaque_pixel_ratio": round(opaque_pixels / total_pixels, 4),
        "transparent_pixel_ratio": round(1.0 - (opaque_pixels / total_pixels), 4),
        "unique_color_count": len(colors),
    }


def _load_source_images(paths: Sequence[str]) -> List[Image.Image]:
    images = []
    for value in paths:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Cloud source image not found: {path}")
        images.append(Image.open(path).convert("RGBA"))
    return images


def build_cloud_sprite_sheet(
    prompt: str,
    output_dir: str | Path,
    provider: str = "openai",
    model: Optional[str] = None,
    source_images: Optional[Sequence[str]] = None,
    frame_count: int = 1,
    frame_prompts: Optional[Sequence[str]] = None,
    size: str = "1024x1024",
    cell_size: str | Tuple[int, int] = "64x64",
    key_color: str = DEFAULT_KEY_COLOR,
    palette_colors: Optional[int] = 24,
    columns: Optional[int] = None,
    fps: float = 12.0,
    animation_name: str = "cloud_sprite",
    constraints: str = DEFAULT_CONSTRAINTS,
    negative: str = DEFAULT_NEGATIVE,
) -> Dict[str, Any]:
    constraints = constraints or DEFAULT_CONSTRAINTS
    negative = negative or DEFAULT_NEGATIVE
    out = Path(output_dir)
    if not out.is_absolute():
        out = ROOT / out
    ensure_dir(out)
    raw_dir = out / "frames_raw"
    processed_dir = out / "frames_processed"
    ensure_dir(raw_dir)
    ensure_dir(processed_dir)

    cell = parse_cell_size(cell_size)
    raw_images = _load_source_images(source_images or [])
    prompts: List[str] = []
    source = "local_images" if raw_images else "cloud_api"
    resolved_model = model or ("gpt-image-1" if provider.lower().strip() == "openai" else "imagen-3.0-generate-002")
    if raw_images:
        frame_count = len(raw_images)
    else:
        frame_count = max(1, int(frame_count))
        frame_prompts = list(frame_prompts or [])
        for idx in range(frame_count):
            pose_suffix = frame_prompts[idx] if idx < len(frame_prompts) else f"pose frame {idx + 1}"
            prompts.append(hardened_prompt(f"{prompt}, {pose_suffix}", constraints, negative))
        raw_images = [generate_cloud_image(provider, item, resolved_model, size) for item in prompts]

    processed: List[FrameItem] = []
    frame_sources: List[Dict[str, Any]] = []
    for idx, image in enumerate(raw_images):
        raw_path = raw_dir / f"raw_{idx:04d}.png"
        image.save(raw_path)
        item = process_cloud_frame(
            image,
            cell_size=cell,
            key_color=key_color,
            palette_colors=palette_colors,
        )
        processed.append(FrameItem(item.image, f"cloud_{idx:04d}", idx))
        cleanup_metrics = _frame_cleanup_metrics(image, item.image)
        frame_sources.append({
            "index": idx,
            "name": f"cloud_{idx:04d}",
            "source": "local_image" if source_images else "cloud_api",
            "source_image": str(source_images[idx]) if source_images and idx < len(source_images) else "",
            "raw_frame": str(raw_path.relative_to(out)).replace("\\", "/"),
            "processed_frame": f"frames_processed/frame_{idx:04d}.png",
            "hardened_prompt": prompts[idx] if idx < len(prompts) else "",
            "provider": provider,
            "model": resolved_model,
            "cell_size": f"{cell[0]}x{cell[1]}",
            "key_color": key_color,
            "palette_colors": palette_colors,
            "cleanup_metrics": cleanup_metrics,
        })

    save_png_sequence(processed, processed_dir, prefix="frame")
    sheet, used_columns, rows, rects = pack_sheet(processed, columns=columns, spacing=0, margin=0, power_of_two=False)
    sheet.save(out / "sheet.png")
    extra = {
        "schema": "spriteforge.cloud_image_sprite.v1",
        "plan_schema": "spriteforge.cloud_generation_plan.v1",
        "provider": provider,
        "model": resolved_model,
        "prompt": prompt,
        "hardened_prompts": prompts,
        "frame_sources": frame_sources,
        "negative": negative,
        "constraints": constraints,
        "key_color": key_color,
        "palette_colors": palette_colors,
        "processing": {
            "transparency_extraction": {
                "engine": "chroma_key",
                "background_color": key_color,
                "key_tolerance": 18.0,
            },
            "downsampling": {
                "target_cell_size": f"{cell[0]}x{cell[1]}",
                "interpolation": "nearest",
            },
            "palette_quantization": {
                "enabled": bool(palette_colors),
                "colors": palette_colors,
            },
            "cleanup_metrics": {
                "schema": "spriteforge.cloud_frame_cleanup.v1",
                "per_frame": True,
            },
            "assembly": {
                "stitcher": "sprite_sheet_service.pack_sheet",
                "grid_aligned": True,
            },
        },
        "source": source,
        "generation_contract": _cloud_generation_contract(
            source=source,
            frame_count=len(raw_images),
            constraints=constraints,
            negative=negative,
            key_color=key_color,
            cell_size=cell,
            palette_colors=palette_colors,
        ),
        "provider_configured": cloud_image_provider_status(provider)["providers"].get(provider, {}).get("configured", False),
    }
    write_metadata(
        out / "sheet.json",
        "sheet.png",
        processed,
        rects,
        cell,
        used_columns,
        rows,
        fps,
        animation_name,
        spacing=0,
        margin=0,
        extra=extra,
    )
    make_preview_gif(processed, out / "preview.gif", fps=fps)
    make_contact_sheet(processed, out / "contact_sheet.jpg", columns=used_columns)
    write_godot_notes(out / "godot_notes.txt", len(processed), used_columns, rows, fps, cell)
    write_report(out / "report.html", "sheet.png", out, len(processed), fps, cell, used_columns, rows, extra)
    manifest = {
        **extra,
        "output_dir": str(out),
        "frame_count": len(processed),
        "frame_width": cell[0],
        "frame_height": cell[1],
        "columns": used_columns,
        "rows": rows,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out / "cloud_generation.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def default_output_dir(prompt: str) -> Path:
    return ROOT / "output" / f"cloud_image_{safe_name(prompt)[:32]}_{time.strftime('%Y%m%d_%H%M%S')}"
