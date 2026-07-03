import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _write_test_sheet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((4, 8, 20, 28), fill=(200, 40, 80, 255))
    draw.rectangle((38, 6, 56, 28), fill=(40, 140, 220, 255))
    img.save(path)


def test_training_dataset_builder_slices_sheet_and_writes_captions(tmp_path):
    from services.training_dataset_service import build_training_dataset

    source = tmp_path / "owned_sakpix_assets"
    _write_test_sheet(source / "crimson_knight_walk_front_right.png")

    out = tmp_path / "dataset"
    result = build_training_dataset(
        source_dir=source,
        output_dir=out,
        trigger="sakpix_style",
        base_caption="premium pixel art RPG character",
        cell_width=32,
        cell_height=32,
    )

    assert result["schema"] == "spriteforge.training_dataset.v1"
    assert result["sample_count"] == 2
    assert result["source_image_count"] == 1

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sample_count"] == 2
    assert manifest["samples"][0]["action"] == "walk"
    assert manifest["samples"][0]["direction"] == "front_right"
    assert manifest["samples"][0]["caption"].startswith("sakpix_style, premium pixel art RPG character")

    images = sorted((out / "images").glob("*.png"))
    captions = sorted((out / "captions").glob("*.txt"))
    assert len(images) == 2
    assert len(captions) == 2
    assert "transparent background" in captions[0].read_text(encoding="utf-8")
    assert (out / "palette.json").exists()
    assert (out / "README_TRAINING_DATASET.md").exists()


def test_training_dataset_action_builds_unified_command(tmp_path):
    from services.web_helpers_cmd import build_action_command

    title, cmd = build_action_command({
        "action": "training_dataset",
        "source_dir": str(tmp_path / "assets"),
        "output": str(tmp_path / "dataset"),
        "trigger": "sakpix_style",
        "cell_size": "32x32",
        "base_caption": "premium pixel art RPG character",
    })

    assert title == "Build training dataset"
    assert cmd[1:] == [
        "spriteforge_unified.py",
        "training-dataset",
        "--source",
        str(tmp_path / "assets"),
        "--output",
        str(tmp_path / "dataset"),
        "--trigger",
        "sakpix_style",
        "--base-caption",
        "premium pixel art RPG character",
        "--cell-size",
        "32x32",
    ]


def test_training_dataset_keeps_duplicate_filenames_from_different_folders(tmp_path):
    from services.training_dataset_service import build_training_dataset

    source = tmp_path / "owned_sakpix_assets"
    _write_test_sheet(source / "hero_a" / "rotations" / "east.png")
    _write_test_sheet(source / "hero_b" / "rotations" / "east.png")

    out = tmp_path / "dataset"
    result = build_training_dataset(
        source_dir=source,
        output_dir=out,
        trigger="sakpix_style",
        base_caption="premium pixel art RPG character",
        cell_width=32,
        cell_height=32,
    )

    assert result["sample_count"] == 4
    images = sorted((out / "images").glob("*.png"))
    captions = sorted((out / "captions").glob("*.txt"))
    assert len(images) == 4
    assert len(captions) == 4
    assert len({p.name for p in images}) == 4
