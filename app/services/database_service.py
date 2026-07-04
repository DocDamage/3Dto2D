"""SQLite persistence layer for SpriteForge records.

This service is intentionally additive: JSON-backed services can migrate into
it gradually while existing flat-file behavior stays intact.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from spriteforge_utils import ROOT, load_json


DEFAULT_DB_PATH = ROOT / "output" / "spriteforge.sqlite3"


class DatabaseService:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    project_name TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    search_text TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                );

                CREATE INDEX IF NOT EXISTS idx_records_kind_created
                    ON records(kind, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_records_project
                    ON records(project_name, kind);

                CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
                    kind,
                    id UNINDEXED,
                    search_text
                );
                """
            )

    def upsert_record(self, kind: str, record: Dict[str, Any]) -> str:
        self.initialize()
        record_id = str(record.get("id") or record.get("job_id") or f"{kind}_{int(time.time() * 1000)}")
        created_at = str(record.get("created_at") or record.get("started_at") or "")
        updated_at = str(record.get("updated_at") or record.get("finished_at") or created_at)
        project_name = str(record.get("project_name") or record.get("metadata", {}).get("project_name") or "")
        title = str(record.get("title") or record.get("prompt") or record.get("sprite_folder") or record_id)
        search_text = self._search_text(record)
        payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO records(kind, id, created_at, updated_at, project_name, title, search_text, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(kind, id) DO UPDATE SET
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    project_name=excluded.project_name,
                    title=excluded.title,
                    search_text=excluded.search_text,
                    payload_json=excluded.payload_json
                """,
                (kind, record_id, created_at, updated_at, project_name, title, search_text, payload_json),
            )
            conn.execute("DELETE FROM records_fts WHERE kind=? AND id=?", (kind, record_id))
            conn.execute(
                "INSERT INTO records_fts(kind, id, search_text) VALUES (?, ?, ?)",
                (kind, record_id, search_text),
            )
        return record_id

    def recent(self, kind: str, limit: int = 100) -> List[Dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM records WHERE kind=? ORDER BY created_at DESC, updated_at DESC LIMIT ?",
                (kind, int(limit)),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def counts_by_kind(self, project_name: str = "") -> Dict[str, int]:
        self.initialize()
        with self.connect() as conn:
            if project_name:
                rows = conn.execute(
                    "SELECT kind, COUNT(*) AS count FROM records WHERE project_name=? GROUP BY kind ORDER BY kind",
                    (str(project_name),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT kind, COUNT(*) AS count FROM records GROUP BY kind ORDER BY kind"
                ).fetchall()
        return {str(row["kind"]): int(row["count"]) for row in rows}

    def health(self) -> Dict[str, Any]:
        self.initialize()
        db_exists = self.db_path.exists()
        wal_path = self.db_path.with_name(self.db_path.name + "-wal")
        with self.connect() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            table_rows = conn.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]
            fts_rows = conn.execute("SELECT COUNT(*) AS count FROM records_fts").fetchone()["count"]
        counts = self.counts_by_kind()
        return {
            "ok": integrity == "ok",
            "schema": "spriteforge.database_health.v1",
            "db_path": str(self.db_path),
            "db_exists": db_exists,
            "db_size_bytes": self.db_path.stat().st_size if db_exists else 0,
            "wal_path": str(wal_path),
            "wal_exists": wal_path.exists(),
            "wal_size_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
            "journal_mode": str(journal_mode),
            "integrity_check": str(integrity),
            "record_count": int(table_rows),
            "fts_record_count": int(fts_rows),
            "fts_in_sync": int(table_rows) == int(fts_rows),
            "counts_by_kind": counts,
        }

    def search(self, query: str, kind: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        self.initialize()
        query = str(query or "").strip()
        if not query:
            return self.recent(kind or "experiment", limit=limit) if kind else []
        fts_query = self._fts_query(query)
        with self.connect() as conn:
            try:
                if kind:
                    rows = conn.execute(
                        """
                        SELECT r.payload_json
                        FROM records_fts f
                        JOIN records r ON r.kind=f.kind AND r.id=f.id
                        WHERE records_fts MATCH ? AND f.kind=?
                        LIMIT ?
                        """,
                        (fts_query, kind, int(limit)),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT r.payload_json
                        FROM records_fts f
                        JOIN records r ON r.kind=f.kind AND r.id=f.id
                        WHERE records_fts MATCH ?
                        LIMIT ?
                        """,
                        (fts_query, int(limit)),
                    ).fetchall()
            except sqlite3.OperationalError:
                like_query = f"%{query}%"
                if kind:
                    rows = conn.execute(
                        "SELECT payload_json FROM records WHERE kind=? AND search_text LIKE ? LIMIT ?",
                        (kind, like_query, int(limit)),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT payload_json FROM records WHERE search_text LIKE ? LIMIT ?",
                        (like_query, int(limit)),
                    ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def migrate_json_list(self, path: Path, kind: str) -> Dict[str, Any]:
        self.initialize()
        rows = load_json(Path(path), [])
        if not isinstance(rows, list):
            return {"ok": False, "kind": kind, "imported": 0, "message": "JSON root is not a list."}
        imported = 0
        for row in rows:
            if isinstance(row, dict):
                self.upsert_record(kind, row)
                imported += 1
        return {"ok": True, "kind": kind, "imported": imported, "source": str(path)}

    def migrate_default_json(self) -> Dict[str, Any]:
        jobs = self.migrate_json_list(ROOT / "output" / "jobs" / "job_history.json", "job")
        experiments = self.migrate_json_list(ROOT / "output" / "experiments" / "experiment_history.json", "experiment")
        return {
            "ok": bool(jobs.get("ok") and experiments.get("ok")),
            "jobs": jobs,
            "experiments": experiments,
            "counts": self.counts_by_kind(),
            "db_path": str(self.db_path),
        }

    @staticmethod
    def _search_text(record: Dict[str, Any]) -> str:
        fields: List[str] = []
        for key in [
            "id", "job_id", "title", "prompt", "negative", "profile", "model_tier",
            "sprite_action", "direction", "sprite_folder", "project_name", "notes",
        ]:
            value = record.get(key)
            if value is not None:
                fields.append(str(value))
        metadata = record.get("metadata")
        if isinstance(metadata, dict):
            fields.extend(str(value) for value in metadata.values() if value is not None)
        return " ".join(fields)

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = re.findall(r"[\w-]+", str(query or ""), flags=re.UNICODE)
        safe_tokens = [token.replace('"', '""') for token in tokens if token.strip("-_")]
        if not safe_tokens:
            return '""'
        return " OR ".join(f'"{token}"' for token in safe_tokens)
