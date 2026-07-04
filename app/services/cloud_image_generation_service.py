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
    names = {
        "openai": ("OPENAI_API_KEY", "SPRITEFORGE_OPENAI_API_KEY"),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "SPRITEFORGE_GEMINI_API_KEY"),
    }.get(provider, ())
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    raise RuntimeError(f"Missing API key for {provider}. Put it in a local .env file or process environment.")


def hardened_prompt(user_prompt: str, constraints: str = DEFAULT_CONSTRAINTS) -> str:
    user_prompt = str(user_prompt or "").strip()
    if not user_prompt:
        raise ValueError("Prompt is required.")
    constraints = str(constraints or DEFAULT_CONSTRAINTS).strip()
    if constraints.lower() in user_prompt.lower():
        return user_prompt
    return f"{user_prompt}, {constraints}"


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
    if raw_images:
        frame_count = len(raw_images)
    else:
        frame_count = max(1, int(frame_count))
        frame_prompts = list(frame_prompts or [])
        for idx in range(frame_count):
            pose_suffix = frame_prompts[idx] if idx < len(frame_prompts) else f"pose frame {idx + 1}"
            prompts.append(hardened_prompt(f"{prompt}, {pose_suffix}", constraints))
        raw_images = [generate_cloud_image(provider, item, model, size) for item in prompts]

    processed: List[FrameItem] = []
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

    save_png_sequence(processed, processed_dir, prefix="frame")
    sheet, used_columns, rows, rects = pack_sheet(processed, columns=columns, spacing=0, margin=0, power_of_two=False)
    sheet.save(out / "sheet.png")
    extra = {
        "schema": "spriteforge.cloud_image_sprite.v1",
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "hardened_prompts": prompts,
        "negative": negative,
        "constraints": constraints,
        "key_color": key_color,
        "palette_colors": palette_colors,
        "source": "local_images" if source_images else "cloud_api",
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
