"""Typed config model for SpriteForge configuration."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def _str(data: Dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    text = str(value or "").strip()
    return text or default


def _int(data: Dict[str, Any], key: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(data.get(key, default)))
    except Exception as exc:
        logger.warning("Invalid integer config value for %s=%r; using %r: %s", key, data.get(key), default, exc)
        return default


def _float(data: Dict[str, Any], key: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(data.get(key, default)))
    except Exception as exc:
        logger.warning("Invalid float config value for %s=%r; using %r: %s", key, data.get(key), default, exc)
        return default


def _bool(data: Dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class PathConfig:
    comfyui_dir: str = "vendor/ComfyUI"
    comfyui_output: str = "vendor/ComfyUI/output"
    sprite_output: str = "output"
    input_dir: str = "input"
    blender_exe: str = "blender"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PathConfig":
        return cls(
            comfyui_dir=_str(data, "comfyui_dir", cls.comfyui_dir),
            comfyui_output=_str(data, "comfyui_output", cls.comfyui_output),
            sprite_output=_str(data, "sprite_output", cls.sprite_output),
            input_dir=_str(data, "input_dir", cls.input_dir),
            blender_exe=_str(data, "blender_exe", cls.blender_exe),
        )


@dataclass
class ComfyConfig:
    host: str = "127.0.0.1"
    port: int = 8188
    listen: str = "127.0.0.1"
    extra_args: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComfyConfig":
        extra = data.get("extra_args", [])
        return cls(
            host=_str(data, "host", cls.host),
            port=_int(data, "port", cls.port, minimum=1),
            listen=_str(data, "listen", cls.listen),
            extra_args=[str(item) for item in extra] if isinstance(extra, list) else [],
        )


@dataclass
class SpriteDefaults:
    fps: int = 12
    cell_size: str = "512x512"
    key_color: str = "auto"
    key_tolerance: float = 45.0
    pad: int = 24
    anchor: str = "bottom-center"
    solidify: int = 2
    drop_loop_duplicate: bool = True
    preview_gif: bool = True
    report: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpriteDefaults":
        return cls(
            fps=_int(data, "fps", cls.fps, minimum=1),
            cell_size=_str(data, "cell_size", cls.cell_size),
            key_color=_str(data, "key_color", cls.key_color),
            key_tolerance=_float(data, "key_tolerance", cls.key_tolerance),
            pad=_int(data, "pad", cls.pad),
            anchor=_str(data, "anchor", cls.anchor),
            solidify=_int(data, "solidify", cls.solidify),
            drop_loop_duplicate=_bool(data, "drop_loop_duplicate", cls.drop_loop_duplicate),
            preview_gif=_bool(data, "preview_gif", cls.preview_gif),
            report=_bool(data, "report", cls.report),
        )


@dataclass
class WanProfile:
    width: int = 832
    height: int = 480
    frames: int = 33
    fps: int = 12
    steps: int = 24
    cfg: float = 6.0
    shift: float = 8.0
    sampler: str = "uni_pc"
    scheduler: str = "simple"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WanProfile":
        return cls(
            width=_int(data, "width", cls.width, minimum=64),
            height=_int(data, "height", cls.height, minimum=64),
            frames=_int(data, "frames", cls.frames, minimum=1),
            fps=_int(data, "fps", cls.fps, minimum=1),
            steps=_int(data, "steps", cls.steps, minimum=1),
            cfg=_float(data, "cfg", cls.cfg),
            shift=_float(data, "shift", cls.shift),
            sampler=_str(data, "sampler", cls.sampler),
            scheduler=_str(data, "scheduler", cls.scheduler),
        )


@dataclass
class SpriteForgeConfig:
    paths: PathConfig = field(default_factory=PathConfig)
    comfy: ComfyConfig = field(default_factory=ComfyConfig)
    sprite_defaults: SpriteDefaults = field(default_factory=SpriteDefaults)
    wan_defaults: WanProfile = field(default_factory=WanProfile)
    profiles: Dict[str, WanProfile] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpriteForgeConfig":
        data = data if isinstance(data, dict) else {}
        warnings: List[str] = []
        raw_profiles = data.get("profiles", {})
        profiles: Dict[str, WanProfile] = {}
        if isinstance(raw_profiles, dict):
            for name, profile in raw_profiles.items():
                if isinstance(profile, dict):
                    profiles[str(name)] = WanProfile.from_dict(profile)
        else:
            warnings.append("profiles must be an object; ignored invalid value")
        model = cls(
            paths=PathConfig.from_dict(data.get("paths", {}) if isinstance(data.get("paths"), dict) else {}),
            comfy=ComfyConfig.from_dict(data.get("comfy", {}) if isinstance(data.get("comfy"), dict) else {}),
            sprite_defaults=SpriteDefaults.from_dict(data.get("sprite_defaults", {}) if isinstance(data.get("sprite_defaults"), dict) else {}),
            wan_defaults=WanProfile.from_dict(data.get("wan_defaults", {}) if isinstance(data.get("wan_defaults"), dict) else {}),
            profiles=profiles,
            warnings=warnings,
        )
        model.warnings.extend(model.validate())
        return model

    def validate(self) -> List[str]:
        warnings: List[str] = []
        if "x" not in self.sprite_defaults.cell_size.lower():
            warnings.append("sprite_defaults.cell_size should look like WIDTHxHEIGHT")
        if not (1 <= self.comfy.port <= 65535):
            warnings.append("comfy.port should be between 1 and 65535")
        for name, profile in self.profiles.items():
            if profile.width % 8 != 0 or profile.height % 8 != 0:
                warnings.append(f"profiles.{name} dimensions should be divisible by 8")
        return warnings

    def effective_profile(self, name: str = "auto") -> Dict[str, Any]:
        profile_name = str(name or "auto").strip()
        if profile_name and profile_name != "auto" and profile_name in self.profiles:
            profile = self.profiles[profile_name]
            source = "profiles"
            resolved_name = profile_name
        else:
            profile = self.wan_defaults
            source = "wan_defaults"
            resolved_name = "wan_defaults" if profile_name == "auto" else profile_name or "wan_defaults"
        return {
            "schema": "spriteforge.effective_profile.v1",
            "requested_profile": profile_name or "auto",
            "resolved_profile": resolved_name,
            "source": source,
            "settings": asdict(profile),
            "sprite_defaults": asdict(self.sprite_defaults),
            "warnings": list(self.warnings),
            "explanation": (
                f"Using named profile '{resolved_name}' from config.profiles."
                if source == "profiles"
                else "Using config.wan_defaults because no matching named profile was found."
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
