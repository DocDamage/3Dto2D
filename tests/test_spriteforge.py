import sys
import os
import json
import time
import zipfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add app directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from services.config_service import ConfigService
from services.model_service import ModelService
from web_helpers import build_action_command

def test_config_service():
    # Test path resolving fallbacks
    comfy_dir = ConfigService.get_path("paths.comfyui_dir")
    assert comfy_dir is not None
    assert str(comfy_dir).replace("\\", "/").endswith("vendor/ComfyUI")

def test_build_action_command():
    payload = {"action": "doctor"}
    title, cmd = build_action_command(payload)
    assert title == "Run Doctor"
    assert "spriteforge_unified.py" in cmd[1]
    assert "doctor" in cmd[2]

    payload_convert = {
        "action": "convert_video",
        "input": "test.mp4",
        "fps": "12",
        "cell_size": "256x256"
    }
    title, cmd = build_action_command(payload_convert)
    assert title == "Convert video to spritesheet"
    assert "convert-video" in cmd
    assert "test.mp4" in cmd

    project_manifest = ROOT / "app" / "projects" / "hero" / "spriteforge_project.json"
    with patch("services.project_service.ProjectService.resolve_project_path", return_value=project_manifest):
        title, cmd = build_action_command({"action": "queue_create", "active_project": "projects/hero/spriteforge_project.json"})
    assert title == "Create persistent production queue"
    assert "--project" in cmd
    assert str(project_manifest) in cmd

    project_meta = {
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    }
    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        payload = {
            "action": "release_package",
            "active_project": "projects/hero/spriteforge_project.json",
            "name": "hero_release",
            "sprites": ["output/demo_sprite_no_gpu"],
        }
        title, cmd = build_action_command(payload)
    assert title == "Build release package"
    assert "--project" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "spriteforge_project.json") in cmd
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "releases" / "hero_release") in cmd
    assert payload["project_name"] == "hero"

    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        title, cmd = build_action_command({
            "action": "convert_video",
            "active_project": "projects/hero/spriteforge_project.json",
            "input": "input/hero_walk.webm",
        })
    assert title == "Convert video to spritesheet"
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "sprites" / "hero_walk_sprite") in cmd

    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        title, cmd = build_action_command({
            "action": "qa_report",
            "active_project": "projects/hero/spriteforge_project.json",
            "sprite_dir": "output/hero_walk_sprite",
        })
    assert title == "Analyze sprite quality"
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "quality" / "hero_walk_sprite") in cmd

    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        title, cmd = build_action_command({
            "action": "autofix",
            "active_project": "projects/hero/spriteforge_project.json",
            "sprite_dir": "output/hero_walk_sprite",
        })
    assert title == "Auto-fix sprite output"
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "sprites" / "hero_walk_sprite_fixed") in cmd

    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        title, cmd = build_action_command({
            "action": "export_godot",
            "active_project": "projects/hero/spriteforge_project.json",
            "sprite_dir": "output/hero_walk_sprite",
        })
    assert title == "Export Godot helper"
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "exports" / "hero_walk_sprite_godot") in cmd

    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        title, cmd = build_action_command({
            "action": "atlas",
            "active_project": "projects/hero/spriteforge_project.json",
            "name": "hero",
            "sprites": ["output/hero_idle_sprite", "output/hero_walk_sprite"],
        })
    assert title == "Build multi-action atlas"
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero" / "exports" / "hero_atlas") in cmd

    with patch("services.project_service.ProjectService.metadata_for_path", return_value=project_meta):
        title, cmd = build_action_command({
            "action": "character_pack",
            "active_project": "projects/hero/spriteforge_project.json",
            "name": "hero",
            "description": "single full body original game hero",
            "actions": "idle,walk",
            "directions": "right",
        })
    assert title == "Create character production pack"
    assert "pack-init" in cmd
    assert "--output" in cmd
    assert str(ROOT / "app" / "projects" / "hero") in cmd
    assert "--pose-guided" in cmd
    assert "--posepacks" in cmd

def test_model_summary_shape(monkeypatch):
    monkeypatch.setattr(
        ModelService,
        "get_tiers_status",
        staticmethod(lambda: {
            "wan21_safe": {"ok": True, "present": 3, "total": 3, "label": "Safe"},
            "wan22_5b": {"ok": False, "present": 1, "total": 3, "label": "Advanced"},
            "wan22_14b_cloud": {"ok": False, "present": 0, "total": 0, "cloud_only": True},
        }),
    )
    monkeypatch.setattr(
        ConfigService,
        "get_config",
        staticmethod(lambda: {"default_model_tier": "wan21_safe"}),
    )

    summary = ModelService.get_summary()

    assert summary["ok"] is True
    assert summary["present"] == 3
    assert summary["total"] == 3
    assert summary["advanced_present"] == 1
    assert summary["advanced_total"] == 3
    assert summary["advanced_ok"] is False
    assert "tiers" in summary

def test_release_manifests(tmp_path):
    from spriteforge_final import build_parser

    # Create mock source sprite output
    src_sprite_dir = tmp_path / "mock_sprite"
    src_sprite_dir.mkdir()
    sheet_meta = {
        "animation": "hero_walk",
        "frame_count": 8,
        "fps": 10,
        "frame_width": 64,
        "frame_height": 64,
        "columns": 8,
        "rows": 1,
        "image": "sheet.png",
    }
    (src_sprite_dir / "sheet.json").write_text(
        json.dumps(sheet_meta), encoding="utf-8"
    )
    (src_sprite_dir / "sheet.png").write_text("fake png bytes", encoding="utf-8")

    out_dir = tmp_path / "release_output"

    parser = build_parser()
    args = parser.parse_args(
        [
            "release",
            "--name",
            "test_release",
            "--sprite-dir",
            str(src_sprite_dir),
            "--output",
            str(out_dir),
            "--zip",
        ]
    )

    mock_preflight = {
        "generated_at": "2026-06-25T12:00:00",
        "checks": {
            "python": {"ok": True, "value": "python"},
            "git": {"ok": True, "value": "git"},
            "nvidia": {"ok": True, "raw": "GeForce RTX", "label": "GeForce RTX"},
            "disk": {"ok": True, "free_gb": 100, "total_gb": 500},
            "comfy_dir": {"ok": True, "value": "comfy_dir"},
            "comfy_output": {"ok": True, "value": "comfy_output"},
            "comfy_running": {"ok": False, "value": "comfy_url"},
            "outputs": {"ok": True, "count": 1},
            "next_step": {"step": "None", "reason": "none"}
        },
        "sprites": []
    }

    mock_record = {
        "name": "mock_sprite",
        "path": "mock_sprite",
        "frame_count": 8,
        "fps": 10,
        "frame_width": 64,
        "frame_height": 64,
    }

    with patch(
        "spriteforge_final.preflight_data", return_value=mock_preflight
    ), patch(
        "spriteforge_final.sprite_record",
        return_value=mock_record,
    ):
        args.func(args)

    assert out_dir.exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "README.md").exists()
    assert (out_dir / "sprites" / "mock_sprite" / "sheet.json").exists()
    assert (out_dir / "engine" / "mock_sprite_import_notes.md").exists()
    assert (out_dir / "preflight" / "preflight.json").exists()

    manifest = json.loads(
        (out_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == "spriteforge_release_v12"
    assert manifest["name"] == "test_release"

    zip_file_path = out_dir.with_suffix(".zip")
    assert zip_file_path.exists()
    with zipfile.ZipFile(zip_file_path, "r") as zf:
        namelist = zf.namelist()
        assert "release_output/manifest.json" in namelist
        assert "release_output/sprites/mock_sprite/sheet.json" in namelist

def test_release_manifest_includes_project_metadata(tmp_path):
    from spriteforge_final import build_parser

    project_dir = tmp_path / "projects" / "hero"
    project_dir.mkdir(parents=True)
    project_manifest = project_dir / "spriteforge_project.json"
    project_manifest.write_text(json.dumps({
        "schema": "spriteforge_project_v1",
        "name": "hero",
    }), encoding="utf-8")

    src_sprite_dir = tmp_path / "mock_sprite"
    src_sprite_dir.mkdir()
    (src_sprite_dir / "sheet.json").write_text(json.dumps({
        "animation": "hero_idle",
        "frame_count": 1,
        "fps": 12,
        "frame_width": 64,
        "frame_height": 64,
        "columns": 1,
        "rows": 1,
        "image": "sheet.png",
    }), encoding="utf-8")
    (src_sprite_dir / "sheet.png").write_text("fake png bytes", encoding="utf-8")

    out_dir = tmp_path / "projects" / "hero" / "releases" / "hero_release"
    parser = build_parser()
    args = parser.parse_args([
        "release",
        "--name",
        "hero_release",
        "--project",
        str(project_manifest),
        "--sprite-dir",
        str(src_sprite_dir),
        "--output",
        str(out_dir),
    ])

    with patch("spriteforge_final.preflight_data", return_value={
        "generated_at": "2026-06-25T12:00:00",
        "checks": {
            "python": {"ok": True, "value": "python"},
            "git": {"ok": True, "value": "git"},
            "nvidia": {"ok": True, "raw": "GeForce RTX", "label": "GeForce RTX"},
            "disk": {"ok": True, "free_gb": 100, "total_gb": 500},
            "comfy_dir": {"ok": True, "value": "comfy_dir"},
            "comfy_output": {"ok": True, "value": "comfy_output"},
            "comfy_running": {"ok": False, "value": "comfy_url"},
            "outputs": {"ok": True, "count": 1},
            "next_step": {"step": "None", "reason": "none"},
        },
        "sprites": [],
    }):
        args.func(args)

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["project_name"] == "hero"
    assert manifest["project_path"].endswith("projects/hero/spriteforge_project.json")
    assert manifest["project_root"].endswith("projects/hero")

def test_godot_export(tmp_path):
    from services.export_service import ExportService

    src_sprite_dir = tmp_path / "mock_sprite"
    src_sprite_dir.mkdir()
    sheet_meta = {
        "animation": "hero_run",
        "frame_count": 6,
        "fps": 12.0,
        "frame_width": 32,
        "frame_height": 32,
        "columns": 6,
        "rows": 1,
        "image": "sheet.png",
    }
    (src_sprite_dir / "sheet.json").write_text(
        json.dumps(sheet_meta), encoding="utf-8"
    )
    (src_sprite_dir / "sheet.png").write_text("fake png bytes", encoding="utf-8")

    dest_dir = tmp_path / "godot_export"

    ExportService.export_godot(
        sprite_dir=src_sprite_dir,
        dest=dest_dir,
        meta=sheet_meta,
        project_root=tmp_path,
        res_path=None,
        mode="sprite2d",
    )

    assert (dest_dir / "sheet.png").exists()
    assert (dest_dir / "sheet.json").exists()
    assert (dest_dir / "hero_run_sprite2d_player.gd").exists()
    assert (dest_dir / "hero_run.tscn").exists()

    script_content = (dest_dir / "hero_run_sprite2d_player.gd").read_text(
        encoding="utf-8"
    )
    assert "extends Sprite2D" in script_content
    assert "hframes = 6" in script_content

    tscn_content = (dest_dir / "hero_run.tscn").read_text(encoding="utf-8")
    assert '[node name="hero_run" type="Sprite2D"]' in tscn_content

    shutil.rmtree(dest_dir)
    dest_dir.mkdir()

    ExportService.export_godot(
        sprite_dir=src_sprite_dir,
        dest=dest_dir,
        meta=sheet_meta,
        project_root=tmp_path,
        res_path="res://custom_path/hero_run",
        mode="animatedsprite2d",
    )

    assert (dest_dir / "hero_run_animatedsprite2d_player.gd").exists()
    script_content_anim = (
        dest_dir / "hero_run_animatedsprite2d_player.gd"
    ).read_text(encoding="utf-8")
    assert "extends AnimatedSprite2D" in script_content_anim
    assert 'preload("res://custom_path/hero_run/sheet.png")' in script_content_anim
