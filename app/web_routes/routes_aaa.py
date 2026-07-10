"""AAA creative-core, studio, pipeline, farm, art-direction, and trust APIs."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from services.art_direction_service import ArtDirectionService
from services.asset_repository_service import AssetRepositoryService
from services.creative_document_service import CreativeDocumentService
from services.pipeline_integration_service import PipelineIntegrationService
from services.project_service import ProjectService
from services.studio_collaboration_service import StudioCollaborationService
from services.trust_service import LocalTelemetry, PluginSecurityService
from services.worker_pool_service import WorkerPoolService


routes_aaa = Blueprint("routes_aaa", __name__)


def _context():
    body = request.get_json(silent=True) or {}
    requested = str(request.args.get("project") or body.get("project") or "")
    path = ProjectService.resolve_project_path(requested) if requested else None
    if path is None:
        active = ProjectService.get_active_project()
        path = ProjectService.resolve_project_path(str(active.get("path"))) if active else None
    if path is None:
        raise ValueError("A valid project or active project is required")
    manifest = ProjectService.load_manifest(path)
    return AssetRepositoryService(path.parent), manifest, path.parent


def _error(exc: Exception):
    status = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, LookupError) else 409 if "conflict" in str(exc).lower() or "locked" in str(exc).lower() else 400
    return jsonify({"ok": False, "message": str(exc), "code": {403: "forbidden", 404: "not_found", 409: "conflict"}.get(status, "invalid_request")}), status


@routes_aaa.route("/api/creative-documents", methods=["GET", "POST"])
def creative_documents():
    try:
        repository, manifest, _ = _context(); service = CreativeDocumentService(repository)
        if request.method == "GET": return jsonify({"ok": True, "documents": service.list(manifest["project_id"], request.args.get("limit", 200))})
        body = request.get_json(silent=True) or {}
        result = service.create(manifest["project_id"], str(body.get("asset_id") or ""), str(body.get("name") or "Untitled"), width=int(body.get("width", 64)), height=int(body.get("height", 64)), frames=int(body.get("frames", 1)), fps=int(body.get("fps", 12)))
        return jsonify({"ok": True, **result}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/creative-documents/<document_id>", methods=["GET", "PUT"])
def creative_document(document_id: str):
    try:
        repository, _, _ = _context(); service = CreativeDocumentService(repository)
        if request.method == "GET": return jsonify({"ok": True, **service.get(document_id)})
        body = request.get_json(silent=True) or {}
        return jsonify({"ok": True, **service.save(document_id, body.get("document", {}), expected_revision_id=body.get("expected_revision_id"))})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/workspaces", methods=["PUT"])
def save_workspace():
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "workspace": CreativeDocumentService(repository).save_workspace(str(body.get("user_id") or "local"), manifest["project_id"], str(body.get("name") or "Default"), body.get("layout", {}))})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/studio/users", methods=["POST"])
def studio_user():
    try:
        repository, _, _ = _context(); body = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "user": StudioCollaborationService(repository).upsert_user(str(body.get("user_id") or ""), str(body.get("display_name") or ""), str(body.get("email") or ""))}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/studio/members", methods=["PUT"])
def studio_member():
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}
        result = StudioCollaborationService(repository).set_member(manifest["project_id"], str(body.get("user_id") or ""), str(body.get("role") or "viewer"), actor_id=str(body.get("actor_id") or "local"))
        return jsonify({"ok": True, "member": result})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/studio/assets/<asset_id>/lock", methods=["POST", "DELETE"])
def studio_lock(asset_id: str):
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}; service = StudioCollaborationService(repository); owner = str(body.get("owner_id") or "local")
        if request.method == "DELETE": return jsonify({"ok": service.release_lock(manifest["project_id"], asset_id, owner, str(body.get("token") or ""))})
        return jsonify({"ok": True, "lock": service.acquire_lock(manifest["project_id"], asset_id, owner, int(body.get("ttl_seconds", 300)))})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/studio/assets/<asset_id>/comments", methods=["POST"])
def studio_comment(asset_id: str):
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}
        result = StudioCollaborationService(repository).comment(manifest["project_id"], asset_id, str(body.get("revision_id") or ""), str(body.get("author_id") or "local"), str(body.get("body") or ""), body.get("location"), str(body.get("parent_comment_id") or ""))
        return jsonify({"ok": True, "comment": result}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/studio/assets/<asset_id>/review", methods=["POST"])
def studio_review(asset_id: str):
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}
        result = StudioCollaborationService(repository).review(manifest["project_id"], asset_id, str(body.get("revision_id") or ""), str(body.get("state") or "in_review"), str(body.get("actor_id") or "local"), str(body.get("assignee_id") or ""), str(body.get("note") or ""))
        return jsonify({"ok": True, "review": result}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/studio/activity", methods=["GET"])
def studio_activity():
    try:
        repository, manifest, _ = _context(); return jsonify({"ok": True, "activity": StudioCollaborationService(repository).activity(manifest["project_id"], request.args.get("limit", 200))})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/live-link/register", methods=["POST"])
def live_link_register():
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "client": PipelineIntegrationService(repository).register_client(manifest["project_id"], str(body.get("engine") or ""), str(body.get("engine_version") or ""), body.get("capabilities"))}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/live-link/poll", methods=["GET"])
def live_link_poll():
    try:
        repository, _, _ = _context(); return jsonify({"ok": True, **PipelineIntegrationService(repository).poll(str(request.args.get("client_id") or ""), request.args.get("limit", 200))})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/live-link/publish", methods=["POST"])
def live_link_publish():
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "event": PipelineIntegrationService(repository).publish_asset(manifest["project_id"], str(body.get("engine") or ""), str(body.get("asset_id") or ""), str(body.get("revision_id") or ""))}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/integrations/<engine>/plugin", methods=["POST"])
def engine_plugin(engine: str):
    try:
        repository, _, project_dir = _context(); result = PipelineIntegrationService(repository).generate_engine_plugin(engine, project_dir / "integrations" / engine); return jsonify({"ok": True, **result}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/interchange/report", methods=["POST"])
def interchange_report():
    try:
        repository, manifest, project_dir = _context(); body = request.get_json(silent=True) or {}; source = (project_dir / str(body.get("source") or "")).resolve(); source.relative_to(project_dir.resolve())
        report = PipelineIntegrationService(repository).interchange_report(manifest["project_id"], str(body.get("format") or ""), str(body.get("direction") or "import"), source, list(body.get("features") or [])); return jsonify({"ok": True, "report": report})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/farm/workers", methods=["POST"])
def farm_worker():
    try:
        repository, _, _ = _context(); return jsonify({"ok": True, "worker": WorkerPoolService(repository).register(request.get_json(silent=True) or {})}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/farm/route", methods=["POST"])
def farm_route():
    try:
        repository, _, _ = _context(); return jsonify(WorkerPoolService(repository).route((request.get_json(silent=True) or {}).get("requirements", {})))
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/art-direction/bibles", methods=["POST"])
def save_bible():
    try:
        repository, manifest, _ = _context(); body = request.get_json(silent=True) or {}; result = ArtDirectionService(repository).save_bible(manifest["project_id"], str(body.get("name") or "Character Bible"), body.get("rules", {}), str(body.get("bible_id") or "")); return jsonify({"ok": True, "bible": result}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/art-direction/analytics", methods=["GET"])
def art_analytics():
    try:
        repository, manifest, _ = _context(); return jsonify({"ok": True, "analytics": ArtDirectionService(repository).analytics(manifest["project_id"])})
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/telemetry/local", methods=["POST"])
def telemetry_local():
    try:
        _, _, project_dir = _context(); body = request.get_json(silent=True) or {}; event = LocalTelemetry(project_dir / ".spriteforge" / "telemetry.jsonl").emit(str(body.get("signal") or "metric"), str(body.get("name") or "event"), value=body.get("value"), attributes=body.get("attributes")); return jsonify({"ok": True, "event": event}), 201
    except Exception as exc: return _error(exc)


@routes_aaa.route("/api/plugins/security", methods=["POST"])
def plugin_security():
    try:
        body = request.get_json(silent=True) or {}; root = Path(__file__).resolve().parents[1]; entrypoint = (root / "plugins" / str(body.get("entrypoint") or "")).resolve(); entrypoint.relative_to((root / "plugins").resolve()); return jsonify(PluginSecurityService.inspect(entrypoint, body.get("manifest", {})))
    except Exception as exc: return _error(exc)
