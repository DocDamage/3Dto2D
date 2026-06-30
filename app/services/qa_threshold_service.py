from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_THRESHOLDS = {
    "loop_rmse_threshold": 20.0,
    "foot_drift_threshold": 3.0,
    "center_drift_threshold": 8.0,
}

PRESET_THRESHOLDS = {
    "Classic Platformer (Side-Scroller)": {
        "loop_rmse_threshold": 15.0,
        "foot_drift_threshold": 2.0,
        "center_drift_threshold": 5.0,
    },
    "Top-Down RPG Character": {
        "loop_rmse_threshold": 18.0,
        "foot_drift_threshold": 3.0,
        "center_drift_threshold": 8.0,
    },
    "Animated Water Tile": {
        "loop_rmse_threshold": 10.0,
        "foot_drift_threshold": 999.0,
        "center_drift_threshold": 999.0,
    },
    "Animated Lava Tile": {
        "loop_rmse_threshold": 10.0,
        "foot_drift_threshold": 999.0,
        "center_drift_threshold": 999.0,
    },
}


def _float_value(data: Dict[str, Any], key: str) -> Optional[float]:
    if key not in data:
        return None
    try:
        return float(data[key])
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _thresholds_from_preset_row(row: Dict[str, Any]) -> Dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    mapping = {
        "qa_threshold_loop_rmse": "loop_rmse_threshold",
        "qa_threshold_foot_drift": "foot_drift_threshold",
        "qa_threshold_center_drift": "center_drift_threshold",
    }
    for source, dest in mapping.items():
        value = _float_value(row, source)
        if value is not None:
            thresholds[dest] = value
    return thresholds


def _user_presets(root: Path) -> Dict[str, Any]:
    data = _load_json(root / "config" / "user_presets.json")
    return data if isinstance(data, dict) else {}


def thresholds_for_preset(root: Path, preset_name: str) -> Dict[str, float]:
    user = _user_presets(root)
    if preset_name in user and isinstance(user[preset_name], dict):
        return _thresholds_from_preset_row(user[preset_name])
    return dict(PRESET_THRESHOLDS.get(preset_name, DEFAULT_THRESHOLDS))


def _project_manifest_for_sprite(root: Path, sprite_dir: Path) -> Optional[Path]:
    resolved = sprite_dir.resolve()
    projects = (root / "projects").resolve()
    try:
        resolved.relative_to(projects)
    except ValueError:
        pass
    else:
        for parent in [resolved, *resolved.parents]:
            manifest = parent / "spriteforge_project.json"
            if manifest.exists():
                return manifest

    state = _load_json(root / "output" / "projects" / "project_state.json")
    active = str(state.get("active_project") or "")
    if active:
        manifest = (root / active).resolve()
        try:
            manifest.relative_to(projects)
        except ValueError:
            return None
        return manifest if manifest.exists() else None
    return None


def thresholds_from_project(root: Path, sprite_dir: Path) -> Dict[str, float]:
    manifest = _project_manifest_for_sprite(root, sprite_dir)
    if not manifest:
        return dict(DEFAULT_THRESHOLDS)
    data = _load_json(manifest)
    if data.get("preset"):
        thresholds = thresholds_for_preset(root, str(data["preset"]))
    else:
        thresholds = dict(DEFAULT_THRESHOLDS)
    gates = data.get("quality_gates", {})
    if isinstance(gates, dict):
        loop = _float_value(gates, "loop_seam_threshold")
        foot = _float_value(gates, "max_foot_drift")
        center = _float_value(gates, "max_center_drift")
        if loop is not None:
            thresholds["loop_rmse_threshold"] = loop
        if foot is not None:
            thresholds["foot_drift_threshold"] = foot
        if center is not None:
            thresholds["center_drift_threshold"] = center
    return thresholds


def resolve_qa_thresholds(root: Path, sprite_dir: Path, preset_name: str = "auto") -> Dict[str, float]:
    if preset_name and preset_name != "auto":
        return thresholds_for_preset(root, preset_name)
    return thresholds_from_project(root, sprite_dir)


def threshold_cli_args(thresholds: Dict[str, float]) -> list[str]:
    return [
        "--loop-rmse-threshold",
        str(thresholds["loop_rmse_threshold"]),
        "--foot-drift-threshold",
        str(thresholds["foot_drift_threshold"]),
        "--center-drift-threshold",
        str(thresholds["center_drift_threshold"]),
    ]
