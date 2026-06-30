"""Smoke tests for SpriteForge Studio v12.

These tests focus on integration-level sanity checks that don't require
ComfyUI, GPU, or any generated outputs to exist.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
GOLDEN_DEMO = APP / "examples" / "prebuilt_demo_sprite"
PYTHON = str(APP / ".venv" / "Scripts" / "python.exe") if (APP / ".venv" / "Scripts" / "python.exe").exists() else sys.executable

sys.path.insert(0, str(APP))


# ---------------------------------------------------------------------------
# Web UI smoke
# ---------------------------------------------------------------------------

def test_web_smoke():
    """spriteforge_web.py --smoke should exit 0 when web assets are present."""
    result = subprocess.run(
        [PYTHON, str(APP / "spriteforge_web.py"), "--smoke"],
        capture_output=True,
        text=True,
        cwd=str(APP),
    )
    assert result.returncode == 0, (
        f"Web smoke failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    )
    assert "passed" in result.stdout.lower()


def test_cross_platform_launchers():
    launchers = {
        "start.sh": "spriteforge_launcher.py \"$@\"",
        "start.command": "spriteforge_launcher.py \"$@\"",
        "run_demo_no_gpu.sh": "spriteforge_launcher.py --demo",
        "start_first_run_wizard.sh": "spriteforge_launcher.py --wizard",
    }
    for name, expected in launchers.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env sh")
        assert "cd \"$SCRIPT_DIR/app\"" in text
        assert expected in text


def test_keyboard_shortcuts_module_loaded():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "keyboard_shortcuts.js").read_text(encoding="utf-8")

    assert "/web/js/keyboard_shortcuts.js" in index
    for shortcut in ["'g'", "'q'", "'s'", "'arrowleft'", "'arrowright'"]:
        assert shortcut in script
    assert "shortcutTargetAllowsTyping" in script


def test_theme_toggle_assets_loaded():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "theme_toggle.js").read_text(encoding="utf-8")
    css = (APP / "web" / "theme.css").read_text(encoding="utf-8")

    assert "/web/theme.css" in index
    assert "/web/js/theme_toggle.js" in index
    assert 'id="themeToggle"' in index
    assert "spriteforgeTheme" in script
    assert "theme-light" in css


def test_mobile_nav_assets_loaded():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "mobile_nav.js").read_text(encoding="utf-8")
    css = (APP / "web" / "mobile_nav.css").read_text(encoding="utf-8")

    assert "/web/mobile_nav.css" in index
    assert "/web/js/mobile_nav.js" in index
    assert 'id="mobileRailToggle"' in index
    assert "mobile-rail-open" in script
    assert "@media (max-width: 760px)" in css


def test_drag_drop_assets_loaded():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "drag_drop.js").read_text(encoding="utf-8")
    css = (APP / "web" / "drag_drop.css").read_text(encoding="utf-8")

    assert "/web/drag_drop.css" in index
    assert "/web/js/drag_drop.js" in index
    assert "referenceDropTarget" in script
    assert "qualityDropTarget" in script
    assert ".drop-target-card" in css


def test_power_of_two_web_option_forwarded():
    from web_helpers import build_action_command
    from spriteforge_unified import build_parser
    generate_html = (APP / "web" / "components" / "generate.html").read_text(encoding="utf-8")
    convert_html = (APP / "web" / "components" / "convert.html").read_text(encoding="utf-8")

    _, generate_cmd = build_action_command({
        "action": "generate_sprite",
        "power_of_two": True,
        "quality_check": False,
    })
    _, convert_cmd = build_action_command({
        "action": "convert_video",
        "input": "test.mp4",
        "power_of_two": True,
    })

    assert "--power-of-two" in generate_cmd
    assert "--power-of-two" in convert_cmd
    assert 'name="power_of_two"' in generate_html
    assert 'name="power_of_two"' in convert_html
    parsed = build_parser().parse_args(["generate-sprite", "--power-of-two"])
    assert parsed.power_of_two is True



def test_compare_smoke(tmp_path):
    """compare_dirs() on two minimal fake sprite dirs writes a report."""
    from spriteforge_compare import compare_dirs

    def _make_sprite_dir(name: str, color: tuple) -> Path:
        d = tmp_path / name
        frames_dir = d / "frames"
        frames_dir.mkdir(parents=True)
        img = Image.new("RGBA", (64, 64), color + (255,))
        img.save(frames_dir / "frame_000.png")
        img.save(frames_dir / "frame_001.png")
        # sheet.json
        sheet = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
        sheet.paste(img, (0, 0))
        sheet.paste(img, (64, 0))
        sheet.save(d / "sheet.png")
        (d / "sheet.json").write_text(json.dumps({
            "frame_width": 64, "frame_height": 64,
            "frame_count": 2, "columns": 2, "rows": 1,
            "fps": 12, "image": "sheet.png",
        }), encoding="utf-8")
        return d

    a = _make_sprite_dir("sprite_a", (255, 0, 0))
    b = _make_sprite_dir("sprite_b", (0, 255, 0))
    out = tmp_path / "compare_out"

    data = compare_dirs(a, b, out)

    assert (out / "compare_report.json").exists()
    assert (out / "compare_report.html").exists()
    assert data["compared_frames"] == 2
    assert data["mean_diff"] > 0


def test_golden_demo_sprite_metadata():
    """The checked-in demo sprite remains a valid known-good fixture."""
    meta = json.loads((GOLDEN_DEMO / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(GOLDEN_DEMO / meta["image"])
    frames = sorted((GOLDEN_DEMO / "frames_processed").glob("frame_*.png"))

    assert sheet.size == (
        meta["frame_width"] * meta["columns"],
        meta["frame_height"] * meta["rows"],
    )
    assert meta["animation"] == "demo_idle"
    assert meta["frame_count"] == 16
    assert len(meta["frames"]) == meta["frame_count"]
    assert len(frames) == meta["frame_count"]
    assert 1 <= meta["fps"] <= 60
    assert (GOLDEN_DEMO / "preview.gif").exists()
    assert (GOLDEN_DEMO / "report.html").exists()

    for frame in meta["frames"]:
        assert frame["w"] == meta["frame_width"]
        assert frame["h"] == meta["frame_height"]
        assert 0 <= frame["x"] < sheet.width
        assert 0 <= frame["y"] < sheet.height
        assert frame["x"] + frame["w"] <= sheet.width
        assert frame["y"] + frame["h"] <= sheet.height


def test_golden_demo_quality_and_compare(tmp_path):
    """Golden fixture produces bounded QC metrics and a compare report."""
    from spriteforge_compare import compare_dirs
    from spriteforge_quality import quality_report

    sprite_a = tmp_path / "demo_a"
    sprite_b = tmp_path / "demo_b"
    shutil.copytree(GOLDEN_DEMO, sprite_a)
    shutil.copytree(GOLDEN_DEMO, sprite_b)

    quality = quality_report(sprite_a, tmp_path / "quality", None)
    assert 0 <= float(quality["score"]) <= 100
    assert quality["grade"] in {"A", "B", "C", "D"}
    assert (tmp_path / "quality" / "quality_report.json").exists()
    assert (tmp_path / "quality" / "quality_report.html").exists()

    compare = compare_dirs(sprite_a, sprite_b, tmp_path / "compare")
    assert compare["compared_frames"] == 16
    assert compare["mean_diff"] == 0
    assert (tmp_path / "compare" / "compare_report.json").exists()
    assert (tmp_path / "compare" / "compare_report.html").exists()


def test_golden_demo_release_zip_contents(tmp_path):
    """Release packaging includes the expected files for the golden fixture."""
    from spriteforge_final import build_parser

    sprite_dir = tmp_path / "prebuilt_demo_sprite"
    shutil.copytree(GOLDEN_DEMO, sprite_dir)
    out_dir = tmp_path / "demo_release"

    parser = build_parser()
    args = parser.parse_args([
        "release",
        "--name",
        "golden_demo",
        "--sprite-dir",
        str(sprite_dir),
        "--output",
        str(out_dir),
        "--zip",
    ])

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
            "next_step": {"step": "None", "reason": "none"},
        },
        "sprites": [],
    }
    with patch("spriteforge_final.preflight_data", return_value=mock_preflight):
        args.func(args)

    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "sprites" / "prebuilt_demo_sprite" / "sheet.json").exists()
    assert (out_dir / "sprites" / "prebuilt_demo_sprite" / "sheet.png").exists()

    zip_file_path = out_dir.with_suffix(".zip")
    assert zip_file_path.exists()
    with zipfile.ZipFile(zip_file_path, "r") as zf:
        names = set(zf.namelist())
    assert "demo_release/manifest.json" in names
    assert "demo_release/sprites/prebuilt_demo_sprite/sheet.json" in names
    assert "demo_release/sprites/prebuilt_demo_sprite/sheet.png" in names


# ---------------------------------------------------------------------------
# Export validate smoke
# ---------------------------------------------------------------------------

def test_export_validate_smoke(tmp_path):
    """validate_export() passes for a well-formed sprite directory."""
    from spriteforge_engine_export import validate_export

    sprite_dir = tmp_path / "test_sprite"
    sprite_dir.mkdir()

    img = Image.new("RGBA", (128, 64), (100, 200, 100, 255))
    img.save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_width": 64, "frame_height": 64,
        "frame_count": 2, "columns": 2, "rows": 1,
        "fps": 12, "image": "sheet.png",
    }), encoding="utf-8")

    ok = validate_export(sprite_dir)
    assert ok, "validate_export should return True for a valid sprite dir"


def test_export_validate_bad_dimensions(tmp_path):
    """validate_export() fails when pixel dimensions don't match metadata."""
    from spriteforge_engine_export import validate_export

    sprite_dir = tmp_path / "bad_sprite"
    sprite_dir.mkdir()

    # Image is 64×64 but metadata says it should be 128×64
    img = Image.new("RGBA", (64, 64), (100, 200, 100, 255))
    img.save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_width": 64, "frame_height": 64,
        "frame_count": 2, "columns": 2, "rows": 1,
        "fps": 12, "image": "sheet.png",
    }), encoding="utf-8")


# ---------------------------------------------------------------------------
# Compare smoke
# ---------------------------------------------------------------------------

def test_compare_smoke(tmp_path):
    """compare_dirs() on two minimal fake sprite dirs writes a report."""
    from spriteforge_compare import compare_dirs

    def _make_sprite_dir(name: str, color: tuple) -> Path:
        d = tmp_path / name
        frames_dir = d / "frames"
        frames_dir.mkdir(parents=True)
        img = Image.new("RGBA", (64, 64), color + (255,))
        img.save(frames_dir / "frame_000.png")
        img.save(frames_dir / "frame_001.png")
        # sheet.json
        sheet = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
        sheet.paste(img, (0, 0))
        sheet.paste(img, (64, 0))
        sheet.save(d / "sheet.png")
        (d / "sheet.json").write_text(json.dumps({
            "frame_width": 64, "frame_height": 64,
            "frame_count": 2, "columns": 2, "rows": 1,
            "fps": 12, "image": "sheet.png",
        }), encoding="utf-8")
        return d

    a = _make_sprite_dir("sprite_a", (255, 0, 0))
    b = _make_sprite_dir("sprite_b", (0, 255, 0))
    out = tmp_path / "compare_out"

    data = compare_dirs(a, b, out)

    assert (out / "compare_report.json").exists()
    assert (out / "compare_report.html").exists()
    assert data["compared_frames"] == 2
    assert data["mean_diff"] > 0


def test_golden_demo_sprite_metadata():
    """The checked-in demo sprite remains a valid known-good fixture."""
    meta = json.loads((GOLDEN_DEMO / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(GOLDEN_DEMO / meta["image"])
    frames = sorted((GOLDEN_DEMO / "frames_processed").glob("frame_*.png"))

    assert sheet.size == (
        meta["frame_width"] * meta["columns"],
        meta["frame_height"] * meta["rows"],
    )
    assert meta["animation"] == "demo_idle"
    assert meta["frame_count"] == 16
    assert len(meta["frames"]) == meta["frame_count"]
    assert len(frames) == meta["frame_count"]
    assert 1 <= meta["fps"] <= 60
    assert (GOLDEN_DEMO / "preview.gif").exists()
    assert (GOLDEN_DEMO / "report.html").exists()

    for frame in meta["frames"]:
        assert frame["w"] == meta["frame_width"]
        assert frame["h"] == meta["frame_height"]
        assert 0 <= frame["x"] < sheet.width
        assert 0 <= frame["y"] < sheet.height
        assert frame["x"] + frame["w"] <= sheet.width
        assert frame["y"] + frame["h"] <= sheet.height


def test_golden_demo_quality_and_compare(tmp_path):
    """Golden fixture produces bounded QC metrics and a compare report."""
    from spriteforge_compare import compare_dirs
    from spriteforge_quality import quality_report

    sprite_a = tmp_path / "demo_a"
    sprite_b = tmp_path / "demo_b"
    shutil.copytree(GOLDEN_DEMO, sprite_a)
    shutil.copytree(GOLDEN_DEMO, sprite_b)

    quality = quality_report(sprite_a, tmp_path / "quality", None)
    assert 0 <= float(quality["score"]) <= 100
    assert quality["grade"] in {"A", "B", "C", "D"}
    assert (tmp_path / "quality" / "quality_report.json").exists()
    assert (tmp_path / "quality" / "quality_report.html").exists()

    compare = compare_dirs(sprite_a, sprite_b, tmp_path / "compare")
    assert compare["compared_frames"] == 16
    assert compare["mean_diff"] == 0
    assert (tmp_path / "compare" / "compare_report.json").exists()
    assert (tmp_path / "compare" / "compare_report.html").exists()


def test_golden_demo_release_zip_contents(tmp_path):
    """Release packaging includes the expected files for the golden fixture."""
    from spriteforge_final import build_parser

    sprite_dir = tmp_path / "prebuilt_demo_sprite"
    shutil.copytree(GOLDEN_DEMO, sprite_dir)
    out_dir = tmp_path / "demo_release"

    parser = build_parser()
    args = parser.parse_args([
        "release",
        "--name",
        "golden_demo",
        "--sprite-dir",
        str(sprite_dir),
        "--output",
        str(out_dir),
        "--zip",
    ])

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
            "next_step": {"step": "None", "reason": "none"},
        },
        "sprites": [],
    }
    with patch("spriteforge_final.preflight_data", return_value=mock_preflight):
        args.func(args)

    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "sprites" / "prebuilt_demo_sprite" / "sheet.json").exists()
    assert (out_dir / "sprites" / "prebuilt_demo_sprite" / "sheet.png").exists()

    zip_file_path = out_dir.with_suffix(".zip")
    assert zip_file_path.exists()
    with zipfile.ZipFile(zip_file_path, "r") as zf:
        names = set(zf.namelist())
    assert "demo_release/manifest.json" in names
    assert "demo_release/sprites/prebuilt_demo_sprite/sheet.json" in names
    assert "demo_release/sprites/prebuilt_demo_sprite/sheet.png" in names


# ---------------------------------------------------------------------------
# Export validate smoke
# ---------------------------------------------------------------------------

def test_export_validate_smoke(tmp_path):
    """validate_export() passes for a well-formed sprite directory."""
    from spriteforge_engine_export import validate_export

    sprite_dir = tmp_path / "test_sprite"
    sprite_dir.mkdir()

    img = Image.new("RGBA", (128, 64), (100, 200, 100, 255))
    img.save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_width": 64, "frame_height": 64,
        "frame_count": 2, "columns": 2, "rows": 1,
        "fps": 12, "image": "sheet.png",
    }), encoding="utf-8")

    ok = validate_export(sprite_dir)
    assert ok, "validate_export should return True for a valid sprite dir"


def test_export_validate_bad_dimensions(tmp_path):
    """validate_export() fails when pixel dimensions don't match metadata."""
    from spriteforge_engine_export import validate_export

    sprite_dir = tmp_path / "bad_sprite"
    sprite_dir.mkdir()

    # Image is 64×64 but metadata says it should be 128×64
    img = Image.new("RGBA", (64, 64), (100, 200, 100, 255))
    img.save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_width": 64, "frame_height": 64,
        "frame_count": 2, "columns": 2, "rows": 1,
        "fps": 12, "image": "sheet.png",
    }), encoding="utf-8")

    ok = validate_export(sprite_dir)
    assert not ok, "validate_export should return False when dimensions are wrong"
