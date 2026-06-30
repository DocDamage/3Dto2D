import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
EASY_CONFIG_PATH = ROOT / "config" / "easy_mode.json"

def load_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default or {}

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        import os
        os.replace(str(temp_path), str(path))
    except Exception as e:
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            raise e
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

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
