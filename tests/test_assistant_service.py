from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.assistant_knowledge_service import (  # noqa: E402
    AssistantKnowledgeService,
    KnowledgeSpec,
    context_to_text,
)
from services.assistant_service import AssistantService  # noqa: E402
from services.local_llm_service import LocalLlmClient, LocalLlmSettings  # noqa: E402


def _local_root(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    (root / "docs").mkdir(parents=True)
    (root / "config").mkdir(parents=True)
    (root / "projects").mkdir(parents=True)
    (root / "docs" / "END_USER_GUIDE.md").write_text(
        """# SpriteForge Guide

## Export
Open Export, choose Godot, and build the package after Review passes.
HF_TOKEN=MARKDOWN-MUST-NOT-LEAK

## Review
Open Review to inspect loop seams, flicker, silhouette, and frame timing.

## Create
Open Create, choose a character and moves, then preview the final prompt.
""",
        encoding="utf-8",
    )
    (root / "config" / "easy_presets.json").write_text(
        json.dumps({"actions": {"idle": {"frames": 25}, "walk": {"frames": 33}}}),
        encoding="utf-8",
    )
    return root


class _ExplodingModel:
    def generate(self, **_kwargs):
        raise AssertionError("disabled model must not be called")


class _FakeModel:
    def __init__(self, answer: str = "Use Export and choose the Godot card.") -> None:
        self.answer = answer
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.answer


def test_deterministic_rag_works_without_an_llm(tmp_path):
    root = _local_root(tmp_path)
    service = AssistantService(
        root,
        settings=LocalLlmSettings(enabled=False),
        llm_client=_ExplodingModel(),  # type: ignore[arg-type]
    )

    first = service.query("How do I export to Godot?", view="guide")
    second = service.query("How do I export to Godot?", view="guide")

    assert first == second
    assert first["ok"] is True
    assert first["mode"] == "deterministic"
    assert first["generation"]["llm_used"] is False
    assert first["sources"][0]["path"] == "docs/END_USER_GUIDE.md"
    assert first["suggestions"][0]["view"] == "release"
    assert first["suggestions"][0]["action"] == "navigate"
    assert first["safety"]["commands_executed"] is False


def test_configured_local_model_is_optional_and_grounded(tmp_path):
    root = _local_root(tmp_path)
    model = _FakeModel()
    settings = LocalLlmSettings(
        enabled=True,
        provider="openai_compatible",
        endpoint="http://127.0.0.1:1234/v1",
        model="tiny-local-model",
    )
    service = AssistantService(root, settings=settings, llm_client=model)  # type: ignore[arg-type]

    response = service.query("How do I export to Godot?", view="release")

    assert response["mode"] == "local-llm"
    assert response["generation"]["llm_used"] is True
    assert response["answer"] == model.answer
    assert len(model.calls) == 1
    assert "docs/END_USER_GUIDE.md" in model.calls[0]["user_prompt"]
    assert "cannot run commands" in model.calls[0]["system_prompt"]
    assert "MARKDOWN-MUST-NOT-LEAK" not in model.calls[0]["user_prompt"]


def test_model_failure_falls_back_to_the_same_read_only_answer(tmp_path):
    root = _local_root(tmp_path)

    class OfflineModel:
        def generate(self, **_kwargs):
            raise TimeoutError("offline")

    settings = LocalLlmSettings(
        enabled=True,
        endpoint="http://127.0.0.1:11434",
        model="small",
    )
    service = AssistantService(root, settings=settings, llm_client=OfflineModel())  # type: ignore[arg-type]

    response = service.query("How do I review a flickering loop?")

    assert response["ok"] is True
    assert response["mode"] == "deterministic"
    assert response["generation"]["fallback_reason"] == "model_unavailable"
    assert "Review" in response["answer"]
    assert response["safety"]["commands_executed"] is False


def test_model_command_or_script_output_is_rejected_for_safe_fallback(tmp_path):
    root = _local_root(tmp_path)
    model = _FakeModel("```sh\nrm -rf output\n```")
    settings = LocalLlmSettings(
        enabled=True,
        endpoint="http://127.0.0.1:11434",
        model="small",
    )

    response = AssistantService(root, settings=settings, llm_client=model).query(  # type: ignore[arg-type]
        "How do I review my sprite?"
    )

    assert response["mode"] == "deterministic"
    assert response["generation"]["fallback_reason"] == "unsafe_model_answer"
    assert "rm -rf" not in response["answer"]
    assert response["suggestions"][0]["action"] == "navigate"


@pytest.mark.parametrize(
    ("context", "expected_view", "answer_fragment"),
    [
        ({"job_running": True, "job_stage": "polishing"}, "tasks", "still being crafted"),
        ({"job_running": False, "output_count": 2}, "quality", "finished result"),
        ({"generation_ready": True, "output_count": 0}, "generate", "generator is ready"),
        ({"generation_ready": False, "output_count": 0}, "setup", "Start in Setup"),
    ],
)
def test_next_step_fallback_uses_safe_ui_context(tmp_path, context, expected_view, answer_fragment):
    response = AssistantService(_local_root(tmp_path)).query(
        "What should I do next?",
        view="guide",
        context=context,
    )

    assert answer_fragment in response["answer"]
    assert response["suggestions"][0]["view"] == expected_view
    assert response["suggestions"][0]["action"] == "navigate"


def test_project_context_is_allowlisted_filtered_and_request_only(tmp_path):
    root = _local_root(tmp_path)
    project_dir = root / "projects" / "hero"
    project_dir.mkdir()
    manifest = project_dir / "spriteforge_project.json"
    manifest.write_text(json.dumps({
        "name": "hero",
        "style": "bright cel-shaded adventure sk-thisCredentialMustNeverLeak123",
        "actions": ["idle", "jump"],
        "api_key": "SECRET-MUST-NOT-LEAK",
        "private_notes": {"password": "ALSO-SECRET"},
    }), encoding="utf-8")
    service = AssistantService(root)

    response = service.query(
        "What style and actions are in my project?",
        project={"path": "projects/hero/spriteforge_project.json"},
    )
    serialized = json.dumps(response)

    assert response["safety"]["project_context_included"] is True
    assert any(source["kind"] == "project" for source in response["sources"])
    assert "bright cel-shaded adventure" in serialized
    assert "sk-thisCredentialMustNeverLeak123" not in serialized
    assert "SECRET-MUST-NOT-LEAK" not in serialized
    assert "ALSO-SECRET" not in serialized

    without_project = service.query("What style and actions are in my project?")
    assert all(source["kind"] != "project" for source in without_project["sources"])


def test_project_context_rejects_paths_outside_projects(tmp_path):
    root = _local_root(tmp_path)
    outside = tmp_path / "spriteforge_project.json"
    outside.write_text('{"name":"outside"}', encoding="utf-8")

    with pytest.raises(ValueError, match="projects folder"):
        AssistantService(root).query("What is this project?", project=str(outside))


def test_safe_config_summary_excludes_credentials(tmp_path):
    root = _local_root(tmp_path)
    (root / "config" / "spriteforge_config.json").write_text(json.dumps({
        "sprite_defaults": {"fps": 12, "api_key": "INNER-SECRET"},
        "assistant": {"api_key": "TOP-SECRET"},
        "cloud": {"access_token": "CLOUD-SECRET"},
    }), encoding="utf-8")

    response = AssistantService(root).query("What is the default sprite fps?")
    serialized = json.dumps(response)

    assert "fps: 12" in serialized
    assert "INNER-SECRET" not in serialized
    assert "TOP-SECRET" not in serialized
    assert "CLOUD-SECRET" not in serialized


def test_user_preset_token_fields_are_never_indexed(tmp_path):
    root = _local_root(tmp_path)
    (root / "config" / "user_presets.json").write_text(json.dumps({
        "export": {
            "refresh_token": "REFRESH-MUST-NOT-LEAK",
            "hf_token": "HF-MUST-NOT-LEAK",
            "style": "friendly adventure",
        }
    }), encoding="utf-8")

    chunks = AssistantKnowledgeService(root).build_chunks()
    indexed = "\n".join(chunk.text for chunk in chunks)

    assert "friendly adventure" in indexed
    assert "REFRESH-MUST-NOT-LEAK" not in indexed
    assert "HF-MUST-NOT-LEAK" not in indexed


def test_context_preserves_false_and_zero_values():
    context = context_to_text({"job_running": False, "output_count": 0, "generation_ready": True})

    assert "job_running: False" in context
    assert "output_count: 0" in context
    assert "generation_ready: True" in context


def test_status_counts_only_sources_that_can_be_indexed(tmp_path):
    root = tmp_path / "app"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "broken.json").write_text("not-json", encoding="utf-8")
    knowledge = AssistantKnowledgeService(
        root,
        approved_files=(KnowledgeSpec("docs/broken.json", "Broken", "preset"),),
    )

    status = AssistantService(root, knowledge=knowledge).status()

    assert status["knowledge"]["approved_sources"] == 1
    assert status["knowledge"]["available_sources"] == 0
    assert status["ready"] is False


def test_local_llm_client_rejects_non_loopback_endpoint():
    settings = LocalLlmSettings(
        enabled=True,
        provider="openai_compatible",
        endpoint="https://example.com/v1",
        model="not-used",
    )
    client = LocalLlmClient(settings)

    assert settings.configured is False
    with pytest.raises(ValueError, match="loopback"):
        client.generate(system_prompt="safe", user_prompt="hello")


@pytest.mark.parametrize(
    ("provider", "response", "expected"),
    [
        ("ollama", {"message": {"content": "Ollama answer"}}, "Ollama answer"),
        (
            "openai_compatible",
            {"choices": [{"message": {"content": "OpenAI-compatible answer"}}]},
            "OpenAI-compatible answer",
        ),
    ],
)
def test_local_llm_client_parses_supported_response_shapes(provider, response, expected):
    class StubClient(LocalLlmClient):
        def _post_json(self, payload):
            assert payload["stream"] is False
            return response

    client = StubClient(LocalLlmSettings(
        enabled=True,
        provider=provider,
        endpoint="http://127.0.0.1:11434",
        model="small",
    ))

    assert client.generate(system_prompt="safe", user_prompt="hello") == expected


def test_assistant_backend_has_no_command_execution_dependencies():
    service_files = [
        APP / "services" / "assistant_service.py",
        APP / "services" / "assistant_knowledge_service.py",
        APP / "services" / "local_llm_service.py",
        APP / "web_routes" / "routes_assistant.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in service_files)

    for forbidden in ("import subprocess", "os.system(", "Popen(", "shell=True"):
        assert forbidden not in source
