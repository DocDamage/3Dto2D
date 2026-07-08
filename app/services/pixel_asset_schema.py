from __future__ import annotations
from typing import Any, Dict, List, Tuple

__all__ = ["validate_pixel_asset", "validate_pixel_style_profile", "validate_pixel_asset_batch"]

def _err(path: str, msg: str) -> Tuple[bool, str]:
    return False, f"Validation error at '{path}': {msg}" if path else f"Validation error: {msg}"

def validate_pixel_asset(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Pixel asset metadata must be a JSON object")

    required = ["schema", "asset_id", "asset_type", "prompt", "resolution", "palette", "outputs"]
    for req in required:
        if req not in data:
            return _err("", f"Missing required field '{req}'")

    if data["schema"] != "spriteforge.pixel_asset.v1":
        return _err("schema", f"Expected schema 'spriteforge.pixel_asset.v1', got '{data['schema']}'")

    if not isinstance(data["asset_id"], str) or not data["asset_id"].startswith("pxa_"):
        return _err("asset_id", "asset_id must be a string starting with 'pxa_'")

    valid_types = {"character", "creature", "item", "weapon", "potion", "ui_icon", "tileset", "background"}
    if data["asset_type"] not in valid_types:
        return _err("asset_type", f"Invalid asset_type. Must be one of {valid_types}")

    if not isinstance(data["resolution"], list) or len(data["resolution"]) != 2:
        return _err("resolution", "resolution must be a list/tuple of two integers")
    if not all(isinstance(x, int) and x > 0 for x in data["resolution"]):
        return _err("resolution", "resolution elements must be positive integers")

    if not isinstance(data["palette"], dict):
        return _err("palette", "palette must be a dictionary")
    if "max_colors" in data["palette"] and not isinstance(data["palette"]["max_colors"], int):
        return _err("palette.max_colors", "max_colors must be an integer")
    if "colors" in data["palette"] and not isinstance(data["palette"]["colors"], list):
        return _err("palette.colors", "colors must be a list of strings")

    if not isinstance(data["outputs"], dict):
        return _err("outputs", "outputs must be a dictionary")
    for key in ["png", "preview", "metadata"]:
        if key in data["outputs"] and not isinstance(data["outputs"][key], str):
            return _err(f"outputs.{key}", f"{key} output path must be a string")

    return True, ""

def validate_pixel_style_profile(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Pixel style profile must be a JSON object")

    required = ["schema", "style_id", "name"]
    for req in required:
        if req not in data:
            return _err("", f"Missing required field '{req}'")

    if data["schema"] != "spriteforge.pixel_style_profile.v1":
        return _err("schema", f"Expected schema 'spriteforge.pixel_style_profile.v1', got '{data['schema']}'")

    if not isinstance(data["style_id"], str) or not data["style_id"].startswith("style_"):
        return _err("style_id", "style_id must be a string starting with 'style_'")

    if not isinstance(data["name"], str) or not data["name"].strip():
        return _err("name", "name must be a non-empty string")

    if "palette" in data and not isinstance(data["palette"], list):
        return _err("palette", "palette must be a list of hex strings")

    if "lora_name" in data and not isinstance(data["lora_name"], str):
        return _err("lora_name", "lora_name must be a string")

    if "lora_weight" in data:
        weight = data["lora_weight"]
        if not isinstance(weight, (int, float)) or weight < 0.1 or weight > 1.5:
            return _err("lora_weight", "lora_weight must be a number between 0.1 and 1.5")

    if "base_model" in data and not isinstance(data["base_model"], str):
        return _err("base_model", "base_model must be a string")

    return True, ""

def validate_pixel_asset_batch(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Pixel asset batch manifest must be a JSON object")

    required = ["schema", "batch_id", "asset_type", "count", "asset_ids", "output_dir"]
    for req in required:
        if req not in data:
            return _err("", f"Missing required field '{req}'")

    if data["schema"] != "spriteforge.pixel_asset_batch.v1":
        return _err("schema", f"Expected schema 'spriteforge.pixel_asset_batch.v1', got '{data['schema']}'")

    if not isinstance(data["batch_id"], str) or not data["batch_id"].startswith("pxb_"):
        return _err("batch_id", "batch_id must be a string starting with 'pxb_'")

    if not isinstance(data["count"], int) or data["count"] <= 0:
        return _err("count", "count must be a positive integer")

    if not isinstance(data["asset_ids"], list):
        return _err("asset_ids", "asset_ids must be a list of asset IDs")

    return True, ""
