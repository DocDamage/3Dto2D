from __future__ import annotations

from typing import Any, Dict

from services.cloud_image_generation_service import cloud_image_provider_status, provider_registry


PIXEL_WORKFLOWS = ("generate", "edit", "inpaint", "prompt_help")

LOCAL_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "local_mock": {
        "provider": "local_mock",
        "label": "Local procedural fallback",
        "configured": True,
        "free_tier": True,
        "local": True,
        "env_names": [],
        "configured_env_name": "",
        "message": "Always available for offline previews and tests.",
        "capabilities": {
            "generate": True,
            "edit": True,
            "inpaint": True,
            "prompt_help": False,
        },
        "limits": [
            "Procedural placeholder output; not a real model result.",
            "Best for validating masks, payloads, history, and export flow.",
        ],
    },
    "comfyui": {
        "provider": "comfyui",
        "label": "ComfyUI local",
        "configured": True,
        "free_tier": True,
        "local": True,
        "env_names": [],
        "configured_env_name": "",
        "message": "Local workflow provider. Requires a running ComfyUI server and matching workflows/models.",
        "capabilities": {
            "generate": True,
            "edit": True,
            "inpaint": True,
            "prompt_help": False,
        },
        "limits": [
            "Startup can be slow while Python, custom nodes, and models load.",
            "Inpaint quality depends on the selected ComfyUI workflow.",
        ],
    },
}

CAPABILITY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "openai": {
        "capabilities": {"generate": True, "edit": True, "inpaint": True, "prompt_help": True},
        "default_model": "gpt-image-1",
        "limits": ["Requires an OpenAI API key with image model access."],
    },
    "gemini": {
        "capabilities": {"generate": True, "edit": False, "inpaint": False, "prompt_help": True},
        "default_model": "imagen-3.0-generate-002",
        "limits": ["Image edit and mask inpaint are treated as unsupported unless routed through ComfyUI."],
    },
    "huggingface": {
        "capabilities": {"generate": True, "edit": False, "inpaint": False, "prompt_help": True},
        "default_model": "community-space",
        "limits": ["Free/community providers vary by model; inpaint requires a selected Space or endpoint."],
    },
    "anthropic": {
        "capabilities": {"generate": False, "edit": False, "inpaint": False, "prompt_help": True},
        "limits": ["Prompt assistance only in SpriteForge; no direct image generation endpoint is wired."],
    },
    "moonshot": {
        "capabilities": {"generate": False, "edit": False, "inpaint": False, "prompt_help": True},
        "limits": ["Prompt assistance only until a compatible image endpoint is configured."],
    },
    "glm": {
        "capabilities": {"generate": False, "edit": False, "inpaint": False, "prompt_help": True},
        "limits": ["Prompt assistance only until a compatible image endpoint is configured."],
    },
    "deepseek": {
        "capabilities": {"generate": False, "edit": False, "inpaint": False, "prompt_help": True},
        "limits": ["Prompt assistance only in SpriteForge; no direct image generation endpoint is wired."],
    },
    "grok": {
        "capabilities": {"generate": False, "edit": False, "inpaint": False, "prompt_help": True},
        "limits": ["Prompt assistance only until xAI image access is wired."],
    },
}


def _empty_capabilities() -> Dict[str, bool]:
    return {workflow: False for workflow in PIXEL_WORKFLOWS}


def _cloud_provider_rows() -> Dict[str, Dict[str, Any]]:
    registry = provider_registry()
    status = cloud_image_provider_status().get("providers", {})
    rows: Dict[str, Dict[str, Any]] = {}
    for provider, info in registry.items():
        cloud_state = status.get(provider, {})
        override = CAPABILITY_OVERRIDES.get(provider, {})
        capabilities = _empty_capabilities()
        capabilities.update(override.get("capabilities", {}))
        rows[provider] = {
            "provider": provider,
            "label": info.get("label", provider),
            "configured": bool(cloud_state.get("configured")),
            "free_tier": bool(info.get("free_tier")),
            "local": False,
            "env_names": info.get("env_names", []),
            "configured_env_name": cloud_state.get("configured_env_name", ""),
            "message": cloud_state.get("message") or "Missing local API key.",
            "image_generation": info.get("image_generation", ""),
            "default_model": override.get("default_model", ""),
            "capabilities": capabilities,
            "limits": list(override.get("limits", [])),
        }
    return rows


def pixel_provider_capabilities(provider: str | None = None) -> Dict[str, Any]:
    rows = {**LOCAL_PROVIDERS, **_cloud_provider_rows()}
    if provider:
        wanted = provider.lower().strip()
        rows = {wanted: rows[wanted]} if wanted in rows else {}
    return {
        "ok": True,
        "schema": "spriteforge.pixel_provider_capabilities.v1",
        "workflows": list(PIXEL_WORKFLOWS),
        "providers": rows,
    }


def provider_workflow_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(payload.get("provider") or "local_mock").lower().strip()
    workflow = str(payload.get("workflow") or "generate").lower().strip()
    rows = pixel_provider_capabilities(provider).get("providers", {})
    if provider not in rows:
        raise ValueError(f"Unsupported provider: {provider}")
    if workflow not in PIXEL_WORKFLOWS:
        raise ValueError(f"Unsupported pixel workflow: {workflow}")

    row = rows[provider]
    supports = bool(row.get("capabilities", {}).get(workflow))
    configured = bool(row.get("configured") or row.get("local"))
    adapter_wired = provider == "local_mock" or workflow in {"generate", "prompt_help"}
    fallback_provider = "local_mock"
    fallback_available = fallback_provider != provider and fallback_provider in LOCAL_PROVIDERS
    if supports and configured and adapter_wired:
        status = "ready"
        action = "Use selected provider."
        mock = provider == "local_mock"
    elif supports and configured and not adapter_wired:
        status = "provider_capable_not_wired"
        action = "Provider can support this workflow, but SpriteForge routes this edit through the local fallback until the adapter is wired."
        mock = fallback_available
    elif supports and not configured:
        status = "missing_key"
        action = f"Add one of these env vars: {', '.join(row.get('env_names', []))}."
        mock = fallback_available
    else:
        status = "unsupported"
        action = "Use local procedural fallback or switch to OpenAI/ComfyUI for real masked edits."
        mock = fallback_available

    return {
        "ok": True,
        "schema": "spriteforge.pixel_provider_workflow_plan.v1",
        "provider": provider,
        "workflow": workflow,
        "status": status,
        "supports_workflow": supports,
        "configured": configured,
        "adapter_wired": adapter_wired,
        "fallback_provider": fallback_provider if mock else "",
        "mock_recommended": mock,
        "action": action,
        "provider_capability": row,
    }
