import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_plugin_manifest_reports_sdk_compatibility(tmp_path):
    from services.plugin_manager import PLUGIN_SDK_VERSION, load_plugin_manifest

    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    manifest = plugin_dir / "spriteforge_plugin.json"
    manifest.write_text(json.dumps({
        "id": "demo",
        "name": "Demo",
        "sdk_version": PLUGIN_SDK_VERSION,
        "hooks": ["filter_prompt", "future_hook"],
        "entrypoint": "demo.py",
    }), encoding="utf-8")

    metadata = load_plugin_manifest(manifest)

    assert metadata is not None
    assert metadata["compatible"] is True
    assert metadata["compatibility"]["status"] == "compatible"
    assert metadata["known_hooks"] == ["filter_prompt"]
    assert metadata["unknown_hooks"] == ["future_hook"]


def test_plugin_manifest_marks_newer_major_sdk_incompatible(tmp_path):
    from services.plugin_manager import load_plugin_manifest

    plugin_dir = tmp_path / "plugins" / "future"
    plugin_dir.mkdir(parents=True)
    manifest = plugin_dir / "spriteforge_plugin.json"
    manifest.write_text(json.dumps({
        "id": "future",
        "sdk_version": "2.0.0",
        "entrypoint": "future.py",
    }), encoding="utf-8")

    metadata = load_plugin_manifest(manifest)

    assert metadata is not None
    assert metadata["compatible"] is False
    assert metadata["compatibility"]["status"] == "major_mismatch"


def test_plugin_sdk_contract_and_scaffold_are_creator_ready():
    from services.plugin_manager import PLUGIN_MANIFEST, PLUGIN_SDK_VERSION, plugin_scaffold, plugin_sdk_contract

    contract = plugin_sdk_contract()
    scaffold = plugin_scaffold("My Cool Plugin")

    assert contract["schema"] == "spriteforge.plugin_sdk_contract.v1"
    assert contract["sdk_version"] == PLUGIN_SDK_VERSION
    assert "filter_prompt" in contract["known_hooks"]
    assert scaffold["schema"] == "spriteforge.plugin_scaffold.v1"
    assert PLUGIN_MANIFEST in scaffold["files"]
    assert scaffold["manifest"]["entrypoint"].endswith(".py")
    assert "def filter_prompt" in scaffold["files"][scaffold["manifest"]["entrypoint"]]


def test_plugin_manifest_validation_reports_authoring_issues(tmp_path):
    from services.plugin_manager import PLUGIN_SDK_VERSION, validate_plugin_manifest

    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    manifest_path = plugin_dir / "spriteforge_plugin.json"
    raw = {
        "id": "broken",
        "name": "Broken",
        "sdk_version": PLUGIN_SDK_VERSION,
        "version": "0.1.0",
        "entrypoint": "missing.py",
        "hooks": ["filter_prompt", "mystery_hook"],
    }

    report = validate_plugin_manifest(raw, manifest_path)

    assert report["schema"] == "spriteforge.plugin_manifest_validation.v1"
    assert report["ok"] is False
    assert report["metadata"]["known_hooks"] == ["filter_prompt"]
    assert {issue["code"] for issue in report["issues"]} == {"unknown_hooks", "missing_entrypoint"}
    assert "filter_prompt" in report["known_hooks"]
    assert "entrypoint" in report["required_fields"]


def test_plugin_sdk_endpoint_returns_contract_and_scaffold():
    from flask import Flask
    from web_routes.routes_misc import routes_misc

    app = Flask(__name__)
    app.register_blueprint(routes_misc)
    response = app.test_client().get("/api/plugins/sdk?id=demo_plugin")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["contract"]["schema"] == "spriteforge.plugin_sdk_contract.v1"
    assert payload["scaffold"]["manifest"]["id"] == "demo_plugin"
