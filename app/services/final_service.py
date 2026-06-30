from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from spriteforge_utils import load_json, save_json, app_python
from services.config_service import ConfigService
from services.comfy_service import ComfyService
from services.model_service import ModelService

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PROJECTS = ROOT / "projects"
RELEASES = ROOT / "releases"
CONFIG = ROOT / "config" / "spriteforge_config.json"
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}

def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def safe_name(value: str) -> str:
    value = (value or "spriteforge").strip()
    out = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in value).strip().replace(" ", "_")
    return out or "spriteforge"

def run_capture(cmd: Sequence[str], timeout: float = 30.0) -> Tuple[int, str]:
    try:
        p = subprocess.run(list(map(str, cmd)), cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 1, str(exc)

def config() -> Dict[str, Any]:
    return ConfigService.get_config()

def comfy_dir() -> Path:
    return ConfigService.get_path("paths.comfyui_dir")

def comfy_output() -> Path:
    return ConfigService.get_path("paths.comfyui_output")

def comfy_url() -> str:
    return ComfyService.get_url()

def check_comfy_running() -> bool:
    return ComfyService.is_running()

def nvidia_summary() -> Dict[str, Any]:
    return ComfyService.get_gpu_info()

def disk_summary(path: Path = ROOT) -> Dict[str, Any]:
    return ModelService.get_disk_summary()

def manifest_status(manifest_rel: str) -> Dict[str, Any]:
    return ModelService.get_manifest_status(manifest_rel)

def model_tier_status() -> Dict[str, Any]:
    return ModelService.get_tiers_status()

def find_sprite_dirs(root: Path = OUTPUT) -> List[Path]:
    if not root.exists():
        return []
    return sorted({p.parent for p in root.rglob("sheet.json")}, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

def sprite_record(folder: Path) -> Dict[str, Any]:
    meta = load_json(folder / "sheet.json", {}) or {}
    frames_dir = folder / "frames_processed"
    qa_json = folder / "qa_report.json"
    quality_json = folder / "quality_report.json"
    qa = load_json(qa_json, None) or load_json(quality_json, None) or {}
    frame_count = meta.get("frame_count") or len(list(frames_dir.glob("*.png"))) if frames_dir.exists() else meta.get("frame_count")
    files = {
        "sheet": (folder / "sheet.png").exists(),
        "json": (folder / "sheet.json").exists(),
        "preview": (folder / "preview.gif").exists(),
        "report": (folder / "report.html").exists(),
        "frames": frames_dir.exists(),
    }
    complete = files["sheet"] and files["json"] and bool(frame_count)
    qa_score = qa.get("score") or qa.get("overall_score") or qa.get("grade")
    return {
        "name": folder.name,
        "path": rel(folder),
        "absolute": str(folder.resolve()),
        "modified": dt.datetime.fromtimestamp(folder.stat().st_mtime).isoformat(timespec="seconds"),
        "frame_count": frame_count or "?",
        "fps": meta.get("fps", "?"),
        "frame_width": meta.get("frame_width", meta.get("w", "?")),
        "frame_height": meta.get("frame_height", meta.get("h", "?")),
        "columns": meta.get("columns", "?"),
        "rows": meta.get("rows", "?"),
        "complete": complete,
        "has_qa": bool(qa),
        "qa_score": qa_score,
        "files": files,
    }

def all_sprite_records(limit: int = 500) -> List[Dict[str, Any]]:
    return [sprite_record(p) for p in find_sprite_dirs()[:limit]]

def recommended_next_step() -> Dict[str, str]:
    py = Path(app_python()).exists()
    if not py:
        return {"step": "Repair SpriteForge Python", "reason": "The local virtual environment (venv) is missing. Click 'Install Everything' or run install_deps.", "action": "install_deps"}

    disk = disk_summary()
    if not disk.get("ok"):
        return {"step": "Clean Disk Space (Warning)", "reason": f"Only {disk.get('free_gb')} GB of free space is available. ComfyUI and WAN models require at least 25 GB of free disk space. Clean up space and try again.", "action": "disk_warning"}

    cdir = comfy_dir()
    if not cdir.exists():
        return {"step": "Install Everything: Safe Wan 2.1", "reason": "ComfyUI directory is missing. We need to clone it and set up nodes. Click 'Install Everything' to start.", "action": "install_all"}

    tiers = model_tier_status()
    safe = tiers.get("wan21_safe", {})
    if not safe.get("ok"):
        missing = [f["filename"] for f in safe.get("files", []) if not f["exists"]]
        missing_str = ", ".join(missing) if missing else "some files"
        return {"step": "Repair / Resume WAN Model Download", "reason": f"Wan 2.1 safe model files are incomplete ({safe.get('present', 0)}/{safe.get('total', 0)} complete). Missing or corrupt files: {missing_str}. The download is resume-enabled and can be retried safely.", "action": "download_models"}

    if not check_comfy_running():
        return {"step": "Launch ComfyUI", "reason": "All safe model files are verified on disk, but the local ComfyUI server is offline. Click 'Launch ComfyUI' or start the server.", "action": "launch_comfy"}

    outputs = find_sprite_dirs()
    if not outputs:
        return {"step": "Generate debug sprite", "reason": "Setup looks ready! Make a small debug idle sprite first to verify the pipeline.", "action": "generate_debug"}

    incomplete = [r for r in all_sprite_records() if not r["has_qa"]]
    if incomplete:
        return {"step": "Run QA on recent sprites", "reason": f"{len(incomplete)} sprite output(s) do not have a QA record yet. Go to Quality Lab, select a sprite, and run a QA report.", "action": "qa_report"}

    return {"step": "Build release package", "reason": "Sprites exist and QA appears to be in place. Package a release for your game engine.", "action": "release_package"}

def preflight_data() -> Dict[str, Any]:
    tiers = model_tier_status()
    outputs = all_sprite_records(200)
    checks = {
        "python": {"ok": Path(app_python()).exists(), "value": app_python()},
        "git": {"ok": shutil.which("git") is not None, "value": shutil.which("git") or "not found"},
        "nvidia": nvidia_summary(),
        "disk": disk_summary(),
        "comfy_dir": {"ok": comfy_dir().exists(), "value": rel(comfy_dir())},
        "comfy_output": {"ok": comfy_output().exists(), "value": rel(comfy_output())},
        "comfy_running": {"ok": check_comfy_running(), "value": comfy_url()},
        "models": tiers,
        "outputs": {"ok": bool(outputs), "count": len(outputs)},
        "next_step": recommended_next_step(),
    }
    return {
        "schema": "spriteforge_preflight_v12",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT.resolve()),
        "platform": platform.platform(),
        "checks": checks,
        "sprites": outputs[:60],
    }

def status_badge(ok: bool) -> str:
    return "PASS" if ok else "CHECK"

def render_preflight_html(data: Dict[str, Any]) -> str:
    checks = data["checks"]
    tiers = checks.get("models", {})
    sprites = data.get("sprites", [])
    rows = []
    simple = ["python", "git", "nvidia", "disk", "comfy_dir", "comfy_output", "comfy_running", "outputs"]
    for key in simple:
        val = checks.get(key, {})
        if key == "outputs":
            text = f"{val.get('count', 0)} sprite output(s)"
        elif key == "disk":
            text = f"{val.get('free_gb')} GB free / {val.get('total_gb')} GB total"
        elif key == "nvidia":
            text = val.get("raw") or val.get("label")
        else:
            text = str(val.get("value", val.get("label", "")))
        rows.append(f"<tr><td>{html.escape(key)}</td><td><b class='{ 'ok' if val.get('ok') else 'warn'}'>{status_badge(bool(val.get('ok')))}</b></td><td>{html.escape(text)}</td></tr>")
    tier_rows = []
    for key, st in tiers.items():
        tier_rows.append(f"<tr><td>{html.escape(key)}</td><td>{html.escape(str(st.get('short_label', key)))}</td><td>{st.get('present',0)}/{st.get('total',0)}</td><td><b class='{ 'ok' if st.get('ok') else 'warn'}'>{status_badge(bool(st.get('ok')))}</b></td></tr>")
    cards = []
    for sp in sprites[:24]:
        preview = Path(sp["absolute"]) / "preview.gif"
        sheet = Path(sp["absolute"]) / "sheet.png"
        image = preview if preview.exists() else sheet
        img_tag = f"<img src='../{rel(image)}'>" if image.exists() else "<div class='noimg'>No preview</div>"
        cards.append(f"<article>{img_tag}<h3>{html.escape(sp['name'])}</h3><p>{sp['frame_count']} frames · {sp['fps']} fps · {sp['frame_width']}×{sp['frame_height']}</p><p>{html.escape(sp['modified'])}</p></article>")
    next_step = checks.get("next_step", {})
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>SpriteForge Preflight</title><style>
    body{{margin:0;background:#080b18;color:#eef4ff;font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:36px}}h1{{font-size:42px;letter-spacing:-.04em}}.hero,.panel{{background:linear-gradient(145deg,rgba(255,255,255,.11),rgba(255,255,255,.04));border:1px solid rgba(255,255,255,.13);border-radius:24px;padding:24px;margin:18px 0;box-shadow:0 24px 80px rgba(0,0,0,.28)}}.next{{font-size:22px;color:#7df3ff}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;border-bottom:1px solid rgba(255,255,255,.1);text-align:left}}.ok{{color:#6affb8}}.warn{{color:#ffd166}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}article{{border:1px solid rgba(255,255,255,.13);background:rgba(255,255,255,.05);border-radius:20px;overflow:hidden}}article img{{width:100%;height:150px;object-fit:contain;background:#030713;image-rendering:pixelated}}article h3,article p{{margin:10px 12px}}article p{{color:#a9b7d0;font-size:13px}}.noimg{{height:150px;display:grid;place-items:center;background:#030713;color:#a9b7d0}}
    </style></head><body><main><section class='hero'><h1>SpriteForge Preflight</h1><p>Generated {html.escape(data['generated_at'])}</p><p class='next'>Recommended next step: <b>{html.escape(str(next_step.get('step','')))}</b></p><p>{html.escape(str(next_step.get('reason','')))}</p></section><section class='panel'><h2>System checks</h2><table><tbody>{''.join(rows)}</tbody></table></section><section class='panel'><h2>WAN model tiers</h2><table><thead><tr><th>Tier</th><th>Label</th><th>Files</th><th>Status</th></tr></thead><tbody>{''.join(tier_rows)}</tbody></table></section><section class='panel'><h2>Recent sprites</h2><div class='grid'>{''.join(cards) or '<p>No sprite outputs yet.</p>'}</div></section></main></body></html>"""

def copy_if_exists(src: Path, dest: Path) -> Optional[str]:
    if not src.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return rel(dest)

def selected_sprite_dirs(args: argparse.Namespace) -> List[Path]:
    dirs: List[Path] = []
    for item in args.sprite_dir or []:
        p = Path(item)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists() and (p / "sheet.json").exists():
            dirs.append(p.resolve())
    if args.root:
        r = Path(args.root)
        if not r.is_absolute():
            r = ROOT / r
        dirs.extend(find_sprite_dirs(r))
    if args.project:
        pr = Path(args.project)
        if not pr.is_absolute():
            pr = ROOT / pr
        dirs.extend(find_sprite_dirs(pr))
        pdata = load_json(pr / "spriteforge_project.json" if pr.is_dir() else pr, {}) or {}
        name = pdata.get("name")
        if name:
            dirs.extend([p for p in find_sprite_dirs() if p.name.startswith(str(name) + "_")])
    out: List[Path] = []
    seen = set()
    for d in dirs:
        key = str(d.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out

def project_release_metadata(project: Optional[str]) -> Dict[str, str]:
    if not project:
        return {}
    path = Path(project)
    if not path.is_absolute():
        path = ROOT / path
    manifest = path / "spriteforge_project.json" if path.is_dir() else path
    data = load_json(manifest, {}) or {}
    if manifest.name != "spriteforge_project.json" or not manifest.exists():
        return {}
    try:
        project_path = rel(manifest)
        project_root = rel(manifest.parent)
    except Exception:
        return {}
    return {
        "project_name": str(data.get("name") or manifest.parent.name),
        "project_path": project_path,
        "project_root": project_root,
    }

def make_release_readme(name: str, sprites: List[Dict[str, Any]], created: str) -> str:
    lines = [
        f"# {name} Sprite Release",
        "",
        f"Created with SpriteForge Studio on {created}.",
        "",
        "## Contents",
        "",
        "- `sprites/`: source SpriteForge outputs containing `sheet.png`, `sheet.json`, preview GIFs, reports, and processed frames when available.",
        "- `engine/`: lightweight Godot/Unity notes and import helpers when generated.",
        "- `manifest.json`: machine-readable release manifest.",
        "- `preflight/`: setup/status report captured at packaging time.",
        "",
        "## Sprite outputs",
        "",
    ]
    for sp in sprites:
        lines.append(f"- `{sp['name']}` — {sp['frame_count']} frames, {sp['fps']} fps, {sp['frame_width']}×{sp['frame_height']}")
    lines += [
        "",
        "## Import notes",
        "",
        "Godot: use `sheet.png` as a texture, set horizontal frames to `columns` and vertical frames to `rows` from `sheet.json`.",
        "",
        "Unity: import `sheet.png` as Sprite Mode Multiple, slice by `frame_width` × `frame_height`, then build an animation clip at the listed FPS.",
        "",
        "## QA reminder",
        "",
        "Run QA and auto-fix before using sprites in-game if the release includes any experimental WAN output.",
    ]
    return "\n".join(lines) + "\n"

def get_project_quality_gates(sprite_dir: Path) -> Dict[str, Any]:
    p = sprite_dir
    for _ in range(4):
        p = p.parent
        proj_manifest = p / "spriteforge_project.json"
        if proj_manifest.exists():
            try:
                data = json.loads(proj_manifest.read_text(encoding="utf-8"))
                if "quality_gates" in data:
                    return data["quality_gates"]
            except Exception:
                pass
                
    try:
        config_path = Path(__file__).resolve().parent.parent / "config" / "spriteforge_config.json"
        if config_path.exists():
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            active_p = config_data.get("active_project")
            if active_p:
                proj_path = (Path(__file__).resolve().parent.parent / active_p).resolve()
                if proj_path.exists():
                    data = json.loads(proj_path.read_text(encoding="utf-8"))
                    if "quality_gates" in data:
                        return data["quality_gates"]
    except Exception:
        pass
        
    return {
        "max_foot_drift": 2.0,
        "max_flicker": 1.0,
        "loop_seam_threshold": 15.0,
        "required_frame_count": None,
        "alpha_cleanliness": 0.05
    }

def check_release_quality_gates(sprite_dirs: List[Path]) -> Dict[str, Any]:
    warnings = []
    errors = []
    
    for folder in sprite_dirs:
        name = folder.name
        meta_file = folder / "sheet.json"
        if not meta_file.exists():
            errors.append(f"Sprite '{name}': Missing sheet.json metadata.")
            continue
            
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Sprite '{name}': Bad sheet.json metadata: {exc}")
            continue
            
        fw = meta.get("frame_width")
        fh = meta.get("frame_height")
        if not fw or not fh:
            errors.append(f"Sprite '{name}': Metadata frame size is not set.")
            
        sheet_png = folder / meta.get("image", "sheet.png")
        if not sheet_png.exists():
            errors.append(f"Sprite '{name}': Missing spritesheet image.")
        else:
            try:
                from PIL import Image
                with Image.open(sheet_png) as img:
                    w, h = img.size
                    cols = meta.get("columns", 1)
                    rows = meta.get("rows", 1)
                    if fw and fh:
                        expected_w = fw * cols
                        expected_h = fh * rows
                        if w != expected_w or h != expected_h:
                            errors.append(f"Sprite '{name}': sheet.png size ({w}x{h}) does not match metadata columns/rows expectation ({expected_w}x{expected_h}).")
            except Exception as exc:
                errors.append(f"Sprite '{name}': Failed to read sheet.png: {exc}")
                
        preview_gif = folder / "preview.gif"
        if not preview_gif.exists():
            warnings.append(f"Sprite '{name}': Missing preview.gif.")
            
        qa_json = folder / "qa_report.json"
        quality_json = folder / "quality_report.json"
        qa_file = qa_json if qa_json.exists() else (quality_json if quality_json.exists() else None)
        
        gates = get_project_quality_gates(folder)
        
        if not qa_file:
            warnings.append(f"Sprite '{name}': Missing QA report (run QA first).")
        else:
            try:
                import numpy as np
                qa_data = json.loads(qa_file.read_text(encoding="utf-8"))
                metrics = qa_data.get("metrics", {})
                
                drift = metrics.get("foot_y_stdev_px", 0.0)
                max_drift = gates.get("max_foot_drift")
                if max_drift is not None and drift > float(max_drift):
                    errors.append(f"Sprite '{name}': Foot drift {drift:.2f}px exceeds gate threshold {max_drift}px.")
                    
                flicker = metrics.get("brightness_stdev", 0.0)
                max_flicker = gates.get("max_flicker")
                if max_flicker is not None and flicker > float(max_flicker):
                    errors.append(f"Sprite '{name}': Flicker {flicker:.2f} exceeds gate threshold {max_flicker}.")
                    
                seam = metrics.get("loop_seam_rmse", 0.0)
                max_seam = gates.get("loop_seam_threshold")
                if max_seam is not None and seam > float(max_seam):
                    errors.append(f"Sprite '{name}': Loop seam RMSE {seam:.2f} exceeds gate threshold {max_seam}.")
                    
                frames_cnt = metrics.get("frame_count")
                req_frames = gates.get("required_frame_count")
                if req_frames is not None and frames_cnt is not None and int(frames_cnt) != int(req_frames):
                    errors.append(f"Sprite '{name}': Frame count {frames_cnt} does not match required gate {req_frames}.")
                    
                cleanliness = metrics.get("alpha_cleanliness")
                if cleanliness is None:
                    if sheet_png.exists():
                        try:
                            from PIL import Image
                            with Image.open(sheet_png) as img:
                                arr = np.asarray(img.convert("RGBA"))
                                alpha = arr[:, :, 3]
                                cleanliness = float(((alpha > 0) & (alpha < 16)).sum() / max(1, alpha.size))
                        except Exception:
                            cleanliness = 0.0
                    else:
                        cleanliness = 0.0
                
                max_clean = gates.get("alpha_cleanliness")
                if max_clean is not None and cleanliness > float(max_clean):
                    errors.append(f"Sprite '{name}': Alpha noise ratio {cleanliness:.4f} exceeds cleanliness gate threshold {max_clean}.")
                    
                score = qa_data.get("score")
                if score is not None:
                    if float(score) < 75.0:
                        errors.append(f"Sprite '{name}': Failed QA gate (score {score} is below 75).")
            except Exception as exc:
                errors.append(f"Sprite '{name}': Failed to read QA report: {exc}")
                
        godot_files = list(folder.glob("*.gd")) + list(folder.glob("godot_export/*.gd")) + list(folder.glob("*.tscn"))
        unity_files = list(folder.glob("*.cs")) + list(folder.glob("unity_export/*.cs"))
        if not godot_files and not unity_files:
            warnings.append(f"Sprite '{name}': Missing Godot or Unity engine exports.")
            
    sizes = set()
    for folder in sprite_dirs:
        meta_file = folder / "sheet.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                fw = meta.get("frame_width")
                fh = meta.get("frame_height")
                if fw and fh:
                    sizes.add((fw, fh))
            except Exception:
                pass
    if len(sizes) > 1:
        warnings.append(f"Inconsistent frame sizes across sprites in this release: {list(sizes)}")
        
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

def render_dashboard_html(records: List[Dict[str, Any]], data: Dict[str, Any]) -> str:
    cards = []
    for sp in records:
        folder = ROOT / sp["path"]
        preview = folder / "preview.gif"
        sheet = folder / "sheet.png"
        image = preview if preview.exists() else sheet
        img = f"<img src='../{rel(image)}'>" if image.exists() else "<div class='noimg'>No preview</div>"
        qa = "QA" if sp.get("has_qa") else "Needs QA"
        qa_class = "ok" if sp.get("has_qa") else "warn"
        cards.append(f"<article>{img}<div class='body'><h3>{html.escape(sp['name'])}</h3><p>{sp['frame_count']} frames · {sp['fps']} fps · {sp['frame_width']}×{sp['frame_height']}</p><p><b class='{qa_class}'>{qa}</b> · {html.escape(sp['modified'])}</p><code>{html.escape(sp['path'])}</code></div></article>")
    nxt = data["checks"]["next_step"]
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>SpriteForge Asset Dashboard</title><style>
    *{{box-sizing:border-box}}body{{margin:0;color:#eef4ff;background:radial-gradient(circle at 20% 0%,rgba(85,241,255,.18),transparent 28%),radial-gradient(circle at 85% 20%,rgba(255,101,189,.14),transparent 30%),#070a17;font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}}main{{max-width:1280px;margin:auto;padding:36px}}h1{{font-size:54px;letter-spacing:-.06em;margin:0 0 10px}}.hero{{padding:28px;border:1px solid rgba(255,255,255,.13);border-radius:30px;background:linear-gradient(145deg,rgba(255,255,255,.12),rgba(255,255,255,.04));box-shadow:0 24px 90px rgba(0,0,0,.3)}}.next{{font-size:20px;color:#7df3ff}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}}.stat{{padding:18px;border-radius:22px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12)}}.stat b{{display:block;font-size:26px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:16px;margin-top:20px}}article{{border:1px solid rgba(255,255,255,.13);border-radius:24px;background:rgba(255,255,255,.06);overflow:hidden}}article img{{width:100%;height:165px;object-fit:contain;image-rendering:pixelated;background:#020511}}.body{{padding:14px}}h3{{margin:0 0 8px}}p{{color:#aab8d3;margin:6px 0}}code{{display:block;color:#7df3ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px}}.ok{{color:#6affb8}}.warn{{color:#ffd166}}.noimg{{height:165px;display:grid;place-items:center;background:#020511;color:#aab8d3}}@media(max-width:800px){{.stats{{grid-template-columns:1fr 1fr}}h1{{font-size:36px}}}}
    </style></head><body><main><section class='hero'><h1>SpriteForge Asset Dashboard</h1><p>Generated {html.escape(data['generated_at'])}</p><p class='next'>Recommended next step: <b>{html.escape(str(nxt.get('step','')))}</b> — {html.escape(str(nxt.get('reason','')))}</p></section><section class='stats'><div class='stat'><span>Sprites</span><b>{len(records)}</b></div><div class='stat'><span>ComfyUI</span><b>{'Online' if data['checks']['comfy_running']['ok'] else 'Offline'}</b></div><div class='stat'><span>Disk free</span><b>{data['checks']['disk']['free_gb']} GB</b></div><div class='stat'><span>GPU</span><b>{html.escape(str(data['checks']['nvidia'].get('vram_gb') or '?'))} GB</b></div></section><section class='grid'>{''.join(cards) or '<p>No sprite outputs found.</p>'}</section></main></body></html>"""
