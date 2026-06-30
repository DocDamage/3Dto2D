from __future__ import annotations
import shutil
import time
from pathlib import Path
from typing import Dict, Any

from spriteforge_utils import ROOT, PROJECTS, load_json, save_json
from services.project_service import ProjectService

__all__ = ["create_sample_project", "build_first_sprite_request"]

def create_sample_project() -> Dict[str, Any]:
    project_name = "SampleProject"
    dest_dir = PROJECTS / project_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy prebuilt demo sprite folder if it exists
    src_sprite = ROOT / "examples" / "prebuilt_demo_sprite"
    dest_sprite = dest_dir / "sprites" / "prebuilt_demo_sprite"
    if src_sprite.exists():
        if dest_sprite.exists():
            shutil.rmtree(dest_sprite)
        shutil.copytree(src_sprite, dest_sprite)

    # 2. Write project metadata manifest
    manifest_path = dest_dir / "spriteforge_project.json"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta = {
        "schema": "spriteforge_project_v12",
        "name": project_name,
        "character": "Knight",
        "style": "Pixel Art 16-bit",
        "actions": ["idle", "walk"],
        "directions": ["right"],
        "created_at": now,
        "updated_at": now
    }
    save_json(manifest_path, meta)

    # 3. Write default project library
    library_path = dest_dir / "library.json"
    save_json(library_path, [])

    return {
        "ok": True,
        "project": project_name,
        "sprite_dir": f"projects/{project_name}/sprites/prebuilt_demo_sprite",
        "next_view": "quality",
        "next_action": "Review the sample sprite in Quality Lab"
    }

def build_first_sprite_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to populate wizard inputs with hardware-safe presets."""
    archetype = payload.get("archetype", "humanoid")
    action = payload.get("action", "idle")
    direction = payload.get("direction", "right")
    name = payload.get("name", "hero")

    # Simple defaults for first-sprite generation
    return {
        "name": name,
        "prompt": f"A 16-bit pixel art {archetype} character performing {action} animation",
        "negative_prompt": "blurry, low quality, high detail, photorealistic, 3D render",
        "action": action,
        "direction": direction,
        "model": "wan2.1-t2v-1.3B",
        "profile": "debug",  # Hardware safe default for first runs
        "steps": 15,
        "cfg": 6.0,
        "fps": 12,
        "frame_count": 8,
        "width": 512,
        "height": 512,
        "seed": -1,
    }
