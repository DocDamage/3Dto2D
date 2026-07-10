"""Engine live links and loss-aware professional interchange contracts."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now
from spriteforge_utils import save_json


ENGINE_SCHEMAS = {"godot": "spriteforge.godot_live_link.v1", "unity": "spriteforge.unity_live_link.v1", "unreal": "spriteforge.unreal_live_link.v1"}
INTERCHANGE_FORMATS = {
    "aseprite": {"extensions": [".ase", ".aseprite", ".json"], "features": {"layers", "frames", "tags", "slices", "durations", "palette"}},
    "psd": {"extensions": [".psd", ".psb"], "features": {"layers", "groups", "masks", "blend_modes", "color_profile"}},
    "krita": {"extensions": [".kra"], "features": {"layers", "groups", "masks", "frames", "color_profile"}},
    "spine": {"extensions": [".json", ".skel"], "features": {"bones", "slots", "skins", "animations", "events"}},
    "dragonbones": {"extensions": [".json"], "features": {"bones", "slots", "skins", "animations", "events"}},
    "tiled": {"extensions": [".tmx", ".tsx", ".json"], "features": {"tiles", "layers", "objects", "properties", "animations"}},
    "ldtk": {"extensions": [".ldtk", ".json"], "features": {"tiles", "layers", "entities", "properties"}},
    "texturepacker": {"extensions": [".json", ".plist", ".xml"], "features": {"atlas", "trim", "rotation", "pivot"}},
}


class PipelineIntegrationService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS live_link_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, engine TEXT NOT NULL,
                    event_type TEXT NOT NULL, asset_id TEXT NOT NULL, revision_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_live_link_project_engine ON live_link_events(project_id,engine,sequence);
                CREATE TABLE IF NOT EXISTS live_link_clients (
                    client_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, engine TEXT NOT NULL, engine_version TEXT NOT NULL,
                    cursor INTEGER NOT NULL DEFAULT 0, capabilities_json TEXT NOT NULL, last_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interchange_history (
                    transfer_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, format TEXT NOT NULL, direction TEXT NOT NULL,
                    source_hash TEXT NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    def register_client(self, project_id: str, engine: str, engine_version: str,
                        capabilities: List[str] | None = None) -> Dict[str, Any]:
        if engine not in ENGINE_SCHEMAS:
            raise ValueError("Engine must be godot, unity, or unreal")
        client_id, now = f"link_{uuid.uuid4().hex}", utc_now()
        payload = {"client_id": client_id, "project_id": project_id, "engine": engine, "engine_version": str(engine_version), "capabilities": sorted(set(capabilities or [])), "cursor": 0, "last_seen": now}
        with self.repository._connect() as connection:
            connection.execute("INSERT INTO live_link_clients VALUES(?,?,?,?,?,?,?)", (
                client_id, project_id, engine, payload["engine_version"], 0, json.dumps(payload["capabilities"]), now,
            ))
        return payload

    def publish_asset(self, project_id: str, engine: str, asset_id: str, revision_id: str,
                      event_type: str = "asset.changed") -> Dict[str, Any]:
        if engine not in ENGINE_SCHEMAS:
            raise ValueError("Unsupported engine")
        asset, revision = self.repository.get_asset(asset_id), self.repository.get_revision(revision_id)
        if asset["project_id"] != project_id or revision["asset_id"] != asset_id:
            raise ValueError("Live-link asset/revision context mismatch")
        payload = {
            "schema": ENGINE_SCHEMAS[engine], "event_type": event_type, "asset_id": asset_id,
            "revision_id": revision_id, "action": asset.get("action", ""), "direction": asset.get("direction", ""),
            "files": revision.get("files", []), "animation": revision.get("metadata", {}).get("animation_workspace"),
            "content_hash": hashlib.sha256(json.dumps(revision, sort_keys=True).encode()).hexdigest(),
        }
        with self.repository._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO live_link_events(project_id,engine,event_type,asset_id,revision_id,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (project_id, engine, event_type, asset_id, revision_id, json.dumps(payload, sort_keys=True), utc_now()),
            ).lastrowid
        return {"cursor": cursor, **payload}

    def poll(self, client_id: str, limit: int = 200) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            client = connection.execute("SELECT * FROM live_link_clients WHERE client_id=?", (client_id,)).fetchone()
            if not client:
                raise LookupError(f"Live-link client not found: {client_id}")
            rows = connection.execute(
                "SELECT * FROM live_link_events WHERE project_id=? AND engine=? AND sequence>? ORDER BY sequence LIMIT ?",
                (client["project_id"], client["engine"], client["cursor"], max(1, min(1000, int(limit)))),
            ).fetchall()
            cursor = rows[-1]["sequence"] if rows else client["cursor"]
            connection.execute("UPDATE live_link_clients SET cursor=?,last_seen=? WHERE client_id=?", (cursor, utc_now(), client_id))
        return {"schema": "spriteforge.live_link_poll.v1", "client_id": client_id, "cursor": cursor, "events": [{"sequence": row["sequence"], **json.loads(row["payload_json"])} for row in rows]}

    def generate_engine_plugin(self, engine: str, output_dir: Path) -> Dict[str, Any]:
        if engine not in ENGINE_SCHEMAS:
            raise ValueError("Unsupported engine")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        common = {"schema": ENGINE_SCHEMAS[engine], "engine": engine, "protocol": "http-json-poll", "endpoints": {"register": "/api/live-link/register", "poll": "/api/live-link/poll"}}
        save_json(output_dir / "spriteforge-live-link.json", common)
        if engine == "godot":
            (output_dir / "plugin.cfg").write_text('[plugin]\nname="SpriteForge Live Link"\ndescription="Synchronizes canonical SpriteForge assets"\nauthor="SpriteForge"\nversion="1.0"\nscript="spriteforge_live_link.gd"\n', encoding="utf-8")
            (output_dir / "spriteforge_live_link.gd").write_text("@tool\nextends EditorPlugin\n# Poll endpoints declared in spriteforge-live-link.json.\n", encoding="utf-8")
        elif engine == "unity":
            (output_dir / "SpriteForgeLiveLink.cs").write_text("using UnityEditor;\npublic static class SpriteForgeLiveLink { [MenuItem(\"SpriteForge/Sync\")] public static void Sync() { AssetDatabase.Refresh(); } }\n", encoding="utf-8")
        else:
            (output_dir / "SpriteForgeLiveLink.uplugin").write_text(json.dumps({"FileVersion": 3, "VersionName": "1.0", "FriendlyName": "SpriteForge Live Link", "Category": "Editor", "Modules": []}, indent=2), encoding="utf-8")
        return {"engine": engine, "output_dir": str(output_dir), "files": sorted(path.name for path in output_dir.iterdir())}

    def interchange_report(self, project_id: str, format_name: str, direction: str,
                           source: Path, requested_features: List[str]) -> Dict[str, Any]:
        if format_name not in INTERCHANGE_FORMATS:
            raise ValueError(f"Unsupported interchange format: {format_name}")
        if direction not in {"import", "export", "round_trip"}:
            raise ValueError("direction must be import, export, or round_trip")
        source = Path(source)
        if source.suffix.lower() not in INTERCHANGE_FORMATS[format_name]["extensions"]:
            raise ValueError(f"File extension is not valid for {format_name}")
        digest = self._hash(source) if source.is_file() else ""
        supported = INTERCHANGE_FORMATS[format_name]["features"]
        preserved, lost = sorted(set(requested_features) & supported), sorted(set(requested_features) - supported)
        report = {
            "schema": "spriteforge.interchange_loss_report.v1", "format": format_name,
            "direction": direction, "source": str(source), "source_hash": digest,
            "preserved": preserved, "not_preserved": [{"feature": feature, "reason": f"{format_name} adapter has no lossless mapping"} for feature in lost],
            "lossless": not lost, "adapter_version": 1,
        }
        with self.repository._connect() as connection:
            connection.execute("INSERT INTO interchange_history VALUES(?,?,?,?,?,?,?)", (
                f"transfer_{uuid.uuid4().hex}", project_id, format_name, direction, digest, json.dumps(report, sort_keys=True), utc_now(),
            ))
        return report

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
