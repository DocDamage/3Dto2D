from __future__ import annotations

import datetime as dt
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from services.pixel_asset_service import ASSETS_DIR
from services.pixel_normalization_service import PixelNormalizationService
from spriteforge_utils import ROOT, load_json, save_json


class PixelReskinService:
    @staticmethod
    def create_variants(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        prompt = str(payload.get("prompt") or payload.get("reskin_prompt") or "").strip()
        count = max(1, min(int(payload.get("count") or 6), 12))
        if not asset_id:
            raise ValueError("asset_id is required")
        if not prompt:
            raise ValueError("prompt is required")

        asset_dir = ASSETS_DIR / asset_id
        asset_png = asset_dir / "asset.png"
        meta_path = asset_dir / "pixel_asset.json"
        if not asset_png.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Pixel asset not found: {asset_id}")

        meta = load_json(meta_path, {})
        base_img = Image.open(asset_png).convert("RGBA")
        request_id = f"reskin_{uuid.uuid4().hex[:12]}"
        variant_dir = asset_dir / "reskin_variants" / request_id
        variant_dir.mkdir(parents=True, exist_ok=True)
        max_colors = int(meta.get("palette", {}).get("max_colors", 24) or 24)

        variants: List[Dict[str, Any]] = []
        for index in range(count):
            reskinned = PixelReskinService._reskin_image(base_img, prompt, index)
            normalized = PixelNormalizationService.normalize_asset(reskinned, {
                "resolution": list(base_img.size),
                "clean_alpha": True,
                "quantize_palette": True,
                "max_colors": max_colors,
                "remove_islands": True,
                "min_island_size": 2,
                "outline": meta.get("pixel_rules", {}).get("outline", "none"),
            })
            variant_id = f"{request_id}_v{index + 1}"
            variant_path = variant_dir / f"{variant_id}.png"
            normalized.save(variant_path)
            variants.append({
                "variant_id": variant_id,
                "index": index,
                "path": PixelReskinService._rel(variant_path),
                "prompt": prompt,
                "recommendation": PixelReskinService._recommendation(prompt, index),
            })

        manifest = {
            "schema": "spriteforge.pixel_reskin.v1",
            "request_id": request_id,
            "asset_id": asset_id,
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
            "prompt": prompt,
            "variants": variants,
        }
        save_json(variant_dir / "reskin_manifest.json", manifest)
        return {"ok": True, "manifest": manifest, "variants": variants}

    @staticmethod
    def accept_variant(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        variant_path_value = str(payload.get("variant_path") or "").strip()
        label = str(payload.get("label") or "accepted reskin").strip()
        if not asset_id or not variant_path_value:
            raise ValueError("asset_id and variant_path are required")

        asset_dir = ASSETS_DIR / asset_id
        asset_png = asset_dir / "asset.png"
        meta_path = asset_dir / "pixel_asset.json"
        variant_path = (ROOT / variant_path_value.strip("/")).resolve()
        try:
            variant_path.relative_to(ROOT.resolve())
            variant_path.relative_to(asset_dir.resolve())
        except ValueError as exc:
            raise ValueError("variant_path must stay inside the selected asset folder") from exc
        if not variant_path.exists() or not variant_path.is_file():
            raise FileNotFoundError(f"Reskin variant not found: {variant_path_value}")

        versions_dir = asset_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = versions_dir / f"before_reskin_{stamp}.png"
        if asset_png.exists():
            shutil.copy(asset_png, backup_path)
        shutil.copy(variant_path, asset_png)

        meta = load_json(meta_path, {})
        result_img = Image.open(asset_png).convert("RGBA")
        max_colors = int(meta.get("palette", {}).get("max_colors", 24) or 24)
        colors = PixelReskinService._colors(result_img, max_colors)
        meta.setdefault("palette", {})["colors"] = colors
        meta.setdefault("qa", {})["color_count"] = len(colors)
        meta["qa"]["alpha_ok"] = True
        meta.setdefault("versions", []).append({
            "path": PixelReskinService._rel(backup_path),
            "label": f"before {label}",
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        meta.setdefault("reskin_history", []).append({
            "label": label,
            "variant_path": PixelReskinService._rel(variant_path),
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        save_json(meta_path, meta)
        return {"ok": True, "asset": meta, "accepted_variant": PixelReskinService._rel(variant_path)}

    @staticmethod
    def _reskin_image(img: Image.Image, prompt: str, index: int) -> Image.Image:
        lower = prompt.lower()
        target = PixelReskinService._target_color(lower, index)
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        pixels = img.load()
        out = result.load()
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]
                if a == 0:
                    continue
                luminance = (r * 0.299 + g * 0.587 + b * 0.114) / 255
                mix = 0.55 + (index % 3) * 0.12
                nr = int((r * (1 - mix)) + (target[0] * mix * luminance))
                ng = int((g * (1 - mix)) + (target[1] * mix * luminance))
                nb = int((b * (1 - mix)) + (target[2] * mix * luminance))
                out[x, y] = (max(0, min(255, nr)), max(0, min(255, ng)), max(0, min(255, nb)), a)
        return result

    @staticmethod
    def _target_color(prompt: str, index: int) -> tuple[int, int, int]:
        if "ice" in prompt or "blue" in prompt:
            return (72, 150, 240)
        if "fire" in prompt or "red" in prompt:
            return (235, 75, 56)
        if "poison" in prompt or "green" in prompt:
            return (70, 210, 110)
        if "gold" in prompt or "royal" in prompt:
            return (235, 190, 62)
        if "shadow" in prompt or "dark" in prompt:
            return (76, 64, 110)
        palette = [(72, 150, 240), (235, 75, 56), (70, 210, 110), (235, 190, 62), (172, 96, 224), (64, 200, 190)]
        return palette[index % len(palette)]

    @staticmethod
    def _recommendation(prompt: str, index: int) -> str:
        labels = ["clean recolor", "high contrast", "muted palette", "bright variant", "dark variant", "alternate trim"]
        return f"{labels[index % len(labels)]}: {prompt}"

    @staticmethod
    def _colors(img: Image.Image, max_colors: int) -> List[str]:
        colors: List[str] = []
        unique = img.getcolors(maxcolors=256)
        if unique:
            for _count, col in unique:
                if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                    colors.append(f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}")
        return colors[:max_colors]

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
