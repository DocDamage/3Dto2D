"""Preset Advisor service for SpriteForge Studio.

Given GPU VRAM, installed models, and a target quality goal, returns a
concrete recommended tier / profile / settings so users don't have to
guess around Wan 2.1 vs 2.2, debug vs quality, frame count, etc.
"""
from __future__ import annotations

from typing import Any, Dict, List


# Quality-goal multipliers relative to the base hardware recommendation
_QUALITY_PRESETS: Dict[str, Dict[str, Any]] = {
    "fast": {
        "steps_override": 15,
        "frames_scale": 0.5,
        "label": "Fast / Draft",
    },
    "balanced": {
        "steps_override": 20,
        "frames_scale": 1.0,
        "label": "Balanced",
    },
    "quality": {
        "steps_override": 30,
        "frames_scale": 1.25,
        "label": "High Quality",
    },
}


def advise(quality_goal: str = "balanced") -> Dict[str, Any]:
    """Return a recommended tier/profile/settings dict for the current hardware."""
    warnings: List[str] = []

    # Lazy imports to avoid circular deps and to let this module load even
    # if optional GPU libs are absent.
    try:
        from services.model_service import ModelService
        models = ModelService.get_summary()
    except Exception:
        models = {}

    try:
        from services.comfy_service import ComfyService
        gpu = ComfyService.get_gpu_info()
    except Exception:
        gpu = {}

    try:
        from services.config_service import ConfigService
        cfg = ConfigService.get_config()
    except Exception:
        cfg = {}

    # --- derive VRAM in MiB ---
    vram_mib = 0
    gpu_label = gpu.get("label", "Unknown GPU")
    mem_str = gpu.get("memory_total", "") or ""
    if mem_str:
        try:
            # e.g. "12288 MiB" or "12 GB"
            num = float("".join(c for c in mem_str if c.isdigit() or c == "."))
            if "GB" in mem_str.upper() or "GiB" in mem_str.upper():
                vram_mib = int(num * 1024)
            else:
                vram_mib = int(num)
        except Exception:
            pass

    # --- base hardware recommendation ---
    try:
        from spriteforge_hardware import recommendation
        hw = recommendation(vram_mib)
    except Exception:
        hw = {
            "tier": "wan21_safe",
            "profile": "auto",
            "sprite_defaults": {"cell_size": "512x512", "fps": 12, "frames": 33},
        }

    base_tier: str = hw.get("tier", "wan21_safe")
    base_profile: str = hw.get("profile", "auto")
    sprite_defaults: Dict[str, Any] = hw.get("sprite_defaults", {})
    base_frames: int = int(sprite_defaults.get("frames", 33))
    base_fps: int = int(sprite_defaults.get("fps", 12))
    cell_size: str = str(sprite_defaults.get("cell_size", "512x512"))

    # --- check model availability ---
    safe_ok = bool(models.get("ok"))
    advanced_present = int(models.get("advanced_present", 0))
    advanced_total = int(models.get("advanced_total", 1))
    advanced_ok = advanced_total > 0 and advanced_present == advanced_total

    if not safe_ok:
        warnings.append("Safe Wan 2.1 models not fully installed — run 'Install All' first.")
    if not advanced_ok:
        warnings.append("Wan 2.2 advanced models not installed — advanced tier unavailable.")

    # Downgrade tier if required models are missing
    tier = base_tier
    if "advanced" in tier and not advanced_ok:
        tier = "wan21_safe"
        warnings.append(f"Tier downgraded from {base_tier!r} to 'wan21_safe' (advanced models absent).")

    # --- apply quality-goal scaling ---
    preset = _QUALITY_PRESETS.get(quality_goal, _QUALITY_PRESETS["balanced"])
    steps: int = preset["steps_override"]
    frames: int = max(9, int(base_frames * preset["frames_scale"]))

    # Round frames to nearest odd number (WAN works best with odd frame counts)
    if frames % 2 == 0:
        frames += 1

    # --- build rationale ---
    vram_gb = vram_mib / 1024 if vram_mib else 0
    rationale_parts = [
        f"GPU: {gpu_label}" + (f" ({vram_gb:.0f} GB VRAM)" if vram_mib else " (unknown VRAM)") + ".",
        f"Hardware tier: {tier}, profile: {base_profile}.",
        f"Quality goal: {preset['label']} → {steps} steps, {frames} frames.",
    ]
    if not safe_ok:
        rationale_parts.append("Safe models missing; install them before generating.")

    return {
        "tier": tier,
        "profile": base_profile,
        "cell_size": cell_size,
        "fps": base_fps,
        "frame_count": frames,
        "steps": steps,
        "quality_goal": quality_goal,
        "rationale": " ".join(rationale_parts),
        "warnings": warnings,
        "gpu": gpu_label,
        "vram_gb": round(vram_gb, 1),
    }
