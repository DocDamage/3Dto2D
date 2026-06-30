import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "spriteforge_sprite"


def load_meta(sprite_dir: Path) -> Dict[str, Any]:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}. Run spriteforge.py video/pack first.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not (sprite_dir / meta.get("image", "sheet.png")).exists():
        raise FileNotFoundError(f"Missing spritesheet image in {sprite_dir}: {meta.get('image', 'sheet.png')}")
    return meta


def sheet_frames(meta: Dict[str, Any]) -> List[Dict[str, int]]:
    raw_frames = meta.get("frames", [])
    frames: List[Dict[str, int]] = []
    if isinstance(raw_frames, list):
        for idx, frame in enumerate(raw_frames):
            if not isinstance(frame, dict):
                continue
            frames.append({
                "index": int(frame.get("index", idx)),
                "x": int(frame.get("x", 0)),
                "y": int(frame.get("y", 0)),
                "w": int(frame.get("w", meta.get("frame_width", 0))),
                "h": int(frame.get("h", meta.get("frame_height", 0))),
            })
    if frames:
        return sorted(frames, key=lambda item: item["index"])

    fw = int(meta.get("frame_width", 0))
    fh = int(meta.get("frame_height", 0))
    cols = int(meta.get("columns", 1))
    count = int(meta.get("frame_count", cols * int(meta.get("rows", 1))))
    return [
        {"index": idx, "x": (idx % cols) * fw, "y": (idx // cols) * fh, "w": fw, "h": fh}
        for idx in range(max(0, count))
    ]


def copy_base_assets(sprite_dir: Path, dest: Path, meta: Dict[str, Any]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sprite_dir / meta.get("image", "sheet.png"), dest / "sheet.png")
    shutil.copy2(sprite_dir / "sheet.json", dest / "sheet.json")
    preview = sprite_dir / "preview.gif"
    if preview.exists():
        shutil.copy2(preview, dest / "preview.gif")


def _sprite_name(meta: Dict[str, Any], sprite_dir: Path, name: Optional[str], convention: str, clip_name: Optional[str]) -> str:
    action = meta.get("animation") or sprite_dir.name
    direction = meta.get("direction") or "right"
    character = name or "hero"
    if clip_name:
        return safe_name(clip_name.replace("[action]", action).replace("[direction]", direction).replace("[character]", character))
    if convention == "prefix":
        return safe_name(f"{character}_{action}_{direction}")
    if convention == "camel":
        return safe_name("".join(p.title() for p in f"{action}_{direction}".split("_") if p))
    return safe_name(name or action)


def export_unreal(
    sprite_dir: Path,
    output: Optional[Path] = None,
    project: Optional[Path] = None,
    name: Optional[str] = None,
    naming_convention: str = "default",
    pivot_mode: str = "bottom-center",
    ppu: int = 100,
    filter_mode: str = "nearest",
    loop_flag: bool = True,
    clip_name: Optional[str] = None,
    import_path: Optional[str] = None,
) -> Path:
    meta = load_meta(sprite_dir)
    sprite_name = _sprite_name(meta, sprite_dir, name, naming_convention, clip_name)
    dest = output or (project / "Content" / "SpriteForge" / sprite_name if project else sprite_dir / "unreal_export")
    copy_base_assets(sprite_dir, dest, meta)

    frames = sheet_frames(meta)
    destination = (import_path or f"/Game/SpriteForge/{sprite_name}").strip() or f"/Game/SpriteForge/{sprite_name}"
    if not destination.startswith("/Game/"):
        destination = "/Game/" + destination.strip("/")
    destination = destination.rstrip("/")
    texture_filter = "TF_NEAREST" if filter_mode == "nearest" else "TF_LINEAR"
    pivot_y = 0.5 if pivot_mode == "center" else 1.0
    helper_path = str(dest / "unreal_import_helper.py").replace("\\", "/")

    py_code = _unreal_helper_script(
        sprite_name=sprite_name,
        destination=destination,
        frames=frames,
        texture_filter=texture_filter,
        pivot_y=pivot_y,
        ppu=ppu,
        loop_flag=loop_flag,
    )
    (dest / "unreal_import_helper.py").write_text(py_code, encoding="utf-8")
    (dest / "UNREAL_IMPORT_NOTES.md").write_text(
        _unreal_notes(sprite_name, destination, frames, ppu, filter_mode, pivot_mode, loop_flag, helper_path),
        encoding="utf-8",
    )
    return dest


def _unreal_helper_script(
    sprite_name: str,
    destination: str,
    frames: List[Dict[str, int]],
    texture_filter: str,
    pivot_y: float,
    ppu: int,
    loop_flag: bool,
) -> str:
    frames_json = json.dumps(frames, indent=4)
    loop_bool = "True" if loop_flag else "False"
    return f'''# Unreal Engine 4/5 Editor Python script to import and slice SpriteForge spritesheet
import os
import json
import unreal

SPRITE_NAME = "{sprite_name}"
DESTINATION_PATH = "{destination}"
FRAMES = {frames_json}
PIVOT = unreal.Vector2D(0.5, {pivot_y})
PIXELS_PER_UNIT = {int(ppu)}
LOOP_ANIMATION = {loop_bool}

def import_and_slice():
    texture_path = os.path.join(os.path.dirname(__file__), "sheet.png")
    json_path = os.path.join(os.path.dirname(__file__), "sheet.json")
    if not os.path.exists(texture_path) or not os.path.exists(json_path):
        unreal.log_error("Could not find sheet.png or sheet.json in the script directory.")
        return
    with open(json_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    fps = meta.get("fps", 12.0)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    task = unreal.AssetImportTask()
    task.filename = os.path.abspath(texture_path)
    task.destination_path = DESTINATION_PATH
    task.destination_name = "T_" + SPRITE_NAME
    task.replace_existing = True
    task.automated = True
    task.save = True
    asset_tools.import_asset_tasks([task])
    texture = unreal.EditorAssetLibrary.load_asset(DESTINATION_PATH + "/T_" + SPRITE_NAME)
    if not texture:
        unreal.log_error("Failed to load imported texture.")
        return
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    texture.set_editor_property("filter", unreal.TextureFilter.{texture_filter})
    texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)
    factory = unreal.PaperSpriteFactory()
    sprites = []
    for i, frame in enumerate(FRAMES):
        sprite = asset_tools.create_asset(f"S_{{SPRITE_NAME}}_{{i:03d}}", DESTINATION_PATH, unreal.PaperSprite, factory)
        if sprite:
            sprite.set_source_texture(texture)
            sprite.set_source_rect_coordinates(frame["x"], frame["y"], frame["w"], frame["h"])
            sprite.set_editor_property("pixels_per_unreal_unit", PIXELS_PER_UNIT)
            sprite.set_editor_property("pivot_mode", unreal.SpritePivotMode.CUSTOM)
            sprite.set_editor_property("custom_pivot_point", PIVOT)
            unreal.EditorAssetLibrary.save_loaded_asset(sprite)
            sprites.append(sprite)
    if sprites:
        flipbook = asset_tools.create_asset("FB_" + SPRITE_NAME, DESTINATION_PATH, unreal.PaperFlipbook, unreal.PaperFlipbookFactory())
        if flipbook:
            flipbook.set_editor_property("frames_per_second", fps)
            for sprite in sprites:
                keyframe = unreal.PaperFlipbookKeyFrame()
                keyframe.set_editor_property("sprite", sprite)
                keyframe.set_editor_property("frame_run", 1)
                flipbook.add_key_frame(keyframe)
            flipbook.set_editor_property("looping", LOOP_ANIMATION)
            unreal.EditorAssetLibrary.save_loaded_asset(flipbook)
            unreal.log("Successfully created Paper2D Flipbook: FB_" + SPRITE_NAME)

if __name__ == "__main__":
    import_and_slice()
'''


def _unreal_notes(
    sprite_name: str,
    destination: str,
    frames: List[Dict[str, int]],
    ppu: int,
    filter_mode: str,
    pivot_mode: str,
    loop_flag: bool,
    helper_path: str,
) -> str:
    return f'''# Unreal Engine Import Notes

Generated files:
- `sheet.png`
- `sheet.json`
- `unreal_import_helper.py`

Steps inside Unreal Engine:

1. Enable the **Python Editor Script Plugin** and the **Paper2D Plugin** in Unreal Engine (`Edit > Plugins`).
2. Copy this folder into your Unreal Engine project's root folder or content directories.
3. Open Unreal Engine's Python Developer Console or the **Output Log** panel.
4. Run the helper Python script:
   ```text
   py "{helper_path}"
   ```
5. The script imports `sheet.png`, configures sprite-friendly filtering, slices frames from `sheet.json`, and creates a Paper2D Flipbook named `FB_{sprite_name}`.

Import settings:

```text
destination = {destination}
frames = {len(frames)}
pixels_per_unreal_unit = {ppu}
filter = {filter_mode}
pivot = {pivot_mode}
loop = {loop_flag}
```
'''
