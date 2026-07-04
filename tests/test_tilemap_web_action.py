import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_tilemap_web_action_builds_autotile_command():
    from services.web_helpers_cmd import build_action_command

    title, cmd = build_action_command({
        "action": "tilemap",
        "mode": "autotile_16",
        "base": "input/base.png",
        "border": "input/border.png",
        "output": "output/tilesets/grass.png",
    })

    assert title == "Generate tilemap sheet"
    assert "tilemap" in cmd
    assert "--mode" in cmd
    assert "autotile_16" in cmd
    assert "--base" in cmd
    assert "input/base.png" in cmd
    assert "--border" in cmd
    assert "input/border.png" in cmd


def test_tilemap_web_action_builds_wang_command():
    from services.web_helpers_cmd import build_action_command

    _title, cmd = build_action_command({
        "action": "tilemap",
        "mode": "wang_16",
        "north": "input/north.png",
        "east": "input/east.png",
        "south": "input/south.png",
        "west": "input/west.png",
        "tile_size": "32",
        "output": "output/tilesets/wang.png",
    })

    assert "wang_16" in cmd
    assert "--north" in cmd
    assert "input/north.png" in cmd
    assert "--east" in cmd
    assert "--south" in cmd
    assert "--west" in cmd
    assert "--tile-size" in cmd
    assert "32" in cmd
