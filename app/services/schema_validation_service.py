from __future__ import annotations
from typing import Any, Dict, List, Tuple

__all__ = ["validate_config", "validate_project", "validate_queue", "validate_sheet"]

def _err(path: str, msg: str) -> Tuple[bool, str]:
    return False, f"Validation error at '{path}': {msg}" if path else f"Validation error: {msg}"

def validate_config(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Config must be a JSON object")

    if "comfy" in data:
        comfy = data["comfy"]
        if comfy is not None:
            if not isinstance(comfy, dict):
                return _err("comfy", "comfy settings must be a JSON object")
            if "host" in comfy and comfy["host"] is not None and not isinstance(comfy["host"], str):
                return _err("comfy.host", "host must be a string")
            if "port" in comfy and comfy["port"] is not None and not isinstance(comfy["port"], int):
                return _err("comfy.port", "port must be an integer")

    if "paths" in data:
        paths = data["paths"]
        if paths is not None and not isinstance(paths, dict):
            return _err("paths", "paths must be a JSON object")

    return True, ""

def validate_project(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Project metadata must be a JSON object")

    required = ["project_name", "project_root"]
    for req in required:
        if req not in data:
            return _err("", f"Missing required field '{req}'")
        if not isinstance(data[req], str) or not data[req].strip():
            return _err(req, f"'{req}' must be a non-empty string")

    return True, ""

def validate_queue(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Queue job must be a JSON object")

    required = ["id", "status", "title"]
    for req in required:
        if req not in data:
            return _err("", f"Missing required field '{req}'")
        if not isinstance(data[req], str) or not data[req].strip():
            return _err(req, f"'{req}' must be a non-empty string")

    if data["status"] not in {"pending", "running", "completed", "failed", "cancelled"}:
        return _err("status", f"Invalid status '{data['status']}'")

    return True, ""

def validate_sheet(data: Any) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return _err("", "Sheet metadata must be a JSON object")

    required = ["frame_count", "fps", "image", "frame_width", "frame_height", "columns", "rows", "frames"]
    for req in required:
        if req not in data:
            return _err("", f"Missing required field '{req}'")

    for num_field in ["frame_count", "frame_width", "frame_height", "columns", "rows"]:
        if not isinstance(data[num_field], int) or data[num_field] <= 0:
            return _err(num_field, f"'{num_field}' must be a positive integer")

    if not isinstance(data["fps"], (int, float)) or data["fps"] <= 0:
        return _err("fps", "'fps' must be a positive number")

    if not isinstance(data["image"], str) or not data["image"].strip():
        return _err("image", "'image' must be a non-empty string")

    if not isinstance(data["frames"], list):
        return _err("frames", "'frames' must be a list of frame objects")

    for idx, frame in enumerate(data["frames"]):
        if not isinstance(frame, dict):
            return _err(f"frames[{idx}]", "Frame item must be a JSON object")
        for rect_field in ["x", "y", "w", "h"]:
            if rect_field not in frame:
                return _err(f"frames[{idx}]", f"Missing field '{rect_field}' in frame object")
            if not isinstance(frame[rect_field], int) or frame[rect_field] < 0:
                return _err(f"frames[{idx}].{rect_field}", f"'{rect_field}' must be a non-negative integer")

    return True, ""
