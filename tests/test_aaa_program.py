import hashlib
import json
from pathlib import Path

import pytest


def _repo(tmp_path):
    from services.asset_repository_service import AssetRepositoryService
    return AssetRepositoryService(tmp_path / "project")


def _asset(repository):
    asset = repository.new_asset(project_id="p", name="Hero", asset_type="animation", action="idle", direction="front")
    revision = repository.new_revision(asset["asset_id"], metadata={"dimensions": {"width": 32, "height": 32}, "palette": ["#FFFFFF"]}, files={"hero.png": b"pixels"})
    return asset, revision


def test_creative_document_layers_curves_and_revision_conflicts(tmp_path):
    from services.creative_document_service import CreativeDocumentService
    repository = _repo(tmp_path); asset, _ = _asset(repository); service = CreativeDocumentService(repository)
    created = service.create("p", asset["asset_id"], "Hero document", width=64, height=64, frames=2000)
    document = created["document"]
    document["layers"].append({"layer_id": "group", "name": "Equipment", "type": "group", "blend_mode": "normal", "children": [{"layer_id": "sword", "name": "Sword", "type": "symbol", "blend_mode": "screen", "keyframes": [{"frame": 10, "value": 0.5, "interpolation": "bezier"}]}]})
    saved = service.save(created["document_id"], document, expected_revision_id=created["revision_id"])
    assert saved["document"]["layers"][1]["children"][0]["keyframes"][0]["frame"] == 10
    with pytest.raises(ValueError, match="conflict"):
        service.save(created["document_id"], document, expected_revision_id=created["revision_id"])


def test_studio_roles_locks_comments_reviews_and_audit(tmp_path):
    from services.studio_collaboration_service import StudioCollaborationService
    repository = _repo(tmp_path); asset, revision = _asset(repository); service = StudioCollaborationService(repository)
    service.upsert_user("lead", "Lead Artist"); service.set_member("p", "lead", "admin", actor_id="lead")
    service.upsert_user("artist", "Artist"); service.set_member("p", "artist", "artist", actor_id="lead")
    lock = service.acquire_lock("p", asset["asset_id"], "artist")
    assert lock["token"].startswith("lock_")
    comment = service.comment("p", asset["asset_id"], revision["revision_id"], "artist", "Adjust the foot", {"frame": 2, "x": 10, "y": 20})
    review = service.review("p", asset["asset_id"], revision["revision_id"], "approved", "lead")
    assert comment["location"]["frame"] == 2 and review["state"] == "approved"
    assert len(service.activity("p")) >= 4


def test_engine_live_link_and_interchange_loss_report(tmp_path):
    from services.pipeline_integration_service import PipelineIntegrationService
    repository = _repo(tmp_path); asset, revision = _asset(repository); service = PipelineIntegrationService(repository)
    client = service.register_client("p", "godot", "4.5", ["anchors", "hitboxes"])
    event = service.publish_asset("p", "godot", asset["asset_id"], revision["revision_id"])
    poll = service.poll(client["client_id"])
    assert poll["events"][0]["cursor"] if "cursor" in poll["events"][0] else event["cursor"]
    source = tmp_path / "project" / "hero.aseprite"; source.write_bytes(b"aseprite")
    report = service.interchange_report("p", "aseprite", "round_trip", source, ["layers", "frames", "bones"])
    assert report["lossless"] is False and report["not_preserved"][0]["feature"] == "bones"
    plugin = service.generate_engine_plugin("unity", tmp_path / "unity-plugin")
    assert "SpriteForgeLiveLink.cs" in plugin["files"]


def test_worker_pool_routes_vram_quotas_and_hashed_outputs(tmp_path):
    from services.worker_pool_service import WorkerPoolService
    service = WorkerPoolService(_repo(tmp_path))
    service.register({"worker_id": "gpu-a", "name": "RTX Worker", "endpoint": "https://worker", "capabilities": ["generate", "qa"], "resources": {"vram_mb": 24000, "disk_free_bytes": 10_000_000}, "max_leases": 2})
    service.set_quota("p", max_concurrent=2, max_daily_cost=20)
    lease = service.lease("job-1", "p", {"capabilities": ["generate"], "vram_mb": 12000}, cost_estimate=3)
    completed = service.complete(lease["lease_id"], [{"name": "hero.png", "sha256": hashlib.sha256(b"pixels").hexdigest(), "size_bytes": 6}], actual_cost=2)
    assert completed["outputs"]["schema"] == "spriteforge.worker_outputs.v1"


def test_character_bible_completeness_gameplay_and_analytics(tmp_path):
    from services.art_direction_service import ArtDirectionService
    repository = _repo(tmp_path); asset, _ = _asset(repository); service = ArtDirectionService(repository)
    bible = service.save_bible("p", "Hero Bible", {"canvas": {"width": 32, "height": 32}, "palette": {"forbidden": ["#FF00FF"]}, "required_actions": ["idle", "walk"], "required_directions": ["front", "right"]})
    assert service.validate_asset(bible["bible_id"], asset["asset_id"])["passed"] is True
    complete = service.project_completeness("p", bible["bible_id"])
    assert complete["complete"] == 1 and len(complete["missing"]) == 3
    scenario = service.save_gameplay_scenario("p", "Combat", {"actors": [{"asset_id": asset["asset_id"], "x": 100, "y": 200}]})
    assert scenario["collision_debug"] is True
    assert service.analytics("p")["assets"] == 1


def test_plugin_permissions_telemetry_sbom_and_provenance(tmp_path):
    from services.trust_service import LocalTelemetry, PluginSecurityService, SupplyChainService
    plugin = tmp_path / "plugin.py"; plugin.write_text("import socket\ndef hook(): return 1\n", encoding="utf-8")
    assert PluginSecurityService.inspect(plugin, {"permissions": []})["ok"] is False
    assert PluginSecurityService.inspect(plugin, {"permissions": ["network"]})["ok"] is True
    telemetry = LocalTelemetry(tmp_path / "telemetry.jsonl", max_events=100)
    event = telemetry.emit("metric", "canvas.frame_ms", value=8.2, attributes={"project_id": "p", "prompt": "secret"})
    assert event["attributes"]["prompt"] == "[redacted]"
    requirements = tmp_path / "requirements.txt"; requirements.write_text("Flask==3.1.3\nPillow==12.2.0\n", encoding="utf-8")
    sbom = SupplyChainService.generate_sbom(requirements, tmp_path / "sbom.json")
    artifact = tmp_path / "app.zip"; artifact.write_bytes(b"release")
    provenance = SupplyChainService.build_provenance([artifact], source_revision="abc123", builder_id="ci", invocation={}, output=tmp_path / "provenance.json")
    assert len(sbom["components"]) == 2 and provenance["predicateType"].endswith("provenance/v1")


def test_aaa_studio_frontend_and_service_architecture_registered():
    root = Path(__file__).resolve().parent.parent
    index = (root / "app" / "web" / "index.html").read_text(encoding="utf-8")
    script = (root / "app" / "web" / "js" / "aaa_studio.js").read_text(encoding="utf-8")
    assert 'data-view="aaa_studio"' in index and 'id="view-aaa_studio"' in index
    assert "getContext('webgl2'" in script and "navigator.gpu" in script
    assert "pressure" in script and "saveWorkspace" in script
    assert (root / "tests" / "browser" / "run_aaa_studio.ps1").is_file()
    openapi = (root / "docs" / "openapi-roadmap.yaml").read_text(encoding="utf-8")
    assert "/api/creative-documents:" in openapi and "/api/farm/route:" in openapi
    assert (root / "packaging" / "windows" / "AppxManifest.xml").is_file()
    assert (root / "packaging" / "windows" / "SpriteForge.appinstaller").is_file()
    build = (root / "packaging" / "windows" / "build_release.ps1").read_text(encoding="utf-8")
    assert "/target:winexe" in build and "tools.release_trust" in build
