#!/usr/bin/env python3
"""Build multi-animation atlases from multiple SpriteForge output folders."""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image


def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "anim"


def load_sprite_dir(sprite_dir: Path) -> Tuple[Dict[str, Any], List[Image.Image]]:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sheet_path = sprite_dir / meta.get("image", "sheet.png")
    if not sheet_path.exists():
        raise FileNotFoundError(f"Missing {sheet_path}")
    sheet = Image.open(sheet_path).convert("RGBA")
    fw = int(meta["frame_width"])
    fh = int(meta["frame_height"])
    count = int(meta["frame_count"])
    cols = int(meta.get("columns", max(1, sheet.width // fw)))
    frames = []
    for i in range(count):
        x = (i % cols) * fw
        y = (i // cols) * fh
        frames.append(sheet.crop((x, y, x + fw, y + fh)))
    return meta, frames


def paste_center_fit(src: Image.Image, cell_size: Tuple[int, int]) -> Image.Image:
    src = src.convert("RGBA")
    cell_w, cell_h = cell_size
    canvas = Image.new("RGBA", cell_size, (0, 0, 0, 0))
    scale = min(cell_w / max(1, src.width), cell_h / max(1, src.height))
    nw = max(1, int(round(src.width * scale)))
    nh = max(1, int(round(src.height * scale)))
    res = src.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.alpha_composite(res, ((cell_w - nw) // 2, (cell_h - nh) // 2))
    return canvas


def build_atlas(sprite_dirs: Sequence[Path], output: Path, columns: Optional[int] = None, cell_size: Optional[Tuple[int, int]] = None, name: str = "spriteforge_atlas") -> Path:
    output.mkdir(parents=True, exist_ok=True)
    animations: Dict[str, Any] = {}
    all_frames: List[Tuple[str, int, Image.Image, Dict[str, Any]]] = []

    loaded = []
    for sd in sprite_dirs:
        sd = sd.resolve()
        meta, frames = load_sprite_dir(sd)
        anim = safe_name(str(meta.get("animation") or sd.name.replace("_sprite", "")))
        base = anim
        idx = 2
        while anim in animations:
            anim = f"{base}_{idx}"
            idx += 1
        loaded.append((sd, anim, meta, frames))

    if not loaded:
        raise RuntimeError("No sprite directories supplied.")
    if cell_size is None:
        fw = max(int(meta["frame_width"]) for _sd, _anim, meta, _frames in loaded)
        fh = max(int(meta["frame_height"]) for _sd, _anim, meta, _frames in loaded)
        cell_size = (fw, fh)
    cell_w, cell_h = cell_size

    for sd, anim, meta, frames in loaded:
        start = len(all_frames)
        for i, frame in enumerate(frames):
            all_frames.append((anim, i, paste_center_fit(frame, cell_size), meta))
        animations[anim] = {
            "name": anim,
            "source_dir": str(sd),
            "start_index": start,
            "frame_count": len(frames),
            "fps": meta.get("fps", 12),
            "loop": True,
        }

    total = len(all_frames)
    if columns is None:
        columns = max(1, math.ceil(math.sqrt(total)))
    rows = math.ceil(total / columns)
    atlas = Image.new("RGBA", (columns * cell_w, rows * cell_h), (0, 0, 0, 0))
    frames_meta = []
    for global_i, (anim, local_i, frame, meta) in enumerate(all_frames):
        x = (global_i % columns) * cell_w
        y = (global_i // columns) * cell_h
        atlas.alpha_composite(frame, (x, y))
        frames_meta.append({
            "index": global_i,
            "animation": anim,
            "local_index": local_i,
            "x": x,
            "y": y,
            "w": cell_w,
            "h": cell_h,
            "duration_ms": int(round(1000 / float(meta.get("fps", 12)))) if float(meta.get("fps", 12)) > 0 else 83,
        })

    atlas_path = output / "atlas.png"
    atlas.save(atlas_path)
    manifest = {
        "name": safe_name(name),
        "image": "atlas.png",
        "frame_width": cell_w,
        "frame_height": cell_h,
        "frame_count": total,
        "columns": columns,
        "rows": rows,
        "animations": animations,
        "frames": frames_meta,
    }
    (output / "atlas.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_godot_atlas_player(output, manifest)
    write_unity_atlas_player(output, manifest)
    write_html(output, manifest)
    print(f"Atlas: {atlas_path}")
    print(f"Manifest: {output / 'atlas.json'}")
    return output


def write_godot_atlas_player(output: Path, manifest: Dict[str, Any]) -> None:
    gd = '''extends Sprite2D

@export var atlas_json_path: String = "res://atlas.json"
@export var animation_name: String = "idle"
@export var autoplay: bool = true

var _data: Dictionary = {}
var _anim: Dictionary = {}
var _accum: float = 0.0
var _local_frame: int = 0

func _ready() -> void:
    region_enabled = true
    texture = preload("res://atlas.png")
    var file := FileAccess.open(atlas_json_path, FileAccess.READ)
    if file:
        _data = JSON.parse_string(file.get_as_text())
    set_animation(animation_name)

func set_animation(name: String) -> void:
    animation_name = name
    _local_frame = 0
    if _data.has("animations") and _data["animations"].has(name):
        _anim = _data["animations"][name]
        _apply_frame()

func _process(delta: float) -> void:
    if not autoplay or _anim.is_empty():
        return
    var fps := float(_anim.get("fps", 12.0))
    if fps <= 0.0:
        return
    _accum += delta
    var step := 1.0 / fps
    while _accum >= step:
        _accum -= step
        _local_frame = (_local_frame + 1) % int(_anim.get("frame_count", 1))
        _apply_frame()

func _apply_frame() -> void:
    var idx := int(_anim.get("start_index", 0)) + _local_frame
    var frame := _data["frames"][idx]
    region_rect = Rect2(frame["x"], frame["y"], frame["w"], frame["h"])
    offset = Vector2(0, -frame["h"] / 2.0)
'''
    (output / "GodotAtlasPlayer.gd").write_text(gd, encoding="utf-8")


def write_unity_atlas_player(output: Path, manifest: Dict[str, Any]) -> None:
    cs = '''using System.Collections.Generic;
using UnityEngine;

[RequireComponent(typeof(SpriteRenderer))]
public class SpriteForgeAtlasPlayer : MonoBehaviour
{
    public Texture2D atlasTexture;
    public TextAsset atlasJson;
    public string animationName = "idle";
    public float pixelsPerUnit = 100f;
    public bool loop = true;

    private SpriteRenderer sr;
    private AtlasData data;
    private Dictionary<string, AnimationData> anims;
    private int localFrame;
    private float accum;

    void Awake()
    {
        sr = GetComponent<SpriteRenderer>();
        if (atlasJson != null)
        {
            data = JsonUtility.FromJson<AtlasData>(atlasJson.text);
            anims = new Dictionary<string, AnimationData>();
            foreach (var a in data.animations) anims[a.name] = a;
            SetAnimation(animationName);
        }
    }

    public void SetAnimation(string name)
    {
        animationName = name;
        localFrame = 0;
        accum = 0f;
        ApplyFrame();
    }

    void Update()
    {
        if (data == null || anims == null || !anims.ContainsKey(animationName)) return;
        var a = anims[animationName];
        if (a.fps <= 0f) return;
        accum += Time.deltaTime;
        float step = 1f / a.fps;
        while (accum >= step)
        {
            accum -= step;
            localFrame++;
            if (localFrame >= a.frame_count) localFrame = loop ? 0 : a.frame_count - 1;
            ApplyFrame();
        }
    }

    void ApplyFrame()
    {
        if (atlasTexture == null || data == null || anims == null || !anims.ContainsKey(animationName)) return;
        var a = anims[animationName];
        var f = data.frames[a.start_index + localFrame];
        // Unity Rect origin is bottom-left; SpriteForge atlas JSON is top-left.
        var rect = new Rect(f.x, atlasTexture.height - f.y - f.h, f.w, f.h);
        sr.sprite = Sprite.Create(atlasTexture, rect, new Vector2(0.5f, 0f), pixelsPerUnit, 0, SpriteMeshType.FullRect);
    }

    [System.Serializable] public class AtlasData { public FrameData[] frames; public AnimationData[] animations; }
    [System.Serializable] public class FrameData { public int x, y, w, h; }
    [System.Serializable] public class AnimationData { public string name; public int start_index; public int frame_count; public float fps; }
}
'''
    # JsonUtility does not deserialize dictionaries, so also write a Unity-friendly flattened copy.
    unity_manifest = dict(manifest)
    unity_manifest["animations"] = list(manifest["animations"].values())
    (output / "atlas_unity.json").write_text(json.dumps(unity_manifest, indent=2), encoding="utf-8")
    (output / "SpriteForgeAtlasPlayer.cs").write_text(cs, encoding="utf-8")


def write_html(output: Path, manifest: Dict[str, Any]) -> None:
    anim_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v['frame_count']}</td><td>{v.get('fps')}</td><td>{v['start_index']}</td></tr>"
        for k, v in manifest["animations"].items()
    )
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>SpriteForge Atlas</title>
<style>body{{font-family:system-ui,Segoe UI,Arial;background:#151515;color:#eee;margin:24px}} table{{border-collapse:collapse}}td,th{{border:1px solid #444;padding:6px 10px}}img{{max-width:100%;background:#333}}</style>
</head><body><h1>SpriteForge Atlas</h1>
<p>Frames: {manifest['frame_count']} | Cell: {manifest['frame_width']}x{manifest['frame_height']} | Grid: {manifest['columns']}x{manifest['rows']}</p>
<table><tr><th>Animation</th><th>Frames</th><th>FPS</th><th>Start</th></tr>{anim_rows}</table>
<p><img src="atlas.png"></p>
<p>Files: <code>atlas.png</code>, <code>atlas.json</code>, <code>atlas_unity.json</code>, <code>GodotAtlasPlayer.gd</code>, <code>SpriteForgeAtlasPlayer.cs</code></p>
</body></html>"""
    (output / "atlas_report.html").write_text(doc, encoding="utf-8")


def parse_size(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if not value:
        return None
    a, b = value.lower().split("x", 1)
    return int(a), int(b)


def discover_sprite_dirs(root: Path) -> List[Path]:
    return sorted({p.parent for p in root.rglob("sheet.json")})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a multi-animation SpriteForge atlas")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("atlas")
    s.add_argument("--sprites", nargs="*", default=[], help="SpriteForge output folders containing sheet.json")
    s.add_argument("--root", default=None, help="Discover all sheet.json files under this root if --sprites is omitted")
    s.add_argument("--output", required=True)
    s.add_argument("--columns", type=int, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--name", default="spriteforge_atlas")
    def _run(a):
        sprites = [Path(x) for x in a.sprites]
        if not sprites and a.root:
            sprites = discover_sprite_dirs(Path(a.root))
        build_atlas(sprites, Path(a.output), a.columns, parse_size(a.cell_size), a.name)
    s.set_defaults(func=_run)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
