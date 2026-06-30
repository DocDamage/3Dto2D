import sys
import os
from pathlib import Path
import pytest
from PIL import Image
import numpy as np

# Add app directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from services.sprite_service import SpriteService
from services.config_service import ConfigService
from services.model_service import ModelService
from web_helpers import build_action_command
from spriteforge_web import app

def test_chroma_keying():
    # Create a solid green image (chroma key)
    # Green = (0, 255, 0)
    img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
    
    # Apply chroma key with "auto" (should detect green corner)
    keyed = SpriteService.apply_chroma_key(img, "auto", tolerance=30, feather=0)
    arr = np.asarray(keyed)
    # Alpha should be 0 for all pixels
    assert np.all(arr[:, :, 3] == 0)

    # Keying with explicit color
    keyed_explicit = SpriteService.apply_chroma_key(img, (0, 255, 0), tolerance=30, feather=0)
    arr_explicit = np.asarray(keyed_explicit)
    assert np.all(arr_explicit[:, :, 3] == 0)

    # Keying with different color should retain alpha
    keyed_diff = SpriteService.apply_chroma_key(img, (255, 0, 0), tolerance=30, feather=0)
    arr_diff = np.asarray(keyed_diff)
    assert np.all(arr_diff[:, :, 3] == 255)

def test_auto_chroma_key_ignores_letterbox_bars():
    img = Image.new("RGBA", (120, 80), (0, 0, 0, 255))
    pixels = np.asarray(img).copy()
    pixels[20:80, :] = [0, 220, 20, 255]
    pixels[36:58, 48:72] = [210, 40, 180, 255]
    img = Image.fromarray(pixels, mode="RGBA")

    keyed = SpriteService.apply_chroma_key(img, "auto", tolerance=45, feather=0)
    arr = np.asarray(keyed)

    assert arr[5, 10, 3] == 0
    assert arr[30, 10, 3] == 0
    assert arr[45, 60, 3] == 255

def test_alpha_bbox():
    # Transparent image
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    # Draw a 20x20 solid square at (10, 20) to (29, 39)
    pixels = np.asarray(img).copy()
    pixels[20:40, 10:30] = [255, 255, 255, 255]
    img_with_box = Image.fromarray(pixels, mode="RGBA")

    bbox = SpriteService.alpha_bbox(img_with_box, threshold=8)
    assert bbox is not None
    l, t, r, b = bbox
    assert l == 10
    assert t == 20
    assert r == 30
    assert b == 40

def test_smooth_sequence():
    coords = [10.0, 10.0, 50.0, 10.0, 10.0]  # outlier 50.0 in the middle
    smoothed = SpriteService.smooth_sequence(coords, window_size=5)
    # The middle element (50.0) should be smoothed out by rolling median to 10.0
    assert smoothed[2] == 10.0

def test_blend_loop_seam():
    # Simple list of images with different colors to test blending
    frames = [Image.new("RGBA", (10, 10), (0, 0, 0, 255)) for _ in range(10)]
    frames[0] = Image.new("RGBA", (10, 10), (255, 0, 0, 255)) # Red
    frames[9] = Image.new("RGBA", (10, 10), (0, 0, 255, 255)) # Blue
    blended = SpriteService.blend_loop_seam(frames, blend_frames=2)
    assert len(blended) == 10
    # The last frame (index 9) should now be blended with the first frame (index 0), so it won't be pure blue
    assert blended[9] != frames[9]


def test_solidify_transparent_rgb():
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))  # fully transparent red
    solid = SpriteService.solidify_transparent_rgb(img, radius=1)
    arr = np.asarray(solid)
    # Alpha remains transparent, but colors are modified by solidify
    assert np.all(arr[:, :, 3] == 0)

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


def test_project_service_create_list_and_select(tmp_path, monkeypatch):
    from services import project_service as ps_mod
    from services.project_service import ProjectService

    projects_dir = tmp_path / "projects"
    state_path = tmp_path / "output" / "projects" / "project_state.json"
    monkeypatch.setattr(ps_mod, "ROOT", tmp_path)
    monkeypatch.setattr(ps_mod, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(ps_mod, "STATE_PATH", state_path)

    project = ProjectService.create_project(name="Hero Knight")

    assert project["name"] == "Hero_Knight"
    assert project["path"] == "projects/Hero_Knight/spriteforge_project.json"
    assert (projects_dir / "Hero_Knight" / "spriteforge_project.json").exists()
    assert (projects_dir / "Hero_Knight" / "queues").is_dir()

    listed = ProjectService.list_projects()
    assert len(listed) == 1
    assert listed[0]["name"] == "Hero_Knight"

    active = ProjectService.get_active_project()
    assert active is not None
    assert active["name"] == "Hero_Knight"

    resolved = ProjectService.resolve_project_path("projects/Hero_Knight/spriteforge_project.json")
    assert resolved == (projects_dir / "Hero_Knight" / "spriteforge_project.json").resolve()
    assert ProjectService.resolve_project_path(str(tmp_path / "outside.json")) is None
    assert ProjectService.item_matches_project(
        {"project_path": "projects/Hero_Knight/spriteforge_project.json"},
        {
            "project_name": "Hero_Knight",
            "project_path": "projects/Hero_Knight/spriteforge_project.json",
            "project_root": "projects/Hero_Knight",
        },
    )
    assert ProjectService.item_matches_project(
        {"path": "output/Hero_Knight_walk_right_sprite", "name": "Hero_Knight_walk_right_sprite"},
        {
            "project_name": "Hero_Knight",
            "project_path": "projects/Hero_Knight/spriteforge_project.json",
            "project_root": "projects/Hero_Knight",
        },
    )
    assert not ProjectService.item_matches_project(
        {"path": "output/Other_walk_right_sprite", "name": "Other_walk_right_sprite"},
        {
            "project_name": "Hero_Knight",
            "project_path": "projects/Hero_Knight/spriteforge_project.json",
            "project_root": "projects/Hero_Knight",
        },
    )


def test_sprite_outputs_project_filter(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    output = tmp_path / "output"
    hero = output / "hero_idle"
    other = output / "other_idle"
    hero.mkdir(parents=True)
    other.mkdir(parents=True)
    (hero / "sheet.json").write_text(json.dumps({
        "frame_count": 1,
        "fps": 12,
        "frame_width": 64,
        "frame_height": 64,
        "columns": 1,
        "rows": 1,
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    }), encoding="utf-8")
    (other / "sheet.json").write_text(json.dumps({
        "frame_count": 1,
        "fps": 12,
        "frame_width": 64,
        "frame_height": 64,
        "columns": 1,
        "rows": 1,
    }), encoding="utf-8")
    monkeypatch.setattr(web_mod, "OUTPUT", output)

    rows = web_mod.sprite_outputs(20, {
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert len(rows) == 1
    assert rows[0]["name"] == "hero_idle"


def test_sprite_outputs_includes_project_local_sprites(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    local_sprite = tmp_path / "projects" / "hero" / "sprites" / "hero_walk_fixed"
    global_sprite = tmp_path / "output" / "global_idle"
    local_sprite.mkdir(parents=True)
    global_sprite.mkdir(parents=True)
    (local_sprite / "sheet.json").write_text(json.dumps({
        "frame_count": 1,
        "fps": 12,
        "frame_width": 64,
        "frame_height": 64,
        "columns": 1,
        "rows": 1,
    }), encoding="utf-8")
    (global_sprite / "sheet.json").write_text(json.dumps({
        "frame_count": 1,
        "fps": 12,
        "frame_width": 64,
        "frame_height": 64,
        "columns": 1,
        "rows": 1,
    }), encoding="utf-8")

    rows = web_mod.sprite_outputs(20, {
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert [row["name"] for row in rows] == ["hero_walk_fixed"]
    assert rows[0]["path"] == "projects/hero/sprites/hero_walk_fixed"


def test_release_listing_project_filter(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    hero_release = tmp_path / "projects" / "hero" / "releases" / "hero_pack"
    other_release = tmp_path / "releases" / "global_pack"
    hero_release.mkdir(parents=True)
    other_release.mkdir(parents=True)
    (hero_release / "manifest.json").write_text(json.dumps({
        "schema": "spriteforge_release_v12",
        "name": "hero_pack",
        "created_at": "2026-06-25T12:00:00",
        "sprite_count": 2,
    }), encoding="utf-8")
    (hero_release.with_suffix(".zip")).write_text("zip bytes", encoding="utf-8")
    (other_release / "manifest.json").write_text(json.dumps({
        "schema": "spriteforge_release_v12",
        "name": "global_pack",
        "created_at": "2026-06-25T12:00:00",
        "sprite_count": 1,
    }), encoding="utf-8")

    rows = web_mod._list_releases({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert [row["name"] for row in rows] == ["hero_pack"]
    assert rows[0]["path"] == "projects/hero/releases/hero_pack"
    assert rows[0]["zip_path"] == "projects/hero/releases/hero_pack.zip"


def test_pack_listing_project_filter(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    hero_pack = tmp_path / "projects" / "hero"
    global_pack = tmp_path / "output" / "packs" / "global"
    hero_pack.mkdir(parents=True)
    global_pack.mkdir(parents=True)
    (hero_pack / "pack_manifest.json").write_text(json.dumps({
        "schema": "spriteforge_pack.v1",
        "pack_name": "hero",
        "created_at": "2026-06-25T12:00:00",
        "actions": ["idle", "walk"],
        "directions": ["right"],
        "entries": [{"action": "idle"}, {"action": "walk"}],
    }), encoding="utf-8")
    (global_pack / "pack_manifest.json").write_text(json.dumps({
        "schema": "spriteforge_pack.v1",
        "pack_name": "global",
        "created_at": "2026-06-25T12:00:00",
        "entries": [],
    }), encoding="utf-8")

    rows = web_mod._list_packs({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert [row["name"] for row in rows] == ["hero"]
    assert rows[0]["path"] == "projects/hero"
    assert rows[0]["manifest_path"] == "projects/hero/pack_manifest.json"
    assert rows[0]["entries"] == 2


def test_quality_listing_project_filter_and_source_path(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    project_sprite = tmp_path / "projects" / "hero" / "sprites" / "hero_walk"
    project_quality = tmp_path / "projects" / "hero" / "quality" / "hero_walk"
    global_quality = tmp_path / "output" / "quality" / "other_walk"
    project_sprite.mkdir(parents=True)
    project_quality.mkdir(parents=True)
    global_quality.mkdir(parents=True)
    (project_sprite / "sheet.json").write_text("{}", encoding="utf-8")
    (project_quality / "qa_report.json").write_text(json.dumps({
        "metrics": {"loop_seam_rmse": 12.5, "foot_y_stdev_px": 1.25},
        "issues": [{"level": "warn", "code": "loop", "message": "Loop seam"}],
    }), encoding="utf-8")
    (project_quality / "qa_report.html").write_text("<html></html>", encoding="utf-8")
    (global_quality / "qa_report.json").write_text(json.dumps({
        "metrics": {},
        "issues": [],
    }), encoding="utf-8")

    rows = web_mod._list_quality_reports({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert [row["name"] for row in rows] == ["hero_walk"]
    assert rows[0]["path"] == "projects/hero/quality/hero_walk"
    assert rows[0]["source_path"] == "projects/hero/sprites/hero_walk"
    assert rows[0]["html_url"] == "/file/projects/hero/quality/hero_walk/qa_report.html"
    assert rows[0]["issue_count"] == 1


def test_reference_listing_project_filter_and_global_fallback(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "UPLOADS", tmp_path / "input")

    hero_refs = tmp_path / "projects" / "hero" / "references"
    other_refs = tmp_path / "projects" / "other" / "references"
    global_refs = tmp_path / "input"
    hero_refs.mkdir(parents=True)
    other_refs.mkdir(parents=True)
    global_refs.mkdir(parents=True)
    (hero_refs / "hero_pose.png").write_bytes(b"png")
    (hero_refs / "notes.txt").write_text("ignore", encoding="utf-8")
    (other_refs / "other_pose.png").write_bytes(b"png")
    (global_refs / "global_walk.mp4").write_bytes(b"video")

    rows = web_mod._list_references({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })
    assert [row["name"] for row in rows] == ["hero_pose.png"]
    assert rows[0]["path"] == "projects/hero/references/hero_pose.png"
    assert rows[0]["kind"] == "image"

    global_rows = web_mod._list_references(None)
    assert [row["name"] for row in global_rows] == ["global_walk.mp4"]
    assert global_rows[0]["path"] == "input/global_walk.mp4"
    assert global_rows[0]["kind"] == "video"


def test_planning_listing_project_assets(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)

    project_dir = tmp_path / "projects" / "hero"
    prompt_dir = project_dir / "prompts"
    pose_dir = project_dir / "posepacks" / "idle_right"
    other_dir = tmp_path / "projects" / "other" / "prompts"
    prompt_dir.mkdir(parents=True)
    pose_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    (prompt_dir / "idle_right.json").write_text(json.dumps({
        "action": "idle",
        "direction": "right",
        "prompt": "hero idle",
    }), encoding="utf-8")
    (pose_dir / "posepack.json").write_text(json.dumps({
        "action": "idle",
        "direction": "right",
        "frames": [{"index": 0}, {"index": 1}],
    }), encoding="utf-8")
    (other_dir / "other.json").write_text(json.dumps({
        "action": "walk",
        "direction": "left",
    }), encoding="utf-8")

    rows = web_mod._list_planning_assets({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert [row["name"] for row in rows["prompts"]] == ["idle_right"]
    assert rows["prompts"][0]["path"] == "projects/hero/prompts/idle_right.json"
    assert rows["prompts"][0]["action"] == "idle"
    assert [row["name"] for row in rows["posepacks"]] == ["idle_right"]
    assert rows["posepacks"][0]["path"] == "projects/hero/posepacks/idle_right"
    assert rows["posepacks"][0]["manifest_path"] == "projects/hero/posepacks/idle_right/posepack.json"
    assert rows["posepacks"][0]["frames"] == 2
    assert web_mod._list_planning_assets(None) == {"prompts": [], "posepacks": []}


def test_project_workspace_counts_releases(tmp_path, monkeypatch):
    import web_helpers as web_mod

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(web_mod.ExperimentService, "get_history", staticmethod(lambda: []))

    release_dir = tmp_path / "projects" / "hero" / "releases" / "hero_pack"
    release_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text(json.dumps({
        "schema": "spriteforge_release_v12",
        "name": "hero_pack",
        "sprite_count": 1,
    }), encoding="utf-8")
    project_dir = tmp_path / "projects" / "hero"
    (project_dir / "references").mkdir(parents=True)
    (project_dir / "prompts").mkdir()
    (project_dir / "quality" / "hero_walk").mkdir(parents=True)
    (project_dir / "posepacks" / "idle_right").mkdir(parents=True)
    (project_dir / "pack_manifest.json").write_text(json.dumps({
        "schema": "spriteforge_pack.v1",
        "project_name": "hero",
    }), encoding="utf-8")
    (project_dir / "quality" / "hero_walk" / "qa_report.json").write_text(json.dumps({
        "metrics": {},
        "issues": [],
    }), encoding="utf-8")
    (project_dir / "references" / "hero_ref.png").write_bytes(b"png")
    (project_dir / "prompts" / "idle_right.json").write_text("{}", encoding="utf-8")
    (project_dir / "posepacks" / "idle_right" / "posepack.json").write_text("{}", encoding="utf-8")

    workspace = web_mod._project_workspace({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert workspace["releases"] == 1
    assert workspace["references"] == 1
    assert workspace["packs"] == 1
    assert workspace["quality"] == 1
    assert workspace["prompts"] == 1
    assert workspace["posepacks"] == 1


from unittest.mock import MagicMock, patch
import json
import time
import zipfile


@pytest.fixture
def flask_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_path_safety(tmp_path, monkeypatch, flask_client):
    import web_helpers as web_mod
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "WEB", tmp_path / "web")

    (tmp_path / "web").mkdir(parents=True, exist_ok=True)

    
    # 1. Allowed paths
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    allowed_file = output_dir / "sheet.png"
    allowed_file.touch()
    
    response = flask_client.get("/file/output/sheet.png")
    assert response.status_code != 403
    
    # 2. Path outside workspace (traversal)
    response = flask_client.get("/file/../../etc/passwd")
    assert response.status_code == 403

    # 3. Disallowed system path (e.g. .venv)
    response = flask_client.get("/file/.venv/pyvenv.cfg")
    assert response.status_code == 403


def test_upload_limits(flask_client):
    # 1. Exceeds 100MB
    large_data = b"x" * (101 * 1024 * 1024)
    import io
    response = flask_client.post(
        "/api/upload",
        data={"file": (io.BytesIO(large_data), "large.png")},
        content_type="multipart/form-data"
    )
    assert response.status_code in (413, 400)


def test_upload_routes_to_active_project_references(tmp_path, monkeypatch, flask_client):
    import web_helpers as web_mod
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "UPLOADS", tmp_path / "input")
    
    project_meta = {
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    }
    monkeypatch.setattr(
        web_mod.ProjectService,
        "metadata_for_path",
        staticmethod(lambda value: project_meta if value == "projects/hero/spriteforge_project.json" else None),
    )
    
    import io
    response = flask_client.post(
        "/api/upload",
        data={
            "active_project": "projects/hero/spriteforge_project.json",
            "file": (io.BytesIO(b"fake png bytes"), "hero ref.png")
        },
        content_type="multipart/form-data"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["relative"] == "projects/hero/references/hero_ref.png"
    assert (tmp_path / "projects" / "hero" / "references" / "hero_ref.png").read_bytes() == b"fake png bytes"


def test_experiment_clear_api_scopes_to_project(tmp_path, monkeypatch, flask_client):
    import services.experiment_service as es_mod
    import web_helpers as web_mod
    from services.experiment_service import ExperimentService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")

    hero_id = ExperimentService.append_run(
        prompt="hero",
        project_name="hero",
        project_path="projects/hero/spriteforge_project.json",
        project_root="projects/hero",
    )
    other_id = ExperimentService.append_run(
        prompt="other",
        project_name="other",
        project_path="projects/other/spriteforge_project.json",
        project_root="projects/other",
    )
    monkeypatch.setattr(
        web_mod.ProjectService,
        "metadata_for_path",
        staticmethod(lambda value: {
            "project_name": "hero",
            "project_path": "projects/hero/spriteforge_project.json",
            "project_root": "projects/hero",
        } if value else None),
    )

    response = flask_client.post(
        "/api/experiments/clear?project=projects%2Fhero%2Fspriteforge_project.json",
        data=json.dumps({"keep_starred": True}),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["removed"] == 1
    assert ExperimentService.get_run(hero_id) is None
    assert ExperimentService.get_run(other_id) is not None



def test_job_lifecycle(tmp_path):
    from services.job_service import JobService
    import services.job_service

    temp_history = tmp_path / "job_history.json"

    with patch("services.job_service.HISTORY_PATH", temp_history):
        # 1. Initially empty history
        assert JobService.get_history() == []

        # 2. Recovery transitions running -> failed
        running_job = {
            "id": "test-uuid-123",
            "title": "Running Job",
            "command": ["echo", "test"],
            "phase": "running",
            "progress": 50.0,
            "started_at": "2026-06-25 12:00:00",
            "finished_at": None,
            "exit_code": None,
            "pid": 1111,
            "logs": ["Starting"],
        }
        JobService._save_history([running_job])

        JobService.recover_interrupted_jobs()

        history = JobService.get_history()
        assert len(history) == 1
        assert history[0]["phase"] == "failed"
        assert history[0]["exit_code"] == -99
        assert history[0]["finished_at"] is not None

        # 3. Start a new job and cancel it
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.return_value = None
        mock_proc.stdout = ["progress: 50%", "step: 5/10"]
        
        import threading
        wait_event = threading.Event()
        mock_proc.wait.side_effect = lambda: (wait_event.wait(), 0)[1]

        # Reset active job
        JobService._active_job = None

        with patch("subprocess.Popen", return_value=mock_proc):
            ok, job_id = JobService.start_job(
                "New Test Job", ["echo", "hello"], metadata={"project_name": "hero"}
            )
            assert ok is True
            assert len(job_id) == 36

            # Wait briefly for worker thread to record PID
            for _ in range(20):
                active = JobService.get_active_job()
                if active and active.get("pid") is not None:
                    break
                time.sleep(0.05)

            active = JobService.get_active_job()
            assert active is not None
            assert active["pid"] == 9999
            assert active["metadata"]["project_name"] == "hero"

            with patch(
                "services.job_service.JobService._kill_process_tree"
            ) as mock_kill:
                cancelled = JobService.cancel_job(job_id)
                assert cancelled is True
                mock_kill.assert_called_once_with(9999)
                
                # Release wait event so the worker thread finishes
                wait_event.set()
                # Wait for active job to finish cleaning up
                for _ in range(20):
                    if JobService.get_active_job() is None:
                        break
                    time.sleep(0.05)

                hist = JobService.get_history()
                c_job = next(j for j in hist if j["id"] == job_id)
                assert c_job["phase"] == "cancelled"
                assert c_job["exit_code"] == -1


def test_job_history_retention(tmp_path):
    import services.job_service
    from services.job_service import JobService

    temp_history = tmp_path / "job_history.json"
    jobs = [{"id": str(i), "phase": "completed", "logs": []} for i in range(5)]

    with patch("services.job_service.HISTORY_PATH", temp_history), patch("services.job_service.MAX_JOB_HISTORY", 3):
        JobService._save_history(jobs)
        history = JobService.get_history()

    assert [job["id"] for job in history] == ["0", "1", "2"]


def test_release_manifests(tmp_path):
    from spriteforge_final import build_parser
    import json
    import zipfile

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
    import json
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


def test_pack_manifest_includes_project_metadata(tmp_path, monkeypatch):
    import argparse
    import json
    import spriteforge_pack as pack_mod

    project_dir = tmp_path / "projects" / "hero"
    project_dir.mkdir(parents=True)
    (project_dir / "spriteforge_project.json").write_text(json.dumps({
        "schema": "spriteforge_project_v1",
        "name": "hero",
    }), encoding="utf-8")
    monkeypatch.setattr(pack_mod, "ROOT", tmp_path)
    monkeypatch.setattr(pack_mod, "ACTION_TEMPLATES", {"idle": {"frames": 2}})
    monkeypatch.setattr(pack_mod, "DIRECTIONS", {"right": "Right"})
    monkeypatch.setattr(pack_mod, "build_prompt", lambda **kwargs: {
        "positive": "hero idle",
        "negative": "",
        "recommended_frames": 2,
    })
    monkeypatch.setattr(pack_mod, "make_posepack", lambda action, direction, frames, size, output: output.mkdir(parents=True))

    args = argparse.Namespace(
        name="hero",
        output=str(project_dir),
        actions="idle",
        directions="right",
        character="hero",
        style="sprite",
        background="green",
        extra="",
        reference=False,
        pose_guided=True,
        posepacks=True,
        pose_size=64,
    )

    pack_mod.cmd_init(args)

    manifest = json.loads((project_dir / "pack_manifest.json").read_text(encoding="utf-8"))
    assert manifest["project_name"] == "hero"
    assert manifest["project_path"] == "projects/hero/spriteforge_project.json"
    assert manifest["project_root"] == "projects/hero"
    assert (project_dir / "prompts" / "idle_right.json").exists()
    assert (project_dir / "posepacks" / "idle_right").exists()


def test_godot_export(tmp_path):
    from services.export_service import ExportService
    import json
    import shutil

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
