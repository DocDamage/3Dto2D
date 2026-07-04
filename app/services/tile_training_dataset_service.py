from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image

from spriteforge_utils import IMAGE_SUFFIXES, safe_name
from services.training_dataset_service import _palette_from_samples

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output" / "training_datasets"

TILE_KEYWORDS = {
    "tile", "tiles", "floor", "wall", "walls", "path", "paths", "road", "roads",
    "ground", "soil", "terrain", "dirt", "sand", "stone", "water", "roof",
    "roofs", "bridge", "bridges", "stairs", "stair", "elevation", "cliff",
    "cliffs", "ledge", "ledges", "platform", "platforms", "edge", "edges",
    "corner", "corners", "walkway", "walkways", "pavement",
}

MATERIAL_WORDS = {
    "grass", "dirt", "soil", "stone", "cobblestone", "marble", "wood", "wooden",
    "snow", "ice", "icy", "water", "lava", "volcanic", "sand", "desert", "mud",
    "metal", "sci-fi", "scifi", "roof", "wall", "floor", "path", "road", "cliff",
    "bridge", "temple", "dungeon", "castle", "forest", "sakura", "cyberpunk",
    "farming", "medieval", "pirate", "underwater", "wasteland",
}


def _image_paths(source_dir: Path) -> List[Path]:
    return sorted(
        path for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _clean_words(value: str) -> List[str]:
    cleaned = value.lower().replace("_", " ").replace("-", " ")
    for ch in ".,!()+[]{}":
        cleaned = cleaned.replace(ch, " ")
    return [part for part in cleaned.split() if part and not part.isdigit()]


def _tile_search_text(path: Path, source: Path) -> str:
    try:
        rel = path.relative_to(source)
        parts = list(rel.parts)
    except ValueError:
        parts = [path.name]
    # Ignore the top-level theme folder so names like "Snowy Village" do not
    # make every prop sheet look tile-like.
    searchable_parts = parts[1:] if len(parts) > 1 else parts
    return " ".join(_clean_words(" ".join(searchable_parts)))


def _is_tile_source(path: Path, source: Path, include_all: bool = False) -> bool:
    if include_all:
        return True
    words = set(_tile_search_text(path, source).split())
    if words & TILE_KEYWORDS:
        return True
    try:
        with Image.open(path) as img:
            width, height = img.size
            if width < 64 or height < 64:
                return False
            candidates = [128, 96, 64, 48, 32, 16]
            for size in candidates:
                if width % size == 0 and height % size == 0 and width // size >= 2 and height // size >= 2:
                    cells = []
                    for row in range(height // size):
                        for col in range(width // size):
                            cell = img.crop((col * size, row * size, (col + 1) * size, (row + 1) * size))
                            if cell.getbbox() is not None:
                                cells.append(cell.tobytes())
                    if len(set(cells)) >= 2:
                        return True
            if width == height:
                for cells in range(2, 13):
                    if width % cells == 0:
                        size = width // cells
                        if 32 <= size <= 256 and cells >= 2:
                            grid = []
                            for row in range(cells):
                                for col in range(cells):
                                    cell = img.crop((col * size, row * size, (col + 1) * size, (row + 1) * size))
                                    if cell.getbbox() is not None:
                                        grid.append(cell.tobytes())
                            if len(set(grid)) >= 2:
                                return True
    except OSError:
        return False
    return False


def _theme_from_path(path: Path, source: Path) -> str:
    try:
        rel = path.relative_to(source)
        return " ".join(_clean_words(rel.parts[0])) if rel.parts else ""
    except ValueError:
        return ""


def _material_tags(path: Path, source: Path) -> List[str]:
    try:
        rel_text = " ".join(path.relative_to(source).parts)
    except ValueError:
        rel_text = path.name
    words = _clean_words(rel_text)
    tags: List[str] = []
    for word in words:
        if word in MATERIAL_WORDS and word not in tags:
            tags.append(word)
    return tags[:8]


def _parse_cell_size(cell_size: Optional[str]) -> Tuple[Optional[int], Optional[int], bool]:
    value = str(cell_size or "auto").strip().lower()
    if value in {"", "auto"}:
        return None, None, True
    parts = value.replace(" ", "").split("x", 1)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1]), False
    raise ValueError("cell_size must be auto or look like 128x128.")


def _auto_cell_size(width: int, height: int) -> Tuple[int, int]:
    for size in (128, 96, 64, 32):
        if width // size >= 2 and height // size >= 2 and width % size == 0 and height % size == 0:
            return size, size
    if width == height:
        for cells in range(2, 13):
            if width % cells == 0:
                size = width // cells
                if 64 <= size <= 256:
                    return size, size
    return 128, 128


def _is_blank(img: Image.Image) -> bool:
    if img.mode != "RGBA":
        return False
    return img.getchannel("A").getbbox() is None


def _cells_from_image(path: Path, cell_size: Optional[str]) -> Iterable[Tuple[int, int, int, str, Image.Image]]:
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    requested_w, requested_h, auto = _parse_cell_size(cell_size)
    cw, ch = _auto_cell_size(width, height) if auto else (requested_w or width, requested_h or height)
    if cw <= 0 or ch <= 0:
        return
    cols = max(1, width // cw)
    rows = max(1, height // ch)
    if cols <= 1 and rows <= 1:
        yield 0, 0, 0, f"{width}x{height}", img
        return
    index = 0
    for row in range(rows):
        for col in range(cols):
            box = (col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)
            cell = img.crop(box)
            if not _is_blank(cell):
                yield index, row, col, f"{cw}x{ch}", cell
            index += 1


def _sample_evenly(items: List[Tuple[int, int, int, str, Image.Image]], limit: Optional[int]) -> List[Tuple[int, int, int, str, Image.Image]]:
    if not limit or limit <= 0 or len(items) <= limit:
        return items
    if limit == 1:
        return [items[0]]
    last = len(items) - 1
    indexes = sorted({round(i * last / (limit - 1)) for i in range(limit)})
    return [items[i] for i in indexes]


def _caption(trigger: str, base_caption: str, theme: str, materials: List[str], row: int, col: int) -> str:
    parts = [
        trigger.strip(),
        base_caption.strip(),
        "auto-tile",
        "seamless terrain tile",
        "top-down game tile",
    ]
    if theme:
        parts.append(theme)
    parts.extend(material.replace("_", " ") for material in materials)
    parts.append(f"tile cell row {row} column {col}")
    parts.extend(["pixel art", "game-ready tileset"])
    return ", ".join(part for part in parts if part)


def _write_training_notes(output_dir: Path, trigger: str) -> None:
    notes = f"""# SpriteForge Auto-Tile Training Dataset

This folder is prepared for private LoRA training from owned SakPix stage tile assets.

Suggested first pass:

- Train a separate SDXL style LoRA from character sprites.
- Use trigger token `{trigger}` in tile prompts.
- Prompt for one material/theme at a time, such as grass path, lava rock, castle wall, or water edge.
- Generate 16-tile or 47-tile auto-tile layouts as full sheets after the style LoRA looks clean.
- Keep trained LoRAs private unless the purchased asset license explicitly allows model-training redistribution.
"""
    (output_dir / "README_AUTOTILE_TRAINING_DATASET.md").write_text(notes, encoding="utf-8")


def build_tile_training_dataset(
    source_dir: Path | str,
    output_dir: Path | str,
    trigger: str = "sakpix_tiles",
    base_caption: str = "premium top-down pixel art tileset",
    cell_size: str = "auto",
    max_samples_per_source: int | str = 32,
    include_all: bool = False,
) -> Dict[str, Any]:
    source = Path(source_dir).resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Source folder not found: {source}")
    out = Path(output_dir).resolve()
    images_dir = out / "images"
    captions_dir = out / "captions"
    images_dir.mkdir(parents=True, exist_ok=True)
    captions_dir.mkdir(parents=True, exist_ok=True)

    try:
        per_source_limit = int(max_samples_per_source)
    except (TypeError, ValueError):
        per_source_limit = 32

    scanned_images = _image_paths(source)
    source_images = [path for path in scanned_images if _is_tile_source(path, source, include_all=include_all)]
    skipped_non_tile_count = len(scanned_images) - len(source_images)
    samples: List[Dict[str, Any]] = []
    sample_images: List[Path] = []

    for source_image in source_images:
        theme = _theme_from_path(source_image, source)
        materials = _material_tags(source_image, source)
        try:
            source_stem = source_image.relative_to(source).with_suffix("").as_posix()
        except ValueError:
            source_stem = source_image.stem
        cells = list(_cells_from_image(source_image, cell_size))
        for cell_index, row, col, resolved_cell_size, cell in _sample_evenly(cells, per_source_limit):
            stem = safe_name(f"{source_stem}_{cell_index:04d}")
            image_path = images_dir / f"{stem}.png"
            caption_path = captions_dir / f"{stem}.txt"
            sidecar_path = images_dir / f"{stem}.txt"
            cap = _caption(trigger, base_caption, theme, materials, row, col)
            cell.save(image_path)
            caption_path.write_text(cap, encoding="utf-8")
            sidecar_path.write_text(cap, encoding="utf-8")
            sample_images.append(image_path)
            samples.append({
                "source": str(source_image),
                "image": str(image_path),
                "caption_file": str(caption_path),
                "caption": cap,
                "theme": theme,
                "materials": materials,
                "cell_index": cell_index,
                "row": row,
                "column": col,
                "cell_size": resolved_cell_size,
            })

    palette = _palette_from_samples(sample_images)
    manifest = {
        "schema": "spriteforge.training_dataset.v1",
        "dataset_kind": "autotile",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(source),
        "output_dir": str(out),
        "trigger": trigger,
        "base_caption": base_caption,
        "cell_size": cell_size,
        "max_samples_per_source": per_source_limit,
        "include_all": include_all,
        "scanned_image_count": len(scanned_images),
        "source_image_count": len(source_images),
        "skipped_non_tile_count": skipped_non_tile_count,
        "sample_count": len(samples),
        "palette": palette,
        "samples": samples,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "palette.json").write_text(json.dumps({"colors": palette}, indent=2), encoding="utf-8")
    _write_training_notes(out, trigger)

    print(f"Auto-tile training dataset: {out}")
    print(f"Samples: {len(samples)} from {len(source_images)} tile-like source images")
    print(f"Skipped non-tile sheets: {skipped_non_tile_count}")
    return manifest


def default_output_dir(name: str = "sakpix_autotiles") -> Path:
    return DEFAULT_OUTPUT / f"{safe_name(name)}_{time.strftime('%Y%m%d_%H%M%S')}"
