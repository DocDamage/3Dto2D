import shutil
from pathlib import Path
from typing import Dict, Any, Optional

class ExportService:
    @staticmethod
    def safe_name(name: str) -> str:
        from spriteforge_utils import safe_name as _safe_name
        return _safe_name(name)

    @staticmethod
    def godot_sprite2d_script(fps: float, frame_count: int, cols: int, rows: int) -> str:
        return f'''extends Sprite2D

@export var fps: float = {fps}
@export var frame_count: int = {frame_count}
@export var loop: bool = true

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

    @staticmethod
    def godot_animatedsprite2d_script(tex_path: str, fps: float, frame_count: int, frame_width: int, frame_height: int, cols: int, rows: int) -> str:
        return f'''extends AnimatedSprite2D

@export var fps: float = {fps}
@export var loop: bool = true

const FRAME_COUNT := {frame_count}
const FRAME_WIDTH := {frame_width}
const FRAME_HEIGHT := {frame_height}
const COLUMNS := {cols}
const ROWS := {rows}
const SHEET := preload("{tex_path}")

func _ready() -> void:
    var sf := SpriteFrames.new()
    var anim := &"default"
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

    @staticmethod
    def export_godot(sprite_dir: Path, dest: Path, meta: Dict[str, Any], project_root: Optional[Path], res_path: Optional[str], mode: str) -> Path:
        dest.mkdir(parents=True, exist_ok=True)
        sprite_name = ExportService.safe_name(meta.get("animation") or sprite_dir.name)

        # Copy base files
        shutil.copy2(sprite_dir / meta.get("image", "sheet.png"), dest / "sheet.png")
        shutil.copy2(sprite_dir / "sheet.json", dest / "sheet.json")
        if (sprite_dir / "preview.gif").exists():
            shutil.copy2(sprite_dir / "preview.gif", dest / "preview.gif")

        # Resolve Godot paths
        if res_path:
            base = res_path.rstrip("/")
            if not base.startswith("res://"):
                base = "res://" + base.strip("/")
            tex_path = base + "/sheet.png"
        elif project_root:
            try:
                rel = dest.relative_to(project_root).as_posix()
                tex_path = "res://" + rel + "/sheet.png"
            except ValueError:
                tex_path = f"res://assets/sprites/{sprite_name}/sheet.png"
        else:
            tex_path = f"res://assets/sprites/{sprite_name}/sheet.png"

        script_name = f"{sprite_name}_{mode}_player.gd"
        scene_name = f"{sprite_name}.tscn"
        fps = float(meta.get("fps", 12))
        frame_count = int(meta.get("frame_count", 1))
        cols = int(meta.get("columns", 1))
        rows = int(meta.get("rows", 1))
        fw = int(meta.get("frame_width", 512))
        fh = int(meta.get("frame_height", 512))

        folder_path = tex_path.rsplit("/", 1)[0]
        script_res_path = f"{folder_path}/{script_name}"

        if mode == "animatedsprite2d":
            script = ExportService.godot_animatedsprite2d_script(tex_path, fps, frame_count, fw, fh, cols, rows)
            node_type = "AnimatedSprite2D"
            node_extra = 'autoplay = &"default"\n'
            tscn = f'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="{script_res_path}" id="1_script"]

[node name="{sprite_name}" type="{node_type}"]
script = ExtResource("1_script")
{node_extra}'''
        else:
            script = ExportService.godot_sprite2d_script(fps, frame_count, cols, rows)
            node_type = "Sprite2D"
            node_extra = f'texture = ExtResource("1_texture")\nhframes = {cols}\nvframes = {rows}\ncentered = true\nfps = {fps}\nframe_count = {frame_count}\nloop = true\n'
            tscn = f'''[gd_scene load_steps=3 format=3]

[ext_resource type="Texture2D" path="{tex_path}" id="1_texture"]
[ext_resource type="Script" path="{script_res_path}" id="2_script"]

[node name="{sprite_name}" type="{node_type}"]
script = ExtResource("2_script")
{node_extra}'''

        (dest / script_name).write_text(script, encoding="utf-8")
        (dest / scene_name).write_text(tscn, encoding="utf-8")

        notes = f'''# Godot import notes
Expected texture path: {tex_path}
Expected script path: {script_res_path}
Columns: {cols}
Rows: {rows}
Frame count: {frame_count}
'''
        (dest / "GODOT_IMPORT_NOTES.md").write_text(notes, encoding="utf-8")
        return dest
