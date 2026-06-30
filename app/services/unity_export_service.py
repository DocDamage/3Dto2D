from __future__ import annotations
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from services.godot_export_service import load_meta, copy_base_assets, safe_name

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
