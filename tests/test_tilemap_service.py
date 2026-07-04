import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_autotile_engine_layouts_describe_godot_and_rpg_maker_tiles():
    from services.tilemap_service import build_autotile_engine_layouts, build_tilemap_engine_manifest

    layouts = build_autotile_engine_layouts(16, 16)
    manifest = build_tilemap_engine_manifest("autotile_16", "tiles.png", 16, 16, 4, 4, {})

    assert layouts["godot"]["terrain_set"] == "matches_sides"
    assert layouts["rpg_maker"]["format"] == "A2-compatible-16tile-subset"
    assert len(layouts["godot"]["tiles"]) == 16
    assert layouts["godot"]["tiles"][15]["open_neighbors"] == {
        "north": False,
        "south": False,
        "east": False,
        "west": False,
    }
    assert layouts["rpg_maker"]["tiles"][0]["tile_id"] == "A2_00"
    assert manifest["schema"] == "spriteforge.tilemap_engine_manifest.v1"
    assert manifest["import"]["godot"]["resource_type"] == "TileSet"
    assert manifest["tiles"][0]["rect"] == {"x": 0, "y": 0, "w": 16, "h": 16}
    assert manifest["tiles"][0]["godot"]["atlas_coords"] == [0, 0]
    assert manifest["tiles"][0]["rpg_maker"]["tile_id"] == "A2_00"
    assert manifest["collision"]["shapes"][0]["shape"] == "rectangle"


def test_autotile_generation_writes_engine_layout_metadata(tmp_path):
    import services.tilemap_service
    from services.tilemap_service import TilemapService

    old_root = services.tilemap_service.ROOT
    try:
        services.tilemap_service.ROOT = tmp_path
        Image.new("RGBA", (16, 16), (20, 120, 40, 255)).save(tmp_path / "base.png")
        Image.new("RGBA", (16, 16), (120, 70, 20, 255)).save(tmp_path / "border.png")

        result = TilemapService.generate_16_autotiles("base.png", "border.png", "tiles.png")
        metadata = json.loads((tmp_path / "tiles.json").read_text(encoding="utf-8"))

        assert result["ok"] is True
        assert result["metadata_path"] == "tiles.json"
        assert metadata["engine_layouts"]["godot"]["tile_layout"] == "4x4"
        assert len(metadata["engine_layouts"]["rpg_maker"]["tiles"]) == 16
        assert metadata["engine_manifest"]["import"]["tiled"]["tilecount"] == 16
        assert metadata["engine_manifest"]["tiles"][15]["godot"]["atlas_coords"] == [3, 3]
        assert metadata["engine_manifest"]["collision"]["default"] == "solid_on_border_tiles"
    finally:
        services.tilemap_service.ROOT = old_root


def test_wang_generation_writes_engine_manifest(tmp_path):
    import services.tilemap_service
    from services.tilemap_service import TilemapService

    old_root = services.tilemap_service.ROOT
    try:
        services.tilemap_service.ROOT = tmp_path
        for name, color in {
            "north": (255, 0, 0, 255),
            "east": (0, 255, 0, 255),
            "south": (0, 0, 255, 255),
            "west": (255, 255, 0, 255),
        }.items():
            Image.new("RGBA", (16, 16), color).save(tmp_path / f"{name}.png")

        result = TilemapService.generate_wang_tiles("north.png", "east.png", "south.png", "west.png", "wang.png")
        metadata = json.loads((tmp_path / "wang.json").read_text(encoding="utf-8"))

        assert result["ok"] is True
        assert metadata["engine_manifest"]["type"] == "wang_16"
        assert metadata["engine_manifest"]["import"]["godot"]["terrain_set_mode"] == "wang_edge_labels"
        assert metadata["engine_manifest"]["tiles"][0]["godot"]["terrain_peering_bits"]["north"] == "south"
        assert metadata["engine_manifest"]["tiles"][0]["rpg_maker"]["tile_id"] == "WANG_00"
        assert len(metadata["engine_manifest"]["collision"]["shapes"]) == 16
    finally:
        services.tilemap_service.ROOT = old_root
