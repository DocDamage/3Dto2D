"""Transactional asset provenance, immutable revisions, and content storage."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from services.roadmap_models import AssetRecord, AssetRevisionRecord, utc_now
from spriteforge_utils import get_app_version


_UNSET = object()


class AssetNotFoundError(LookupError):
    pass


class RevisionConflictError(ValueError):
    pass


class AssetRepositoryService:
    """Canonical repository used by web and CLI-facing services.

    Metadata commits in SQLite. File payloads are content-addressed and written
    atomically before a revision can become active, preventing dangling pointers.
    """

    def __init__(self, project_dir: Path, db_path: Optional[Path] = None):
        self.project_dir = Path(project_dir).resolve()
        self.managed_dir = self.project_dir / ".spriteforge"
        self.objects_dir = self.managed_dir / "objects"
        self.db_path = Path(db_path) if db_path else self.managed_dir / "project.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.managed_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    current_revision_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    parent_revision_id TEXT REFERENCES revisions(revision_id),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_revisions_asset ON revisions(asset_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS blobs (
                    sha256 TEXT PRIMARY KEY,
                    size_bytes INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revision_blobs (
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id) ON DELETE CASCADE,
                    sha256 TEXT NOT NULL REFERENCES blobs(sha256),
                    logical_name TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    PRIMARY KEY(revision_id, logical_name)
                );
                CREATE TABLE IF NOT EXISTS qa_reports (
                    report_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id) ON DELETE CASCADE,
                    input_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_qa_revision_input ON qa_reports(revision_id, input_hash);
                CREATE TABLE IF NOT EXISTS export_history (
                    export_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    preset_id TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)",
                (utc_now(),),
            )

    def create_asset(self, record: AssetRecord | Dict[str, Any]) -> Dict[str, Any]:
        asset = record if isinstance(record, AssetRecord) else AssetRecord.from_dict(record)
        payload = asset.to_dict()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO assets(asset_id, project_id, current_revision_id, payload_json, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (asset.asset_id, asset.project_id, None, self._json(payload), asset.created_at, asset.updated_at),
            )
        return payload

    def new_asset(self, *, project_id: str, name: str, asset_type: str, **labels: Any) -> Dict[str, Any]:
        return self.create_asset(AssetRecord.from_dict({
            "asset_id": f"asset_{uuid.uuid4().hex}", "project_id": project_id, "name": name,
            "asset_type": asset_type, "role": str(labels.get("role") or ""),
            "action": str(labels.get("action") or ""), "direction": str(labels.get("direction") or ""),
            "variant": str(labels.get("variant") or ""),
        }))

    def get_asset(self, asset_id: str) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload_json, current_revision_id FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if not row:
            raise AssetNotFoundError(f"Asset not found: {asset_id}")
        payload = json.loads(row["payload_json"])
        payload["current_revision_id"] = row["current_revision_id"]
        return payload

    def list_assets(self, project_id: str, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json, current_revision_id FROM assets WHERE project_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (project_id, max(1, min(int(limit), 1000)), max(0, int(offset))),
            ).fetchall()
        result = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload["current_revision_id"] = row["current_revision_id"]
            result.append(payload)
        return result

    def commit_revision(
        self,
        record: AssetRevisionRecord | Dict[str, Any],
        files: Optional[Dict[str, bytes | bytearray | Path]] = None,
        *,
        expected_current_revision_id: object = _UNSET,
    ) -> Dict[str, Any]:
        revision = record if isinstance(record, AssetRevisionRecord) else AssetRevisionRecord.from_dict(record)
        files = files or {}
        asset = self.get_asset(revision.asset_id)
        if asset["project_id"] != revision.project_id:
            raise RevisionConflictError("Revision project_id does not match its asset")
        if expected_current_revision_id is not _UNSET and asset.get("current_revision_id") != expected_current_revision_id:
            raise RevisionConflictError("Asset changed since it was loaded")
        if revision.parent_revision_id is None and asset.get("current_revision_id"):
            revision = replace(revision, parent_revision_id=asset["current_revision_id"])

        staged = [self._store_blob(name, value) for name, value in sorted(files.items())]
        file_records = list(revision.files)
        known_names = {str(item.get("name")) for item in file_records}
        for item in staged:
            if item["name"] not in known_names:
                file_records.append({key: item[key] for key in ("name", "sha256", "size_bytes", "media_type")})
        revision = replace(revision, files=file_records, application_version=revision.application_version or get_app_version())
        payload = revision.to_dict()
        now = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT current_revision_id FROM assets WHERE asset_id=?", (revision.asset_id,)).fetchone()
            if not current:
                raise AssetNotFoundError(f"Asset not found: {revision.asset_id}")
            if expected_current_revision_id is not _UNSET and current["current_revision_id"] != expected_current_revision_id:
                raise RevisionConflictError("Asset changed while revision was being committed")
            if revision.parent_revision_id:
                parent = connection.execute(
                    "SELECT 1 FROM revisions WHERE revision_id=? AND asset_id=?",
                    (revision.parent_revision_id, revision.asset_id),
                ).fetchone()
                if not parent:
                    raise RevisionConflictError("Parent revision does not belong to this asset")
            connection.execute(
                "INSERT INTO revisions(revision_id, asset_id, parent_revision_id, payload_json, created_at) VALUES(?,?,?,?,?)",
                (revision.revision_id, revision.asset_id, revision.parent_revision_id, self._json(payload), revision.created_at),
            )
            for item in staged:
                connection.execute(
                    "INSERT OR IGNORE INTO blobs(sha256,size_bytes,relative_path,created_at) VALUES(?,?,?,?)",
                    (item["sha256"], item["size_bytes"], item["relative_path"], now),
                )
                connection.execute(
                    "INSERT INTO revision_blobs(revision_id,sha256,logical_name,media_type) VALUES(?,?,?,?)",
                    (revision.revision_id, item["sha256"], item["name"], item["media_type"]),
                )
            updated_asset = dict(asset)
            updated_asset["current_revision_id"] = revision.revision_id
            updated_asset["updated_at"] = now
            connection.execute(
                "UPDATE assets SET current_revision_id=?, payload_json=?, updated_at=? WHERE asset_id=?",
                (revision.revision_id, self._json(updated_asset), now, revision.asset_id),
            )
        return payload

    def new_revision(self, asset_id: str, *, generation: Optional[Dict[str, Any]] = None,
                     operations: Optional[List[Dict[str, Any]]] = None, metadata: Optional[Dict[str, Any]] = None,
                     files: Optional[Dict[str, bytes | bytearray | Path]] = None,
                     inherit_files: bool = True) -> Dict[str, Any]:
        asset = self.get_asset(asset_id)
        parent = self.get_revision(asset["current_revision_id"]) if asset.get("current_revision_id") else None
        return self.commit_revision({
            "revision_id": f"rev_{uuid.uuid4().hex}", "asset_id": asset_id,
            "project_id": asset["project_id"], "parent_revision_id": asset.get("current_revision_id"),
            "generation": generation or {}, "operations": operations or [], "metadata": metadata or {},
            "source_asset_ids": [], "files": list(parent.get("files", [])) if parent and inherit_files else [],
        }, files, expected_current_revision_id=asset.get("current_revision_id"))

    def get_revision(self, revision_id: str) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload_json FROM revisions WHERE revision_id=?", (revision_id,)).fetchone()
        if not row:
            raise AssetNotFoundError(f"Revision not found: {revision_id}")
        return json.loads(row["payload_json"])

    def history(self, asset_id: str) -> List[Dict[str, Any]]:
        self.get_asset(asset_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM revisions WHERE asset_id=? ORDER BY created_at DESC, rowid DESC", (asset_id,)
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def restore(self, asset_id: str, revision_id: str) -> Dict[str, Any]:
        revision = self.get_revision(revision_id)
        if revision["asset_id"] != asset_id:
            raise RevisionConflictError("Revision does not belong to this asset")
        now = utc_now()
        with self._connect() as connection:
            asset = self.get_asset(asset_id)
            asset["current_revision_id"] = revision_id
            asset["updated_at"] = now
            connection.execute(
                "UPDATE assets SET current_revision_id=?, payload_json=?, updated_at=? WHERE asset_id=?",
                (revision_id, self._json(asset), now, asset_id),
            )
        return self.get_asset(asset_id)

    def verify_integrity(self) -> Dict[str, Any]:
        missing: List[str] = []
        corrupt: List[str] = []
        with self._connect() as connection:
            rows = connection.execute("SELECT sha256, relative_path FROM blobs ORDER BY sha256").fetchall()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        for row in rows:
            path = self.managed_dir / row["relative_path"]
            if not path.is_file():
                missing.append(row["sha256"])
            elif self._hash_file(path) != row["sha256"]:
                corrupt.append(row["sha256"])
        return {
            "schema": "spriteforge.asset_integrity.v1", "ok": integrity == "ok" and not missing and not corrupt,
            "database": integrity, "blob_count": len(rows), "missing": missing, "corrupt": corrupt,
        }

    def _store_blob(self, name: str, value: bytes | bytearray | Path) -> Dict[str, Any]:
        logical_name = Path(str(name)).name
        if not logical_name or logical_name in {".", ".."}:
            raise ValueError("File logical name is invalid")
        data = Path(value).read_bytes() if isinstance(value, Path) else bytes(value)
        digest = hashlib.sha256(data).hexdigest()
        relative = Path("objects") / digest[:2] / digest[2:4] / digest
        target = self.managed_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_bytes(data)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return {
            "name": logical_name, "sha256": digest, "size_bytes": len(data),
            "relative_path": relative.as_posix(), "media_type": self._media_type(logical_name),
        }

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _media_type(name: str) -> str:
        return {".png": "image/png", ".json": "application/json", ".gif": "image/gif", ".webp": "image/webp"}.get(
            Path(name).suffix.lower(), "application/octet-stream"
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
