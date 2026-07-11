import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))


def _sprite(tmp_path: Path) -> Path:
    sprite = tmp_path / "hero_idle"
    sprite.mkdir()
    (sprite / "sheet.json").write_text(
        json.dumps({
            "animation": "hero_idle",
            "frame_count": 4,
            "fps": 12,
            "frame_width": 32,
            "frame_height": 48,
            "columns": 4,
            "rows": 1,
            "image": "sheet.png",
        }),
        encoding="utf-8",
    )
    (sprite / "sheet.png").write_bytes(b"png")
    return sprite


def _preflight() -> dict:
    return {
        "generated_at": "2026-07-10T12:00:00",
        "checks": {
            "python": {"ok": True, "value": "python"},
            "git": {"ok": True, "value": "git"},
            "nvidia": {"ok": True, "label": "available"},
            "disk": {"ok": True, "free_gb": 100, "total_gb": 500},
            "comfy_dir": {"ok": True, "value": "comfy"},
            "comfy_output": {"ok": True, "value": "output"},
            "comfy_running": {"ok": False, "value": "offline"},
            "outputs": {"ok": True, "count": 1},
            "next_step": {"step": "Import", "reason": "Package is ready."},
        },
        "sprites": [],
    }


def test_release_web_command_forwards_and_validates_consumer_target():
    from services.web_helpers_cmd import build_action_command

    with patch("services.project_service.ProjectService.metadata_for_path", return_value={}):
        title, command = build_action_command({
            "action": "release_package",
            "name": "hero",
            "sprites": ["output/hero_idle"],
            "consumer_target": "Unreal",
        })

    assert title == "Build release package"
    assert command[command.index("--target") + 1] == "unreal"

    with patch("services.project_service.ProjectService.metadata_for_path", return_value={}):
        _, default_command = build_action_command({
            "action": "release_package",
            "sprites": ["output/hero_idle"],
        })
    assert default_command[default_command.index("--target") + 1] == "godot"

    with patch("services.project_service.ProjectService.metadata_for_path", return_value={}):
        with pytest.raises(ValueError, match="Unsupported release target"):
            build_action_command({
                "action": "release_package",
                "sprites": ["output/hero_idle"],
                "consumer_target": "console",
            })


def test_release_cli_target_defaults_to_godot_and_rejects_unknown_values():
    from spriteforge_final import build_parser

    parser = build_parser()
    args = parser.parse_args(["release", "--sprite-dir", "output/hero"])
    assert args.target == "godot"

    with pytest.raises(SystemExit):
        parser.parse_args(["release", "--target", "console"])


@pytest.mark.parametrize(
    ("target", "label", "marker"),
    [
        ("godot", "Godot", "AnimatedSprite2D"),
        ("unity", "Unity", "Sprite (2D and UI)"),
        ("unreal", "Unreal Engine", "Paper2D"),
        ("png", "PNG Images", "Engine-neutral image handoff"),
        ("web", "Web", "image-rendering: pixelated"),
    ],
)
def test_release_packages_have_target_specific_handoffs(tmp_path, target, label, marker):
    from spriteforge_final import build_parser

    sprite = _sprite(tmp_path)
    output = tmp_path / f"release_{target}"
    args = build_parser().parse_args([
        "release",
        "--name",
        f"hero_{target}",
        "--sprite-dir",
        str(sprite),
        "--output",
        str(output),
        "--target",
        target,
    ])

    with patch("spriteforge_final.preflight_data", return_value=_preflight()):
        args.func(args)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    handoff = manifest["handoff"]
    engine_import = handoff["engine_import"]
    guide = (output / "engine" / "TARGET_GUIDE.md").read_text(encoding="utf-8")
    sprite_notes = (output / "engine" / "hero_idle_import_notes.md").read_text(encoding="utf-8")
    readme = (output / "README.md").read_text(encoding="utf-8")

    assert manifest["consumer_target"] == target
    assert handoff["consumer_target"] == target
    assert handoff["target_guidance"]["path"] == "engine/TARGET_GUIDE.md"
    assert engine_import["target"] == target
    assert engine_import["target_label"] == label
    assert engine_import["guidance"] == "engine/TARGET_GUIDE.md"
    assert marker in guide
    assert label in sprite_notes
    assert "Frame size: 32x48" in sprite_notes
    assert f"targets **{label}** (`{target}`)" in readme


def test_make_release_readme_legacy_call_remains_supported():
    from services.final_service import make_release_readme

    readme = make_release_readme(
        "legacy",
        [{"name": "idle", "frame_count": 1, "fps": 12, "frame_width": 32, "frame_height": 32}],
        "2026-07-10",
    )

    assert "Godot:" in readme
    assert "Unity:" in readme
