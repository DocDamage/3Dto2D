from flask import Blueprint, request, jsonify
from services.onboarding_service import create_sample_project, build_first_sprite_request
from services.action_command_service import discover_commands, execute_command

routes_onboarding = Blueprint("routes_onboarding", __name__)

@routes_onboarding.route("/api/onboarding/sample", methods=["POST"])
def post_sample_project():
    res = create_sample_project()
    return jsonify(res)

@routes_onboarding.route("/api/onboarding/wizard", methods=["POST"])
def post_wizard_payload():
    body = request.json or {}
    res = build_first_sprite_request(body)
    return jsonify({"ok": True, "payload": res})

@routes_onboarding.route("/api/commands/list", methods=["GET"])
def get_commands():
    return jsonify({"ok": True, "commands": discover_commands()})

@routes_onboarding.route("/api/commands/execute", methods=["POST"])
def post_execute_command():
    body = request.json or {}
    cmd_id = str(body.get("id") or "").strip()
    if not cmd_id:
        return jsonify({"ok": False, "message": "id parameter required"}), 400
    res = execute_command(cmd_id)
    return jsonify(res)
