from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = ROOT / "config" / "trained_loras.json"


def _empty_registry() -> Dict[str, Any]:
    return {
        "schema": "spriteforge.trained_loras.v1",
        "defaults": {},
        "loras": {},
    }


def load_registry(registry_path: Optional[Path | str] = None) -> Dict[str, Any]:
    path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    if not path.exists():
        return _empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = _empty_registry()
    if not isinstance(data, dict):
        data = _empty_registry()
    data.setdefault("schema", "spriteforge.trained_loras.v1")
    data.setdefault("defaults", {})
    data.setdefault("loras", {})
    return data


def save_registry(registry: Dict[str, Any], registry_path: Optional[Path | str] = None) -> Dict[str, Any]:
    path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return registry


def set_default_lora(
    role: str,
    filename: str,
    label: str,
    trigger: str,
    base_model: str,
    source_path: str = "",
    installed_path: str = "",
    notes: str = "",
    registry_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    clean_role = str(role or "").strip()
    clean_filename = str(filename or "").strip()
    if not clean_role:
        raise ValueError("role is required.")
    if not clean_filename:
        raise ValueError("filename is required.")

    registry = load_registry(registry_path)
    record = {
        "role": clean_role,
        "filename": clean_filename,
        "label": str(label or clean_filename).strip(),
        "trigger": str(trigger or "").strip(),
        "base_model": str(base_model or "").strip(),
        "source_path": str(source_path or "").strip(),
        "installed_path": str(installed_path or "").strip(),
        "notes": str(notes or "").strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    registry["loras"][clean_filename] = record
    registry["defaults"][clean_role] = record
    return save_registry(registry, registry_path)
