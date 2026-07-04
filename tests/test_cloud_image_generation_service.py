import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_hardened_prompt_appends_sprite_constraints():
    from services.cloud_image_generation_service import hardened_prompt

    prompt = hardened_prompt("clockwork knight idle")

    assert "clockwork knight idle" in prompt
    assert "pixel art sprite" in prompt
    assert "solid magenta background" in prompt


def test_cloud_image_source_processing_builds_engine_ready_sheet(tmp_path):
    from services.cloud_image_generation_service import build_cloud_sprite_sheet

    src = tmp_path / "source.png"
    img = Image.new("RGBA", (128, 128), (255, 0, 255, 255))
    for y in range(36, 110):
        for x in range(48, 82):
            img.putpixel((x, y), (30, 140, 220, 255))
    img.save(src)

    out = tmp_path / "sprite"
    manifest = build_cloud_sprite_sheet(
        prompt="blue test hero",
        output_dir=out,
        provider="openai",
        source_images=[str(src)],
        cell_size="32x32",
        palette_colors=None,
        animation_name="idle",
    )

    meta = json.loads((out / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(out / "sheet.png").convert("RGBA")

    assert manifest["schema"] == "spriteforge.cloud_image_sprite.v1"
    assert manifest["source"] == "local_images"
    assert meta["frame_width"] == 32
    assert meta["frame_height"] == 32
    assert meta["frame_count"] == 1
    assert sheet.size == (32, 32)
    assert sheet.getbbox() is not None
    assert sheet.getpixel((0, 0))[3] == 0
    assert (out / "frames_processed" / "frame_0000.png").exists()
    assert (out / "cloud_generation.json").exists()


def test_cloud_image_sprite_parser_and_web_command_forwarding():
    from spriteforge_unified import build_parser
    from web_helpers import build_action_command

    parsed = build_parser().parse_args([
        "cloud-image-sprite",
        "--prompt",
        "mage idle",
        "--provider",
        "gemini",
        "--cell-size",
        "64x64",
        "--source-image",
        "output/raw.png",
    ])

    assert parsed.provider == "gemini"
    assert parsed.cell_size == "64x64"
    assert parsed.source_image == ["output/raw.png"]

    title, cmd = build_action_command({
        "action": "cloud_image_sprite",
        "prompt": "mage idle",
        "provider": "openai",
        "cell_size": "64x64",
        "source_images": ["output/raw.png"],
        "frames": 2,
        "no_palette_cleanup": True,
    })

    assert title == "Generate cloud image sprite"
    assert "cloud-image-sprite" in cmd
    assert "--provider" in cmd
    assert "--source-image" in cmd
    assert "--no-palette-cleanup" in cmd
