"""HTTP boundary for SpriteForge companion queries and bounded local settings."""
from __future__ import annotations

import threading
from typing import Any, Mapping

from flask import Blueprint, jsonify, request

from services.assistant_service import AssistantService
from services import config_service as config_service_module
from services.config_service import ConfigService
from services.local_llm_service import LocalLlmSettings, normalize_persisted_llm_settings
from services.rate_limit_service import route_rate_limited
from spriteforge_utils import load_json as load_json_file
from web_helpers import ROOT
from web_routes.api_errors import ApiError, api_exception_response


routes_assistant = Blueprint("routes_assistant", __name__)
MAX_ASSISTANT_REQUEST_BYTES = 64_000
_SETTINGS_LOCK = threading.RLock()


def _service() -> AssistantService:
    return AssistantService.from_config(ROOT, ConfigService.get_config())


def _assistant_error(exc: Exception, *, status: int = 500):
    return api_exception_response(exc, default_status=status, context="assistant-routes")


def _save_llm_settings(update: Mapping[str, Any]) -> dict[str, Any]:
    with _SETTINGS_LOCK:
        config_path = config_service_module.CONFIG_PATH
        config = load_json_file(config_path, None) if config_path.exists() else {}
        if not isinstance(config, dict):
            raise ValueError("SpriteForge configuration could not be read as a JSON object; no settings were changed.")
        assistant = config.get("assistant")
        assistant_section = dict(assistant) if isinstance(assistant, Mapping) else {}
        current_llm = assistant_section.get("llm")
        normalized = normalize_persisted_llm_settings(
            current_llm if isinstance(current_llm, Mapping) else {},
            update,
        )
        # The persisted llm object is rebuilt from the explicit allowlist. This
        # also removes any legacy api_key field while preserving all config data
        # outside assistant.llm.
        assistant_section["llm"] = normalized
        config["assistant"] = assistant_section
        ConfigService.save_config(config)
    settings = LocalLlmSettings.from_mapping(normalized, environ={})
    return {
        "ok": True,
        "settings": normalized,
        "llm": settings.public_status(),
        "message": "Local assistant settings saved.",
    }


@routes_assistant.route("/api/assistant/status", methods=["GET"])
def get_assistant_status():
    try:
        return jsonify(_service().status())
    except Exception as exc:
        return _assistant_error(exc)


@routes_assistant.route("/api/assistant/settings", methods=["POST"])
@route_rate_limited("assistant_settings", limit=10, window_seconds=60)
def post_assistant_settings():
    if request.content_length is not None and request.content_length > MAX_ASSISTANT_REQUEST_BYTES:
        return _assistant_error(
            ApiError("Assistant settings request is too large.", 413, code="payload_too_large"),
            status=413,
        )
    body = request.get_json(silent=True)
    if not isinstance(body, Mapping):
        return _assistant_error(ApiError("A JSON object is required.", 400), status=400)
    if "llm" in body:
        raw_update = body.get("llm")
    elif "assistant" in body:
        assistant = body.get("assistant")
        raw_update = assistant.get("llm") if isinstance(assistant, Mapping) else None
    else:
        raw_update = body
    if not isinstance(raw_update, Mapping):
        return _assistant_error(ApiError("LLM settings must be a JSON object.", 400), status=400)
    try:
        return jsonify(_save_llm_settings(raw_update))
    except ValueError as exc:
        return _assistant_error(exc, status=400)
    except Exception as exc:
        return _assistant_error(exc)


@routes_assistant.route("/api/assistant/query", methods=["POST"])
@route_rate_limited("assistant_query", limit=30, window_seconds=60)
def post_assistant_query():
    if request.content_length is not None and request.content_length > MAX_ASSISTANT_REQUEST_BYTES:
        return _assistant_error(
            ApiError("Assistant request is too large.", 413, code="payload_too_large"),
            status=413,
        )
    body = request.get_json(silent=True)
    if not isinstance(body, Mapping):
        return _assistant_error(ApiError("A JSON object is required.", 400), status=400)
    question: Any = body.get("question")
    if not isinstance(question, str):
        return _assistant_error(ApiError("Question must be text.", 400), status=400)
    view = body.get("view", "")
    if view is not None and not isinstance(view, str):
        return _assistant_error(ApiError("View must be text.", 400), status=400)
    project = body.get("project")
    if project is not None and not isinstance(project, (str, bool, Mapping)):
        return _assistant_error(ApiError("Project must be a project path or project summary.", 400), status=400)
    context = body.get("context")
    if context is not None and not isinstance(context, (str, Mapping, list)):
        return _assistant_error(ApiError("Context must be text, an object, or a list.", 400), status=400)
    try:
        response = _service().query(
            question,
            project=project,
            view=str(view or ""),
            context=context,
        )
        return jsonify(response)
    except ValueError as exc:
        return _assistant_error(exc, status=400)
    except Exception as exc:
        return _assistant_error(exc)


__all__ = ["routes_assistant"]
