from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional

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
