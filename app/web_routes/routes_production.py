"""Roadmap production surfaces: animation, matrices, workflows, dashboard, recovery."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from services.animation_workspace_service import AnimationWorkspaceService
from services.asset_repository_service import AssetRepositoryService
from services.batch_matrix_service import BatchMatrixService
from services.distribution_service import DistributionService
from services.production_dashboard_service import ProductionDashboardService
from services.project_service import ProjectService
from services.workflow_builder_service import NODE_TYPES, WorkflowBuilderService
from services.export_preset_service import BUILTIN_PRESETS, ExportPresetService


routes_production = Blueprint("routes_production", __name__)


def _context() -> tuple[AssetRepositoryService, dict, Path]:
    body = request.get_json(silent=True) or {}
    requested = str(request.args.get("project") or body.get("project") or "")
    path = ProjectService.resolve_project_path(requested) if requested else None
    if path is None:
        active = ProjectService.get_active_project()
        path = ProjectService.resolve_project_path(str(active.get("path"))) if active else None
    if path is None:
        raise ValueError("A valid project or active project is required")
    return AssetRepositoryService(path.parent), ProjectService.load_manifest(path), path.parent


def _failed(exc: Exception):
    status = 404 if isinstance(exc, LookupError) else 400
    return jsonify({"ok": False, "code": "not_found" if status == 404 else "invalid_request", "message": str(exc)}), status


@routes_production.route("/api/animation/<asset_id>/workspace", methods=["GET", "PUT"])
def animation_workspace(asset_id: str):
    try:
        repository, _, _ = _context()
        service = AnimationWorkspaceService(repository)
        if request.method == "GET":
            return jsonify({"ok": True, **service.load(asset_id)})
        return jsonify({"ok": True, "revision": service.save(asset_id, (request.get_json(silent=True) or {}).get("workspace", {}))})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/animation/synchronize", methods=["POST"])
def animation_synchronize():
    try:
        repository, _, _ = _context()
        body = request.get_json(silent=True) or {}
        revisions = AnimationWorkspaceService(repository).synchronize(
            list(body.get("asset_ids") or []), str(body.get("source_asset_id") or ""),
            timing=bool(body.get("timing", True)), anchors=bool(body.get("anchors", True)),
        )
        return jsonify({"ok": True, "revisions": revisions})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/estimate", methods=["POST"])
def batch_estimate():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "estimate": BatchMatrixService.estimate(
            body.get("dimensions", {}), bytes_per_result=body.get("bytes_per_result", 1_000_000),
            cost_per_result=body.get("cost_per_result", 0),
        )})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches", methods=["POST"])
def batch_create():
    try:
        repository, manifest, _ = _context()
        body = request.get_json(silent=True) or {}
        result = BatchMatrixService(repository).create(
            manifest["project_id"], str(body.get("name") or "Batch experiment"), body.get("dimensions", {}),
            bytes_per_result=body.get("bytes_per_result", 1_000_000), cost_per_result=body.get("cost_per_result", 0),
        )
        return jsonify({"ok": True, "experiment": result}), 201
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>", methods=["GET"])
def batch_get(experiment_id: str):
    try:
        repository, _, _ = _context()
        result = BatchMatrixService(repository).get(
            experiment_id, status=str(request.args.get("status") or ""),
            limit=request.args.get("limit", 500), offset=request.args.get("offset", 0),
        )
        return jsonify({"ok": True, "experiment": result})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>/cells/<cell_id>", methods=["PATCH"])
def batch_curate(experiment_id: str, cell_id: str):
    try:
        repository, _, _ = _context()
        body = request.get_json(silent=True) or {}
        result = BatchMatrixService(repository).curate(
            experiment_id, cell_id, rating=body.get("rating"), tags=body.get("tags"), decision=str(body.get("decision") or ""),
        )
        return jsonify({"ok": True, "cell": result})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>/retry", methods=["POST"])
def batch_retry(experiment_id: str):
    try:
        repository, _, _ = _context()
        return jsonify({"ok": True, "retried": BatchMatrixService(repository).retry_failed(experiment_id)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>/cells/<cell_id>/submit", methods=["POST"])
def batch_submit(experiment_id: str, cell_id: str):
    try:
        repository, _, _ = _context()
        cell = BatchMatrixService(repository).submit_cell(experiment_id, cell_id, (request.get_json(silent=True) or {}).get("generation", {}))
        return jsonify({"ok": True, "cell": cell}), 202
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>/synchronize", methods=["POST"])
def batch_synchronize(experiment_id: str):
    try:
        repository, _, _ = _context()
        return jsonify({"ok": True, **BatchMatrixService(repository).synchronize_jobs(experiment_id)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>/cells/<cell_id>/cancel", methods=["POST"])
def batch_cancel(experiment_id: str, cell_id: str):
    try:
        repository, _, _ = _context()
        return jsonify({"ok": True, "cell": BatchMatrixService(repository).cancel_cell(experiment_id, cell_id)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/batches/<experiment_id>/cells/<cell_id>/promote", methods=["POST"])
def batch_promote(experiment_id: str, cell_id: str):
    try:
        repository, _, _ = _context()
        result = BatchMatrixService(repository).promote(experiment_id, cell_id, name=str((request.get_json(silent=True) or {}).get("name") or ""))
        return jsonify({"ok": True, **result}), 201
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/workflows/node-types", methods=["GET"])
def workflow_node_types():
    return jsonify({"ok": True, "node_types": NODE_TYPES})


@routes_production.route("/api/workflows/validate", methods=["POST"])
def workflow_validate():
    try:
        repository, _, _ = _context()
        return jsonify(WorkflowBuilderService(repository).validate((request.get_json(silent=True) or {}).get("workflow", {})))
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/workflows", methods=["POST"])
def workflow_save():
    try:
        repository, manifest, _ = _context()
        workflow = WorkflowBuilderService(repository).save(manifest["project_id"], (request.get_json(silent=True) or {}).get("workflow", {}))
        return jsonify({"ok": True, "workflow": workflow}), 201
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/workflows/<workflow_id>/runs", methods=["POST"])
def workflow_run(workflow_id: str):
    try:
        repository, _, _ = _context()
        body = request.get_json(silent=True) or {}
        run = WorkflowBuilderService(repository).run(workflow_id, body.get("inputs", {}), restart_from=str(body.get("restart_from") or ""))
        return jsonify({"ok": True, "run": run}), 202 if run["status"] == "waiting" else 200
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/workflows/runs/<run_id>/synchronize", methods=["POST"])
def workflow_synchronize(run_id: str):
    try:
        repository, _, _ = _context()
        result = WorkflowBuilderService(repository).synchronize_run(run_id)
        return jsonify({"ok": True, "run": result}), 202 if result["status"] == "waiting" else 200
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/production/dashboard", methods=["GET"])
def production_dashboard():
    try:
        repository, manifest, _ = _context()
        return jsonify({"ok": True, "dashboard": ProductionDashboardService(repository, manifest).summary()})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/recovery/snapshots", methods=["GET", "POST"])
def recovery_snapshots():
    try:
        _, _, project_dir = _context()
        if request.method == "POST":
            return jsonify({"ok": True, "snapshot": DistributionService.snapshot(project_dir)}), 201
        return jsonify({"ok": True, "snapshots": DistributionService.recovery_candidates(project_dir)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/version-report", methods=["GET"])
def version_report():
    return jsonify({"ok": True, "versions": DistributionService.version_report()})


@routes_production.route("/api/export-presets", methods=["GET"])
def export_presets():
    return jsonify({"ok": True, "presets": ExportPresetService.list_presets()})


@routes_production.route("/api/export-presets/preview", methods=["POST"])
def export_preview():
    try:
        repository, manifest, _ = _context()
        body = request.get_json(silent=True) or {}
        preset = body.get("preset") or BUILTIN_PRESETS.get(str(body.get("preset_id") or "raw"))
        return jsonify({"ok": True, "preview": ExportPresetService(repository).preview(manifest["project_id"], preset)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/export-presets/export", methods=["POST"])
def export_with_preset():
    try:
        repository, manifest, project_dir = _context()
        body = request.get_json(silent=True) or {}
        preset = body.get("preset") or BUILTIN_PRESETS.get(str(body.get("preset_id") or "raw"))
        output_name = str(body.get("output_name") or f"preset-{preset['preset_id']}")
        if Path(output_name).name != output_name:
            raise ValueError("output_name must be a simple directory name")
        result = ExportPresetService(repository).export(manifest["project_id"], preset, project_dir / "exports" / output_name)
        return jsonify(result), 201
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/updates/apply", methods=["POST"])
def apply_update():
    try:
        body = request.get_json(silent=True) or {}
        staged = Path(str(body.get("staged_dir") or ""))
        install = Path(str(body.get("install_root") or Path(__file__).resolve().parents[2]))
        if not staged.is_absolute():
            staged = Path(__file__).resolve().parents[1] / staged
        allowed_staging = (Path(__file__).resolve().parents[1] / "state" / "updates").resolve()
        staged.resolve().relative_to(allowed_staging)
        if install.resolve() != Path(__file__).resolve().parents[2]:
            raise ValueError("install_root must be the SpriteForge installation root")
        return jsonify({"ok": True, "update": DistributionService.apply_staged_update(staged, install)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/updates/rollback", methods=["POST"])
def rollback_update():
    try:
        record = Path(str((request.get_json(silent=True) or {}).get("applied_record") or ""))
        if not record.is_absolute():
            record = Path(__file__).resolve().parents[1] / record
        record.resolve().relative_to((Path(__file__).resolve().parents[1] / "state" / "updates" / "backups").resolve())
        return jsonify({"ok": True, "update": DistributionService.rollback_update(record)})
    except Exception as exc:
        return _failed(exc)


@routes_production.route("/api/releases/readiness", methods=["POST"])
def release_readiness():
    body = request.get_json(silent=True) or {}
    evidence = Path(str(body["clean_machine_evidence"])) if body.get("clean_machine_evidence") else None
    return jsonify(DistributionService.release_readiness(
        certificate_thumbprint=str(body.get("certificate_thumbprint") or ""), clean_machine_evidence=evidence,
    ))
