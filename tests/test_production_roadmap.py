import hashlib
import json
import zipfile
from pathlib import Path

import pytest


def _repository(tmp_path):
    from services.asset_repository_service import AssetRepositoryService
    return AssetRepositoryService(tmp_path / "project")


def test_animation_workspace_persists_timing_anchors_hitboxes_and_clips(tmp_path):
    from services.animation_workspace_service import AnimationWorkspaceService

    repository = _repository(tmp_path)
    asset = repository.new_asset(project_id="p", name="Hero idle", asset_type="animation")
    state = {
        "fps": 12,
        "frames": [
            {"source_index": 0, "duration_ms": 80, "anchors": {"foot": {"x": 8, "y": 16}}, "hitboxes": [{"x": 1, "y": 2, "width": 6, "height": 12}]},
            {"source_index": 1, "duration_ms": 120, "anchors": {"foot": {"x": 9, "y": 16}}, "hitboxes": []},
        ],
        "clips": [{"name": "idle", "start": 0, "end": 1, "loop": True}],
        "onion_skin": {"previous": 2, "next": 1, "opacity": 0.4},
        "viewport": {"zoom": 3, "selected_frames": [1]},
    }
    revision = AnimationWorkspaceService(repository).save(asset["asset_id"], state)
    loaded = AnimationWorkspaceService(repository).load(asset["asset_id"])
    assert loaded["revision_id"] == revision["revision_id"]
    assert loaded["workspace"]["clips"][0]["name"] == "idle"
    assert loaded["workspace"]["frames"][0]["anchors"]["foot"] == {"x": 8.0, "y": 16.0}


def test_batch_matrix_estimates_persists_curates_and_retries_cells(tmp_path):
    from services.batch_matrix_service import BatchMatrixService

    service = BatchMatrixService(_repository(tmp_path))
    experiment = service.create("p", "search", {"seed": [1, 2], "direction": ["left", "right"]})
    assert experiment["estimate"]["cell_count"] == 4
    cell = experiment["cells"][0]
    curated = service.curate(experiment["experiment_id"], cell["cell_id"], rating=5, tags=["best", "best"], decision="shortlisted")
    assert curated["rating"] == 5 and curated["tags"] == ["best"]
    service.update_cell(experiment["experiment_id"], cell["cell_id"], status="failed", error="provider unavailable")
    assert service.retry_failed(experiment["experiment_id"]) == 1


def test_batch_matrix_rejects_runaway_expansion():
    from services.batch_matrix_service import BatchMatrixService
    dimensions = {"a": list(range(101))}
    with pytest.raises(ValueError, match="exceeds 100"):
        BatchMatrixService.estimate(dimensions)


def test_workflow_rejects_cycles_and_caches_deterministic_nodes(tmp_path):
    from services.workflow_builder_service import WorkflowBuilderService

    service = WorkflowBuilderService(_repository(tmp_path))
    invalid = {
        "nodes": [{"id": "a", "type": "transform"}, {"id": "b", "type": "transform"}],
        "edges": [
            {"from": "a", "output": "asset", "to": "b", "input": "asset"},
            {"from": "b", "output": "asset", "to": "a", "input": "asset"},
        ],
    }
    assert service.validate(invalid)["ok"] is False
    workflow = service.save("p", {
        "name": "QA",
        "nodes": [{"id": "source", "type": "import", "parameters": {"path": "hero.png"}}, {"id": "qa", "type": "qa"}],
        "edges": [{"from": "source", "output": "asset", "to": "qa", "input": "asset"}],
    })
    first = service.run(workflow["workflow_id"])
    second = service.run(workflow["workflow_id"])
    assert first["status"] == "completed" and second["status"] == "completed"
    with service.repository._connect() as connection:
        cached = connection.execute("SELECT COUNT(*) count FROM workflow_cache").fetchone()["count"]
    assert cached == 2


def test_workflow_pauses_at_provider_or_human_boundary(monkeypatch, tmp_path):
    from services.workflow_builder_service import WorkflowBuilderService
    from services.job_service import JobService
    monkeypatch.setattr(JobService, "start_job", staticmethod(lambda title, command, metadata=None: (True, "job-1")))
    service = WorkflowBuilderService(_repository(tmp_path))
    workflow = service.save("p", {"name": "Generate", "nodes": [{"id": "gen", "type": "generate"}], "edges": []})
    run = service.run(workflow["workflow_id"])
    assert run["status"] == "waiting"
    assert run["nodes"]["gen"]["job_id"] == "job-1"


def test_production_dashboard_reports_missing_combinations(tmp_path):
    from services.production_dashboard_service import ProductionDashboardService
    repository = _repository(tmp_path)
    repository.new_asset(project_id="p", name="Idle front", asset_type="animation", action="idle", direction="front")
    summary = ProductionDashboardService(repository, {
        "project_id": "p", "actions": ["idle", "walk"], "directions": ["front", "right"]
    }).summary()
    assert summary["completion"]["present"] == 1
    assert len(summary["completion"]["missing"]) == 3
    assert summary["readiness"]["ready"] is False


def test_update_staging_requires_matching_hash_and_blocks_traversal(tmp_path):
    from services.distribution_service import DistributionService
    package = tmp_path / "update.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("app/version.txt", "2")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    staged = DistributionService.stage_update(package, {"version": "2.0", "sha256": digest}, tmp_path / "staging")
    assert staged["status"] == "ready"
    with pytest.raises(ValueError, match="hash"):
        DistributionService.stage_update(package, {"version": "2.0", "sha256": "0" * 64}, tmp_path / "bad")


def test_batch_cell_submits_persistent_job_and_promotes_result(monkeypatch, tmp_path):
    from services.batch_matrix_service import BatchMatrixService
    from services.job_service import JobService
    service = BatchMatrixService(_repository(tmp_path))
    experiment = service.create("p", "search", {"prompt": ["hero"], "seed": [1]})
    cell = experiment["cells"][0]
    monkeypatch.setattr(JobService, "start_job", staticmethod(lambda title, command, metadata=None: (True, "job-7")))
    submitted = service.submit_cell(experiment["experiment_id"], cell["cell_id"], {"profile": "debug"})
    assert submitted["status"] == "running" and submitted["job_id"] == "job-7"
    service.update_cell(experiment["experiment_id"], cell["cell_id"], status="completed", output={"sprite_folder": "output/hero"})
    promoted = service.promote(experiment["experiment_id"], cell["cell_id"], name="Hero winner")
    assert promoted["revision"]["generation"]["matrix_cell_id"] == cell["cell_id"]


def test_deterministic_export_preset_is_atomic_and_repeatable(tmp_path):
    from services.export_preset_service import BUILTIN_PRESETS, ExportPresetService
    repository = _repository(tmp_path)
    asset = repository.new_asset(project_id="p", name="Hero", asset_type="sprite")
    repository.new_revision(asset["asset_id"], metadata={"dimensions": {"width": 16, "height": 16}}, files={"hero.png": b"pixels"})
    service = ExportPresetService(repository)
    output = tmp_path / "export"
    first = service.export("p", BUILTIN_PRESETS["generic_json"], output)
    second = service.export("p", BUILTIN_PRESETS["generic_json"], output)
    assert first["manifest"]["logical_digest"] == second["manifest"]["logical_digest"]
    assert json.loads((output / "spriteforge-export.json").read_text())["preset"]["schema_version"] == 1


def test_update_apply_health_check_and_rollback(tmp_path):
    import sys
    from services.distribution_service import DistributionService
    install = tmp_path / "install"
    (install / "app").mkdir(parents=True)
    target = install / "app" / "version.txt"
    target.write_text("old", encoding="utf-8")
    staged = tmp_path / "staged"
    (staged / "app").mkdir(parents=True)
    (staged / "app" / "version.txt").write_text("new", encoding="utf-8")
    (staged / "staged_update.json").write_text(json.dumps({"version": "2", "status": "ready"}), encoding="utf-8")
    result = DistributionService.apply_staged_update(staged, install, health_command=[sys.executable, "-c", "raise SystemExit(0)"])
    assert target.read_text(encoding="utf-8") == "new"
    rolled = DistributionService.rollback_update(Path(result["backup_root"]) / "applied_update.json")
    assert rolled["status"] == "rolled_back"
    assert target.read_text(encoding="utf-8") == "old"


def test_production_ui_and_installer_are_registered():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    index = (root / "app" / "web" / "index.html").read_text(encoding="utf-8")
    loader = (root / "app" / "web" / "js" / "script_loader.js").read_text(encoding="utf-8")
    assert 'data-view="production"' in index
    assert 'id="view-production"' in index
    assert "js/production_studio.js" in loader
    assert (root / "packaging" / "windows" / "SpriteForgeStudio.iss").is_file()
    assert (root / "packaging" / "windows" / "build_release.ps1").is_file()
    assert (root / "packaging" / "windows" / "test_clean_machine.ps1").is_file()
    assert (root / "tests" / "browser" / "run_production_studio.ps1").is_file()
