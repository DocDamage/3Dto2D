import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add app directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from services.project_service import ProjectService

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
