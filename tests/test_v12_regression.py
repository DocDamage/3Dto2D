import os
import json
import shutil
import zipfile
from pathlib import Path
import pytest
from PIL import Image

import sys
ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.sprite_service import SpriteService
from services.pose_estimation_service import PoseEstimationService
from services.tilemap_service import TilemapService
from services.plugin_manager import PluginManager

def test_chroma_spill_suppression():
    # Create an image with transparent green fringe
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    # Add a pixel with a green spill on edge
    img.putpixel((5, 5), (100, 240, 100, 128)) # Semi-transparent greenish pixel
    
    # Run keying with green chroma key (0, 255, 0)
    cleaned = SpriteService.apply_chroma_key(img, key_color=(0, 255, 0), tolerance=141.0, feather=10.0)
    
    # Verify green color spill is suppressed (green channel scaled down on transparent edge)
    r, g, b, a = cleaned.getpixel((5, 5))
    assert g < 240 # Green channel must be reduced

def test_palette_snapping():
    # 1. Parse preset palettes
    pico8 = SpriteService.parse_palette("pico8")
    assert len(pico8) == 16
    assert pico8[0] == (0, 0, 0) # Black
    
    # 2. Parse custom palette string
    custom = SpriteService.parse_palette("FF0000, 00FF00, 0000FF")
    assert len(custom) == 3
    assert custom[0] == (255, 0, 0)
    assert custom[1] == (0, 255, 0)
    assert custom[2] == (0, 0, 255)
    
    # 3. Apply palette lock
    img = Image.new("RGBA", (4, 4), (250, 5, 5, 255)) # Near red
    locked = SpriteService.apply_palette_lock(img, custom)
    
    # Check it snapped to the exact red color in custom palette
    assert locked.getpixel((0, 0)) == (255, 0, 0, 255)

def test_autotile_compilation(tmp_path):
    base_tile = tmp_path / "base.png"
    border_tile = tmp_path / "border.png"
    output_tile = tmp_path / "output.png"
    
    Image.new("RGBA", (16, 16), (100, 100, 100, 255)).save(base_tile)
    Image.new("RGBA", (16, 16), (200, 200, 200, 255)).save(border_tile)
    
    # Mock ROOT path in TilemapService to run tests cleanly
    import services.tilemap_service
    old_root = services.tilemap_service.ROOT
    try:
        # Override ROOT for test path lookup
        services.tilemap_service.ROOT = tmp_path
        
        res = TilemapService.generate_16_autotiles(
            "base.png",
            "border.png",
            "output.png"
        )
        assert res["ok"]
        assert output_tile.exists()
        assert (tmp_path / "output.json").exists()
        
        # Load compiled sheet
        sheet = Image.open(output_tile)
        assert sheet.size == (64, 64) # 4x4 grid of 16x16 tiles
    finally:
        services.tilemap_service.ROOT = old_root

def test_plugin_hooks(tmp_path):
    # Write a test plugin dynamically
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    
    plugin_code = """
def on_qa_check(sprite_dir, report):
    report["suggestions"].append("Plugin suggestion!")
    report["score"] = 99.9
"""
    (plugins_dir / "my_test_plugin.py").write_text(plugin_code, encoding="utf-8")
    
    import services.plugin_manager
    old_root = services.plugin_manager.ROOT
    old_plugins = services.plugin_manager.PLUGINS_DIR
    try:
        services.plugin_manager.ROOT = tmp_path
        services.plugin_manager.PLUGINS_DIR = plugins_dir
        
        # Reset loader state to reload for test
        PluginManager._loaded = False
        
        report = {"suggestions": [], "score": 50.0}
        PluginManager.trigger_hook("on_qa_check", sprite_dir=tmp_path, report=report)
        
        assert "Plugin suggestion!" in report["suggestions"]
        assert report["score"] == 99.9
    finally:
        services.plugin_manager.ROOT = old_root
        services.plugin_manager.PLUGINS_DIR = old_plugins
        PluginManager._loaded = False
