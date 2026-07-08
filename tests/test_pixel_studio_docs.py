from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_DOCS = ROOT / "app" / "docs"


def test_phase14_pixel_studio_docs_cover_required_workflows():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (APP_DOCS / "END_USER_GUIDE.md").read_text(encoding="utf-8")
    api = (APP_DOCS / "api.md").read_text(encoding="utf-8")
    cheat = (APP_DOCS / "ONE_PAGE_CHEAT_SHEET.md").read_text(encoding="utf-8")
    troubleshooting = (APP_DOCS / "TROUBLESHOOTING_v8.md").read_text(encoding="utf-8")

    for text in (readme, guide, cheat):
        assert "Pixel Studio" in text
        assert "Cohesive Pack Builder" in text

    assert "First asset" in cheat
    assert "First tileset" in cheat
    assert "First animation" in cheat
    assert "First pack" in cheat
    assert "Visual QA report" in cheat
    assert "Search/filter recipe cards" in cheat

    assert "POST /api/pixel-assets/qa/report" in api
    assert "GET /api/pixel-assets/providers/capabilities" in api
    assert "POST /api/pixel-assets/providers/plan" in api
    assert "GET /api/pixel-assets/recipes" in api

    assert "Pixel Studio provider" in troubleshooting
    assert "Pixel Studio inpaint" in troubleshooting
    assert "Pixel Studio Visual QA" in troubleshooting
    assert "Pixel Studio recipes" in troubleshooting


def test_magicpixel_parity_plan_has_regression_evidence_for_every_phase():
    files = {
        "plan": ROOT / "docs" / "superpowers" / "plans" / "2026-07-07-pixel-asset-studio-magicpixel-parity.md",
        "routes": ROOT / "app" / "web_routes" / "routes_pixel_asset.py",
        "html": ROOT / "app" / "web" / "components" / "pixel_studio.html",
        "js": ROOT / "app" / "web" / "js" / "pixel_studio.js",
        "tests": ROOT / "tests" / "test_pixel_asset_studio.py",
        "api": APP_DOCS / "api.md",
        "guide": APP_DOCS / "END_USER_GUIDE.md",
    }
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in files.values())

    phase_evidence = {
        "Phase 0": ["GET /api/pixel-assets/modes", "pixelModeConfigs", "pixelActiveMode"],
        "Phase 1": ["generate_pixel_asset_batch", "/api/pixel-assets/generate", "test_real_generation_mock_mode"],
        "Phase 2": ["PixelNormalizationService", "/api/pixel-assets/normalize", "test_normalize_endpoint"],
        "Phase 3": ["PixelDirectionService", "/api/pixel-assets/directions", "test_direction_generation_endpoint"],
        "Phase 4": ["test_mode_configs_and_mode_specific_prompt_options", "mode_options", "material: crystal"],
        "Phase 5": ["PixelTilesetService", "/api/pixel-assets/tileset", "godot_tileset.json"],
        "Phase 6": ["btnEditorPencil", "/api/pixel-assets/edit/save", "btnEditorVersion"],
        "Phase 7": ["PixelInpaintService", "/api/pixel-assets/inpaint", "btnEditorCompareInpaint"],
        "Phase 8": ["PixelAnimationService", "/api/pixel-assets/animate", "preview.webp"],
        "Phase 9": ["PixelTransferService", "/api/pixel-assets/animation-transfer", "pose_captions"],
        "Phase 10": ["PixelRigService", "/api/pixel-assets/rig/render", "pixelRigOverlayContainer"],
        "Phase 11": ["PixelStyleService", "/api/pixel-assets/style/compare", "pixelHistorySearchInput"],
        "Phase 12": ["PixelPackService", "/api/pixel-assets/pack/generate", "catalog.html"],
        "Phase 13": ["PixelRecipeService", "/api/pixel-assets/recipes/import", "pixelRecipeCardGrid"],
        "Phase 14": ["PixelQAReportService", "/api/pixel-assets/qa/report.html", "Pixel Studio Visual QA"],
    }

    missing = {
        phase: [token for token in tokens if token not in corpus]
        for phase, tokens in phase_evidence.items()
    }
    missing = {phase: tokens for phase, tokens in missing.items() if tokens}
    assert missing == {}
