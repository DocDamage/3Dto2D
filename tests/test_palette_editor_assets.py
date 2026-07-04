from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_palette_editor_is_wired_into_harmonizer():
    script = (APP / "web" / "js" / "palette_harmonizer.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert "normalizePaletteEditorColors" in script
    assert "parseImportedPaletteText" in script
    assert "paletteEditorImportFile" in script
    assert "importPaletteEditorFile" in script
    assert "paletteEditorColorsText" in script
    assert "paletteEditorSwatches" in script
    assert "paletteEditorPreviewCanvas" in script
    assert "refreshPaletteQuantizedPreview" in script
    assert "paletteHslWheel" in script
    assert "installPaletteHslWheel" in script
    assert "source: 'palette_editor'" in script
    assert ".palette-editor-panel" in css
    assert 'input[type="file"]' in css
    assert ".palette-editor-swatches" in css
    assert ".palette-editor-preview" in css
    assert ".palette-hsl-wheel" in css
    assert "conic-gradient" in css


def test_palette_editor_import_parser_supports_hex_and_gpl_rows():
    script = (APP / "web" / "js" / "palette_harmonizer.js").read_text(encoding="utf-8")

    assert "GIMP Palette" in script
    assert "Name:" in script
    assert "Columns:" in script
    assert "paletteRgbToHex" in script
    assert "Imported ${colors.length} colors" in script


def test_palette_editor_import_parser_supports_lospec_json_and_ase():
    script = (APP / "web" / "js" / "palette_harmonizer.js").read_text(encoding="utf-8")

    assert "JSON.parse" in script
    assert "parsed?.colors" in script
    assert "Lospec JSON" in script
    assert "parseAsePalette" in script
    assert "ASEF" in script
    assert "CMYK" in script
    assert "Adobe ASE swatches" in script
    assert ".json,.ase,application/json" in script


def test_palette_editor_has_hsl_color_wheel_picker():
    script = (APP / "web" / "js" / "palette_harmonizer.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert "paletteHslToHex" in script
    assert "updatePaletteHslWheel" in script
    assert "refreshPaletteHslPreview" in script
    assert "Add wheel color" in script
    assert "pointermove" in script
    assert "palette-hsl-picker" in css
    assert "cursor: crosshair" in css


def test_palette_editor_preview_quantizes_against_nearest_palette_color():
    script = (APP / "web" / "js" / "palette_harmonizer.js").read_text(encoding="utf-8")

    assert "nearestPaletteRgb" in script
    assert "paletteHexToRgb" in script
    assert "source left, snapped right" in script
    assert "ctx.imageSmoothingEnabled = false" in script
