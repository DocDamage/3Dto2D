"""Persistent professional animation workspace backed by asset revisions."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


WORKSPACE_SCHEMA = "spriteforge.animation_workspace.v1"


class AnimationWorkspaceService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository

    @staticmethod
    def normalize(state: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(state, dict):
            raise ValueError("Animation workspace must be an object")
        frames = state.get("frames", [])
        if not isinstance(frames, list) or not frames:
            raise ValueError("Animation workspace requires at least one frame")
        normalized_frames = []
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict):
                raise ValueError(f"frames[{index}] must be an object")
            duration = frame.get("duration_ms", 83)
            if not isinstance(duration, (int, float)) or duration < 1 or duration > 60_000:
                raise ValueError(f"frames[{index}].duration_ms must be between 1 and 60000")
            normalized_frames.append({
                "source_index": int(frame.get("source_index", index)),
                "duration_ms": int(duration),
                "anchors": AnimationWorkspaceService._points(frame.get("anchors", {}), f"frames[{index}].anchors"),
                "hitboxes": AnimationWorkspaceService._hitboxes(frame.get("hitboxes", []), index),
            })
        clips = state.get("clips", [])
        if not isinstance(clips, list):
            raise ValueError("clips must be a list")
        normalized_clips = []
        names = set()
        for index, clip in enumerate(clips):
            if not isinstance(clip, dict) or not str(clip.get("name") or "").strip():
                raise ValueError(f"clips[{index}].name is required")
            name = str(clip["name"]).strip()
            if name in names:
                raise ValueError(f"Duplicate clip name: {name}")
            names.add(name)
            start, end = int(clip.get("start", 0)), int(clip.get("end", len(frames) - 1))
            if start < 0 or end < start or end >= len(frames):
                raise ValueError(f"clips[{index}] is outside the frame range")
            normalized_clips.append({"name": name, "start": start, "end": end, "loop": bool(clip.get("loop", True))})
        onion = state.get("onion_skin", {}) if isinstance(state.get("onion_skin", {}), dict) else {}
        viewport = state.get("viewport", {}) if isinstance(state.get("viewport", {}), dict) else {}
        return {
            "schema": WORKSPACE_SCHEMA, "schema_version": 1, "frames": normalized_frames,
            "clips": normalized_clips, "fps": max(1, min(240, int(state.get("fps", 12)))),
            "direction_group": str(state.get("direction_group") or ""),
            "onion_skin": {
                "previous": max(0, min(8, int(onion.get("previous", 1)))),
                "next": max(0, min(8, int(onion.get("next", 1)))),
                "opacity": max(0.0, min(1.0, float(onion.get("opacity", 0.28)))),
                "previous_tint": str(onion.get("previous_tint") or "#4cc9f0"),
                "next_tint": str(onion.get("next_tint") or "#f72585"),
            },
            "viewport": {
                "zoom": max(0.25, min(16.0, float(viewport.get("zoom", 1)))),
                "selected_frames": [int(value) for value in viewport.get("selected_frames", []) if isinstance(value, int)],
                "overlay": str(viewport.get("overlay") or "onion"),
            },
        }

    def save(self, asset_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        workspace = self.normalize(state)
        asset = self.repository.get_asset(asset_id)
        current = self.repository.get_revision(asset["current_revision_id"]) if asset.get("current_revision_id") else None
        metadata = copy.deepcopy(current.get("metadata", {})) if current else {}
        metadata["animation_workspace"] = workspace
        operations = list(current.get("operations", [])) if current else []
        operations.append({
            "operation_id": f"op_{uuid.uuid4().hex}", "kind": "animation.workspace",
            "parameters": workspace, "enabled": True,
        })
        return self.repository.new_revision(
            asset_id, generation=copy.deepcopy(current.get("generation", {})) if current else {},
            operations=operations, metadata=metadata,
        )

    def load(self, asset_id: str) -> Dict[str, Any]:
        asset = self.repository.get_asset(asset_id)
        if not asset.get("current_revision_id"):
            return {"schema": WORKSPACE_SCHEMA, "asset_id": asset_id, "workspace": None}
        revision = self.repository.get_revision(asset["current_revision_id"])
        return {
            "schema": WORKSPACE_SCHEMA, "asset_id": asset_id, "revision_id": revision["revision_id"],
            "workspace": revision.get("metadata", {}).get("animation_workspace"),
        }

    def synchronize(self, asset_ids: List[str], source_asset_id: str, *, timing: bool = True, anchors: bool = True) -> List[Dict[str, Any]]:
        source = self.load(source_asset_id).get("workspace")
        if not source:
            raise ValueError("Source asset has no animation workspace")
        results = []
        for asset_id in asset_ids:
            if asset_id == source_asset_id:
                continue
            target = self.load(asset_id).get("workspace") or copy.deepcopy(source)
            if len(target.get("frames", [])) != len(source["frames"]):
                raise ValueError(f"Asset {asset_id} has an incompatible frame count")
            for index, frame in enumerate(target["frames"]):
                if timing:
                    frame["duration_ms"] = source["frames"][index]["duration_ms"]
                if anchors:
                    frame["anchors"] = copy.deepcopy(source["frames"][index]["anchors"])
            if timing:
                target["clips"] = copy.deepcopy(source["clips"])
                target["fps"] = source["fps"]
            results.append(self.save(asset_id, target))
        return results

    @staticmethod
    def _points(value: Any, path: str) -> Dict[str, Dict[str, float]]:
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        result = {}
        for name, point in value.items():
            if not isinstance(point, dict) or not isinstance(point.get("x"), (int, float)) or not isinstance(point.get("y"), (int, float)):
                raise ValueError(f"{path}.{name} must contain numeric x and y")
            result[str(name)] = {"x": float(point["x"]), "y": float(point["y"])}
        return result

    @staticmethod
    def _hitboxes(value: Any, frame_index: int) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"frames[{frame_index}].hitboxes must be a list")
        result = []
        for index, box in enumerate(value):
            if not isinstance(box, dict) or any(not isinstance(box.get(key), (int, float)) for key in ("x", "y", "width", "height")):
                raise ValueError(f"frames[{frame_index}].hitboxes[{index}] has invalid bounds")
            if box["width"] < 0 or box["height"] < 0:
                raise ValueError(f"frames[{frame_index}].hitboxes[{index}] dimensions cannot be negative")
            result.append({
                "name": str(box.get("name") or f"hitbox_{index}"), "kind": str(box.get("kind") or "collision"),
                **{key: float(box[key]) for key in ("x", "y", "width", "height")},
            })
        return result
