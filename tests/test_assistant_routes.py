from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.rate_limit_service import reset_rate_limits  # noqa: E402
from spriteforge_web import app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    for name in (
        "SPRITEFORGE_ASSISTANT_LLM_ENABLED",
        "SPRITEFORGE_ASSISTANT_PROVIDER",
        "SPRITEFORGE_ASSISTANT_ENDPOINT",
        "SPRITEFORGE_ASSISTANT_MODEL",
        "SPRITEFORGE_ASSISTANT_API_KEY",
        "SPRITEFORGE_ASSISTANT_TIMEOUT_SECONDS",
        "SPRITEFORGE_ASSISTANT_MAX_CONTEXT_CHUNKS",
        "SPRITEFORGE_ASSISTANT_MAX_ANSWER_CHARS",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_rate_limits()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
    reset_rate_limits()


def test_assistant_status_is_local_read_only_and_disabled_by_default(client):
    response = client.get("/api/assistant/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["mode"] == "deterministic"
    assert payload["llm"]["enabled"] is False
    assert payload["llm"]["local_only"] is True
    assert payload["llm"]["endpoint"].startswith(("http://127.0.0.1", "http://localhost"))
    assert payload["llm"]["timeout_seconds"] > 0
    assert payload["llm"]["max_context_chunks"] > 0
    assert payload["llm"]["max_answer_chars"] >= 500
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["commands_executed"] is False


def test_assistant_query_route_returns_companion_contract(client):
    response = client.post("/api/assistant/query", json={
        "question": "How do I export a sprite to Godot?",
        "view": "release",
        "context": {"phase": "export", "provider": "local"},
    })
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert isinstance(payload["answer"], str) and payload["answer"]
    assert payload["mode"] == "deterministic"
    assert payload["sources"]
    assert {"title", "path", "snippet"}.issubset(payload["sources"][0])
    assert payload["suggestions"][0]["action"] == "navigate"
    assert payload["suggestions"][0]["view"] == "release"
    assert payload["safety"]["actions"] == "navigation_only"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": ["not", "text"]},
        {"question": "hello", "view": {"bad": True}},
        {"question": "hello", "context": 123},
    ],
)
def test_assistant_query_validates_input(client, body):
    response = client.post("/api/assistant/query", json=body)

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_assistant_query_rejects_oversized_payload(client):
    response = client.post(
        "/api/assistant/query",
        data=json.dumps({"question": "export", "context": "x" * 70_000}),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json()["code"] == "payload_too_large"


def test_assistant_query_rejects_project_path_escape(client, tmp_path):
    outside = tmp_path / "spriteforge_project.json"
    outside.write_text('{"name":"outside"}', encoding="utf-8")

    response = client.post("/api/assistant/query", json={
        "question": "What is this project?",
        "project": str(outside),
    })

    assert response.status_code == 400
    assert "projects folder" in response.get_json()["message"]


def test_assistant_query_uses_standard_token_protection(client):
    response = client.post(
        "/api/assistant/query",
        headers={"X-Force-Token-Check": "true"},
        json={"question": "How do I create a sprite?"},
    )

    assert response.status_code == 401
    assert "Unauthorized" in response.get_json()["message"]


def _write_config(monkeypatch, tmp_path, payload):
    import services.config_service as config_module

    path = tmp_path / "spriteforge_config.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    return path


def test_assistant_settings_saves_allowlisted_fields_and_preserves_config(client, monkeypatch, tmp_path):
    path = _write_config(monkeypatch, tmp_path, {
        "paths": {"sprite_output": "keep-output"},
        "custom_section": {"keep": True},
        "assistant": {
            "mascot": {"name": "Forge"},
            "llm": {
                "enabled": False,
                "provider": "ollama",
                "endpoint": "http://127.0.0.1:11434",
                "model": "",
                "api_key": "OLD-CONFIG-SECRET",
                "legacy_field": "remove-me",
            },
        },
    })

    response = client.post("/api/assistant/settings", json={
        "enabled": True,
        "provider": "openai",
        "endpoint": "http://localhost:1234/v1",
        "model": "tiny-local",
        "timeout_seconds": 7.5,
        "max_context_chunks": 4,
        "max_answer_chars": 2_500,
        "api_key": "REQUEST-SECRET",
        "unknown": "do-not-save",
    })
    payload = response.get_json()
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["settings"]["provider"] == "openai_compatible"
    assert payload["llm"]["configured"] is True
    assert stored["paths"] == {"sprite_output": "keep-output"}
    assert stored["custom_section"] == {"keep": True}
    assert stored["assistant"]["mascot"] == {"name": "Forge"}
    assert set(stored["assistant"]["llm"]) == {
        "enabled", "provider", "endpoint", "model", "timeout_seconds",
        "max_context_chunks", "max_answer_chars",
    }
    serialized = json.dumps({"response": payload, "stored": stored})
    assert "OLD-CONFIG-SECRET" not in serialized
    assert "REQUEST-SECRET" not in serialized
    assert "legacy_field" not in serialized
    assert "do-not-save" not in serialized


def test_assistant_settings_supports_nested_partial_updates(client, monkeypatch, tmp_path):
    path = _write_config(monkeypatch, tmp_path, {
        "logging": {"level": "DEBUG"},
        "assistant": {"llm": {
            "enabled": False,
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "old-model",
            "timeout_seconds": 12,
            "max_context_chunks": 5,
            "max_answer_chars": 4_000,
        }},
    })

    response = client.post("/api/assistant/settings", json={"llm": {"model": "new-model"}})
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert stored["logging"] == {"level": "DEBUG"}
    assert stored["assistant"]["llm"]["model"] == "new-model"
    assert stored["assistant"]["llm"]["endpoint"] == "http://127.0.0.1:11434"
    assert stored["assistant"]["llm"]["max_context_chunks"] == 5

    wrapped = client.post(
        "/api/assistant/settings",
        json={"assistant": {"llm": {"max_context_chunks": 3}}},
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert wrapped.status_code == 200
    assert stored["assistant"]["llm"]["max_context_chunks"] == 3


def test_assistant_settings_rejects_remote_endpoint_without_mutating_config(client, monkeypatch, tmp_path):
    path = _write_config(monkeypatch, tmp_path, {
        "custom": {"untouched": "yes"},
        "assistant": {"llm": {
            "enabled": False,
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "small",
        }},
    })
    before = path.read_text(encoding="utf-8")

    response = client.post("/api/assistant/settings", json={
        "enabled": False,
        "endpoint": "https://example.com/v1",
    })

    assert response.status_code == 400
    assert "loopback" in response.get_json()["message"]
    assert path.read_text(encoding="utf-8") == before


def test_assistant_settings_never_overwrites_an_unreadable_config(client, monkeypatch, tmp_path):
    path = _write_config(monkeypatch, tmp_path, {"temporary": True})
    path.write_text("{broken-json", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    response = client.post("/api/assistant/settings", json={"model": "small"})

    assert response.status_code == 400
    assert path.read_text(encoding="utf-8") == before
    assert "no settings were changed" in response.get_json()["message"]


@pytest.mark.parametrize("update", [
    {"enabled": "sometimes"},
    {"enabled": True},
    {"provider": "hosted_cloud"},
    {"endpoint": "http://127.0.0.1:0"},
    {"endpoint": "http://user:password@127.0.0.1:11434"},
    {"endpoint": "http://127.0.0.1:11434/api?key=secret"},
    {"model": "x" * 257},
    {"timeout_seconds": 0},
    {"timeout_seconds": 31},
    {"max_context_chunks": 0},
    {"max_context_chunks": 9},
    {"max_answer_chars": 499},
    {"max_answer_chars": 8_001},
    {"api_key": "ONLY-A-SECRET"},
])
def test_assistant_settings_rejects_invalid_or_secret_only_updates(client, monkeypatch, tmp_path, update):
    path = _write_config(monkeypatch, tmp_path, {
        "assistant": {"llm": {
            "enabled": False,
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "",
            "timeout_seconds": 12,
            "max_context_chunks": 5,
            "max_answer_chars": 4_000,
        }},
    })
    before = path.read_text(encoding="utf-8")

    response = client.post("/api/assistant/settings", json=update)

    assert response.status_code == 400
    assert path.read_text(encoding="utf-8") == before
    assert "ONLY-A-SECRET" not in json.dumps(response.get_json())


def test_assistant_settings_never_echoes_or_persists_environment_api_key(client, monkeypatch, tmp_path):
    path = _write_config(monkeypatch, tmp_path, {
        "assistant": {"llm": {
            "enabled": False,
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "small",
        }},
    })
    monkeypatch.setenv("SPRITEFORGE_ASSISTANT_API_KEY", "ENVIRONMENT-SECRET")

    response = client.post("/api/assistant/settings", json={"timeout_seconds": 9})
    combined = json.dumps(response.get_json()) + path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "ENVIRONMENT-SECRET" not in combined
    assert "api_key" not in combined


def test_assistant_settings_uses_standard_token_protection(client):
    response = client.post(
        "/api/assistant/settings",
        headers={"X-Force-Token-Check": "true"},
        json={"enabled": False},
    )

    assert response.status_code == 401
    assert "Unauthorized" in response.get_json()["message"]


def test_assistant_settings_accepts_a_valid_session_token(client, monkeypatch, tmp_path):
    _write_config(monkeypatch, tmp_path, {
        "assistant": {"llm": {
            "enabled": False,
            "provider": "ollama",
            "endpoint": "http://127.0.0.1:11434",
            "model": "small",
        }},
    })
    token = client.get("/api/auth/token").get_json()["token"]

    response = client.post(
        "/api/assistant/settings",
        headers={"X-Force-Token-Check": "true", "X-SF-Token": token},
        json={"timeout_seconds": 8},
    )

    assert response.status_code == 200
    assert response.get_json()["settings"]["timeout_seconds"] == 8
