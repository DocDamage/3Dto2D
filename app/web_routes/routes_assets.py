"""Asset provenance and unified QA API."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from services.asset_repository_service import (
    AssetNotFoundError, AssetRepositoryService, RevisionConflictError,
)
from services.feature_flag_service import FeatureFlagService
from services.project_service import ProjectService
from services.qa_rule_service import DEFAULT_QA_REGISTRY, QAService
from services.roadmap_models import RecordValidationError


routes_assets = Blueprint("routes_assets", __name__)


def _repository() -> tuple[AssetRepositoryService, dict]:
    requested = str(request.args.get("project") or (request.get_json(silent=True) or {}).get("project") or "")
    project_path = ProjectService.resolve_project_path(requested) if requested else None
    if project_path is None:
        active = ProjectService.get_active_project()
        project_path = ProjectService.resolve_project_path(str(active.get("path"))) if active else None
    if project_path is None:
        raise ValueError("A valid project or active project is required")
    manifest = ProjectService.load_manifest(project_path)
    return AssetRepositoryService(project_path.parent), manifest


def _error(exc: Exception):
    if isinstance(exc, AssetNotFoundError):
        return jsonify({"ok": False, "code": "not_found", "message": str(exc)}), 404
    if isinstance(exc, RevisionConflictError):
        return jsonify({"ok": False, "code": "revision_conflict", "message": str(exc)}), 409
    if isinstance(exc, (ValueError, RecordValidationError)):
        payload = {"ok": False, "code": "invalid_record", "message": str(exc)}
        if isinstance(exc, RecordValidationError):
            payload["path"] = exc.path
        return jsonify(payload), 400
    raise exc


@routes_assets.route("/api/features", methods=["GET"])
def feature_flags():
    try:
        _, manifest = _repository()
        return jsonify({"ok": True, "flags": FeatureFlagService.resolve(manifest)})
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/assets", methods=["GET"])
def list_assets():
    try:
        repository, manifest = _repository()
        rows = repository.list_assets(
            str(manifest["project_id"]), limit=request.args.get("limit", 200), offset=request.args.get("offset", 0)
        )
        return jsonify({"ok": True, "assets": rows, "count": len(rows)})
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/assets", methods=["POST"])
def create_asset():
    try:
        repository, manifest = _repository()
        body = request.get_json(silent=True) or {}
        asset = repository.new_asset(
            project_id=str(manifest["project_id"]), name=str(body.get("name") or "").strip(),
            asset_type=str(body.get("asset_type") or "sprite").strip(), role=body.get("role"),
            action=body.get("action"), direction=body.get("direction"), variant=body.get("variant"),
        )
        return jsonify({"ok": True, "asset": asset}), 201
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/assets/<asset_id>", methods=["GET"])
def get_asset(asset_id: str):
    try:
        repository, _ = _repository()
        asset = repository.get_asset(asset_id)
        return jsonify({"ok": True, "asset": asset, "history": repository.history(asset_id)})
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/assets/<asset_id>/revisions", methods=["POST"])
def create_revision(asset_id: str):
    try:
        repository, _ = _repository()
        body = request.get_json(silent=True) or {}
        revision = repository.new_revision(
            asset_id, generation=body.get("generation"), operations=body.get("operations"), metadata=body.get("metadata")
        )
        return jsonify({"ok": True, "revision": revision}), 201
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/assets/<asset_id>/restore", methods=["POST"])
def restore_revision(asset_id: str):
    try:
        repository, _ = _repository()
        revision_id = str((request.get_json(silent=True) or {}).get("revision_id") or "")
        if not revision_id:
            raise ValueError("revision_id is required")
        return jsonify({"ok": True, "asset": repository.restore(asset_id, revision_id)})
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/qa/rules", methods=["GET"])
def qa_rules():
    return jsonify({"ok": True, "rules": DEFAULT_QA_REGISTRY.describe()})


@routes_assets.route("/api/revisions/<revision_id>/validate", methods=["POST"])
def validate_revision(revision_id: str):
    try:
        repository, _ = _repository()
        report = QAService(repository).validate_revision(revision_id, request.get_json(silent=True) or {})
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        return _error(exc)


@routes_assets.route("/api/projects/integrity", methods=["GET"])
def project_integrity():
    try:
        repository, _ = _repository()
        report = repository.verify_integrity()
        return jsonify(report), 200 if report["ok"] else 409
    except Exception as exc:
        return _error(exc)
