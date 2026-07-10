"""Canonical layered creative documents and professional workspace layouts."""
from __future__ import annotations

import copy
import json
import uuid
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


DOCUMENT_SCHEMA = "spriteforge.creative_document.v1"
WORKSPACE_SCHEMA = "spriteforge.workspace_layout.v1"
BLEND_MODES = {"normal", "multiply", "screen", "overlay", "add", "subtract", "darken", "lighten", "color", "luminosity"}
LAYER_TYPES = {"paint", "reference", "group", "mask", "adjustment", "symbol", "bone", "hitbox", "guide"}


class CreativeDocumentService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS creative_documents (
                    document_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_id TEXT NOT NULL,
                    current_revision_id TEXT, name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS creative_document_revisions (
                    revision_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES creative_documents(document_id) ON DELETE CASCADE,
                    parent_revision_id TEXT, payload_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_creative_documents_project ON creative_documents(project_id,updated_at DESC);
                CREATE TABLE IF NOT EXISTS workspace_layouts (
                    user_id TEXT NOT NULL, project_id TEXT NOT NULL, name TEXT NOT NULL,
                    payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id,project_id,name)
                );
                """
            )

    def create(self, project_id: str, asset_id: str, name: str, *, width: int, height: int,
               frames: int = 1, fps: int = 12) -> Dict[str, Any]:
        if width < 1 or height < 1 or width > 32768 or height > 32768:
            raise ValueError("Document dimensions must be between 1 and 32768")
        if frames < 1 or frames > 100_000:
            raise ValueError("Document frame count must be between 1 and 100000")
        document_id, now = f"doc_{uuid.uuid4().hex}", utc_now()
        with self.repository._connect() as connection:
            connection.execute(
                "INSERT INTO creative_documents(document_id,project_id,asset_id,name,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (document_id, project_id, asset_id, str(name or "Untitled"), now, now),
            )
        payload = {
            "schema": DOCUMENT_SCHEMA, "schema_version": 1, "document_id": document_id,
            "project_id": project_id, "asset_id": asset_id, "name": str(name or "Untitled"),
            "canvas": {"width": int(width), "height": int(height), "pixel_aspect": 1.0, "color_space": "srgb"},
            "timeline": {"frame_count": int(frames), "fps": int(fps), "clips": [], "events": []},
            "layers": [{"layer_id": f"layer_{uuid.uuid4().hex}", "name": "Paint", "type": "paint", "visible": True, "locked": False, "opacity": 1.0, "blend_mode": "normal", "children": [], "keyframes": []}],
            "symbols": {}, "bones": [], "constraints": [], "guides": [], "metadata": {},
        }
        return self.save(document_id, payload, expected_revision_id=None)

    def save(self, document_id: str, payload: Dict[str, Any], *, expected_revision_id: str | None) -> Dict[str, Any]:
        normalized = self.validate(payload)
        with self.repository._connect() as connection:
            document = connection.execute("SELECT * FROM creative_documents WHERE document_id=?", (document_id,)).fetchone()
            if not document:
                raise LookupError(f"Creative document not found: {document_id}")
            current = document["current_revision_id"]
            if current != expected_revision_id:
                raise ValueError("Document revision conflict; reload before saving")
            normalized["document_id"] = document_id
            normalized["project_id"] = document["project_id"]
            normalized["asset_id"] = document["asset_id"]
            import hashlib
            canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            revision_id, now = f"docrev_{uuid.uuid4().hex}", utc_now()
            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute("SELECT current_revision_id FROM creative_documents WHERE document_id=?", (document_id,)).fetchone()[0]
            if latest != expected_revision_id:
                raise ValueError("Document changed while saving")
            connection.execute(
                "INSERT INTO creative_document_revisions VALUES(?,?,?,?,?,?)",
                (revision_id, document_id, current, canonical, digest, now),
            )
            connection.execute(
                "UPDATE creative_documents SET current_revision_id=?,name=?,updated_at=? WHERE document_id=?",
                (revision_id, normalized["name"], now, document_id),
            )
        return {"document_id": document_id, "revision_id": revision_id, "parent_revision_id": current, "content_hash": digest, "document": normalized}

    def get(self, document_id: str) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute(
                """SELECT d.*,r.payload_json,r.content_hash FROM creative_documents d
                   LEFT JOIN creative_document_revisions r ON r.revision_id=d.current_revision_id WHERE d.document_id=?""", (document_id,)
            ).fetchone()
        if not row:
            raise LookupError(f"Creative document not found: {document_id}")
        return {"document_id": document_id, "revision_id": row["current_revision_id"], "content_hash": row["content_hash"], "document": json.loads(row["payload_json"]) if row["payload_json"] else None}

    def list(self, project_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self.repository._connect() as connection:
            rows = connection.execute(
                "SELECT document_id,asset_id,current_revision_id,name,updated_at FROM creative_documents WHERE project_id=? ORDER BY updated_at DESC LIMIT ?",
                (project_id, max(1, min(1000, int(limit)))),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_workspace(self, user_id: str, project_id: str, name: str, layout: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(layout, dict) or not isinstance(layout.get("panels", []), list):
            raise ValueError("Workspace layout requires a panels list")
        payload = {
            "schema": WORKSPACE_SCHEMA, "schema_version": 1, "user_id": str(user_id),
            "project_id": str(project_id), "name": str(name or "Default"),
            "panels": layout.get("panels", []), "shortcuts": layout.get("shortcuts", {}),
            "active_tool": str(layout.get("active_tool") or "brush"), "updated_at": utc_now(),
        }
        with self.repository._connect() as connection:
            connection.execute(
                """INSERT INTO workspace_layouts VALUES(?,?,?,?,?) ON CONFLICT(user_id,project_id,name)
                   DO UPDATE SET payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
                (payload["user_id"], payload["project_id"], payload["name"], json.dumps(payload, sort_keys=True), payload["updated_at"]),
            )
        return payload

    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Creative document must be an object")
        normalized = copy.deepcopy(payload)
        normalized["schema"], normalized["schema_version"] = DOCUMENT_SCHEMA, 1
        normalized["name"] = str(normalized.get("name") or "Untitled")[:200]
        canvas = normalized.get("canvas")
        if not isinstance(canvas, dict) or any(not isinstance(canvas.get(key), int) or canvas[key] < 1 for key in ("width", "height")):
            raise ValueError("canvas requires positive integer width and height")
        timeline = normalized.get("timeline", {})
        if not isinstance(timeline, dict) or int(timeline.get("frame_count", 0)) < 1:
            raise ValueError("timeline.frame_count must be positive")
        layers = normalized.get("layers")
        if not isinstance(layers, list) or not layers:
            raise ValueError("Document requires at least one layer")
        seen: set[str] = set()
        normalized["layers"] = [self._layer(layer, seen, 0) for layer in layers]
        constraints = normalized.get("constraints", [])
        if not isinstance(constraints, list):
            raise ValueError("constraints must be a list")
        return normalized

    def _layer(self, layer: Any, seen: set[str], depth: int) -> Dict[str, Any]:
        if depth > 32 or not isinstance(layer, dict):
            raise ValueError("Layer hierarchy is invalid or exceeds depth 32")
        layer_id = str(layer.get("layer_id") or f"layer_{uuid.uuid4().hex}")
        if layer_id in seen:
            raise ValueError(f"Duplicate layer ID: {layer_id}")
        seen.add(layer_id)
        layer_type = str(layer.get("type") or "paint")
        blend = str(layer.get("blend_mode") or "normal")
        if layer_type not in LAYER_TYPES or blend not in BLEND_MODES:
            raise ValueError(f"Unsupported layer type or blend mode on {layer_id}")
        keyframes = layer.get("keyframes", [])
        if not isinstance(keyframes, list):
            raise ValueError(f"Layer {layer_id} keyframes must be a list")
        clean_keys = []
        for key in keyframes:
            if not isinstance(key, dict) or not isinstance(key.get("frame"), int) or key["frame"] < 0:
                raise ValueError(f"Layer {layer_id} has an invalid keyframe")
            clean_keys.append({
                "frame": key["frame"], "value": key.get("value"),
                "interpolation": str(key.get("interpolation") or "hold"),
                "in_tangent": key.get("in_tangent"), "out_tangent": key.get("out_tangent"),
            })
        return {
            "layer_id": layer_id, "name": str(layer.get("name") or layer_type.title()), "type": layer_type,
            "visible": bool(layer.get("visible", True)), "locked": bool(layer.get("locked", False)),
            "opacity": max(0.0, min(1.0, float(layer.get("opacity", 1)))), "blend_mode": blend,
            "content": layer.get("content"), "mask_layer_id": layer.get("mask_layer_id"),
            "transform": layer.get("transform", {"x": 0, "y": 0, "scale_x": 1, "scale_y": 1, "rotation": 0}),
            "keyframes": sorted(clean_keys, key=lambda item: item["frame"]),
            "children": [self._layer(child, seen, depth + 1) for child in layer.get("children", [])],
        }
