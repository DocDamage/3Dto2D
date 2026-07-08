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
