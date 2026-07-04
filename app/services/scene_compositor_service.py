from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _safe_name(value: str, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_. -]+", "_", str(value or "").strip())
    return text[:80] or fallback


def _safe_sprite_dir(root: Path, value: str) -> Path:
    rel = str(value or "").replace("\\", "/").strip("/")
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Sprite path must stay inside the SpriteForge workspace.") from exc
    if not candidate.is_dir() or not (candidate / "sheet.json").is_file():
        raise ValueError(f"Sprite output not found: {value}")
    return candidate


def _rel_url(root: Path, path: Path) -> str:
    return "/file/" + path.resolve().relative_to(root.resolve()).as_posix()


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _color(value: Any, default: str = "#1b1f2a") -> str:
    text = str(value or "").strip()
    if re.match(r"^#[0-9A-Fa-f]{6}$", text):
        return text.upper()
    return default


def _snap(value: float, grid: int) -> float:
    if grid <= 1:
        return value
    return round(value / grid) * grid


def _godot_scene_text(manifest: Dict[str, Any]) -> str:
    lines = [
        '[gd_scene format=3]',
        '',
        '[node name="' + manifest["scene"]["name"] + '" type="Node2D"]',
    ]
    for idx, layer in enumerate(manifest["layers"]):
        node_name = re.sub(r"[^A-Za-z0-9_]+", "_", layer["name"]) or f"Layer{idx + 1}"
        lines.extend([
            '',
            f'[node name="{node_name}" type="AnimatedSprite2D" parent="."]',
            f'position = Vector2({float(layer["x"]):.2f}, {float(layer["y"]):.2f})',
            f'scale = Vector2({float(layer["scale"]):.3f}, {float(layer["scale"]):.3f})',
            f'z_index = {int(layer["z"])}',
            f'modulate = Color(1, 1, 1, {float(layer["opacity"]):.3f})',
            f'; SpriteFrames source: {layer["sprite_path"]}/sheet.json',
        ])
    return "\n".join(lines) + "\n"


def _composite_animation_plan(root: Path, manifest: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    fps = int(manifest["scene"]["fps"])
    frame_count = max([int(layer.get("frame_count") or 1) for layer in manifest["layers"]] or [1])
    duration_seconds = round(frame_count / max(1, fps), 3)
    gif_path = out_dir / "composite.gif"
    webm_path = out_dir / "composite.webm"
    return {
        "schema": "spriteforge.scene_composite_exports.v1",
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration_seconds,
        "gif_path": gif_path.relative_to(root.resolve()).as_posix(),
        "gif_url": _rel_url(root, gif_path),
        "webm_path": webm_path.relative_to(root.resolve()).as_posix(),
        "webm_url": _rel_url(root, webm_path),
        "render_status": "planned",
        "layers": [
            {
                "name": layer["name"],
                "sprite_path": layer["sprite_path"],
                "animation": layer["animation"],
                "fps": layer["fps"],
                "frame_count": layer["frame_count"],
            }
            for layer in manifest["layers"]
        ],
    }


def _scene_handoff(root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    dependencies = []
    for layer in manifest["layers"]:
        sprite_path = root / str(layer["sprite_path"])
        dependencies.append({
            "name": layer["name"],
            "sprite_path": layer["sprite_path"],
            "sheet_json": (sprite_path / "sheet.json").relative_to(root.resolve()).as_posix(),
            "sheet_image_url": layer["sheet_url"],
            "frame_size": {"width": layer["frame_width"], "height": layer["frame_height"]},
            "frame_count": layer["frame_count"],
            "fps": layer["fps"],
        })
    return {
        "schema": "spriteforge.scene_handoff.v1",
        "engine_import": {
            "godot_scene": "Use exported .tscn as a layout scaffold; attach SpriteFrames from each layer sheet.json.",
            "texture_filter": "nearest",
            "coordinate_space": "Node2D pixels, origin at top-left of scene canvas.",
            "camera": manifest["scene"]["camera"],
        },
        "dependencies": dependencies,
        "validation": {
            "layer_count": len(manifest["layers"]),
            "unique_sprite_paths": len({layer["sprite_path"] for layer in manifest["layers"]}),
            "background_type": manifest["scene"]["background"]["type"],
        },
    }


def _write_exports(root: Path, manifest: Dict[str, Any], output_dir_value: str) -> Dict[str, str]:
    name = _safe_name(manifest["scene"]["name"], "scene")
    output_rel = str(output_dir_value or f"output/scenes/{name}").replace("\\", "/").strip("/")
    out_dir = (root / output_rel).resolve()
    try:
        out_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Scene export path must stay inside the SpriteForge workspace.") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "scene_manifest.json"
    godot_path = out_dir / f"{name}.tscn"
    export_manifest = dict(manifest)
    animation_exports = _composite_animation_plan(root, manifest, out_dir)
    export_manifest["exports"] = {"animation_exports": animation_exports}
    manifest_path.write_text(json.dumps(export_manifest, indent=2), encoding="utf-8")
    godot_path.write_text(_godot_scene_text(manifest), encoding="utf-8")
    return {
        "manifest_path": manifest_path.relative_to(root.resolve()).as_posix(),
        "manifest_url": _rel_url(root, manifest_path),
        "godot_scene_path": godot_path.relative_to(root.resolve()).as_posix(),
        "godot_scene_url": _rel_url(root, godot_path),
        "animation_exports": animation_exports,
    }


def build_scene_manifest(root: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    width = max(64, min(4096, _int(payload.get("width"), 640)))
    height = max(64, min(4096, _int(payload.get("height"), 360)))
    fps = max(1, min(60, _int(payload.get("fps"), 12)))
    grid_size = max(1, min(256, _int(payload.get("grid_size"), 16)))
    snap_to_grid = bool(payload.get("snap_to_grid", False))
    layers_in = payload.get("layers") if isinstance(payload.get("layers"), list) else []
    if not layers_in:
        raise ValueError("At least one scene layer is required.")

    layers: List[Dict[str, Any]] = []
    for idx, raw in enumerate(layers_in):
        if not isinstance(raw, dict):
            continue
        sprite_dir = _safe_sprite_dir(root, str(raw.get("sprite_path") or ""))
        meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
        image = str(meta.get("image") or "sheet.png")
        sheet_path = sprite_dir / image
        if not sheet_path.is_file():
            raise ValueError(f"Missing sprite sheet image for {raw.get('sprite_path')}")
        raw_x = _float(raw.get("x"), width / 2)
        raw_y = _float(raw.get("y"), height / 2)
        layers.append({
            "name": _safe_name(raw.get("name"), f"Layer {idx + 1}"),
            "sprite_path": sprite_dir.relative_to(root.resolve()).as_posix(),
            "sheet_url": _rel_url(root, sheet_path),
            "x": _snap(raw_x, grid_size) if snap_to_grid else raw_x,
            "y": _snap(raw_y, grid_size) if snap_to_grid else raw_y,
            "z": max(-1024, min(1024, _int(raw.get("z"), idx))),
            "scale": max(0.1, min(8.0, _float(raw.get("scale"), 1.0))),
            "opacity": max(0.0, min(1.0, _float(raw.get("opacity"), 1.0))),
            "frame_width": _int(meta.get("frame_width"), 1),
            "frame_height": _int(meta.get("frame_height"), 1),
            "frame_count": _int(meta.get("frame_count"), 1),
            "columns": _int(meta.get("columns"), 1),
            "rows": _int(meta.get("rows"), 1),
            "fps": _int(meta.get("fps"), fps),
            "animation": str(meta.get("animation") or sprite_dir.name),
        })
    if not layers:
        raise ValueError("No valid scene layers were provided.")
    layers.sort(key=lambda layer: (int(layer["z"]), float(layer["y"]), layer["name"]))
    manifest = {
        "ok": True,
        "scene": {
            "name": _safe_name(payload.get("name"), "scene"),
            "width": width,
            "height": height,
            "fps": fps,
            "grid_size": grid_size,
            "snap_to_grid": snap_to_grid,
            "camera": {
                "x": _float(payload.get("camera_x"), width / 2),
                "y": _float(payload.get("camera_y"), height / 2),
                "zoom": max(0.1, min(8.0, _float(payload.get("camera_zoom"), 1.0))),
            },
            "background": {
                "type": str(payload.get("background_type") or "color"),
                "color": _color(payload.get("background_color")),
                "image": str(payload.get("background_image") or "").replace("\\", "/"),
            },
        },
        "layers": layers,
    }
    manifest["handoff"] = _scene_handoff(root, manifest)
    if payload.get("write_exports"):
        manifest["exports"] = _write_exports(root, manifest, str(payload.get("output_dir") or ""))
    return manifest
