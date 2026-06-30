import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.marketplace_service import discover_local_bundles, load_index_entries, marketplace_gallery
from spriteforge_web import app


def test_marketplace_discovers_local_spriteforge_bundles(tmp_path):
    bundle = tmp_path / "output" / "releases" / "hero_pack.spriteforge"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")
    (bundle.parent / "preview.png").write_bytes(b"png")

    entries = discover_local_bundles(tmp_path)

    assert len(entries) == 1
    assert entries[0]["title"] == "Hero Pack"
    assert entries[0]["bundle_url"] == "/file/output/releases/hero_pack.spriteforge"
    assert entries[0]["preview_url"] == "/file/output/releases/preview.png"


def test_marketplace_index_filters_invalid_bundle_urls(tmp_path):
    index = tmp_path / "marketplace_index.json"
    index.write_text(
        json.dumps(
            {
                "entries": [
                    {"title": "Bad", "bundle_url": "javascript:alert(1)"},
                    {
                        "id": "hero",
                        "title": "Hero Bundle",
                        "author": "Sprite Artist",
                        "bundle_url": "https://example.test/hero.spriteforge",
                        "preview_url": "https://example.test/hero.png",
                        "tags": ["idle", "walk"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = load_index_entries(index)

    assert [entry["title"] for entry in entries] == ["Hero Bundle"]
    assert entries[0]["tags"] == ["idle", "walk"]


def test_marketplace_api_returns_gallery(monkeypatch, tmp_path):
    bundle = tmp_path / "output" / "releases" / "mage.spriteforge"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")

    routes_misc_mod = sys.modules["web_routes.routes_misc"]
    web_helpers_mod = sys.modules["web_helpers"]
    monkeypatch.setattr(routes_misc_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_helpers_mod, "ROOT", tmp_path)

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/marketplace/gallery")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["schema"] == "spriteforge_marketplace.v1"
    assert data["entries"][0]["bundle_url"] == "/file/output/releases/mage.spriteforge"


def test_marketplace_gallery_merges_local_and_index(tmp_path):
    bundle = tmp_path / "output" / "releases" / "local.spriteforge"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")
    index = tmp_path / "config" / "marketplace_index.json"
    index.parent.mkdir()
    index.write_text(
        json.dumps({"entries": [{"title": "Remote", "bundle_url": "https://example.test/remote.spriteforge"}]}),
        encoding="utf-8",
    )

    gallery = marketplace_gallery(tmp_path)

    assert gallery["local_count"] == 1
    assert [entry["title"] for entry in gallery["entries"]] == ["Local", "Remote"]
