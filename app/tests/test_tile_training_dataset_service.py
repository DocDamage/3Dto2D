from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.tile_training_dataset_service import build_tile_training_dataset


def _save_rgba(path: Path, size: tuple[int, int], fill: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, fill).save(path)


def test_build_tile_dataset_filters_non_tile_sheets_and_caps_samples(tmp_path: Path) -> None:
    source = tmp_path / "source"
    # Four 128px cells, but the builder should keep only two because of the cap.
    _save_rgba(source / "Magic Forest" / "1. Grass tiles.png", (256, 256), (40, 160, 82, 255))
    # This is in a snowy theme, but the filename is props-only and should not become auto-tile data.
    _save_rgba(source / "Snowy Village" / "11. Village furniture and props.png", (256, 128), (180, 180, 210, 255))

    output = tmp_path / "dataset"
    manifest = build_tile_training_dataset(
        source_dir=source,
        output_dir=output,
        trigger="sakpix_tiles",
        cell_size="128x128",
        max_samples_per_source=2,
    )

    assert manifest["source_image_count"] == 1
    assert manifest["skipped_non_tile_count"] == 1
    assert manifest["sample_count"] == 2
    assert len(list((output / "images").glob("*.png"))) == 2
    assert len(list((output / "images").glob("*.txt"))) == 2

    captions = [path.read_text(encoding="utf-8") for path in sorted((output / "images").glob("*.txt"))]
    assert all("sakpix_tiles" in caption for caption in captions)
    assert all("magic forest" in caption for caption in captions)
    assert all("grass" in caption for caption in captions)
    assert all("auto-tile" in caption for caption in captions)
    assert all("seamless terrain tile" in caption for caption in captions)


def test_build_tile_dataset_auto_detects_209px_square_grid(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _save_rgba(source / "Cozy Farming" / "2. Grass path tiles.png", (418, 418), (70, 180, 88, 255))

    output = tmp_path / "dataset"
    manifest = build_tile_training_dataset(
        source_dir=source,
        output_dir=output,
        trigger="sakpix_tiles",
        cell_size="auto",
    )

    assert manifest["sample_count"] == 4
    assert manifest["samples"][0]["cell_size"] == "209x209"
    saved = sorted((output / "images").glob("*.png"))
    assert Image.open(saved[0]).size == (209, 209)

    manifest_path = output / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["dataset_kind"] == "autotile"
