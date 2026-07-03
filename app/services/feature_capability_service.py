from __future__ import annotations

from typing import Any, Dict, List

def _default_runtime(row: Dict[str, Any]) -> str:
    configured = str(row.get("default_runtime") or "").strip().lower()
    if configured in {"native", "external"}:
        return configured
    if row.get("native_ready"):
        return "native"
    if row.get("external_ready"):
        return "external"
    return "external"


def _runtime_payload(feature_id: str, runtime: str, row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "feature": feature_id,
        "runtime": runtime,
        "native_ready": bool(row.get("native_ready")),
        "external_ready": bool(row.get("external_ready")),
        "external_apps": list(row.get("external_apps") or []),
        "default_runtime": _default_runtime(row),
        "notes": str(row.get("notes") or ""),
    }


FEATURES: Dict[str, Dict[str, Any]] = {
    "video_to_sprite_conversion": {
        "label": "Video to sprite conversion",
        "native_ready": True,
        "external_ready": False,
        "external_apps": [],
        "notes": "Core extraction, matting, packing, QA, and export run in SpriteForge.",
    },
    "pose_estimation": {
        "label": "Pose estimation",
        "native_ready": True,
        "external_ready": True,
        "external_apps": ["MediaPipe (optional)"] ,
        "notes": "MediaPipe is optional; native OpenCV fallback now ships in-app.",
    },
    "part_segmentation": {
        "label": "Part segmentation",
        "native_ready": True,
        "external_ready": True,
        "external_apps": ["SAM2 (optional)"],
        "notes": "SAM2 is optional; native GrabCut propagation fallback ships in-app.",
    },
    "advanced_matting": {
        "label": "Advanced matting",
        "native_ready": True,
        "external_ready": True,
        "external_apps": ["rembg (optional)", "BiRefNet (optional)"],
        "notes": "Chroma and pixel-art matting are native. Optional ML engines can be selected.",
    },
    "wan_generation": {
        "label": "WAN text/reference generation",
        "native_ready": False,
        "external_ready": True,
        "external_apps": ["ComfyUI"],
        "notes": "Current generation backend is external until native parity is implemented.",
    },
    "lora_training_prepare": {
        "label": "LoRA training prep",
        "native_ready": True,
        "external_ready": False,
        "external_apps": [],
        "notes": "Dataset/config/run-manifest preparation runs inside SpriteForge.",
    },
    "lora_training_run": {
        "label": "LoRA training execution",
        "native_ready": True,
        "external_ready": True,
        "default_runtime": "external",
        "external_apps": ["kohya_ss or ai-toolkit"],
        "notes": "Native in-app style-adapter execution is available with --native-only --run; external trainer stacks remain optional.",
    },
}


def capability_report() -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    native_count = 0
    external_count = 0
    for feature_id, row in FEATURES.items():
        default_runtime = _default_runtime(row)
        runtime = resolve_runtime(feature_id)
        item = {
            "id": feature_id,
            "label": row.get("label") or feature_id,
            "native_ready": bool(row.get("native_ready")),
            "external_ready": bool(row.get("external_ready")),
            "external_apps": list(row.get("external_apps") or []),
            "notes": str(row.get("notes") or ""),
            "default_runtime": default_runtime,
            "runtime": runtime["runtime"],
        }
        entries.append(item)
        if item["native_ready"]:
            native_count += 1
        if item["external_ready"]:
            external_count += 1
    entries.sort(key=lambda item: item["id"])
    return {
        "schema": "spriteforge.feature_capabilities.v1",
        "native_ready_count": native_count,
        "external_ready_count": external_count,
        "entries": entries,
    }


def resolve_runtime(feature_id: str, native_only: bool = False, allow_external: bool = True) -> Dict[str, Any]:
    row = FEATURES.get(feature_id)
    if not row:
        raise RuntimeError(f"Unknown feature capability id: {feature_id}")

    native_ready = bool(row.get("native_ready"))
    external_ready = bool(row.get("external_ready"))
    external_apps = list(row.get("external_apps") or [])
    feature_default = _default_runtime(row)

    if native_ready:
        if feature_default == "external" and not native_only and allow_external and external_ready:
            return _runtime_payload(feature_id, "external", row)
        return _runtime_payload(feature_id, "native", row)

    if not native_only and feature_default != "native" and allow_external and external_ready:
        return _runtime_payload(feature_id, "external", row)

    if external_apps:
        app_list = ", ".join(external_apps)
        if feature_default == "external":
            raise RuntimeError(
                f"Feature '{feature_id}' is not native-ready yet. Current execution requires external app(s): {app_list}."
            )
        if native_only:
            raise RuntimeError(
                f"Feature '{feature_id}' is not native-ready yet. Current execution requires external app(s): {app_list}."
            )
        raise RuntimeError(
            f"Feature '{feature_id}' is not available without external dependencies. External options: {app_list}."
        )

    raise RuntimeError(f"Feature '{feature_id}' has no available runtime in this configuration.")
