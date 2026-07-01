"""Cross-sheet palette harmonization for generated sprite outputs."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from PIL import Image

RGB = Tuple[int, int, int]


@dataclass
class SpritePalette:
    sprite_dir: Path
    sheet_path: Path
    colors: Counter[RGB]


def _hex(rgb: RGB) -> str:
    return "#%02X%02X%02X" % rgb


def _distance(a: RGB, b: RGB) -> float:
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def _sheet_path(sprite_dir: Path) -> Path:
    meta_path = sprite_dir / "sheet.json"
    image_name = "sheet.png"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            image_name = str(meta.get("image") or image_name)
        except Exception:
            pass
    path = sprite_dir / image_name
    if not path.exists():
        path = sprite_dir / "sheet.png"
    if not path.is_file():
        raise FileNotFoundError(f"No sheet image found in {sprite_dir}")
    return path


def _sample_colors(path: Path, max_side: int = 256) -> Counter[RGB]:
    img = Image.open(path).convert("RGBA")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.NEAREST)
    colors: Counter[RGB] = Counter()
    pixel_list = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    for r, g, b, a in pixel_list:
        if a > 64:
            colors[(r, g, b)] += 1
    if not colors:
        for r, g, b, _a in pixel_list:
            colors[(r, g, b)] += 1
    return colors


def _pick_unified_palette(sprite_palettes: Sequence[SpritePalette], limit: int) -> List[RGB]:
    merged: Counter[RGB] = Counter()
    for sprite in sprite_palettes:
        merged.update(sprite.colors)
    if not merged:
        return []
    source_pixels: List[RGB] = []
    for rgb, count in merged.most_common(min(len(merged), 4096)):
        source_pixels.extend([rgb] * max(1, min(64, count)))
    work = Image.new("RGB", (len(source_pixels), 1))
    work.putdata(source_pixels)
    q = work.quantize(colors=max(1, min(limit, len(set(source_pixels)))), method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    ranked = sorted(q.getcolors() or [], reverse=True)
    unified: List[RGB] = []
    for _count, index in ranked:
        offset = index * 3
        if offset + 2 < len(pal):
            rgb = (pal[offset], pal[offset + 1], pal[offset + 2])
            if rgb not in unified:
                unified.append(rgb)
    return unified[:limit]


def _nearest_palette_color(rgb: RGB, palette: Sequence[RGB]) -> RGB:
    return min(palette, key=lambda candidate: _distance(rgb, candidate))


def _palette_image(palette: Sequence[RGB]) -> Image.Image:
    pal_img = Image.new("P", (1, 1))
    flat: List[int] = []
    for rgb in palette:
        flat.extend(rgb)
    flat.extend([0] * max(0, 768 - len(flat)))
    pal_img.putpalette(flat[:768])
    return pal_img


def _write_harmonized_sheet(sheet_path: Path, out_path: Path, palette: Sequence[RGB]) -> None:
    src = Image.open(sheet_path).convert("RGBA")
    alpha = src.getchannel("A")
    quantized = src.convert("RGB").quantize(
        palette=_palette_image(palette),
        dither=Image.Dither.NONE,
    ).convert("RGBA")
    quantized.putalpha(alpha)
    quantized.save(out_path)


def _sprite_metrics(sprite: SpritePalette, palette: Sequence[RGB]) -> Dict[str, Any]:
    used = [rgb for rgb, _count in sprite.colors.most_common(64)]
    distances = [_distance(rgb, _nearest_palette_color(rgb, palette)) for rgb in used] if palette else []
    shared = sum(1 for rgb in used if rgb in palette)
    avg = sum(distances) / len(distances) if distances else 0.0
    worst = max(distances) if distances else 0.0
    return {
        "path": str(sprite.sprite_dir),
        "sheet": str(sprite.sheet_path),
        "distinct_colors": len(sprite.colors),
        "sample_palette": [_hex(rgb) for rgb, _count in sprite.colors.most_common(12)],
        "shared_top_colors": shared,
        "average_palette_drift": round(avg, 2),
        "max_palette_drift": round(worst, 2),
    }


def _report_url(root: Path, path: Path) -> str:
    try:
        return "/file/" + path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def harmonize_palette(
    sprite_dirs: Iterable[Path],
    *,
    colors: int = 32,
    write_images: bool = True,
    root: Path | None = None,
) -> Dict[str, Any]:
    """Analyze sprite sheets, write a shared palette report, and optionally remap sheets."""
    resolved_dirs = [Path(path).resolve() for path in sprite_dirs]
    if len(resolved_dirs) < 2:
        raise ValueError("At least two sprite folders are required.")
    limit = max(2, min(int(colors or 32), 256))
    root_path = (root or resolved_dirs[0].parents[1] if len(resolved_dirs[0].parents) > 1 else resolved_dirs[0].parent).resolve()

    sprite_palettes = [
        SpritePalette(sprite_dir=path, sheet_path=_sheet_path(path), colors=_sample_colors(_sheet_path(path)))
        for path in resolved_dirs
    ]
    unified = _pick_unified_palette(sprite_palettes, limit)
    if not unified:
        raise ValueError("No visible pixels found in the selected sprite sheets.")

    report_dir = resolved_dirs[0].parent / "_palette_harmonization"
    report_dir.mkdir(parents=True, exist_ok=True)
    palette_path = report_dir / "palette.json"
    report_path = report_dir / "palette_harmonization.json"
    palette_path.write_text(json.dumps([_hex(rgb) for rgb in unified], indent=2), encoding="utf-8")

    sprites: List[Dict[str, Any]] = []
    for sprite in sprite_palettes:
        metrics = _sprite_metrics(sprite, unified)
        out_path = sprite.sprite_dir / "sheet_harmonized.png"
        if write_images:
            _write_harmonized_sheet(sprite.sheet_path, out_path, unified)
            metrics["harmonized_sheet"] = str(out_path)
            metrics["harmonized_sheet_url"] = _report_url(root_path, out_path)
        sprites.append(metrics)

    report = {
        "ok": True,
        "colors": len(unified),
        "palette": [_hex(rgb) for rgb in unified],
        "palette_file": str(palette_path),
        "palette_url": _report_url(root_path, palette_path),
        "report_file": str(report_path),
        "report_url": _report_url(root_path, report_path),
        "sprites": sprites,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
