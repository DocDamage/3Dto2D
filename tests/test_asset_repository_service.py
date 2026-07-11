import hashlib
import json
from pathlib import Path

import pytest


def test_asset_revisions_are_immutable_branchable_and_deduplicated(tmp_path):
    from services.asset_repository_service import AssetRepositoryService

    project = tmp_path / "hero"
    project.mkdir()
    repository = AssetRepositoryService(project)
    asset = repository.new_asset(project_id="hero", name="Hero idle", asset_type="animation", action="idle")
    first = repository.new_revision(
        asset["asset_id"], metadata={"dimensions": {"width": 32, "height": 32}}, files={"hero.png": b"same-pixels"}
    )
    second = repository.new_revision(
        asset["asset_id"], metadata={"dimensions": {"width": 32, "height": 32}}, files={"hero.png": b"same-pixels"}
    )

    digest = hashlib.sha256(b"same-pixels").hexdigest()
    assert first["parent_revision_id"] is None
    assert second["parent_revision_id"] == first["revision_id"]
    assert len(list((project / ".spriteforge" / "objects").rglob(digest))) == 1
    assert repository.restore(asset["asset_id"], first["revision_id"])["current_revision_id"] == first["revision_id"]
    assert len(repository.history(asset["asset_id"])) == 2
    assert repository.verify_integrity()["ok"] is True


def test_revision_compare_and_swap_prevents_lost_updates(tmp_path):
    from services.asset_repository_service import AssetRepositoryService, RevisionConflictError

    repository = AssetRepositoryService(tmp_path / "project")
    asset = repository.new_asset(project_id="p", name="Knight", asset_type="sprite")
    original = asset["current_revision_id"]
    repository.new_revision(asset["asset_id"], metadata={"dimensions": {"width": 16, "height": 16}})
    stale = {
        "revision_id": "rev_stale", "asset_id": asset["asset_id"], "project_id": "p",
        "source_asset_ids": [], "generation": {}, "operations": [], "metadata": {}, "files": [],
    }
    with pytest.raises(RevisionConflictError):
        repository.commit_revision(stale, expected_current_revision_id=original)


def test_qa_results_are_cached_and_located(tmp_path):
    from services.asset_repository_service import AssetRepositoryService
    from services.qa_rule_service import QAService

    repository = AssetRepositoryService(tmp_path / "project")
    asset = repository.new_asset(project_id="p", name="Knight", asset_type="sprite")
    revision = repository.new_revision(asset["asset_id"])
    first = QAService(repository).validate_revision(revision["revision_id"])
    second = QAService(repository).validate_revision(revision["revision_id"])
    assert first["cached"] is False
    assert second["cached"] is True
    assert first["passed"] is False
    assert all(item["location"] for item in first["findings"])


def test_legacy_project_manifest_migration_is_versioned_and_backed_up(monkeypatch, tmp_path):
    import services.project_service as project_module
    from services.project_service import ProjectService

    projects = tmp_path / "projects"
    manifest = projects / "old" / "spriteforge_project.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"schema": "spriteforge_project_v1", "name": "old"}), encoding="utf-8")
    monkeypatch.setattr(project_module, "PROJECTS_DIR", projects)
    monkeypatch.setattr(project_module, "ROOT", tmp_path)

    migrated = ProjectService.load_manifest(manifest)
    assert migrated["schema"] == "spriteforge.project.v2"
    assert migrated["schema_version"] == 2
    assert migrated["project_id"] == "old"
    assert (manifest.parent / "spriteforge_project.pre-v2.json").exists()


def test_asset_api_round_trip(monkeypatch, tmp_path):
    import services.project_service as project_module
    from spriteforge_web import app

    projects = tmp_path / "projects"
    manifest = projects / "demo" / "spriteforge_project.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"schema": "spriteforge.project.v2", "schema_version": 2, "name": "demo", "project_id": "demo"}), encoding="utf-8")
    monkeypatch.setattr(project_module, "PROJECTS_DIR", projects)
    monkeypatch.setattr(project_module, "ROOT", tmp_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        created = client.post("/api/assets?project=projects/demo/spriteforge_project.json", json={"name": "Hero", "asset_type": "sprite"})
        assert created.status_code == 201
        asset = created.get_json()["asset"]
        revised = client.post(
            f"/api/assets/{asset['asset_id']}/revisions?project=projects/demo/spriteforge_project.json",
            json={"metadata": {"dimensions": {"width": 32, "height": 32}}},
        )
        assert revised.status_code == 201
        fetched = client.get(f"/api/assets/{asset['asset_id']}?project=projects/demo/spriteforge_project.json")
        assert fetched.get_json()["history"][0]["metadata"]["dimensions"]["width"] == 32


def test_project_bundle_rejects_tampered_managed_object(tmp_path):
    import io
    import zipfile
    from services.project_bundle_service import import_project_bundle

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("spriteforge_project.json", json.dumps({"name": "hero"}))
        archive.writestr(f".spriteforge/objects/00/00/{'0' * 64}", b"tampered")
    stream.seek(0)
    with pytest.raises(ValueError, match="content-hash verification"):
        import_project_bundle(stream, "hero.spriteforge", tmp_path / "projects")
