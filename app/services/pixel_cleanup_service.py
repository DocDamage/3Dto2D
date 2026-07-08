from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from services.pixel_asset_service import ASSETS_DIR
from services.pixel_normalization_service import PixelNormalizationService
from spriteforge_utils import ROOT, load_json, save_json


class PixelCleanupService:
    @staticmethod
    def cleanup_asset(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("asset_id is required")

        asset_dir = ASSETS_DIR / asset_id
        asset_png = asset_dir / "asset.png"
        meta_path = asset_dir / "pixel_asset.json"
        if not asset_png.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Pixel asset not found: {asset_id}")

        meta = load_json(meta_path, {})
        img = Image.open(asset_png).convert("RGBA")
        before_colors = len(PixelCleanupService._colors(img, 256))

        if payload.get("remove_background", True):
            img = PixelCleanupService._remove_corner_background(img, int(payload.get("background_tolerance", 18) or 18))

        resolution = payload.get("resolution") or meta.get("resolution") or list(img.size)
        if isinstance(resolution, str):
            try:
                resolution = [int(part) for part in resolution.lower().split("x")]
            except (TypeError, ValueError):
                resolution = list(img.size)
        max_colors = int(payload.get("max_colors") or meta.get("palette", {}).get("max_colors", 24) or 24)
        rules = {
            "resolution": resolution,
            "clean_alpha": payload.get("clean_alpha", True),
            "quantize_palette": payload.get("quantize_palette", True),
            "max_colors": max_colors,
            "remove_islands": payload.get("remove_islands", True),
            "min_island_size": int(payload.get("min_island_size", 2) or 2),
            "outline": payload.get("outline", meta.get("pixel_rules", {}).get("outline", "none")),
        }
        cleaned = PixelNormalizationService.normalize_asset(img, rules)

        versions_dir = asset_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = versions_dir / f"before_cleanup_{stamp}.png"
        shutil.copy(asset_png, backup_path)
        cleaned.save(asset_png)
        preview_path = asset_dir / "preview.png"
        cleaned.save(preview_path)

        colors = PixelCleanupService._colors(cleaned, max_colors)
        meta["resolution"] = list(cleaned.size)
        meta.setdefault("palette", {})["max_colors"] = max_colors
        meta["palette"]["colors"] = colors
        meta.setdefault("qa", {})["ok"] = True
        meta["qa"]["color_count"] = len(colors)
        meta["qa"]["alpha_ok"] = PixelCleanupService._has_transparency(cleaned)
        meta["qa"]["blur_score"] = 0.0
        meta.setdefault("versions", []).append({
            "path": PixelCleanupService._rel(backup_path),
            "label": "before cleanup",
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        meta.setdefault("cleanup_history", []).append({
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
            "rules": rules,
            "remove_background": bool(payload.get("remove_background", True)),
            "before_color_count": before_colors,
            "after_color_count": len(colors),
        })
        save_json(meta_path, meta)
        return {"ok": True, "asset": meta, "rules_applied": rules}

    @staticmethod
    def _remove_corner_background(img: Image.Image, tolerance: int) -> Image.Image:
        rgba = img.convert("RGBA")
        pixels = rgba.load()
        corners = [
            pixels[0, 0],
            pixels[rgba.width - 1, 0],
            pixels[0, rgba.height - 1],
            pixels[rgba.width - 1, rgba.height - 1],
        ]
        bg = max(corners, key=corners.count)
        out = rgba.copy()
        out_pixels = out.load()
        for y in range(out.height):
            for x in range(out.width):
                r, g, b, a = pixels[x, y]
                if a == 0:
                    continue
                dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
                if dist <= tolerance:
                    out_pixels[x, y] = (r, g, b, 0)
        return out

    @staticmethod
    def _colors(img: Image.Image, max_colors: int) -> List[str]:
        colors: List[str] = []
        unique = img.convert("RGBA").getcolors(maxcolors=512)
        if unique:
            for _count, col in unique:
                if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                    colors.append(f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}")
        return colors[:max_colors]

    @staticmethod
    def _has_transparency(img: Image.Image) -> bool:
        alpha = img.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
