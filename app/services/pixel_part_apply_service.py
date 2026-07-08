from __future__ import annotations

import base64
import datetime as dt
import json
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw

from services.pixel_asset_service import ASSETS_DIR
from services.pixel_normalization_service import PixelNormalizationService
from spriteforge_utils import ROOT, load_json, save_json


class PixelPartApplyService:
    @staticmethod
    def create_variants(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        part_prompt = str(payload.get("part_prompt") or "").strip()
        count = int(payload.get("count") or 3)
        count = max(1, min(count, 6))
        if not asset_id:
            raise ValueError("asset_id is required")
        if not part_prompt and not payload.get("part_image_data"):
            raise ValueError("part_prompt or part_image_data is required")

        asset_dir = ASSETS_DIR / asset_id
        meta_path = asset_dir / "pixel_asset.json"
        asset_png = asset_dir / "asset.png"
        if not asset_png.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Pixel asset not found: {asset_id}")

        meta = load_json(meta_path, {})
        base_img = Image.open(asset_png).convert("RGBA")
        part_img = PixelPartApplyService._decode_optional_image(payload.get("part_image_data"))
        request_id = f"part_{uuid.uuid4().hex[:12]}"
        variant_dir = asset_dir / "part_variants" / request_id
        variant_dir.mkdir(parents=True, exist_ok=True)

        variants: List[Dict[str, Any]] = []
        for index in range(count):
            result = PixelPartApplyService._render_variant(base_img, part_prompt, index, part_img)
            rules = {
                "resolution": list(base_img.size),
                "clean_alpha": True,
                "quantize_palette": True,
                "max_colors": int(meta.get("palette", {}).get("max_colors", 24) or 24),
                "remove_islands": True,
                "min_island_size": 2,
                "outline": meta.get("pixel_rules", {}).get("outline", "none"),
            }
            normalized = PixelNormalizationService.normalize_asset(result, rules)
            variant_id = f"{request_id}_v{index + 1}"
            filename = f"{variant_id}.png"
            variant_path = variant_dir / filename
            normalized.save(variant_path)
            rel_path = PixelPartApplyService._rel(variant_path)
            variants.append({
                "variant_id": variant_id,
                "index": index,
                "path": rel_path,
                "prompt": part_prompt,
                "recommendation": PixelPartApplyService._recommendation(part_prompt, index),
            })

        manifest = {
            "schema": "spriteforge.pixel_part_apply.v1",
            "request_id": request_id,
            "asset_id": asset_id,
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
            "part_prompt": part_prompt,
            "part_image_used": bool(part_img),
            "variants": variants,
        }
        save_json(variant_dir / "part_apply_manifest.json", manifest)
        return {"ok": True, "manifest": manifest, "variants": variants}

    @staticmethod
    def accept_variant(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        variant_path_value = str(payload.get("variant_path") or "").strip()
        label = str(payload.get("label") or "applied part").strip()
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
            raise FileNotFoundError(f"Part variant not found: {variant_path_value}")

        versions_dir = asset_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = versions_dir / f"before_part_apply_{stamp}.png"
        if asset_png.exists():
            shutil.copy(asset_png, backup_path)
        shutil.copy(variant_path, asset_png)

        meta = load_json(meta_path, {})
        result_img = Image.open(asset_png).convert("RGBA")
        colors = PixelPartApplyService._colors(result_img, int(meta.get("palette", {}).get("max_colors", 24) or 24))
        meta.setdefault("palette", {})["colors"] = colors
        meta.setdefault("qa", {})["color_count"] = len(colors)
        meta["qa"]["alpha_ok"] = True
        meta.setdefault("versions", []).append({
            "path": PixelPartApplyService._rel(backup_path),
            "label": f"before {label}",
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        meta.setdefault("part_apply_history", []).append({
            "label": label,
            "variant_path": PixelPartApplyService._rel(variant_path),
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        save_json(meta_path, meta)
        return {"ok": True, "asset": meta, "accepted_variant": PixelPartApplyService._rel(variant_path)}

    @staticmethod
    def _render_variant(base_img: Image.Image, prompt: str, index: int, part_img: Image.Image | None) -> Image.Image:
        result = base_img.copy()
        w, h = result.size
        if part_img:
            overlay = part_img.resize((max(1, w // 2), max(1, h // 2)), Image.Resampling.NEAREST)
            result.alpha_composite(overlay, ((w - overlay.width) // 2, max(0, h // 4)))
            return result

        lower = prompt.lower()
        palette = [
            (92, 126, 190, 255),
            (190, 92, 92, 255),
            (224, 180, 64, 255),
            (82, 178, 108, 255),
            (160, 100, 210, 255),
            (64, 64, 72, 255),
        ]
        color = palette[index % len(palette)]
        if "gold" in lower:
            color = (224, 180, 64, 255)
        elif "blue" in lower:
            color = (64, 120, 220, 255)
        elif "red" in lower:
            color = (220, 70, 70, 255)
        elif "green" in lower:
            color = (70, 190, 100, 255)
        elif "black" in lower or "shadow" in lower:
            color = (36, 36, 44, 255)

        draw = ImageDraw.Draw(result)
        if any(word in lower for word in ["hat", "helm", "helmet", "hood"]):
            draw.rectangle([w // 4, h // 8, (w * 3) // 4, h // 3], fill=color)
        elif any(word in lower for word in ["weapon", "sword", "axe", "staff"]):
            x = min(w - 2, (w * 3) // 4 + index % 2)
            draw.line([(x, h // 4), (x, (h * 7) // 8)], fill=color, width=1)
            draw.rectangle([x - 1, h // 4, x + 1, h // 3], fill=color)
        else:
            draw.rectangle([w // 4, h // 3, (w * 3) // 4, (h * 2) // 3], fill=color)
            draw.rectangle([w // 3, h // 2, (w * 2) // 3, (h * 3) // 4], fill=tuple(max(0, c - 35) for c in color[:3]) + (255,))
        return result

    @staticmethod
    def _decode_optional_image(data_url: Any) -> Image.Image | None:
        if not isinstance(data_url, str) or "," not in data_url:
            return None
        _, encoded = data_url.split(",", 1)
        encoded += "=" * (-len(encoded) % 4)
        return Image.open(BytesIO(base64.b64decode(encoded))).convert("RGBA")

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
    def _recommendation(prompt: str, index: int) -> str:
        tone = ["closest fit", "bolder silhouette", "alternate colorway", "strong contrast", "subtle pass", "detail pass"]
        return f"{tone[index % len(tone)]} for {prompt or 'part'}"

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
