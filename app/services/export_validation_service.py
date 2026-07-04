from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional

def _check(label: str, ok: bool, detail: str = "") -> Dict:
    status = "PASS" if ok else "FAIL"
    msg = f"[{status}] {label}" + (f": {detail}" if detail else "")
    print(msg)
    return {"label": label, "ok": ok, "detail": detail}


def _restricted_zip_members(names: set[str]) -> list[str]:
    blocked_parts = {"vendor", "models", "node_modules", "venv", ".venv", "comfyui", "logs", "uploads", "uploaded_videos", "__pycache__"}
    blocked_suffixes = {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".log"}
    blocked_names = {".env", "app.log"}
    violations: list[str] = []
    for name in sorted(names):
        parts = [part.lower() for part in name.replace("\\", "/").split("/") if part]
        filename = parts[-1] if parts else ""
        if filename in blocked_names or any(part in blocked_parts for part in parts) or any(filename.endswith(suffix) for suffix in blocked_suffixes):
            violations.append(name)
    return violations


def _validate_sidecar_manifest(path: Path, sprite_dir: Path, expected_frame_count: int) -> list[Dict]:
    results = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [_check(f"{path.name} parseable", False, str(exc))]

    schema = str(manifest.get("schema") or "")
    schema_ok = schema.startswith("spriteforge.") and schema.endswith(".v1")
    results.append(_check(f"{path.name} schema present", schema_ok, schema or "missing schema"))

    file_name = str(manifest.get("file") or "").strip()
    asset_ok = bool(file_name) and ((path.parent / file_name).exists() or (sprite_dir / file_name).exists())
    results.append(_check(f"{path.name} referenced asset exists", asset_ok, file_name or "missing file"))

    manifest_frame_count = manifest.get("frame_count")
    if manifest_frame_count is not None:
        frame_ok = int(manifest_frame_count) == expected_frame_count
        results.append(_check(
            f"{path.name} frame_count matches sheet",
            frame_ok,
            f"manifest={manifest_frame_count} sheet={expected_frame_count}",
        ))

    engine_ready = manifest.get("engine_ready")
    if engine_ready is not None:
        ready_ok = isinstance(engine_ready, dict) and bool(engine_ready.get("godot") or engine_ready.get("web"))
        results.append(_check(f"{path.name} engine_ready target present", ready_ok))
    if schema == "spriteforge.lighting_preview.v1":
        lighting_maps = manifest.get("lighting_maps") if isinstance(manifest.get("lighting_maps"), dict) else {}
        rendering = manifest.get("rendering") if isinstance(manifest.get("rendering"), dict) else {}
        maps_ok = lighting_maps.get("schema") == "spriteforge.lighting_maps.v1" and lighting_maps.get("server_bake") in {"normal_specular_ao", "radial_fallback"}
        render_ok = rendering.get("schema") == "spriteforge.lighting_preview_render.v1" and rendering.get("texture_filter") == "nearest"
        results.append(_check(f"{path.name} lighting maps contract valid", maps_ok))
        results.append(_check(f"{path.name} lighting render contract valid", render_ok))
    return results


def _validate_audio_cues_manifest(path: Path, sprite_dir: Path, expected_frame_count: int, fps: float) -> list[Dict]:
    results = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [_check("audio_cues.json parseable", False, str(exc))]

    schema_ok = manifest.get("schema") == "spriteforge_audio_cues.v1"
    results.append(_check("audio_cues.json schema valid", schema_ok, str(manifest.get("schema") or "missing")))

    engine_import = manifest.get("engine_import") if isinstance(manifest.get("engine_import"), dict) else {}
    sync_ok = engine_import.get("sync") == "frame_index" and bool(engine_import.get("godot") or engine_import.get("unity"))
    results.append(_check("audio_cues.json engine sync metadata present", sync_ok))

    cues = manifest.get("cues") if isinstance(manifest.get("cues"), list) else []
    frame_range_ok = True
    timing_ok = True
    asset_ok = True
    safe_fps = max(1.0, float(fps or 12))
    for cue in cues:
        if not isinstance(cue, dict):
            frame_range_ok = False
            timing_ok = False
            asset_ok = False
            continue
        try:
            frame_index = int(cue.get("frame_index"))
        except (TypeError, ValueError):
            frame_range_ok = False
            timing_ok = False
            continue
        if frame_index < 0 or frame_index >= expected_frame_count:
            frame_range_ok = False
        expected_time = round(frame_index / safe_fps, 4)
        try:
            cue_time = round(float(cue.get("time_seconds")), 4)
        except (TypeError, ValueError):
            timing_ok = False
        else:
            if cue_time != expected_time:
                timing_ok = False
        audio_path = str(cue.get("audio_path") or "").strip()
        if not audio_path or not (sprite_dir / audio_path).exists():
            asset_ok = False

    results.append(_check("audio_cues.json cue frames in range", frame_range_ok, f"frame_count={expected_frame_count}"))
    results.append(_check("audio_cues.json cue timing matches fps", timing_ok, f"fps={safe_fps:g}"))
    results.append(_check("audio_cues.json referenced audio exists", asset_ok))
    return results


def _validate_tilemap_manifest(path: Path, sprite_dir: Path) -> list[Dict]:
    results = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [_check(f"{path.name} parseable", False, str(exc))]

    engine_manifest = manifest.get("engine_manifest") if isinstance(manifest.get("engine_manifest"), dict) else manifest
    schema_ok = engine_manifest.get("schema") == "spriteforge.tilemap_engine_manifest.v1"
    results.append(_check(f"{path.name} tilemap engine schema valid", schema_ok, str(engine_manifest.get("schema") or "missing")))

    image_name = str(engine_manifest.get("image") or "").strip()
    image_path = path.parent / image_name if image_name else path.with_suffix(".png")
    image_ok = image_path.exists() and image_path.is_file()
    results.append(_check(f"{path.name} tilemap image exists", image_ok, image_name or image_path.name))

    try:
        tile_width = int(engine_manifest.get("tile_width"))
        tile_height = int(engine_manifest.get("tile_height"))
        columns = int(engine_manifest.get("columns"))
        rows = int(engine_manifest.get("rows"))
        tile_count = int(engine_manifest.get("tile_count"))
    except (TypeError, ValueError):
        tile_width = tile_height = columns = rows = tile_count = 0
    dimensions_ok = tile_width > 0 and tile_height > 0 and columns > 0 and rows > 0 and tile_count == columns * rows
    results.append(_check(f"{path.name} tile dimensions consistent", dimensions_ok, f"{columns}x{rows} tiles={tile_count}"))

    tiles = engine_manifest.get("tiles") if isinstance(engine_manifest.get("tiles"), list) else []
    tiles_ok = len(tiles) == tile_count and all(isinstance(tile, dict) and "rect" in tile for tile in tiles)
    results.append(_check(f"{path.name} tile index table complete", tiles_ok, f"tiles={len(tiles)} expected={tile_count}"))

    import_block = engine_manifest.get("import") if isinstance(engine_manifest.get("import"), dict) else {}
    import_ok = all(key in import_block for key in ("godot", "rpg_maker", "tiled"))
    results.append(_check(f"{path.name} tilemap engine import targets present", import_ok))

    if image_ok and dimensions_ok:
        try:
            from PIL import Image as _Img
            with _Img.open(image_path) as image:
                expected_size = (tile_width * columns, tile_height * rows)
                size_ok = image.size == expected_size
            results.append(_check(f"{path.name} tilemap image dimensions match", size_ok, f"image={image.size} expected={expected_size}"))
        except Exception as exc:
            results.append(_check(f"{path.name} tilemap image validation", False, str(exc)))
    return results


def _validate_skeletal_manifest(path: Path) -> list[Dict]:
    results = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [_check("skeletal_manifest.json parseable", False, str(exc))]

    schema_ok = manifest.get("schema") == "spriteforge_skeletal_export_v1"
    results.append(_check("skeletal_manifest.json schema valid", schema_ok, str(manifest.get("schema") or "missing")))

    engine_import = manifest.get("engine_import") if isinstance(manifest.get("engine_import"), dict) else {}
    contract_ok = (
        engine_import.get("texture_filter") == "nearest"
        and isinstance(engine_import.get("coordinate_space"), dict)
        and engine_import.get("coordinate_space", {}).get("pivot_mode") == "alpha-bottom-center"
    )
    results.append(_check("skeletal_manifest.json engine import contract valid", contract_ok))

    spine_name = str(engine_import.get("spine", {}).get("json") or "spine.json")
    dragonbones_name = str(engine_import.get("dragonbones", {}).get("json") or "dragonbones.json")
    spine_path = path.parent / spine_name
    dragonbones_path = path.parent / dragonbones_name
    results.append(_check("skeletal spine.json exists", spine_path.exists(), spine_name))
    results.append(_check("skeletal dragonbones.json exists", dragonbones_path.exists(), dragonbones_name))

    parts = engine_import.get("parts") if isinstance(engine_import.get("parts"), list) else []
    parts_ok = bool(parts)
    for part in parts:
        if not isinstance(part, dict):
            parts_ok = False
            continue
        rel = str(part.get("path") or "").strip()
        pivot = part.get("pivot") if isinstance(part.get("pivot"), dict) else {}
        bounds = part.get("bounds") if isinstance(part.get("bounds"), dict) else {}
        if not rel or not (path.parent / rel).exists():
            parts_ok = False
        if pivot.get("mode") != "alpha-bottom-center":
            parts_ok = False
        if int(bounds.get("w", 0) or 0) <= 0 or int(bounds.get("h", 0) or 0) <= 0:
            parts_ok = False
    results.append(_check("skeletal part sheets and pivots valid", parts_ok, f"parts={len(parts)}"))

    if spine_path.exists():
        try:
            spine = json.loads(spine_path.read_text(encoding="utf-8"))
            slot_names = [slot.get("name") for slot in spine.get("slots", []) if isinstance(slot, dict)]
            expected = engine_import.get("spine", {}).get("slot_order") or []
            results.append(_check("skeletal spine slot order matches manifest", slot_names == expected, f"spine={slot_names} expected={expected}"))
        except Exception as exc:
            results.append(_check("skeletal spine.json parseable", False, str(exc)))
    if dragonbones_path.exists():
        try:
            dragonbones = json.loads(dragonbones_path.read_text(encoding="utf-8"))
            armatures = dragonbones.get("armature") if isinstance(dragonbones.get("armature"), list) else []
            armature_name = armatures[0].get("name") if armatures and isinstance(armatures[0], dict) else ""
            expected_armature = engine_import.get("dragonbones", {}).get("armature")
            results.append(_check("skeletal dragonbones armature matches manifest", armature_name == expected_armature, f"dragonbones={armature_name} expected={expected_armature}"))
        except Exception as exc:
            results.append(_check("skeletal dragonbones.json parseable", False, str(exc)))
    return results


def _validate_scene_manifest(path: Path) -> list[Dict]:
    results = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [_check("scene_manifest.json parseable", False, str(exc))]

    handoff = manifest.get("handoff") if isinstance(manifest.get("handoff"), dict) else {}
    schema_ok = handoff.get("schema") == "spriteforge.scene_handoff.v1"
    results.append(_check("scene_manifest.json scene handoff schema valid", schema_ok, str(handoff.get("schema") or "missing")))

    engine_import = handoff.get("engine_import") if isinstance(handoff.get("engine_import"), dict) else {}
    engine_ok = engine_import.get("texture_filter") == "nearest" and "camera" in engine_import and "coordinate_space" in engine_import
    results.append(_check("scene_manifest.json engine import metadata valid", engine_ok))

    dependencies = handoff.get("dependencies") if isinstance(handoff.get("dependencies"), list) else []
    deps_ok = bool(dependencies)
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            deps_ok = False
            continue
        rel_sheet = str(dependency.get("sheet_json") or "").strip()
        if not rel_sheet or not any((parent / rel_sheet).exists() for parent in [path.parent, *path.parents]):
            deps_ok = False
        frame_size = dependency.get("frame_size") if isinstance(dependency.get("frame_size"), dict) else {}
        if int(frame_size.get("width", 0) or 0) <= 0 or int(frame_size.get("height", 0) or 0) <= 0:
            deps_ok = False
        if int(dependency.get("frame_count", 0) or 0) <= 0:
            deps_ok = False
    results.append(_check("scene_manifest.json dependencies valid", deps_ok, f"dependencies={len(dependencies)}"))

    validation = handoff.get("validation") if isinstance(handoff.get("validation"), dict) else {}
    layers = manifest.get("layers") if isinstance(manifest.get("layers"), list) else []
    layer_count_ok = int(validation.get("layer_count", -1)) == len(layers)
    results.append(_check("scene_manifest.json layer count matches", layer_count_ok, f"handoff={validation.get('layer_count')} layers={len(layers)}"))

    scene_name = str(manifest.get("scene", {}).get("name") or path.parent.name)
    godot_scene = path.parent / f"{scene_name}.tscn"
    godot_ok = godot_scene.exists() and "AnimatedSprite2D" in godot_scene.read_text(encoding="utf-8", errors="replace")
    results.append(_check("scene_manifest.json Godot scaffold exists", godot_ok, godot_scene.name))

    exports = manifest.get("exports") if isinstance(manifest.get("exports"), dict) else {}
    animation_exports = exports.get("animation_exports") if isinstance(exports.get("animation_exports"), dict) else {}
    planned_ok = animation_exports.get("schema") == "spriteforge.scene_composite_exports.v1" and animation_exports.get("render_status") in {"planned", "rendered"}
    results.append(_check("scene_manifest.json composite export plan valid", planned_ok, str(animation_exports.get("render_status") or "missing")))
    return results


def _validate_cloud_generation_manifest(path: Path, sprite_dir: Path, expected_frame_count: int) -> list[Dict]:
    results = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [_check("cloud_generation.json parseable", False, str(exc))]

    schema_ok = manifest.get("schema") == "spriteforge.cloud_image_sprite.v1"
    results.append(_check("cloud_generation.json schema valid", schema_ok, str(manifest.get("schema") or "missing")))

    frame_count_ok = int(manifest.get("frame_count", 0) or 0) == expected_frame_count
    results.append(_check("cloud_generation.json frame_count matches sheet", frame_count_ok, f"manifest={manifest.get('frame_count')} sheet={expected_frame_count}"))

    processing = manifest.get("processing") if isinstance(manifest.get("processing"), dict) else {}
    transparency = processing.get("transparency_extraction") if isinstance(processing.get("transparency_extraction"), dict) else {}
    downsampling = processing.get("downsampling") if isinstance(processing.get("downsampling"), dict) else {}
    assembly = processing.get("assembly") if isinstance(processing.get("assembly"), dict) else {}
    processing_ok = (
        transparency.get("engine") == "chroma_key"
        and downsampling.get("interpolation") == "nearest"
        and assembly.get("grid_aligned") is True
    )
    results.append(_check("cloud_generation.json processing contract valid", processing_ok))

    generation_contract = manifest.get("generation_contract") if isinstance(manifest.get("generation_contract"), dict) else {}
    secrets_policy = generation_contract.get("secrets_policy") if isinstance(generation_contract.get("secrets_policy"), dict) else {}
    contract_ok = (
        generation_contract.get("schema") == "spriteforge.cloud_generation_contract.v1"
        and generation_contract.get("request_strategy") in {"one_frame_per_request", "local_source_images_only"}
        and secrets_policy.get("secret_values_exposed") is False
        and secrets_policy.get("secret_values_persisted") is False
    )
    results.append(_check("cloud_generation.json generation contract valid", contract_ok))

    frame_sources = manifest.get("frame_sources") if isinstance(manifest.get("frame_sources"), list) else []
    sources_ok = len(frame_sources) == expected_frame_count
    cleanup_ok = True
    for source in frame_sources:
        if not isinstance(source, dict):
            sources_ok = False
            cleanup_ok = False
            continue
        for key in ("raw_frame", "processed_frame"):
            rel = str(source.get(key) or "").strip()
            if not rel or not (sprite_dir / rel).exists():
                sources_ok = False
        cleanup = source.get("cleanup_metrics") if isinstance(source.get("cleanup_metrics"), dict) else {}
        if cleanup.get("schema") != "spriteforge.cloud_frame_cleanup.v1":
            cleanup_ok = False
        if not cleanup.get("processed_size") or cleanup.get("opaque_pixel_ratio") is None:
            cleanup_ok = False
    results.append(_check("cloud_generation.json frame source files exist", sources_ok, f"frames={len(frame_sources)} expected={expected_frame_count}"))
    results.append(_check("cloud_generation.json cleanup metrics valid", cleanup_ok))

    provider_ok = bool(manifest.get("provider")) and manifest.get("provider_configured") in {True, False}
    results.append(_check("cloud_generation.json provider metadata present", provider_ok, str(manifest.get("provider") or "missing")))
    return results


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

    # --- 6. Optional SpriteForge sidecar manifest checks ---
    expected_frame_count = int(meta.get("frame_count", 0) or 0)
    sidecar_paths = sorted({
        *sprite_dir.glob("animated_exports/*.manifest.json"),
        *sprite_dir.glob("*.lighting_preview.json"),
    })
    for sidecar_path in sidecar_paths:
        sidecar_results = _validate_sidecar_manifest(sidecar_path, sprite_dir, expected_frame_count)
        results.extend(sidecar_results)
        if not all(item["ok"] for item in sidecar_results):
            all_ok = False
    audio_cues_path = sprite_dir / "audio_cues.json"
    if audio_cues_path.exists():
        audio_results = _validate_audio_cues_manifest(audio_cues_path, sprite_dir, expected_frame_count, float(meta.get("fps", 12) or 12))
        results.extend(audio_results)
        if not all(item["ok"] for item in audio_results):
            all_ok = False
    tilemap_paths = sorted({
        *sprite_dir.glob("*.tilemap.json"),
        *sprite_dir.glob("*_tilemap.json"),
        *sprite_dir.glob("*tilemap*.json"),
    })
    for tilemap_path in tilemap_paths:
        tilemap_results = _validate_tilemap_manifest(tilemap_path, sprite_dir)
        results.extend(tilemap_results)
        if not all(item["ok"] for item in tilemap_results):
            all_ok = False
    skeletal_paths = sorted({
        *sprite_dir.glob("skeletal_manifest.json"),
        *sprite_dir.glob("skeletal_export/skeletal_manifest.json"),
        *sprite_dir.glob("skeletal/skeletal_manifest.json"),
    })
    for skeletal_path in skeletal_paths:
        skeletal_results = _validate_skeletal_manifest(skeletal_path)
        results.extend(skeletal_results)
        if not all(item["ok"] for item in skeletal_results):
            all_ok = False
    scene_paths = sorted({
        *sprite_dir.glob("scene_manifest.json"),
        *sprite_dir.glob("scenes/*/scene_manifest.json"),
        *sprite_dir.glob("*/scene_manifest.json"),
    })
    for scene_path in scene_paths:
        scene_results = _validate_scene_manifest(scene_path)
        results.extend(scene_results)
        if not all(item["ok"] for item in scene_results):
            all_ok = False
    cloud_generation_path = sprite_dir / "cloud_generation.json"
    if cloud_generation_path.exists():
        cloud_results = _validate_cloud_generation_manifest(cloud_generation_path, sprite_dir, expected_frame_count)
        results.extend(cloud_results)
        if not all(item["ok"] for item in cloud_results):
            all_ok = False

    # --- 6. Release zip checks ---
    if release_zip and Path(release_zip).exists():
        import zipfile as _zf
        try:
            with _zf.ZipFile(release_zip, "r") as zf:
                names = set(zf.namelist())
                manifest_names = [name for name in names if name.endswith("/manifest.json") or name == "manifest.json"]
                manifest_data = None
                if manifest_names:
                    manifest_data = json.loads(zf.read(sorted(manifest_names)[0]).decode("utf-8"))
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
            r = _check("Release zip contains manifest.json", bool(manifest_names))
            results.append(r)
            if not r["ok"]:
                all_ok = False
            restricted_members = _restricted_zip_members(names)
            r = _check("Release zip excludes restricted/heavy files", not restricted_members, ", ".join(restricted_members[:8]))
            results.append(r)
            if restricted_members:
                all_ok = False
            if manifest_data is not None:
                schema_ok = manifest_data.get("schema") == "spriteforge_release_v12"
                r = _check("Release manifest schema valid", schema_ok, str(manifest_data.get("schema") or "missing"))
                results.append(r)
                if not schema_ok:
                    all_ok = False
                handoff = manifest_data.get("handoff") if isinstance(manifest_data.get("handoff"), dict) else {}
                handoff_ok = handoff.get("schema") == "spriteforge.release_handoff.v1"
                r = _check("Release handoff schema valid", handoff_ok, str(handoff.get("schema") or "missing"))
                results.append(r)
                if not handoff_ok:
                    all_ok = False
                preflight = handoff.get("preflight") if isinstance(handoff.get("preflight"), dict) else {}
                manifest_root = str(sorted(manifest_names)[0]).rsplit("/", 1)[0]
                prefix = f"{manifest_root}/" if manifest_root else ""
                for label, rel_name in [("JSON", preflight.get("json")), ("HTML", preflight.get("html"))]:
                    expected = prefix + str(rel_name or "")
                    present = bool(rel_name) and expected in names
                    r = _check(f"Release handoff preflight {label} exists", present, expected or "missing")
                    results.append(r)
                    if not present:
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
