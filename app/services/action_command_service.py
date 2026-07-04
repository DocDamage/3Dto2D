from __future__ import annotations
from typing import Dict, Any, List

__all__ = ["discover_commands", "execute_command"]


def _normalize_command(cmd: Dict[str, Any]) -> Dict[str, Any]:
    action_type = str(cmd.get("action_type") or "frontend_route")
    requires_confirmation = bool(cmd.get("requires_confirmation"))
    endpoint = str(cmd.get("endpoint") or "")
    mutating = action_type == "backend_action" or endpoint.startswith("/api/job") or endpoint.startswith("/api/onboarding") or "build" in endpoint
    risk_level = "high" if requires_confirmation else "medium" if mutating else "low"
    category = "navigation" if action_type == "frontend_route" else "operation"
    normalized = {
        "enabled": True,
        "disabled_reason": None,
        "requires_confirmation": False,
        "endpoint": "",
        **cmd,
    }
    normalized["category"] = str(cmd.get("category") or category)
    normalized["risk_level"] = str(cmd.get("risk_level") or risk_level)
    normalized["mutates_state"] = bool(cmd.get("mutates_state", mutating))
    normalized["confirmation_message"] = str(
        cmd.get("confirmation_message")
        or (f"Run {cmd.get('label', cmd.get('id', 'command'))}? This may change project state." if requires_confirmation else "")
    )
    return normalized


def discover_commands() -> List[Dict[str, Any]]:
    commands = [
        {
            "id": "run_qa",
            "label": "Run QA Checks",
            "description": "Analyzes the current active project outputs.",
            "view": "quality",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/sprite/qa",
            "requires_confirmation": False,
            "shortcut": "Ctrl+Q",
        },
        {
            "id": "open_latest",
            "label": "Open Latest Output",
            "description": "Opens the folder containing the most recently processed sprite sheet.",
            "view": "dashboard",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "backend_action",
            "endpoint": "/api/open",
            "requires_confirmation": False
        },
        {
            "id": "build_release",
            "label": "Build Character Release",
            "description": "Packages the active sprite sheet into a game-ready zip release.",
            "view": "release",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/release/build",
            "requires_confirmation": False,
            "shortcut": "Ctrl+E",
        },
        {
            "id": "retry_jobs",
            "label": "Retry Failed Jobs",
            "description": "Reruns all failed generator tasks in the queue.",
            "view": "queues",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "backend_action",
            "endpoint": "/api/job/retry",
            "requires_confirmation": True
        },
        {
            "id": "create_sample",
            "label": "Create Onboarding Sample Project",
            "description": "Copies the demo sprite assets and configures the SampleProject workspace.",
            "view": "guide",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "backend_action",
            "endpoint": "/api/onboarding/sample",
            "requires_confirmation": False
        },
        {
            "id": "generate_sprite",
            "label": "Generate First Sprite",
            "description": "Starts the guided simple character generator.",
            "view": "generate",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/onboarding/wizard",
            "requires_confirmation": False
        },
        {
            "id": "training_lab",
            "label": "Open Training Lab",
            "description": "Builds private LoRA-ready character and auto-tile datasets from owned assets.",
            "view": "training",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False
        }
    ]
    commands.extend([
        {
            "id": "open_cloud_hub",
            "label": "Open Cloud Generation Hub",
            "description": "Manage remote ComfyUI nodes and cloud image provider readiness.",
            "view": "cloud_hub",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
        },
        {
            "id": "open_animation_player",
            "label": "Open Animation Player",
            "description": "Preview sprite sheets with playback, frame stepping, and export controls.",
            "view": "animation_player",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
        },
        {
            "id": "open_compare_player",
            "label": "Open Compare Player",
            "description": "Compare two or more sprite variants with synchronized playback.",
            "view": "compare_player",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
        },
        {
            "id": "open_lighting_preview",
            "label": "Open Lighting Preview",
            "description": "Preview normal-map lighting for generated sprite sheets.",
            "view": "lighting_preview",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
        },
        {
            "id": "open_frame_editor",
            "label": "Open Frame Timeline Editor",
            "description": "Delete, reorder, duplicate, and repack generated frames.",
            "view": "frame_editor",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
        },
        {
            "id": "open_packs_exports",
            "label": "Open Packs and Export Tools",
            "description": "Build atlases, animated exports, and Spine/DragonBones skeletal JSON.",
            "view": "packs",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
            "shortcut": "Ctrl+E",
        },
        {
            "id": "export_animation_webm",
            "label": "Export Animation WebM Preview",
            "description": "Open the Animation Player and use Record WebM for the selected sprite playback.",
            "view": "animation_player",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "",
            "requires_confirmation": False,
            "shortcut": "Ctrl+E",
        },
        {
            "id": "pick_compare_winner",
            "label": "Pick Compare Winner",
            "description": "Open the Compare Player to mark the winning variant in experiment history.",
            "view": "compare_player",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/experiments/pick-winner",
            "requires_confirmation": False,
        },
        {
            "id": "open_qa_advisor",
            "label": "Open QA Advisor Repairs",
            "description": "Review sprite quality guidance and one-click repair suggestions.",
            "view": "quality",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/qa/advisor",
            "requires_confirmation": False,
            "shortcut": "Ctrl+Q",
        },
        {
            "id": "preview_cloud_sprite_plan",
            "label": "Preview Cloud Sprite Plan",
            "description": "Open Cloud Hub to inspect provider readiness, hardened prompts, and local post-processing.",
            "view": "cloud_hub",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/cloud/image-generation-plan",
            "requires_confirmation": False,
        },
    ])
    return [_normalize_command(command) for command in commands]

def execute_command(cmd_id: str) -> Dict[str, Any]:
    commands = {c["id"]: c for c in discover_commands()}
    if cmd_id not in commands:
        return {"ok": False, "message": f"Command '{cmd_id}' not found."}

    cmd = commands[cmd_id]
    if cmd["requires_confirmation"]:
        return {
            "ok": True,
            "requires_confirmation": True,
            "message": f"Execution of '{cmd['label']}' requires user confirmation."
        }

    return {
        "ok": True,
        "requires_confirmation": False,
        "action": cmd
    }
