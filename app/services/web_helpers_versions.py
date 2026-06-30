import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict
from spriteforge_utils import load_json, save_json

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"

def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False

def _resolve_sprite_output_dir(value: str) -> Path:
    import web_helpers
    sprite_dir = (web_helpers.ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    projects_dir = (web_helpers.ROOT / "projects").resolve()
    if not (_is_relative_to(sprite_dir, web_helpers.OUTPUT) or _is_relative_to(sprite_dir, projects_dir)):
        raise ValueError("Sprite path must be inside output or projects.")
    if not sprite_dir.is_dir() or not (sprite_dir / "sheet.json").is_file():
        raise FileNotFoundError("Sprite output folder not found.")
    return sprite_dir

def _sprite_version_save(sprite_dir_str: str, label: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    versions_dir = sprite_dir / ".versions"
    versions_dir.mkdir(exist_ok=True)
    vfile = versions_dir / "versions.json"
    data = load_json(vfile, {"versions": []})
    
    vid = f"v_{int(time.time())}"
    v_subdir = versions_dir / vid
    v_subdir.mkdir(exist_ok=True)
    
    # Copy files
    for name in ["sheet.png", "sheet.json", "preview.gif", "report.html", "qa_report.json", "quality_report.json"]:
        f = sprite_dir / name
        if f.exists():
            shutil.copy2(f, v_subdir / name)
            
    # Copy qa directory files
    qa_dir = sprite_dir / "qa"
    if qa_dir.exists():
        v_qa_dir = v_subdir / "qa"
        shutil.copytree(qa_dir, v_qa_dir, dirs_exist_ok=True)
            
    # Copy frames_processed
    frames_dir = sprite_dir / "frames_processed"
    if frames_dir.exists():
        v_frames_dir = v_subdir / "frames_processed"
        shutil.copytree(frames_dir, v_frames_dir, dirs_exist_ok=True)
        
    data["versions"].append({
        "id": vid,
        "label": label or f"Snapshot {len(data['versions'])+1}",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    data["active_version"] = vid
    save_json(vfile, data)
    return {"ok": True, "version_id": vid, "versions": data["versions"]}

def _sprite_version_list(sprite_dir_str: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    versions_dir = sprite_dir / ".versions"
    vfile = versions_dir / "versions.json"
    data = load_json(vfile, {"active_version": "current", "versions": []})
    
    # Load quality metrics for each version to display in trend graphs
    for v in data.get("versions", []):
        vid = v.get("id")
        v_subdir = versions_dir / vid
        qa_data = {}
        for p in ["qa/qa_report.json", "qa_report.json", "quality_report.json"]:
            p_path = v_subdir / p
            if p_path.exists():
                try:
                    qa_data = json.loads(p_path.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass
        v["metrics"] = qa_data.get("metrics", {}) if qa_data else {}
        
    return data

def _sprite_version_rollback(sprite_dir_str: str, vid: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    v_subdir = sprite_dir / ".versions" / vid
    if not v_subdir.exists():
        raise FileNotFoundError(f"Version backup {vid} not found.")
        
    # Copy files back
    for name in ["sheet.png", "sheet.json", "preview.gif", "report.html", "qa_report.json", "quality_report.json"]:
        f = v_subdir / name
        dest = sprite_dir / name
        if f.exists():
            shutil.copy2(f, dest)
        elif dest.exists():
            dest.unlink()
            
    # Copy qa back
    v_qa_dir = v_subdir / "qa"
    dest_qa_dir = sprite_dir / "qa"
    if v_qa_dir.exists():
        if dest_qa_dir.exists():
            shutil.rmtree(dest_qa_dir)
        shutil.copytree(v_qa_dir, dest_qa_dir)
        
    # Copy frames_processed back
    v_frames_dir = v_subdir / "frames_processed"
    dest_frames_dir = sprite_dir / "frames_processed"
    if v_frames_dir.exists():
        if dest_frames_dir.exists():
            shutil.rmtree(dest_frames_dir)
        shutil.copytree(v_frames_dir, dest_frames_dir)
        
    vfile = sprite_dir / ".versions" / "versions.json"
    data = load_json(vfile, {"versions": []})
    data["active_version"] = vid
    save_json(vfile, data)
    return {"ok": True, "active_version": vid}
