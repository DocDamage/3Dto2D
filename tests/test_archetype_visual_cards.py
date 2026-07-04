from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_archetype_modal_has_selected_preview_panel():
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert 'id="archetypeSelectedPanel"' in html
    assert 'id="archetypeSelectedPortrait"' in html
    assert 'id="applySelectedArchetypeBtn"' in html
    assert 'id="archetypeCustomizePanel"' in html
    assert 'id="archetypeCustomizeCharacter"' in html
    assert 'id="archetypeCustomizeActions"' in html
    assert "Apply to Generate" in html


def test_archetype_cards_are_visual_selectable_and_apply_to_generate():
    js = (WEB / "js" / "app_presets.js").read_text(encoding="utf-8")
    html = (WEB / "components" / "generate.html").read_text(encoding="utf-8")

    assert "function archetypeInitials" in js
    assert "function archetypeGradient" in js
    assert "function updateSelectedArchetypePanel" in js
    assert "function populateArchetypeCustomizePanel" in js
    assert "function customizedArchetypePayload" in js
    assert "function setArchetypeProvenance" in js
    assert "setArchetypeProvenance(form, arc)" in js
    assert "archetype_customized: arc.customized ? 'true' : 'false'" in js
    assert "archetype-card-portrait" in js
    assert "card.tabIndex = 0" in js
    assert "applySelectedArchetypeBtn" in js
    assert "[name=\"sprite_action\"]" in js
    assert "[name=\"direction\"]" in js
    assert "[name=\"pixel_cleanup\"]" in js
    assert "applyArchetype(customizedArchetypePayload(selectedArchetype))" in js
    assert "refreshGeneratePromptPreview" in js
    assert 'name="archetype_id"' in html
    assert 'name="archetype_palette_hint"' in html
    assert 'name="archetype_customized"' in html


def test_archetype_visual_card_styles_are_present():
    css = (WEB / "css" / "components_recipes_modal.css").read_text(encoding="utf-8")
    compact_css = (WEB / "css" / "app_compact_fit.css").read_text(encoding="utf-8")

    assert ".archetype-card-portrait" in css
    assert ".archetype-card.selected" in css
    assert ".archetype-selected-panel" in css
    assert ".archetype-selected-meta" in css
    assert ".archetype-customize-panel" in css
    assert ".archetype-customize-grid" in css
    assert ".archetype-selected-panel" in compact_css
    assert "overflow-y: auto !important" in compact_css
