import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_default_presets_include_trained_sakpix_character_families():
    from web_helpers import _get_presets

    presets = _get_presets()

    expected = {
        "SakPix Trained Hero Knight",
        "SakPix Trained Forest Ranger",
        "SakPix Trained Arcane Caster",
        "SakPix Trained Town NPC",
    }
    assert expected.issubset(presets.keys())

    for name in expected:
        preset = presets[name]
        assert "sakpix_style" in preset["character"]
        assert "trained SakPix" in preset["style"]
        assert preset["tier"] == "wan22_5b"
        assert preset["profile"] == "wan22_5b_3060_best"
        assert preset["default_actions"]
        assert preset["default_directions"]


def test_easy_mode_styles_surface_trained_sakpix_options():
    data = json.loads((APP / "config" / "easy_presets.json").read_text(encoding="utf-8"))

    styles = data["styles"]
    assert any("trained SakPix" in style and "side-view" in style for style in styles)
    assert any("trained SakPix" in style and "top-down RPG" in style for style in styles)


def test_archetype_browser_has_sakpix_set_like_filters():
    data = json.loads((APP / "config" / "character_archetypes.json").read_text(encoding="utf-8"))
    archetypes = data["archetypes"]
    sakpix_archetypes = [arc for arc in archetypes if "sakpix" in arc.get("tags", [])]

    assert len(sakpix_archetypes) >= 4
    assert {arc["id"] for arc in sakpix_archetypes} >= {
        "sakpix_trained_knight",
        "sakpix_trained_ranger",
        "sakpix_trained_caster",
        "sakpix_trained_villager",
    }
    assert all("sakpix_style" in arc["character"] for arc in sakpix_archetypes)


def test_training_lab_contains_tile_set_representation_controls():
    html = (APP / "web" / "components" / "training.html").read_text(encoding="utf-8")

    assert 'class="training-tabs"' in html
    assert 'data-training-tab="datasets"' in html
    assert 'data-training-tab="lora"' in html
    assert 'data-training-tab="tiles"' in html
    assert 'data-training-tab="path"' in html
    assert 'class="tile-set-reference-grid"' in html
    assert 'data-tile-preset="top_down_terrain"' in html
    assert 'data-tile-preset="dungeon_edges"' in html
    assert 'id="tileTrainingPreviewManifest"' in html
    assert 'id="tilemapGeneratorForm"' in html
    assert 'value="autotile_16"' in html
    assert 'value="wang_16"' in html
    assert "16-tile auto-tile sheet" in html


def test_training_lab_tabs_are_bound_without_global_subview_routing():
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert "function initTrainingTabs()" in js
    assert "initTrainingTabs();" in js
    assert "data-training-tab" in js
    assert "data-training-panel" in js


def test_mobile_css_stacks_training_grids():
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert "@media(max-width: 900px)" in css
    assert ".training-primary-grid" in css
    assert ".training-run-grid" in css
    assert "grid-template-columns: 1fr" in css
