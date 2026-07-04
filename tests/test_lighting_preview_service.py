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
    normal_dir = sprite_dir / "frames_normal"
    specular_dir = sprite_dir / "frames_specular"
    ao_dir = sprite_dir / "frames_ao"
    frames_dir.mkdir(parents=True)
    normal_dir.mkdir(parents=True)
    specular_dir.mkdir(parents=True)
    ao_dir.mkdir(parents=True)
    for index, color in enumerate([(255, 0, 0, 255), (0, 128, 255, 255)]):
        Image.new("RGBA", (8, 8), color).save(frames_dir / f"frame_{index:04d}.png")
        Image.new("RGBA", (8, 8), (128, 128, 255, 255)).save(normal_dir / f"frame_{index:04d}.png")
        Image.new("RGBA", (8, 8), (220, 220, 220, 255)).save(specular_dir / f"frame_{index:04d}.png")
        Image.new("RGBA", (8, 8), (200, 200, 200, 255)).save(ao_dir / f"frame_{index:04d}.png")
    (sprite_dir / "sheet.json").write_text(
        json.dumps(
            {
                "image": "sheet.png",
                "animation": "idle",
                "frame_width": 8,
                "frame_height": 8,
                "frame_count": 2,
                "fps": 8,
            }
        ),
        encoding="utf-8",
    )
    return sprite_dir


def test_export_lighting_preview_gif_writes_manifest(tmp_path):
    from services.lighting_preview_service import export_lighting_preview_gif

    result = export_lighting_preview_gif(_make_sprite_dir(tmp_path), light_x=0.8, light_y=-0.2)
    gif_path = Path(result["path"])
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["schema"] == "spriteforge.lighting_preview.v1"
    assert gif_path.exists()
    assert gif_path.suffix == ".gif"
    assert manifest["schema"] == "spriteforge.lighting_preview.v1"
    assert manifest["frame_count"] == 2
    assert manifest["fps"] == 8.0
    assert manifest["light"]["x"] == 0.8
    assert manifest["lighting_maps"]["schema"] == "spriteforge.lighting_maps.v1"
    assert manifest["lighting_maps"]["server_bake"] == "normal_specular_ao"
    assert manifest["lighting_maps"]["normal"]["frame_count"] == 2
    assert manifest["rendering"]["schema"] == "spriteforge.lighting_preview_render.v1"
    assert manifest["rendering"]["normal_compositing"] is True
    assert manifest["rendering"]["specular_compositing"] is True
    assert manifest["rendering"]["ao_compositing"] is True
    assert manifest["rendering"]["texture_filter"] == "nearest"
    assert manifest["engine_ready"]["godot"] is True
