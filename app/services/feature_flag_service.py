"""Small, explicit feature-flag boundary for incremental roadmap delivery."""
from __future__ import annotations

import os
from typing import Any, Dict


DEFAULT_FLAGS = {
    "asset_history": True,
    "non_destructive_editing": True,
    "unified_qa": True,
    "professional_animation": True,
    "batch_matrix": True,
    "deterministic_exports": False,
    "workflow_builder": True,
    "production_dashboard": True,
    "packaging_updates": True,
}


class FeatureFlagService:
    @staticmethod
    def resolve(project_manifest: Dict[str, Any] | None = None) -> Dict[str, bool]:
        flags = dict(DEFAULT_FLAGS)
        project_flags = (project_manifest or {}).get("feature_flags", {})
        if isinstance(project_flags, dict):
            for key, value in project_flags.items():
                if key in flags and isinstance(value, bool):
                    flags[key] = value
        for key in flags:
            env = os.getenv(f"SPRITEFORGE_FEATURE_{key.upper()}")
            if env is not None:
                flags[key] = env.strip().lower() in {"1", "true", "yes", "on"}
        return flags
