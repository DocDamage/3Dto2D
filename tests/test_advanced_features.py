import json
import shutil
from pathlib import Path
import pytest
from PIL import Image

import sys
ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.project_service import ProjectService
from web_helpers import (
    _sprite_version_save, _sprite_version_list, _sprite_version_rollback,
    _ab_run_create, _ab_run_list, _library_save, _library_list, _library_delete,
    _qa_batch_summary
)

def test_project_quality_gates(tmp_path, monkeypatch):
    # Setup mock workspace paths
    monkeypatch.setattr("web_helpers.PROJECTS", tmp_path / "projects")
    monkeypatch.setattr("services.project_service.PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("services.project_service.ROOT", tmp_path)

    
    # Create project
    proj = ProjectService.create_project(name="TestProj")
    manifest_path = tmp_path / "projects" / "TestProj" / "spriteforge_project.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "quality_gates" in data
    assert data["quality_gates"]["max_foot_drift"] == 2.0
    
    # Update config
    gate_updates = {
        "quality_gates": {
            "max_foot_drift": 4.5,
            "max_flicker": 2.5,
            "loop_seam_threshold": 12.0,
            "required_frame_count": 24,
            "alpha_cleanliness": 0.08
        }
    }
    data.update(gate_updates)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    
    # Read back gates
    from spriteforge_final import get_project_quality_gates
    gates = get_project_quality_gates(tmp_path / "projects" / "TestProj" / "sprites" / "dummy_sprite")
    assert gates["max_foot_drift"] == 4.5
    assert gates["required_frame_count"] == 24


def test_library_crud(tmp_path, monkeypatch):
    monkeypatch.setattr("web_helpers.PROJECTS", tmp_path / "projects")
    monkeypatch.setattr("services.project_service.PROJECTS_DIR", tmp_path / "projects")
    
    # Save pose asset
    res = _library_save("TestProj", {
        "title": "Sword Swing",
        "category": "pose",
        "content": "Description of sword swing silhouette"
      })
    assert res["ok"]
    assert res["asset"]["title"] == "Sword Swing"
    
    # List assets
    assets = _library_list("TestProj")
    assert len(assets) == 1
    assert assets[0]["title"] == "Sword Swing"
    
    # Delete asset
    del_res = _library_delete("TestProj", res["asset"]["id"])
    assert del_res["ok"]
    assert len(_library_list("TestProj")) == 0


def test_sprite_versioning(tmp_path, monkeypatch):
    # Mock output root
    sprite_dir = tmp_path / "output" / "my_hero"
    sprite_dir.mkdir(parents=True)
    
    # Create fake sheet.json, sheet.png, preview.gif, frames_processed
    (sprite_dir / "sheet.json").write_text(json.dumps({"frame_count": 2, "image": "sheet.png"}), encoding="utf-8")
    (sprite_dir / "sheet.png").write_text("fake_png", encoding="utf-8")
    (sprite_dir / "preview.gif").write_text("fake_gif", encoding="utf-8")
    
    frames_dir = sprite_dir / "frames_processed"
    frames_dir.mkdir()
    (frames_dir / "frame_0000.png").write_text("f0", encoding="utf-8")
    (frames_dir / "frame_0001.png").write_text("f1", encoding="utf-8")
    
    monkeypatch.setattr("web_helpers.OUTPUT", tmp_path / "output")
    monkeypatch.setattr("web_helpers.ROOT", tmp_path)
    
    # Save version
    res = _sprite_version_save("output/my_hero", "first snapshot")
    assert res["ok"]
    assert len(res["versions"]) == 1
    assert res["versions"][0]["label"] == "first snapshot"
    
    # Modify files
    (sprite_dir / "sheet.json").write_text(json.dumps({"frame_count": 2, "image": "modified.png"}), encoding="utf-8")
    
    # List versions
    versions = _sprite_version_list("output/my_hero")
    assert len(versions["versions"]) == 1
    
    # Rollback version
    rb_res = _sprite_version_rollback("output/my_hero", res["version_id"])
    assert rb_res["ok"]
    
    # Read back sheet.json
    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
    assert meta["image"] == "sheet.png"
