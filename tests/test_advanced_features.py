import json
import importlib.util
import shutil
from pathlib import Path
import pytest
from PIL import Image

import sys
ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.project_service import ProjectService
from services.frame_status_service import update_frame_status
from services.palette_harmonizer_service import harmonize_palette
from services.audio_cue_service import remove_audio_cue, upsert_audio_cue
from services.state_machine_service import build_state_machine
from web_helpers import (
    _sprite_version_save, _sprite_version_list, _sprite_version_rollback,
    _ab_run_create, _ab_run_list, _library_save, _library_list, _library_delete,
    _qa_batch_summary, sprite_preview_bundle
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


def test_sprite_preview_bundle_includes_frame_manifest(tmp_path, monkeypatch):
    sprite_dir = tmp_path / "output" / "my_hero"
    sprite_dir.mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_count": 2,
        "fps": 12,
        "image": "sheet.png",
        "frame_width": 64,
        "frame_height": 64,
        "columns": 2,
        "rows": 1,
        "frames": [
            {"index": 0, "x": 0, "y": 0, "w": 64, "h": 64},
            {"index": 1, "x": 64, "y": 0, "w": 64, "h": 64}
        ]
    }), encoding="utf-8")
    (sprite_dir / "sheet.png").write_text("fake_png", encoding="utf-8")
    frames_dir = sprite_dir / "frames_processed"
    frames_dir.mkdir()
    (frames_dir / "frame_0000.png").write_text("f0", encoding="utf-8")
    (frames_dir / "frame_0001.png").write_text("f1", encoding="utf-8")

    monkeypatch.setattr("web_helpers.OUTPUT", tmp_path / "output")
    monkeypatch.setattr("web_helpers.ROOT", tmp_path)

    bundle = sprite_preview_bundle("output/my_hero")

    assert bundle["frame_manifest"]["frame_count"] == 2
    assert bundle["frame_manifest"]["fps"] == 12
    assert bundle["frames"][0]["index"] == 0
    assert bundle["frames"][0]["url"].endswith("/file/output/my_hero/frames_processed/frame_0000.png")
    assert bundle["frames"][0]["sheet_rect"] == {"x": 0, "y": 0, "w": 64, "h": 64}


def test_example_plugin_hooks(tmp_path):
    plugin_path = APP / "plugins" / "example_quality_metric.py"
    spec = importlib.util.spec_from_file_location("example_quality_metric", plugin_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sprite_dir = tmp_path / "sprite"
    frames_dir = sprite_dir / "frames_processed"
    frames_dir.mkdir(parents=True)
    (frames_dir / "frame_0000.png").write_text("fake", encoding="utf-8")
    report = {}
    module.on_qa_check(sprite_dir, report)

    metric = report["plugin_metrics"]["example_quality_metric"]
    assert metric["value"] == 1
    assert metric["ok"] is True

    export_dir = tmp_path / "export"
    export_dir.mkdir()
    module.on_export_engine(sprite_dir, "godot", export_dir)
    note = export_dir / "plugin_example_export_note.txt"
    assert note.exists()
    assert "godot" in note.read_text(encoding="utf-8")


def test_frame_status_updates_sheet_metadata(tmp_path):
    sprite_dir = tmp_path / "sprite"
    sprite_dir.mkdir()
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_count": 2,
        "frames": [{"index": 0}, {"index": 1}]
    }), encoding="utf-8")

    summary = update_frame_status(sprite_dir, 1, "needs_edit", "left foot jumps")
    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))

    assert summary["counts"]["needs_edit"] == 1
    assert summary["counts"]["unreviewed"] == 1
    assert meta["frames"][1]["review_status"] == "needs_edit"
    assert meta["frames"][1]["review_note"] == "left foot jumps"


def test_palette_harmonizer_writes_report_and_remapped_sheets(tmp_path):
    output = tmp_path / "output"
    idle = output / "hero_idle"
    walk = output / "hero_walk"
    idle.mkdir(parents=True)
    walk.mkdir(parents=True)
    (idle / "sheet.json").write_text(json.dumps({"image": "sheet.png"}), encoding="utf-8")
    (walk / "sheet.json").write_text(json.dumps({"image": "sheet.png"}), encoding="utf-8")
    Image.new("RGBA", (4, 4), (220, 40, 50, 255)).save(idle / "sheet.png")
    Image.new("RGBA", (4, 4), (40, 80, 220, 255)).save(walk / "sheet.png")

    report = harmonize_palette([idle, walk], colors=4, root=tmp_path)

    assert report["ok"] is True
    assert report["colors"] >= 2
    assert (output / "_palette_harmonization" / "palette_harmonization.json").exists()
    assert (idle / "sheet_harmonized.png").exists()
    assert (walk / "sheet_harmonized.png").exists()
    assert report["sprites"][0]["harmonized_sheet_url"].startswith("/file/output/")


def test_audio_cue_manifest_upsert_and_remove(tmp_path):
    sprite_dir = tmp_path / "sprite"
    sprite_dir.mkdir()

    manifest = upsert_audio_cue(sprite_dir, 3, "input/sfx/step.wav", "footstep")
    assert manifest["cues"][0]["frame_index"] == 3
    assert manifest["cues"][0]["audio_path"] == "input/sfx/step.wav"

    removed = remove_audio_cue(sprite_dir, 3)
    assert removed["cues"] == []


def test_state_machine_service_exports_manifest_and_scripts(tmp_path):
    result = build_state_machine({
        "name": "hero_controller",
        "initial_state": "idle",
        "states": [
            {"name": "idle", "sprite_path": "output/hero_idle"},
            {"name": "walk", "sprite_path": "output/hero_walk"},
        ],
        "transitions": [{"from": "idle", "to": "walk", "condition": "move"}],
    }, tmp_path / "state_machine")

    assert result["ok"] is True
    assert (tmp_path / "state_machine" / "state_machine.json").exists()
    assert "set_state(\"walk\")" in (tmp_path / "state_machine" / "SpriteForgeStateMachine.gd").read_text(encoding="utf-8")
    assert "HandleCondition" in (tmp_path / "state_machine" / "SpriteForgeStateMachine.cs").read_text(encoding="utf-8")
