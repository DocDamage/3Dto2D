from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from spriteforge_utils import ROOT, load_json, save_json

DEFAULT_REGISTRY_PATH = ROOT / "config" / "trained_loras.json"
logger = logging.getLogger(__name__)


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
    data = load_json(path, None)
    if data is None:
        logger.warning("Could not load trained LoRA registry from %s; using an empty registry.", path)
        data = _empty_registry()
    if not isinstance(data, dict):
        logger.warning("Trained LoRA registry at %s was not an object; using an empty registry.", path)
        data = _empty_registry()
    data.setdefault("schema", "spriteforge.trained_loras.v1")
    data.setdefault("defaults", {})
    data.setdefault("loras", {})
    return data


def save_registry(registry: Dict[str, Any], registry_path: Optional[Path | str] = None) -> Dict[str, Any]:
    path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path, registry)
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
    metadata: Optional[Dict[str, Any]] = None,
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
        "metadata": metadata if isinstance(metadata, dict) else {},
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    registry["loras"][clean_filename] = record
    registry["defaults"][clean_role] = record
    return save_registry(registry, registry_path)


def plan_lora_comparison(
    prompt: str,
    lora_names: list[str] | None = None,
    registry_path: Optional[Path | str] = None,
    base_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    registry = load_registry(registry_path)
    loras = registry.get("loras") if isinstance(registry.get("loras"), dict) else {}
    selected_names = [
        str(name or "").strip()
        for name in (lora_names or list(loras.keys())[:4])
        if str(name or "").strip()
    ]
    if not selected_names:
        raise ValueError("At least one LoRA must be selected for comparison.")
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        raise ValueError("prompt is required.")

    payload_template = dict(base_payload or {})
    variants = []
    missing = []
    for index, name in enumerate(selected_names[:4]):
        record = loras.get(name)
        if not isinstance(record, dict):
            missing.append(name)
            continue
        trigger = str(record.get("trigger") or "").strip()
        variant_prompt = f"{trigger}, {clean_prompt}" if trigger and trigger not in clean_prompt else clean_prompt
        payload = {
            **payload_template,
            "prompt": variant_prompt,
            "lora_name": record.get("filename") or name,
            "lora_label": record.get("label") or name,
            "lora_trigger": trigger,
            "comparison_slot": chr(ord("A") + index),
        }
        variants.append({
            "slot": payload["comparison_slot"],
            "lora_name": payload["lora_name"],
            "label": payload["lora_label"],
            "trigger": trigger,
            "base_model": record.get("base_model", ""),
            "metadata": record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
            "payload": payload,
        })
    if not variants:
        raise ValueError("No selected LoRAs were found in the registry.")
    return {
        "ok": True,
        "schema": "spriteforge.lora_comparison_plan.v1",
        "prompt": clean_prompt,
        "variant_count": len(variants),
        "variants": variants,
        "missing": missing,
        "compare_player": {
            "min_variants": 2,
            "max_variants": 4,
            "next_step": "Generate each variant, then open Compare Player with the resulting sprite folders.",
        },
    }
