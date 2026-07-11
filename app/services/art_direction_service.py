"""Versioned character bibles, art-direction validation, gameplay previews, and yield analytics."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


class ArtDirectionService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS character_bibles (
                    bible_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
                    current_revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS character_bible_revisions (
                    bible_id TEXT NOT NULL REFERENCES character_bibles(bible_id), revision INTEGER NOT NULL,
                    payload_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(bible_id,revision)
                );
                CREATE TABLE IF NOT EXISTS gameplay_scenarios (
                    scenario_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
                    payload_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approval_board_items (
                    item_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_id TEXT NOT NULL, revision_id TEXT NOT NULL,
                    lane TEXT NOT NULL, rank INTEGER NOT NULL, note TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                """
            )

    def save_bible(self, project_id: str, name: str, rules: Dict[str, Any], bible_id: str = "") -> Dict[str, Any]:
        normalized = self._bible_rules(rules)
        bible_id = bible_id or f"bible_{uuid.uuid4().hex}"
        now = utc_now()
        with self.repository._connect() as connection:
            current = connection.execute("SELECT current_revision FROM character_bibles WHERE bible_id=?", (bible_id,)).fetchone()
            revision = int(current["current_revision"] + 1) if current else 1
            payload = {"schema": "spriteforge.character_bible.v1", "schema_version": 1, "bible_id": bible_id, "revision": revision, "project_id": project_id, "name": str(name or "Character Bible"), **normalized}
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO character_bibles VALUES(?,?,?,?,?,?) ON CONFLICT(bible_id) DO UPDATE SET name=excluded.name,current_revision=excluded.current_revision,updated_at=excluded.updated_at", (bible_id, project_id, payload["name"], revision, now, now))
            connection.execute("INSERT INTO character_bible_revisions VALUES(?,?,?,?,?)", (bible_id, revision, canonical, digest, now))
        return {**payload, "content_hash": digest}

    def validate_asset(self, bible_id: str, asset_id: str) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute("""SELECT r.payload_json FROM character_bibles b JOIN character_bible_revisions r
                ON r.bible_id=b.bible_id AND r.revision=b.current_revision WHERE b.bible_id=?""", (bible_id,)).fetchone()
        if not row:
            raise LookupError(f"Character bible not found: {bible_id}")
        bible, asset = json.loads(row["payload_json"]), self.repository.get_asset(asset_id)
        revision = self.repository.get_revision(asset["current_revision_id"]) if asset.get("current_revision_id") else {}
        metadata = revision.get("metadata", {})
        findings = []
        palette = set(str(color).upper() for color in metadata.get("palette", []))
        forbidden = set(bible["palette"].get("forbidden", []))
        if palette & forbidden:
            findings.append({"rule": "palette.forbidden", "severity": "error", "colors": sorted(palette & forbidden)})
        dimensions = metadata.get("dimensions", {})
        expected = bible.get("canvas", {})
        if expected and (dimensions.get("width"), dimensions.get("height")) != (expected.get("width"), expected.get("height")):
            findings.append({"rule": "canvas.dimensions", "severity": "warning", "expected": expected, "actual": dimensions})
        if bible.get("required_actions") and asset.get("action") not in bible["required_actions"]:
            findings.append({"rule": "actions.mapping", "severity": "info", "action": asset.get("action", "")})
        return {"schema": "spriteforge.art_direction_report.v1", "bible_id": bible_id, "bible_revision": bible["revision"], "asset_id": asset_id, "revision_id": asset.get("current_revision_id"), "passed": not any(item["severity"] == "error" for item in findings), "findings": findings}

    def project_completeness(self, project_id: str, bible_id: str) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute("""SELECT r.payload_json FROM character_bibles b JOIN character_bible_revisions r
                ON r.bible_id=b.bible_id AND r.revision=b.current_revision WHERE b.bible_id=? AND b.project_id=?""", (bible_id, project_id)).fetchone()
        if not row:
            raise LookupError("Character bible not found in this project")
        bible = json.loads(row["payload_json"])
        required = {(action, direction) for action in bible["required_actions"] for direction in bible["required_directions"]}
        assets = self.repository.list_assets(project_id, limit=1000)
        present = {(asset.get("action"), asset.get("direction")) for asset in assets}
        return {"required": len(required), "complete": len(required & present), "missing": [{"action": a, "direction": d} for a, d in sorted(required - present)], "percent": round(len(required & present) / max(1, len(required)) * 100, 1)}

    def save_gameplay_scenario(self, project_id: str, name: str, payload: Dict[str, Any], scenario_id: str = "") -> Dict[str, Any]:
        scenario_id, now = scenario_id or f"scenario_{uuid.uuid4().hex}", utc_now()
        normalized = {
            "schema": "spriteforge.gameplay_scenario.v1", "scenario_id": scenario_id, "project_id": project_id,
            "name": str(name or "Gameplay Preview"), "viewport": payload.get("viewport", {"width": 1280, "height": 720, "pixel_scale": 4}),
            "background": payload.get("background", {}), "terrain": payload.get("terrain", []),
            "actors": payload.get("actors", []), "camera": payload.get("camera", {"mode": "follow", "zoom": 1}),
            "collision_debug": bool(payload.get("collision_debug", True)), "lighting": payload.get("lighting", {}),
        }
        with self.repository._connect() as connection:
            connection.execute("INSERT INTO gameplay_scenarios VALUES(?,?,?,?,?) ON CONFLICT(scenario_id) DO UPDATE SET name=excluded.name,payload_json=excluded.payload_json,updated_at=excluded.updated_at", (scenario_id, project_id, normalized["name"], json.dumps(normalized, sort_keys=True), now))
        return normalized

    def analytics(self, project_id: str) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            assets = connection.execute("SELECT COUNT(*) count FROM assets WHERE project_id=?", (project_id,)).fetchone()["count"]
            revisions = connection.execute("SELECT COUNT(*) count FROM revisions r JOIN assets a ON a.asset_id=r.asset_id WHERE a.project_id=?", (project_id,)).fetchone()["count"]
            batches = connection.execute("SELECT COUNT(*) count,SUM(CASE WHEN decision='promoted' THEN 1 ELSE 0 END) promoted FROM batch_cells c JOIN batch_experiments e ON e.experiment_id=c.experiment_id WHERE e.project_id=?", (project_id,)).fetchone() if self._table(connection, "batch_cells") else {"count": 0, "promoted": 0}
            reviews = connection.execute("SELECT state,COUNT(*) count FROM asset_reviews WHERE project_id=? GROUP BY state", (project_id,)).fetchall() if self._table(connection, "asset_reviews") else []
            leases = connection.execute("SELECT COUNT(*) count,SUM(cost_estimate) cost FROM farm_leases WHERE project_id=?", (project_id,)).fetchone() if self._table(connection, "farm_leases") else {"count": 0, "cost": 0}
        generated = int(batches["count"] or 0)
        promoted = int(batches["promoted"] or 0)
        return {"schema": "spriteforge.production_analytics.v1", "project_id": project_id, "assets": assets, "revisions": revisions, "generated_cells": generated, "promoted_cells": promoted, "promotion_yield_percent": round(promoted / max(1, generated) * 100, 2), "review_states": {row["state"]: row["count"] for row in reviews}, "farm_jobs": int(leases["count"] or 0), "estimated_farm_cost": float(leases["cost"] or 0)}

    @staticmethod
    def _bible_rules(rules: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(rules, dict):
            raise ValueError("Character bible rules must be an object")
        palette = rules.get("palette", {}) if isinstance(rules.get("palette", {}), dict) else {}
        return {
            "identity": rules.get("identity", {}), "proportions": rules.get("proportions", {}),
            "silhouette": rules.get("silhouette", {}), "canvas": rules.get("canvas", {}),
            "palette": {"locked": sorted(set(palette.get("locked", []))), "optional": sorted(set(palette.get("optional", []))), "forbidden": sorted(set(str(c).upper() for c in palette.get("forbidden", [])))},
            "lighting": rules.get("lighting", {}), "outline": rules.get("outline", {}),
            "poses": rules.get("poses", []), "expressions": rules.get("expressions", []),
            "mouth_shapes": rules.get("mouth_shapes", []), "equipment_slots": rules.get("equipment_slots", []),
            "required_actions": sorted(set(rules.get("required_actions", ["idle", "walk"]))),
            "required_directions": sorted(set(rules.get("required_directions", ["front", "right", "back", "left"]))),
            "model_preferences": rules.get("model_preferences", {}), "qa_thresholds": rules.get("qa_thresholds", {}),
        }

    @staticmethod
    def _table(connection: Any, name: str) -> bool:
        return bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())
