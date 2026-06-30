from __future__ import annotations
from typing import Dict, Any, List

__all__ = ["discover_commands", "execute_command"]

def discover_commands() -> List[Dict[str, Any]]:
    return [
        {
            "id": "run_qa",
            "label": "Run QA Checks",
            "description": "Analyzes the current active project outputs.",
            "view": "qa",
            "enabled": True,
            "disabled_reason": None,
            "action_type": "frontend_route",
            "endpoint": "/api/sprite/qa",
            "requires_confirmation": False
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
            "requires_confirmation": False
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
        }
    ]

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
