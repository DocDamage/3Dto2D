from __future__ import annotations
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "spriteforge_sprite"

def load_meta(sprite_dir: Path) -> Dict:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}. Run spriteforge.py video/pack first.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not (sprite_dir / meta.get("image", "sheet.png")).exists():
        raise FileNotFoundError(f"Missing spritesheet image in {sprite_dir}: {meta.get('image', 'sheet.png')}")
    return meta

def copy_base_assets(sprite_dir: Path, dest: Path, meta: Dict) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    image = sprite_dir / meta.get("image", "sheet.png")
    shutil.copy2(image, dest / "sheet.png")
    shutil.copy2(sprite_dir / "sheet.json", dest / "sheet.json")
    preview = sprite_dir / "preview.gif"
    if preview.exists():
        shutil.copy2(preview, dest / "preview.gif")
    return dest / "sheet.png"

def godot_res_path(project: Optional[Path], dest: Path, res_path: Optional[str], sprite_name: str, filename: str = "sheet.png") -> str:
    if res_path:
        base = res_path.rstrip("/")
        if not base.startswith("res://"):
            base = "res://" + base.strip("/")
        return base + "/" + filename
    if project:
        try:
            rel = dest.relative_to(project).as_posix()
            return "res://" + rel + "/" + filename
        except ValueError:
            pass
    return f"res://assets/sprites/{sprite_name}/{filename}"

def godot_sprite2d_script(fps: float, frame_count: int, cols: int, rows: int, loop: bool = True) -> str:
    loop_str = "true" if loop else "false"
    return f'''extends Sprite2D

@export var fps: float = {fps}
@export var frame_count: int = {frame_count}
@export var loop: bool = {loop_str}

var _accum: float = 0.0

func _ready() -> void:
    hframes = {cols}
    vframes = {rows}
    frame = 0

func _process(delta: float) -> void:
    if fps <= 0.0 or frame_count <= 1:
        return
    _accum += delta
    var step := 1.0 / fps
    while _accum >= step:
        _accum -= step
        var next_frame := frame + 1
        if next_frame >= frame_count:
            next_frame = 0 if loop else frame_count - 1
        frame = next_frame
'''

def godot_animatedsprite2d_script(tex_path: str, fps: float, frame_count: int, frame_width: int, frame_height: int, cols: int, rows: int, loop: bool = True, anim_name: str = "default") -> str:
    loop_str = "true" if loop else "false"
    return f'''extends AnimatedSprite2D

@export var fps: float = {fps}
@export var loop: bool = {loop_str}

const FRAME_COUNT := {frame_count}
const FRAME_WIDTH := {frame_width}
const FRAME_HEIGHT := {frame_height}
const COLUMNS := {cols}
const ROWS := {rows}
const SHEET := preload("{tex_path}")

func _ready() -> void:
    var sf := SpriteFrames.new()
    var anim := &"{anim_name}"
    if not sf.has_animation(anim):
        sf.add_animation(anim)
    sf.set_animation_speed(anim, fps)
    sf.set_animation_loop(anim, loop)
    for i in range(FRAME_COUNT):
        var col := i % COLUMNS
        var row := int(i / COLUMNS)
        var at := AtlasTexture.new()
        at.atlas = SHEET
        at.region = Rect2(col * FRAME_WIDTH, row * FRAME_HEIGHT, FRAME_WIDTH, FRAME_HEIGHT)
        sf.add_frame(anim, at)
    sprite_frames = sf
    animation = anim
    play(anim)
'''

def export_godot(
    sprite_dir: Path, output: Optional[Path], project: Optional[Path], name: Optional[str], res_path: Optional[str], mode: str,
    naming_convention: str = "default",
    pivot_mode: str = "bottom-center",
    ppu: int = 100,
    filter_mode: str = "nearest",
    loop_flag: bool = True,
    clip_name: Optional[str] = None
) -> Path:
    meta = load_meta(sprite_dir)
    sprite_name = safe_name(name or meta.get("animation") or sprite_dir.name)
    dest = output if output else (project / "assets" / "sprites" / sprite_name if project else sprite_dir / "godot_export")
    copy_base_assets(sprite_dir, dest, meta)

    tex_path = godot_res_path(project, dest, res_path, sprite_name, "sheet.png")
    script_name = f"{sprite_name}_{mode}_player.gd"
    scene_name = f"{sprite_name}.tscn"
    fps = float(meta.get("fps", 12))
    frame_count = int(meta.get("frame_count", 1))
    cols = int(meta.get("columns", 1))
    rows = int(meta.get("rows", 1))
    fw = int(meta.get("frame_width", 0))
    fh = int(meta.get("frame_height", 0))
    folder_path = tex_path.rsplit("/", 1)[0]
    script_res_path = f"{folder_path}/{script_name}"

    # Determine animation clip name
    action_str = meta.get("animation") or sprite_dir.name
    direction_str = meta.get("direction") or "right"
    char_str = name or "hero"
    if clip_name:
        anim_name = clip_name.replace("[action]", action_str).replace("[direction]", direction_str).replace("[character]", char_str)
    elif naming_convention == "prefix":
        anim_name = f"{char_str}_{action_str}_{direction_str}"
    elif naming_convention == "camel":
        parts = [p.title() for p in f"{action_str}_{direction_str}".split("_") if p]
        anim_name = "".join(parts)
    else:
        anim_name = f"{action_str}_{direction_str}"
    anim_name = safe_name(anim_name)

    if mode == "animatedsprite2d":
        script = godot_animatedsprite2d_script(tex_path, fps, frame_count, fw, fh, cols, rows, loop_flag, anim_name)
        node_type = "AnimatedSprite2D"
        node_extra = f"autoplay = &\"{anim_name}\"\n"
    else:
        script = godot_sprite2d_script(fps, frame_count, cols, rows, loop_flag)
        node_type = "Sprite2D"
        node_extra = f"texture = ExtResource(\"1_texture\")\nhframes = {cols}\nvframes = {rows}\n"
        if pivot_mode == "bottom-center":
            node_extra += f"centered = true\noffset = Vector2(0, {-fh // 2})\n"
        elif pivot_mode == "center":
            node_extra += f"centered = true\noffset = Vector2(0, 0)\n"
        else:
            node_extra += f"centered = false\n"
        loop_val = "true" if loop_flag else "false"
        node_extra += f"fps = {fps}\nframe_count = {frame_count}\nloop = {loop_val}\n"

    # Add texture filter setting for Godot 4
    filter_val = "1" if filter_mode == "nearest" else "2"
    node_extra += f"texture_filter = {filter_val}\n"

    (dest / script_name).write_text(script, encoding="utf-8")

    if mode == "animatedsprite2d":
        tscn = f'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="{script_res_path}" id="1_script"]

[node name="{sprite_name}" type="{node_type}"]
script = ExtResource("1_script")
{node_extra}'''
    else:
        tscn = f'''[gd_scene load_steps=3 format=3]

[ext_resource type="Texture2D" path="{tex_path}" id="1_texture"]
[ext_resource type="Script" path="{script_res_path}" id="2_script"]

[node name="{sprite_name}" type="{node_type}"]
script = ExtResource("2_script")
{node_extra}'''
    (dest / scene_name).write_text(tscn, encoding="utf-8")

    notes = f'''# Godot import notes

Generated files:

- `sheet.png`
- `sheet.json`
- `{script_name}`
- `{scene_name}`

Godot mode:

```text
{mode}
```

Expected texture path:

```text
{tex_path}
```

Sprite settings:

```text
columns = {cols}
rows = {rows}
frame_count = {frame_count}
fps = {fps}
cell = {fw}x{fh}
```

`animatedsprite2d` mode builds a `SpriteFrames` resource at runtime from atlas regions.
`sprite2d` mode uses `hframes`, `vframes`, and manual frame stepping.
'''
    (dest / "GODOT_IMPORT_NOTES.md").write_text(notes, encoding="utf-8")
    return dest
