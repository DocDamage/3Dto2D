from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image

from spriteforge_utils import IMAGE_SUFFIXES, safe_name

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output" / "training_datasets"

ACTION_WORDS = {
    "idle", "walk", "run", "attack_light", "attack_heavy", "cast", "jump", "hurt",
    "death", "block", "dodge", "shoot", "slash", "thrust", "spin_attack", "throw",
    "heal", "summon", "talk", "wave", "cheer", "fall", "land", "sleep", "sit",
    "read", "drink", "search", "grab", "push", "pull", "dance", "parry", "kick",
}

DIRECTION_WORDS = [
    "iso_front_left", "iso_front_right", "iso_back_left", "iso_back_right",
    "front_right", "front_left", "back_right", "back_left",
    "three_quarter", "front", "back", "left", "right",
]


def _image_paths(source_dir: Path) -> List[Path]:
    return sorted(
        path for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _parse_cell_size(cell_size: Optional[str], cell_width: Optional[int], cell_height: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
    if cell_size:
        parts = str(cell_size).lower().replace(" ", "").split("x", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
        raise ValueError("cell_size must look like 92x92 or 128x128.")
    return cell_width, cell_height


def _infer_tags(path: Path) -> Tuple[str, str, List[str]]:
    stem = path.stem.lower().replace("-", "_").replace(" ", "_")
    direction = ""
    for candidate in DIRECTION_WORDS:
        if candidate in stem:
            direction = candidate
            break
    action = ""
    for candidate in sorted(ACTION_WORDS, key=len, reverse=True):
        if candidate in stem:
            action = candidate
            break
    leftover = stem
    for token in [direction, action]:
        if token:
            leftover = leftover.replace(token, "_")
    tags = [part for part in leftover.split("_") if part and not part.isdigit()]
    return action, direction, tags[:8]


def _is_blank(img: Image.Image) -> bool:
    if img.mode != "RGBA":
        return False
    alpha = img.getchannel("A")
    return alpha.getbbox() is None


def _frames_from_image(path: Path, cell_width: Optional[int], cell_height: Optional[int]) -> Iterable[Tuple[int, Image.Image]]:
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    if not cell_width or not cell_height or width < cell_width or height < cell_height:
        yield 0, img
        return
    if width == cell_width and height == cell_height:
        yield 0, img
        return
    index = 0
    rows = height // cell_height
    cols = width // cell_width
    for row in range(rows):
        for col in range(cols):
            box = (col * cell_width, row * cell_height, (col + 1) * cell_width, (row + 1) * cell_height)
            frame = img.crop(box)
            if not _is_blank(frame):
                yield index, frame
            index += 1


def _palette_from_samples(samples: List[Path], max_colors: int = 16) -> List[str]:
    pixels: List[Tuple[int, int, int]] = []
    for path in samples[:256]:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((96, 96), Image.Resampling.NEAREST)
        pixel_data = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
        for r, g, b, a in pixel_data:
            if a > 32:
                pixels.append((r, g, b))
    if not pixels:
        return []
    work = Image.new("RGB", (len(pixels), 1))
    work.putdata(pixels)
    q = work.quantize(colors=min(max_colors, max(1, len(set(pixels)))), method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    used = sorted(q.getcolors() or [], reverse=True)
    colors: List[str] = []
    for _count, idx in used[:max_colors]:
        i = idx * 3
        if i + 2 < len(pal):
            colors.append("#%02X%02X%02X" % (pal[i], pal[i + 1], pal[i + 2]))
    return colors


def _caption(trigger: str, base_caption: str, action: str, direction: str, tags: List[str]) -> str:
    parts = [trigger.strip(), base_caption.strip()]
    if action:
        parts.append(f"{action} animation")
    if direction:
        parts.append(f"{direction} view")
    parts.extend(tag.replace("_", " ") for tag in tags)
    parts.extend(["transparent background", "pixel art sprite", "game-ready character"])
    return ", ".join(part for part in parts if part)


def _write_training_notes(output_dir: Path, trigger: str) -> None:
    notes = f"""# SpriteForge Training Dataset

This folder is prepared for private LoRA training from owned sprite assets.

Suggested first pass:

- Train a private SDXL/Flux style LoRA for new static characters.
- Use trigger token `{trigger}` in prompts.
- Keep captions concise and preserve action/direction tags.
- Do not publish the trained LoRA unless the purchased asset license explicitly allows model training redistribution.

For Wan2.2 animation LoRA training, use this dataset as source material after converting sheets into short clips or frame buckets.
"""
    (output_dir / "README_TRAINING_DATASET.md").write_text(notes, encoding="utf-8")


def build_training_dataset(
    source_dir: Path | str,
    output_dir: Path | str,
    trigger: str = "sakpix_style",
    base_caption: str = "premium pixel art RPG character",
    cell_width: Optional[int] = None,
    cell_height: Optional[int] = None,
    cell_size: Optional[str] = None,
) -> Dict[str, Any]:
    source = Path(source_dir).resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Source folder not found: {source}")
    out = Path(output_dir).resolve()
    images_dir = out / "images"
    captions_dir = out / "captions"
    images_dir.mkdir(parents=True, exist_ok=True)
    captions_dir.mkdir(parents=True, exist_ok=True)

    cw, ch = _parse_cell_size(cell_size, cell_width, cell_height)
    source_images = _image_paths(source)
    samples: List[Dict[str, Any]] = []
    sample_images: List[Path] = []

    for source_image in source_images:
        action, direction, tags = _infer_tags(source_image)
        try:
            source_stem = source_image.relative_to(source).with_suffix("").as_posix()
        except ValueError:
            source_stem = source_image.stem
        for frame_index, frame in _frames_from_image(source_image, cw, ch):
            stem = safe_name(f"{source_stem}_{frame_index:04d}")
            image_path = images_dir / f"{stem}.png"
            caption_path = captions_dir / f"{stem}.txt"
            sidecar_path = images_dir / f"{stem}.txt"
            cap = _caption(trigger, base_caption, action, direction, tags)
            frame.save(image_path)
            caption_path.write_text(cap, encoding="utf-8")
            sidecar_path.write_text(cap, encoding="utf-8")
            sample_images.append(image_path)
            samples.append({
                "source": str(source_image),
                "image": str(image_path),
                "caption_file": str(caption_path),
                "caption": cap,
                "action": action,
                "direction": direction,
                "frame_index": frame_index,
            })

    palette = _palette_from_samples(sample_images)
    manifest = {
        "schema": "spriteforge.training_dataset.v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(source),
        "output_dir": str(out),
        "trigger": trigger,
        "base_caption": base_caption,
        "cell_size": f"{cw}x{ch}" if cw and ch else None,
        "source_image_count": len(source_images),
        "sample_count": len(samples),
        "palette": palette,
        "samples": samples,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "palette.json").write_text(json.dumps({"colors": palette}, indent=2), encoding="utf-8")
    _write_training_notes(out, trigger)

    print(f"Training dataset: {out}")
    print(f"Samples: {len(samples)} from {len(source_images)} source images")
    return manifest


def default_output_dir(name: str = "sakpix_dataset") -> Path:
    return DEFAULT_OUTPUT / f"{safe_name(name)}_{time.strftime('%Y%m%d_%H%M%S')}"
