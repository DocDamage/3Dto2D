#!/usr/bin/env python3
"""Direct Godot/Unity helper export for SpriteForge spritesheets.

v6 adds:
- Godot Sprite2D mode (grid-frame playback) and AnimatedSprite2D mode (runtime SpriteFrames from atlas regions)
- Unity editor helper that slices a sheet and can create an AnimationClip from the sliced sprites
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Dict, Optional


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


def unity_runtime_script(class_name: str, fps: float, frame_count: int, loop: bool = True) -> str:
    loop_str = "true" if loop else "false"
    return f'''using UnityEngine;

[RequireComponent(typeof(SpriteRenderer))]
public class {class_name} : MonoBehaviour
{{
    public Sprite[] frames;
    public float fps = {fps}f;
    public bool loop = {loop_str};

    private SpriteRenderer spriteRenderer;
    private float accum;
    private int index;

    void Awake()
    {{
        spriteRenderer = GetComponent<SpriteRenderer>();
        if (frames != null && frames.Length > 0)
            spriteRenderer.sprite = frames[0];
    }}

    void Update()
    {{
        if (frames == null || frames.Length <= 1 || fps <= 0f) return;
        accum += Time.deltaTime;
        float step = 1f / fps;
        while (accum >= step)
        {{
            accum -= step;
            index++;
            if (index >= frames.Length)
                index = loop ? 0 : frames.Length - 1;
            spriteRenderer.sprite = frames[index];
        }}
    }}
}}
'''


def unity_editor_importer(ppu: int = 100, filter_mode: str = "nearest", pivot_mode: str = "bottom-center", loop_flag: bool = True) -> str:
    filter_val = "FilterMode.Point" if filter_mode == "nearest" else "FilterMode.Bilinear"
    pivot_x = 0.5
    pivot_y = 0.5 if pivot_mode == "center" else 0.0
    alignment_val = "(int)SpriteAlignment.Center" if pivot_mode == "center" else "(int)SpriteAlignment.Custom"
    loop_bool_str = "true" if loop_flag else "false"
    
    return f'''#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class SpriteForgeSheetImporter
{{
    [MenuItem("Tools/SpriteForge/Slice Selected SpriteForge Sheet")]
    public static void SliceSelected()
    {{
        var texturePath = SelectedTexturePath();
        if (string.IsNullOrEmpty(texturePath)) return;
        var meta = LoadMeta(texturePath);
        if (meta == null) return;

        var importer = AssetImporter.GetAtPath(texturePath) as TextureImporter;
        if (importer == null)
        {{
            Debug.LogError("Selected asset is not a TextureImporter texture.");
            return;
        }}

        importer.textureType = TextureImporterType.Sprite;
        importer.spriteImportMode = SpriteImportMode.Multiple;
        importer.spritePixelsPerUnit = {ppu};
        importer.mipmapEnabled = false;
        importer.filterMode = {filter_val};
        importer.textureCompression = TextureImporterCompression.Uncompressed;

#pragma warning disable 0618
        var sprites = new List<SpriteMetaData>();
        for (int i = 0; i < meta.frame_count; i++)
        {{
            int col = i % meta.columns;
            int row = i / meta.columns;
            var smd = new SpriteMetaData();
            smd.name = meta.animation + "_" + i.ToString("0000");
            smd.rect = new Rect(col * meta.frame_width, (meta.rows - row - 1) * meta.frame_height, meta.frame_width, meta.frame_height);
            smd.pivot = new Vector2({pivot_x}f, {pivot_y}f);
            smd.alignment = {alignment_val};
            sprites.Add(smd);
        }}
        importer.spritesheet = sprites.ToArray();
#pragma warning restore 0618

        EditorUtility.SetDirty(importer);
        importer.SaveAndReimport();
        AssetDatabase.Refresh();
        Debug.Log("SpriteForge sheet sliced: " + texturePath);
    }}

    [MenuItem("Tools/SpriteForge/Create Animation Clip From Selected Sheet")]
    public static void CreateAnimationClipFromSelectedSheet()
    {{
        var texturePath = SelectedTexturePath();
        if (string.IsNullOrEmpty(texturePath)) return;
        var meta = LoadMeta(texturePath);
        if (meta == null) return;

        var sprites = AssetDatabase.LoadAllAssetRepresentationsAtPath(texturePath)
            .OfType<Sprite>()
            .OrderBy(s => s.name)
            .ToArray();
        if (sprites.Length == 0)
        {{
            Debug.LogError("No sliced sprites found. Run Slice Selected SpriteForge Sheet first.");
            return;
        }}

        var clip = new AnimationClip();
        clip.frameRate = Mathf.Max(1f, meta.fps);
        var binding = EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite");
        var keyframes = new ObjectReferenceKeyframe[sprites.Length];
        for (int i = 0; i < sprites.Length; i++)
        {{
            keyframes[i] = new ObjectReferenceKeyframe
            {{
                time = i / clip.frameRate,
                value = sprites[i]
            }};
        }}
        AnimationUtility.SetObjectReferenceCurve(clip, binding, keyframes);

        var settings = AnimationUtility.GetAnimationClipSettings(clip);
        settings.loopTime = {loop_bool_str};
        AnimationUtility.SetAnimationClipSettings(clip, settings);

        var clipPath = Path.Combine(Path.GetDirectoryName(texturePath), meta.animation + ".anim").Replace("\\", "/");
        AssetDatabase.CreateAsset(clip, AssetDatabase.GenerateUniqueAssetPath(clipPath));
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log("Created SpriteForge animation clip: " + clipPath);
    }}

    private static string SelectedTexturePath()
    {{
        var obj = Selection.activeObject;
        var texturePath = AssetDatabase.GetAssetPath(obj);
        if (string.IsNullOrEmpty(texturePath) || !texturePath.EndsWith(".png"))
        {{
            Debug.LogError("Select a SpriteForge sheet.png texture first.");
            return null;
        }}
        return texturePath;
    }}

    private static SpriteForgeMeta LoadMeta(string texturePath)
    {{
        var jsonPath = Path.Combine(Path.GetDirectoryName(texturePath), "sheet.json");
        if (!File.Exists(jsonPath))
        {{
            Debug.LogError("Could not find sheet.json next to the selected sheet.png.");
            return null;
        }}
        return JsonUtility.FromJson<SpriteForgeMeta>(File.ReadAllText(jsonPath));
    }}

    [System.Serializable]
    public class SpriteForgeMeta
    {{
        public string animation;
        public int frame_width;
        public int frame_height;
        public int frame_count;
        public float fps;
        public int columns;
        public int rows;
    }}
}}
#endif
'''


def export_unity(
    sprite_dir: Path, output: Optional[Path], project: Optional[Path], name: Optional[str],
    naming_convention: str = "default",
    pivot_mode: str = "bottom-center",
    ppu: int = 100,
    filter_mode: str = "nearest",
    loop_flag: bool = True,
    clip_name: Optional[str] = None
) -> Path:
    meta = load_meta(sprite_dir)
    sprite_name = safe_name(name or meta.get("animation") or sprite_dir.name)
    dest = output if output else (project / "Assets" / "SpriteForge" / sprite_name if project else sprite_dir / "unity_export")
    copy_base_assets(sprite_dir, dest, meta)

    runtime_class = safe_name(sprite_name.title().replace("_", "")) + "Animator"
    (dest / f"{runtime_class}.cs").write_text(unity_runtime_script(runtime_class, float(meta.get("fps", 12)), int(meta.get("frame_count", 1)), loop_flag), encoding="utf-8")
    editor_dir = dest / "Editor"
    editor_dir.mkdir(parents=True, exist_ok=True)
    (editor_dir / "SpriteForgeSheetImporter.cs").write_text(unity_editor_importer(ppu, filter_mode, pivot_mode, loop_flag), encoding="utf-8")

    notes = f'''# Unity import notes

Generated files:

- `sheet.png`
- `sheet.json`
- `{runtime_class}.cs`
- `Editor/SpriteForgeSheetImporter.cs`

Steps inside Unity:

1. Put this folder under your project's `Assets/` folder.
2. Select `sheet.png`.
3. Run `Tools > SpriteForge > Slice Selected SpriteForge Sheet`.
4. Run `Tools > SpriteForge > Create Animation Clip From Selected Sheet` if you want a `.anim` clip.
5. Or create a GameObject with a `SpriteRenderer`, add `{runtime_class}`, and assign the sliced frame sprites in order.

Sprite settings:

```text
columns = {meta.get('columns')}
rows = {meta.get('rows')}
frame_count = {meta.get('frame_count')}
fps = {meta.get('fps')}
cell = {meta.get('frame_width')}x{meta.get('frame_height')}
```
'''
    (dest / "UNITY_IMPORT_NOTES.md").write_text(notes, encoding="utf-8")
    return dest


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
) -> Path:
    meta_path = sprite_dir / "sheet.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sprite_name = name or safe_name(sprite_dir.name)
    
    if output:
        dest = output
    elif project:
        dest = project / "Content" / "SpriteForge" / sprite_name
    else:
        dest = sprite_dir / "unreal_export"
        
    dest.mkdir(parents=True, exist_ok=True)
    
    sheet_png = sprite_dir / meta.get("image", "sheet.png")
    if not sheet_png.exists():
        sheet_png = sprite_dir / "sheet.png"
    shutil.copy2(sheet_png, dest / "sheet.png")
    shutil.copy2(meta_path, dest / "sheet.json")
    
    py_code = f'''# Unreal Engine 4/5 Editor Python script to import and slice SpriteForge spritesheet
import os
import json
import unreal

def import_and_slice():
    texture_path = os.path.join(os.path.dirname(__file__), "sheet.png")
    json_path = os.path.join(os.path.dirname(__file__), "sheet.json")
    
    if not os.path.exists(texture_path) or not os.path.exists(json_path):
        unreal.log_error("Could not find sheet.png or sheet.json in the script directory.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
        
    sprite_name = "{sprite_name}"
    fps = meta.get("fps", 12.0)
    
    destination_path = "/Game/SpriteForge/" + sprite_name
    
    # 1. Import Texture
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    import_tasks = []
    
    task = unreal.AssetImportTask()
    task.filename = os.path.abspath(texture_path)
    task.destination_path = destination_path
    task.destination_name = "T_" + sprite_name
    task.replace_existing = True
    task.automated = True
    task.save = True
    
    import_tasks.append(task)
    asset_tools.import_asset_tasks(import_tasks)
    
    texture = unreal.EditorAssetLibrary.load_asset(destination_path + "/T_" + sprite_name)
    if not texture:
        unreal.log_error("Failed to load imported texture!")
        return
        
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    texture.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
    texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)
    
    # 2. Slice Sprites using PaperSpriteFactory
    factory = unreal.PaperSpriteFactory()
    sprites = []
    
    frames = sorted(meta.get("frames", []), key=lambda f: f.get("index", 0))
    for i, frame in enumerate(frames):
        sprite_asset_name = f"S_{{sprite_name}}_{{i:03d}}"
        
        sprite = asset_tools.create_asset(sprite_asset_name, destination_path, unreal.PaperSprite, factory)
        if sprite:
            sprite.set_source_texture(texture)
            sprite.set_source_rect_coordinates(frame["x"], frame["y"], frame["w"], frame["h"])
            unreal.EditorAssetLibrary.save_loaded_asset(sprite)
            sprites.append(sprite)
            
    # 3. Create Flipbook using PaperFlipbookFactory
    if sprites:
        flipbook_factory = unreal.PaperFlipbookFactory()
        flipbook_name = f"FB_{{sprite_name}}"
        flipbook = asset_tools.create_asset(flipbook_name, destination_path, unreal.PaperFlipbook, flipbook_factory)
        if flipbook:
            flipbook.set_editor_property("frames_per_second", fps)
            for sprite in sprites:
                keyframe = unreal.PaperFlipbookKeyFrame()
                keyframe.set_editor_property("sprite", sprite)
                keyframe.set_editor_property("frame_run", 1)
                flipbook.add_key_frame(keyframe)
            unreal.EditorAssetLibrary.save_loaded_asset(flipbook)
            unreal.log(f"Successfully created Paper2D Flipbook: {{flipbook_name}}")

if __name__ == "__main__":
    import_and_slice()
'''
    (dest / "unreal_import_helper.py").write_text(py_code, encoding="utf-8")
    
    helper_path_str = str(dest / "unreal_import_helper.py").replace("\\", "/")
    notes = f'''# Unreal Engine Import Notes

Generated files:
- `sheet.png`
- `sheet.json`
- `unreal_import_helper.py`

Steps inside Unreal Engine:

1. Enable the **Python Editor Script Plugin** and the **Paper2D Plugin** in Unreal Engine (`Edit > Plugins`).
2. Copy this folder into your Unreal Engine project's root folder or content directories.
3. Open Unreal Engine's Python Developer Console or the **Output Log** panel.
4. Run the helper Python script using Unreal's script execution mechanism:
   ```text
   py "{helper_path_str}"
   ```
5. The script will automatically import `sheet.png` into `/Game/SpriteForge/{sprite_name}/`, configure it with Pixel/Nearest point filtering, slice the texture into individual PaperSprite assets based on `sheet.json`, and compile them into a Paper2D Flipbook named `FB_{sprite_name}` ready to use in your Paper2D game!
'''

    (dest / "UNREAL_IMPORT_NOTES.md").write_text(notes, encoding="utf-8")
    return dest


def cmd_export(args: argparse.Namespace) -> None:
    sprite_dir = Path(args.sprite_dir).resolve()
    output = Path(args.output).resolve() if args.output else None
    project = Path(args.project).resolve() if args.project else None
    loop_bool = getattr(args, "loop_flag", "true").lower() == "true"
    
    if args.engine == "godot":
        dest = export_godot(
            sprite_dir, output, project, args.name, args.res_path, args.godot_mode,
            naming_convention=getattr(args, "naming_convention", "default"),
            pivot_mode=getattr(args, "pivot_mode", "bottom-center"),
            ppu=getattr(args, "ppu", 100),
            filter_mode=getattr(args, "filter_mode", "nearest"),
            loop_flag=loop_bool,
            clip_name=getattr(args, "clip_name", None)
        )
    elif args.engine == "unity":
        dest = export_unity(
            sprite_dir, output, project, args.name,
            naming_convention=getattr(args, "naming_convention", "default"),
            pivot_mode=getattr(args, "pivot_mode", "bottom-center"),
            ppu=getattr(args, "ppu", 100),
            filter_mode=getattr(args, "filter_mode", "nearest"),
            loop_flag=loop_bool,
            clip_name=getattr(args, "clip_name", None)
        )
    else:
        dest = export_unreal(
            sprite_dir, output, project, args.name,
            naming_convention=getattr(args, "naming_convention", "default"),
            pivot_mode=getattr(args, "pivot_mode", "bottom-center"),
            ppu=getattr(args, "ppu", 100),
            filter_mode=getattr(args, "filter_mode", "nearest"),
            loop_flag=loop_bool,
            clip_name=getattr(args, "clip_name", None)
        )
    print(f"Exported {args.engine} helper files: {dest}")
    
    try:
        from services.plugin_manager import PluginManager
        PluginManager.trigger_hook("on_export_engine", sprite_dir=sprite_dir, engine=args.engine, dest=dest)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Validate export
# ---------------------------------------------------------------------------

def _check(label: str, ok: bool, detail: str = "") -> Dict:
    status = "PASS" if ok else "FAIL"
    msg = f"[{status}] {label}" + (f": {detail}" if detail else "")
    print(msg)
    return {"label": label, "ok": ok, "detail": detail}


def validate_export(
    sprite_dir: Path,
    engine: Optional[str] = None,
    release_zip: Optional[Path] = None,
    return_dict: bool = False,
) -> bool | Dict[str, Any]:
    """Validate Godot/Unity export files for a sprite output directory.

    Returns True if all checks pass, False otherwise.
    Prints a structured pass/fail table to stdout.
    """
    import zipfile
    results = []
    all_ok = True

    # --- 1. sheet.json exists and parses ---
    meta_path = sprite_dir / "sheet.json"
    r = _check("sheet.json exists", meta_path.exists())
    results.append(r)
    if not r["ok"]:
        all_ok = False
        if return_dict:
            return {"ok": False, "results": results}
        print(f"\nResult: FAIL ({sum(1 for r in results if r['ok'])}/{len(results)} passed)")
        return False

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        r = _check("sheet.json parseable", True)
    except Exception as exc:
        r = _check("sheet.json parseable", False, str(exc))
        all_ok = False
        results.append(r)
        if return_dict:
            return {"ok": False, "results": results}
        print(f"\nResult: FAIL ({sum(1 for r in results if r['ok'])}/{len(results)} passed)")
        return False
    results.append(r)

    # --- 2. sheet.png exists ---
    sheet_img = sprite_dir / meta.get("image", "sheet.png")
    if not sheet_img.exists():
        sheet_img = sprite_dir / "sheet.png"
    r = _check("sheet.png exists", sheet_img.exists(), str(sheet_img))
    results.append(r)
    if not r["ok"]:
        all_ok = False

    # --- 3. Pixel dimensions match metadata ---
    if sheet_img.exists():
        try:
            from PIL import Image as _Img
            with _Img.open(sheet_img) as im:
                img_w, img_h = im.size
            fw = int(meta.get("frame_width", 0))
            fh = int(meta.get("frame_height", 0))
            cols = int(meta.get("columns", 1))
            rows = int(meta.get("rows", 1))
            expected_w = fw * cols
            expected_h = fh * rows
            dim_ok = (img_w == expected_w and img_h == expected_h)
            r = _check(
                "Sheet pixel dimensions match metadata",
                dim_ok,
                f"image={img_w}x{img_h} expected={expected_w}x{expected_h} (fw={fw} fh={fh} cols={cols} rows={rows})",
            )
            results.append(r)
            if not dim_ok:
                all_ok = False

            # --- 4. Frame count matches grid ---
            fc_meta = int(meta.get("frame_count", 0))
            fc_grid = cols * rows
            # frame_count must be <= grid cells
            fc_ok = 0 < fc_meta <= fc_grid
            r = _check(
                "frame_count consistent with grid",
                fc_ok,
                f"frame_count={fc_meta} grid_cells={fc_grid}",
            )
            results.append(r)
            if not fc_ok:
                all_ok = False
        except Exception as exc:
            r = _check("Sheet image validation", False, str(exc))
            results.append(r)
            all_ok = False

    # --- 5. Engine-specific file checks ---
    if engine == "godot":
        gd_files = list(sprite_dir.glob("*.gd")) + list(sprite_dir.glob("godot_export/*.gd"))
        r = _check("Godot .gd script present", bool(gd_files),
                   f"found: {[f.name for f in gd_files]}" if gd_files else "no .gd file found")
        results.append(r)
        if not r["ok"]:
            all_ok = False

        tscn_files = list(sprite_dir.glob("*.tscn")) + list(sprite_dir.glob("godot_export/*.tscn"))
        r = _check("Godot .tscn scene present", bool(tscn_files),
                   f"found: {[f.name for f in tscn_files]}" if tscn_files else "no .tscn scene found")
        results.append(r)
        if not r["ok"]:
            all_ok = False

        if tscn_files:
            tscn_text = tscn_files[0].read_text(encoding="utf-8", errors="replace")
            # 5a. Check columns/rows in tscn
            expected_hf = str(meta.get("columns", 1))
            expected_vf = str(meta.get("rows", 1))
            hf_ok = f"hframes = {expected_hf}" in tscn_text
            vf_ok = f"vframes = {expected_vf}" in tscn_text
            r = _check("Godot scene hframes match columns", hf_ok, f"expected hframes={expected_hf}")
            results.append(r)
            if not hf_ok:
                all_ok = False
            r = _check("Godot scene vframes match rows", vf_ok, f"expected vframes={expected_vf}")
            results.append(r)
            if not vf_ok:
                all_ok = False

            # 5b. Validate Godot pivots/centered
            has_centered = "centered = true" in tscn_text
            has_offset = "offset = Vector2(" in tscn_text
            pivot_ok = has_centered or has_offset or "centered = false" in tscn_text
            r = _check("Godot pivot configuration present", pivot_ok)
            results.append(r)
            if not pivot_ok:
                all_ok = False

            # 5c. Validate Godot loop flags
            has_loop = "loop = true" in tscn_text or "loop = false" in tscn_text or "autoplay = &" in tscn_text
            r = _check("Godot animation loop config present", has_loop)
            results.append(r)
            if not has_loop:
                all_ok = False

            # 5d. Validate Godot filter mode
            has_filter = "texture_filter = 1" in tscn_text or "texture_filter = 2" in tscn_text
            r = _check("Godot texture filter mode set", has_filter)
            results.append(r)
            if not has_filter:
                all_ok = False

    elif engine == "unity":
        cs_files = list(sprite_dir.glob("*.cs")) + list(sprite_dir.glob("unity_export/*.cs"))
        r = _check("Unity .cs script present", bool(cs_files),
                   f"found: {[f.name for f in cs_files]}" if cs_files else "no .cs file found")
        results.append(r)
        if not r["ok"]:
            all_ok = False

        if cs_files:
            cs_text = "".join(f.read_text(encoding="utf-8", errors="replace") for f in cs_files)
            # Validate Unity pivots/PPU
            has_ppu = "ppu" in cs_text.lower() or "pixelsperunit" in cs_text.lower() or "100" in cs_text
            r = _check("Unity PPU configuration present", has_ppu)
            results.append(r)
            if not has_ppu:
                all_ok = False

            has_filter = "filtermode" in cs_text.lower() or "nearest" in cs_text.lower() or "point" in cs_text.lower()
            r = _check("Unity texture filter mode present", has_filter)
            results.append(r)
            if not has_filter:
                all_ok = False

            has_pivot = "spritealignment" in cs_text.lower() or "pivot" in cs_text.lower() or "custom" in cs_text.lower()
            r = _check("Unity pivot configuration present", has_pivot)
            results.append(r)
            if not has_pivot:
                all_ok = False

    elif engine == "unreal":
        py_files = list(sprite_dir.glob("*.py")) + list(sprite_dir.glob("unreal_export/*.py"))
        py_helper_present = any("unreal_import_helper.py" in f.name for f in py_files)
        r = _check("Unreal Python helper present", py_helper_present,
                   f"found: {[f.name for f in py_files]}" if py_files else "no .py file found")
        results.append(r)
        if not r["ok"]:
            all_ok = False

        notes_files = list(sprite_dir.glob("*.md")) + list(sprite_dir.glob("unreal_export/*.md"))
        notes_present = any("UNREAL_IMPORT_NOTES.md" in f.name for f in notes_files)
        r = _check("Unreal import notes present", notes_present,
                   f"found: {[f.name for f in notes_files]}" if notes_files else "no .md notes found")
        results.append(r)
        if not r["ok"]:
            all_ok = False

        if py_helper_present:
            helper_file = next(f for f in py_files if "unreal_import_helper.py" in f.name)
            py_text = helper_file.read_text(encoding="utf-8", errors="replace")
            
            has_import = "import_and_slice" in py_text
            r = _check("Unreal helper contains import logic", has_import)
            results.append(r)
            if not has_import:
                all_ok = False
                
            has_paper = "PaperSpriteFactory" in py_text or "PaperFlipbookFactory" in py_text
            r = _check("Unreal helper contains Paper2D factory references", has_paper)
            results.append(r)
            if not has_paper:
                all_ok = False

    # --- 6. Release zip checks ---
    if release_zip and Path(release_zip).exists():
        import zipfile as _zf
        try:
            with _zf.ZipFile(release_zip, "r") as zf:
                names = set(zf.namelist())
            has_sheet = any("sheet.png" in n for n in names)
            has_json = any("sheet.json" in n for n in names)
            r = _check("Release zip contains sheet.png", has_sheet)
            results.append(r)
            if not has_sheet:
                all_ok = False
            r = _check("Release zip contains sheet.json", has_json)
            results.append(r)
            if not has_json:
                all_ok = False
        except Exception as exc:
            r = _check("Release zip readable", False, str(exc))
            results.append(r)
            all_ok = False
    elif release_zip:
        r = _check("Release zip exists", False, str(release_zip))
        results.append(r)
        all_ok = False

    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    status_str = "PASS" if all_ok else "FAIL"
    print(f"\nResult: {status_str} ({passed}/{total} checks passed)")
    if return_dict:
        return {"ok": all_ok, "results": results}
    return all_ok


def cmd_validate(args: argparse.Namespace) -> None:
    sprite_dir = Path(args.sprite_dir).resolve()
    engine = args.engine or None
    release_zip = Path(args.release_zip).resolve() if args.release_zip else None
    ok = validate_export(sprite_dir, engine=engine, release_zip=release_zip)
    if not ok:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export SpriteForge sheets to Godot/Unity helper files")
    s = p.add_subparsers(dest="command", required=True)
    e = s.add_parser("export")
    e.add_argument("--sprite-dir", required=True, help="Folder containing sheet.png and sheet.json")
    e.add_argument("--engine", required=True, choices=["godot", "unity", "unreal"])
    e.add_argument("--output", default=None, help="Output folder. Defaults inside the project or sprite_dir.")
    e.add_argument("--project", default=None, help="Godot or Unity project root")
    e.add_argument("--name", default=None)
    e.add_argument("--res-path", default=None, help="Godot res:// folder path, for example res://assets/sprites/hero_walk")
    e.add_argument("--godot-mode", choices=["sprite2d", "animatedsprite2d"], default="animatedsprite2d")
    e.add_argument("--naming-convention", default="default")
    e.add_argument("--pivot-mode", default="bottom-center")
    e.add_argument("--ppu", type=int, default=100)
    e.add_argument("--filter-mode", default="nearest")
    e.add_argument("--loop-flag", default="true")
    e.add_argument("--import-path", default=None)
    e.add_argument("--clip-name", default=None)
    e.set_defaults(func=cmd_export)
    v = s.add_parser("validate", help="Validate export files for correctness")
    v.add_argument("--sprite-dir", required=True, help="Sprite output folder")
    v.add_argument("--engine", default=None, choices=["godot", "unity", "unreal"], help="Engine to check engine-specific files")
    v.add_argument("--release-zip", default=None, help="Release zip to check for completeness")
    v.set_defaults(func=cmd_validate)
    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
