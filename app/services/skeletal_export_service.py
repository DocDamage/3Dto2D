from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image


def _safe_name(value: str, fallback: str = "sprite") -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text[:80] or fallback


def _alpha_bounds(img: Image.Image) -> Tuple[int, int, int, int]:
    alpha = np.asarray(img.convert("RGBA").getchannel("A"))
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0 or len(ys) == 0:
        return (0, 0, img.width, img.height)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _part_sources(sprite_dir: Path, meta: Dict[str, Any]) -> List[Path]:
    parts = sorted(path for path in sprite_dir.glob("sheet_*.png") if path.name != "sheet_normal.png")
    if parts:
        return parts
    image_name = str(meta.get("image") or "sheet.png")
    return [sprite_dir / image_name]


def _segmentation_provenance(sprite_dir: Path, sources: List[Path]) -> Dict[str, Any]:
    segmented = [path for path in sources if path.stem.startswith("sheet_")]
    source = "segmented_layers" if segmented else "fallback_full_sheet"
    part_dirs = sorted(path.name for path in sprite_dir.glob("part_*") if path.is_dir())
    return {
        "source": source,
        "method": "sam2_or_grabcut_layer_sheets" if segmented else "alpha_body_fallback",
        "part_sheet_count": len(segmented),
        "part_directories": part_dirs,
        "notes": "SpriteForge uses sheet_<part>.png layers when SAM2/GrabCut segmentation has produced them; otherwise it exports the full sheet as a single body part.",
    }


def _part_name(path: Path) -> str:
    if path.stem.startswith("sheet_"):
        return _safe_name(path.stem[len("sheet_"):], "part")
    return "body"


def _engine_import_contract(
    export_name: str,
    frame_width: int,
    frame_height: int,
    frame_count: int,
    columns: int,
    part_metadata: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "texture_filter": "nearest",
        "coordinate_space": {
            "origin": "top-left frame pixels",
            "y_axis": "down",
            "pivot_mode": "alpha-bottom-center",
        },
        "animation": {
            "name": export_name,
            "frame_count": frame_count,
            "columns": columns,
            "frame_size": {"width": frame_width, "height": frame_height},
        },
        "spine": {
            "json": "spine.json",
            "atlas_required": False,
            "skin": "default",
            "slot_order": [part["name"] for part in part_metadata],
        },
        "dragonbones": {
            "json": "dragonbones.json",
            "armature": export_name,
            "slot_order": [part["name"] for part in part_metadata],
        },
        "parts": [
            {
                "name": part["name"],
                "path": f"parts/{Path(str(part['output'])).name}",
                "pivot": part["pivot"],
                "bounds": part["bounds"],
            }
            for part in part_metadata
        ],
    }


def export_skeletal_parts(sprite_dir: Path, output_dir: Path | None = None, name: str = "") -> Dict[str, Any]:
    sprite_dir = sprite_dir.resolve()
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing sheet.json in {sprite_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frame_width = int(meta.get("frame_width") or meta.get("cell_width") or 1)
    frame_height = int(meta.get("frame_height") or meta.get("cell_height") or 1)
    frame_count = int(meta.get("frame_count") or 1)
    columns = max(1, int(meta.get("columns") or 1))
    export_name = _safe_name(name or str(meta.get("animation") or sprite_dir.name), "sprite")
    out = (output_dir or (sprite_dir / "skeletal_export")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    parts_dir = out / "parts"
    parts_dir.mkdir(exist_ok=True)

    slots: List[Dict[str, Any]] = []
    bones: List[Dict[str, Any]] = [{"name": "root", "parent": "", "x": 0, "y": 0}]
    part_metadata: List[Dict[str, Any]] = []
    skins: Dict[str, Any] = {"default": {}}
    animations: Dict[str, Any] = {str(meta.get("animation") or "idle"): {"frames": frame_count, "fps": meta.get("fps", 12)}}
    sources = _part_sources(sprite_dir, meta)
    segmentation = _segmentation_provenance(sprite_dir, sources)

    for source in sources:
        if not source.exists():
            continue
        part = _part_name(source)
        sheet = Image.open(source).convert("RGBA")
        first_frame = sheet.crop((0, 0, min(frame_width, sheet.width), min(frame_height, sheet.height)))
        bounds = _alpha_bounds(first_frame)
        frame_bounds = []
        for frame_index in range(frame_count):
            col = frame_index % columns
            row = frame_index // columns
            x0 = col * frame_width
            y0 = row * frame_height
            frame = sheet.crop((x0, y0, min(x0 + frame_width, sheet.width), min(y0 + frame_height, sheet.height)))
            fb = _alpha_bounds(frame)
            frame_bounds.append({
                "frame": frame_index,
                "x": fb[0],
                "y": fb[1],
                "w": fb[2] - fb[0],
                "h": fb[3] - fb[1],
            })
        pivot_x = (bounds[0] + bounds[2]) / 2.0
        pivot_y = float(bounds[3])
        pivot = {
            "x": round(pivot_x, 2),
            "y": round(pivot_y, 2),
            "normalized_x": round(pivot_x / max(1, frame_width), 4),
            "normalized_y": round(pivot_y / max(1, frame_height), 4),
            "mode": "alpha-bottom-center",
        }
        dest = parts_dir / source.name
        sheet.save(dest)
        bones.append({"name": part, "parent": "root", "x": pivot["x"], "y": pivot["y"]})
        slots.append({"name": part, "bone": part, "attachment": part})
        part_metadata.append({
            "name": part,
            "source": str(source),
            "output": str(dest),
            "bounds": {
                "x": bounds[0],
                "y": bounds[1],
                "w": bounds[2] - bounds[0],
                "h": bounds[3] - bounds[1],
            },
            "pivot": pivot,
            "frame_bounds": frame_bounds,
            "segmentation_source": segmentation["source"],
        })
        skins["default"][part] = {
            part: {
                "path": f"parts/{source.name}",
                "x": round(frame_width / 2 - pivot_x, 2),
                "y": round(frame_height - pivot_y, 2),
                "width": frame_width,
                "height": frame_height,
                "frame_count": frame_count,
                "columns": columns,
            }
        }

    spine = {
        "skeleton": {"hash": export_name, "spine": "spriteforge-json", "width": frame_width, "height": frame_height},
        "bones": bones,
        "slots": slots,
        "skins": skins,
        "animations": animations,
    }
    dragonbones = {
        "name": export_name,
        "version": "5.5",
        "frameRate": int(meta.get("fps") or 12),
        "armature": [{
            "name": export_name,
            "bone": [
                {
                    "name": bone["name"],
                    "parent": bone.get("parent", ""),
                    "transform": {
                        "x": bone.get("x", 0),
                        "y": bone.get("y", 0),
                    },
                }
                for bone in bones
            ],
            "slot": [{"name": slot["name"], "parent": slot["bone"], "displayIndex": 0} for slot in slots],
            "skin": [{"slot": [{"name": slot["name"], "display": [{"name": slot["attachment"], "path": skins["default"][slot["name"]][slot["attachment"]]["path"]}]} for slot in slots]}],
            "animation": [{"name": next(iter(animations.keys())), "duration": frame_count}],
        }],
    }
    manifest = {
        "ok": True,
        "schema": "spriteforge_skeletal_export_v1",
        "name": export_name,
        "source": str(sprite_dir),
        "parts": [slot["name"] for slot in slots],
        "segmentation": segmentation,
        "part_metadata": part_metadata,
        "engine_import": _engine_import_contract(export_name, frame_width, frame_height, frame_count, columns, part_metadata),
        "frame_width": frame_width,
        "frame_height": frame_height,
        "frame_count": frame_count,
        "spine_json": str(out / "spine.json"),
        "dragonbones_json": str(out / "dragonbones.json"),
        "skeletal_manifest": str(out / "skeletal_manifest.json"),
    }
    (out / "spine.json").write_text(json.dumps(spine, indent=2), encoding="utf-8")
    (out / "dragonbones.json").write_text(json.dumps(dragonbones, indent=2), encoding="utf-8")
    (out / "skeletal_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
