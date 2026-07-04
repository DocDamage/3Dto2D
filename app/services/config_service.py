from pathlib import Path
from typing import Any, Dict

from spriteforge_utils import ROOT, load_json as _load_json, save_json as _save_json

CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
EASY_CONFIG_PATH = ROOT / "config" / "easy_mode.json"

def load_json(path: Path, default: Any = None) -> Any:
    return _load_json(path, default if default is not None else {})

def save_json(path: Path, data: Any) -> None:
    _save_json(path, data)

class ConfigService:
    @staticmethod
    def get_config() -> Dict[str, Any]:
        cfg = load_json(CONFIG_PATH, {})
        from services.schema_validation_service import validate_config
        ok, err = validate_config(cfg)
        if not ok:
            import sys
            print(f"[WARN] Config validation warning: {err}", file=sys.stderr)
        return cfg

    @staticmethod
    def get_typed_config():
        from services.config_model import SpriteForgeConfig
        return SpriteForgeConfig.from_dict(ConfigService.get_config())

    @staticmethod
    def explain_effective_profile(profile: str = "auto") -> Dict[str, Any]:
        return ConfigService.get_typed_config().effective_profile(profile)

    @staticmethod
    def save_config(data: Dict[str, Any]) -> None:
        save_json(CONFIG_PATH, data)

    @staticmethod
    def get_easy_config() -> Dict[str, Any]:
        return load_json(EASY_CONFIG_PATH, {})

    @staticmethod
    def save_easy_config(data: Dict[str, Any]) -> None:
        save_json(EASY_CONFIG_PATH, data)

    @staticmethod
    def get_path(dotted_key: str) -> Path:
        cfg = ConfigService.get_config()
        parts = dotted_key.split(".")
        data: Any = cfg
        for p in parts:
            if isinstance(data, dict):
                data = data.get(p, {})
            else:
                data = {}
        if not data or not isinstance(data, str):
            # Fallbacks
            if dotted_key == "paths.comfyui_dir":
                data = "vendor/ComfyUI"
            elif dotted_key == "paths.comfyui_output":
                data = "vendor/ComfyUI/output"
            elif dotted_key == "paths.sprite_output":
                data = "output"
            else:
                data = "."
        p = Path(str(data))
        return p if p.is_absolute() else ROOT / p
