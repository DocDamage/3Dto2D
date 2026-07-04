import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _make_sprite_dir(tmp_path: Path) -> Path:
    sprite_dir = tmp_path / "sprite"
    frames_dir = sprite_dir / "frames_processed"
    frames_dir.mkdir(parents=True)
    colors = [(255, 0, 255, 0), (255, 0, 0, 255), (0, 255, 0, 255)]
    for index, color in enumerate(colors):
        Image.new("RGBA", (8, 8), color).save(frames_dir / f"frame_{index:04d}.png")
    (sprite_dir / "sheet.json").write_text(
        json.dumps(
            {
                "image": "sheet.png",
                "animation": "idle",
                "frame_width": 8,
                "frame_height": 8,
                "frame_count": len(colors),
                "fps": 6,
            }
        ),
        encoding="utf-8",
    )
    return sprite_dir


def _make_retimed_sprite_dir(tmp_path: Path) -> Path:
    sprite_dir = _make_sprite_dir(tmp_path)
    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
    meta["frames"] = [
        {"name": "anticipation", "duration_ms": 150},
        {"name": "impact", "duration_ms": 300},
        {"name": "recover"},
    ]
    (sprite_dir / "sheet.json").write_text(json.dumps(meta), encoding="utf-8")
    return sprite_dir


def test_export_animation_writes_engine_ready_manifest(tmp_path):
    from services.animated_export_service import export_animation

    result = export_animation(_make_sprite_dir(tmp_path), "lottie")
    manifest_path = Path(result["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["schema"] == "spriteforge.animated_export.v1"
    assert manifest["schema"] == "spriteforge.animated_export.v1"
    assert manifest["format"] == "lottie"
    assert manifest["frame_count"] == 3
    assert manifest["fps"] == 6.0
    assert manifest["duration_seconds"] == 0.501
    assert manifest["frame_width"] == 8
    assert manifest["frame_height"] == 8
    assert manifest["engine_ready"]["web"] is True
    assert manifest["engine_import"]["texture_filter"] == "nearest"
    assert manifest["engine_import"]["web"]["element_hint"] == "lottie-web"
    assert len(manifest["frames"]) == 3
    
    # Lottie format_capabilities checks
    caps = manifest["format_capabilities"]
    assert caps["schema"] == "spriteforge.animated_export_format.v1"
    assert caps["format"] == "lottie"
    assert caps["animated_raster"] is False
    assert caps["runtime_asset"] is False
    assert caps["metadata_asset"] is True
    assert caps["transparent_animation"] is True
    assert caps["engine_targets"] == {"godot": False, "unity": False, "web": True}


def test_export_animation_manifest_preserves_retimed_frame_durations(tmp_path):
    from services.animated_export_service import export_animation

    result = export_animation(_make_retimed_sprite_dir(tmp_path), "webp")
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["timing_source"] == "sheet.json duration_ms"
    assert manifest["engine_import"]["timing"]["mode"] == "per_frame_duration_ms"
    assert manifest["engine_import"]["godot"]["resource_type"] == "AnimatedTexture"
    assert manifest["duration_seconds"] == 0.617
    assert [frame["duration_ms"] for frame in manifest["frames"]] == [150, 300, 167]

    # WebP format_capabilities checks
    caps = manifest["format_capabilities"]
    assert caps["schema"] == "spriteforge.animated_export_format.v1"
    assert caps["format"] == "webp"
    assert caps["animated_raster"] is True
    assert caps["runtime_asset"] is True
    assert caps["metadata_asset"] is False
    assert caps["transparent_animation"] is True
    assert caps["engine_targets"] == {"godot": True, "unity": True, "web": True}
