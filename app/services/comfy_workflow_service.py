#!/usr/bin/env python3
"""ComfyUI workflow patching, validation, and prompt submission."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from .config_service import ConfigService
except ImportError:
    from config_service import ConfigService  # type: ignore


def validate_workflow_file(path: Path, print_errors: bool = True) -> bool:
    ok = True
    try:
        wf = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        if print_errors:
            print(f"[FAIL] Could not load workflow: {exc}")
        return False
    node_ids = {str(k) for k in wf if not str(k).startswith("_")}
    for k, v in wf.items():
        if str(k).startswith("_"):
            continue
        if not isinstance(v, dict) or "class_type" not in v:
            ok = False
            if print_errors:
                print(f"[FAIL] Node {k} missing class_type")
            continue
        inputs = v.get("inputs", {})
        if isinstance(inputs, dict):
            for name, val in inputs.items():
                if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                    if val[0] not in node_ids:
                        ok = False
                        if print_errors:
                            print(f"[FAIL] Node {k}.{name} links to missing node {val[0]}")
    if print_errors:
        print(f"{'[OK]' if ok else '[FAIL]'} Workflow sanity: {path}")
    return ok


def node_inputs_by_id_or_class(out: Dict[str, Any], node_id: Optional[str], classes: Sequence[str]) -> Tuple[str, Dict[str, Any]]:
    if node_id and node_id in out:
        return node_id, out[node_id].setdefault("inputs", {})
    for cls in classes:
        for k, v in sorted(out.items(), key=lambda kv: str(kv[0])):
            if isinstance(v, dict) and v.get("class_type") == cls:
                return k, v.setdefault("inputs", {})
    raise KeyError(f"Workflow is missing node id={node_id!r} or classes={list(classes)}")


def clip_text_nodes(out: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if "6" in out and "7" in out:
        return out["6"].setdefault("inputs", {}), out["7"].setdefault("inputs", {})
    nodes = []
    for k, v in out.items():
        if isinstance(v, dict) and v.get("class_type") == "CLIPTextEncode":
            nodes.append((str(k), v.setdefault("inputs", {})))
    nodes.sort(key=lambda kv: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", kv[0])])
    if len(nodes) < 2:
        raise KeyError("Workflow needs at least two CLIPTextEncode nodes for positive and negative prompts")
    return nodes[0][1], nodes[1][1]


def set_input(inputs: Dict[str, Any], key_options: Sequence[str], value: Any) -> bool:
    for key in key_options:
        if key in inputs:
            inputs[key] = value
            return True
    return False


def find_nodes_feeding_into(workflow: Dict[str, Any], target_classes: set) -> set:
    feeding_ids = set()
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        if cls in target_classes:
            for val in node.get("inputs", {}).values():
                if isinstance(val, list) and len(val) == 2:
                    source_id = str(val[0])
                    feeding_ids.add(source_id)
    return feeding_ids


def patch_workflow_images(workflow: Dict[str, Any], reference_image_name: Optional[str], style_image_name: Optional[str]) -> Tuple[int, int]:
    ip_clip_classes = {
        "IPAdapterApply", "IPAdapterApplyAdvanced", "IPAdapter", "IPAdapterAdvanced",
        "IPAdapterEncoder", "CLIPVisionEncode", "PrepImageForClipVision", "IPAdapterFaceID"
    }
    style_source_ids = find_nodes_feeding_into(workflow, ip_clip_classes)
    if style_source_ids:
        style_source_ids = style_source_ids.union(find_nodes_feeding_into(workflow, {
            workflow[sid].get("class_type") for sid in style_source_ids if sid in workflow
        }))

    style_count = 0
    ref_count = 0

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        if cls in {"LoadImage", "LoadImageMask", "LoadImageUpload"}:
            inputs = node.setdefault("inputs", {})
            if style_image_name and node_id in style_source_ids:
                inputs["image"] = style_image_name
                if "upload" in inputs:
                    inputs["upload"] = "image"
                style_count += 1
            elif reference_image_name:
                inputs["image"] = reference_image_name
                if "upload" in inputs:
                    inputs["upload"] = "image"
                ref_count += 1

    if style_image_name and style_count == 0:
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") in {"LoadImage", "LoadImageMask", "LoadImageUpload"}:
                inputs = node.setdefault("inputs", {})
                inputs["image"] = style_image_name
                style_count += 1
                break

    return ref_count, style_count


def patch_clip_vision_nodes(workflow: Dict[str, Any], clip_vision: Optional[str]) -> int:
    if not clip_vision:
        return 0
    count = 0
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "CLIPVisionLoader":
            inputs = node.setdefault("inputs", {})
            if set_input(inputs, ["clip_name", "model_name", "clip_vision_name"], clip_vision):
                count += 1
    return count


def patch_posepack_nodes(workflow: Dict[str, Any], posepack_path: str) -> int:
    pp = Path(posepack_path)
    frame_dir = pp / "frames" if pp.is_dir() and (pp / "frames").exists() else pp
    count = 0
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        cls = str(node.get("class_type", "")).lower()
        if "pose" in cls or "image" in cls or "video" in cls or "vhs" in cls:
            for key in ["directory", "image_dir", "folder", "path", "input_dir", "frame_dir"]:
                if key in inputs:
                    inputs[key] = str(frame_dir)
                    count += 1
            for key in ["image", "start_image"]:
                if key in inputs and frame_dir.is_dir():
                    first = sorted(frame_dir.glob("*.png"))[:1]
                    if first:
                        inputs[key] = str(first[0])
                        count += 1
    return count