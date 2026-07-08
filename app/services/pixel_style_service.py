from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService
from spriteforge_utils import ROOT, load_json


class PixelStyleService:
    @staticmethod
    def extract_style_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id", "")).strip()
        image_path = str(payload.get("path", "")).strip()
        name = str(payload.get("name", "")).strip() or "Extracted Pixel Style"

        resolved = PixelStyleService._resolve_asset_image(asset_id, image_path)
        image = Image.open(resolved).convert("RGBA")
        palette = PixelStyleService.extract_palette(image, int(payload.get("max_colors", 24)))
        bbox = image.getbbox()

        style = {
            "schema": "spriteforge.pixel_style_profile.v1",
            "style_id": f"style_{uuid.uuid4().hex[:12]}",
            "name": name,
            "source_assets": [PixelStyleService._display_path(resolved)],
            "palette": palette,
            "max_colors": int(payload.get("max_colors", 24)),
            "resolution_default": [image.width, image.height],
            "outline_hint": PixelStyleService._infer_outline_hint(palette),
            "shading_hint": "limited palette pixel shading",
            "camera_hint": "orthographic sprite view",
            "negative_prompt": "blur, antialiasing, painterly texture, photographic detail",
            "metrics": {
                "alpha_bbox": list(bbox) if bbox else None,
                "opaque_ratio": PixelStyleService._opaque_ratio(image),
                "color_count": len(palette),
            },
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        }
        return PixelAssetService.save_style_profile(style)

    @staticmethod
    def extract_palette(image: Image.Image, max_colors: int) -> List[str]:
        colors = image.getcolors(maxcolors=image.width * image.height) or []
        visible = []
        for count, color in colors:
            if len(color) >= 4 and color[3] == 0:
                continue
            visible.append((count, color[:3]))
        visible.sort(reverse=True, key=lambda item: item[0])
        palette: List[str] = []
        for _count, color in visible:
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            if hex_color not in palette:
                palette.append(hex_color)
            if len(palette) >= max_colors:
                break
        return palette

    @staticmethod
    def compare_to_style(asset_palette: List[str], style_palette: List[str]) -> Dict[str, Any]:
        asset_set = {color.lower() for color in asset_palette}
        style_set = {color.lower() for color in style_palette}
        if not asset_set or not style_set:
            score = 0.0
        else:
            score = len(asset_set & style_set) / max(len(asset_set | style_set), 1)
        return {
            "schema": "spriteforge.pixel_style_match.v1",
            "palette_overlap": round(score, 4),
            "ok": score >= 0.35,
        }

    @staticmethod
    def _resolve_asset_image(asset_id: str, image_path: str) -> Path:
        if asset_id:
            candidate = pas_mod.ASSETS_DIR / asset_id / "asset.png"
            if candidate.exists():
                return candidate
            raise FileNotFoundError(f"Asset image not found for {asset_id}")
        if image_path:
            candidate = (ROOT / image_path.strip("/")).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError as exc:
                raise ValueError("Style extraction path must stay inside the workspace.") from exc
            if candidate.exists() and candidate.is_file():
                return candidate
        raise ValueError("asset_id or path is required for style extraction.")

    @staticmethod
    def _display_path(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            return str(path)

    @staticmethod
    def _infer_outline_hint(palette: List[str]) -> str:
        if not palette:
            return "clean one-pixel outline"
        first = palette[0].lower()
        if first in {"#000000", "#111111", "#1b1b1b"}:
            return "dark one-pixel outline"
        return "clean one-pixel outline"

    @staticmethod
    def _opaque_ratio(image: Image.Image) -> float:
        alpha = image.getchannel("A")
        histogram = alpha.histogram()
        opaque = sum(histogram[1:])
        return round(opaque / max(image.width * image.height, 1), 4)
