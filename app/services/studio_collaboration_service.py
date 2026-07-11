"""Local-first studio roles, review, comments, locks, presence, and audit history."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


ROLES = {"viewer", "artist", "reviewer", "lead", "admin"}
REVIEW_STATES = {"draft", "in_review", "changes_requested", "approved", "rejected"}


class StudioCollaborationService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS studio_users (
                    user_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_members (
                    project_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES studio_users(user_id), role TEXT NOT NULL,
                    PRIMARY KEY(project_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS asset_comments (
                    comment_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_id TEXT NOT NULL, revision_id TEXT,
                    author_id TEXT NOT NULL, body TEXT NOT NULL, location_json TEXT NOT NULL, parent_comment_id TEXT,
                    resolved INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asset_comments_context ON asset_comments(project_id,asset_id,created_at);
                CREATE TABLE IF NOT EXISTS asset_reviews (
                    review_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_id TEXT NOT NULL, revision_id TEXT NOT NULL,
                    state TEXT NOT NULL, assignee_id TEXT, actor_id TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_locks (
                    project_id TEXT NOT NULL, asset_id TEXT NOT NULL, owner_id TEXT NOT NULL, token TEXT NOT NULL,
                    acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL, PRIMARY KEY(project_id,asset_id)
                );
                CREATE TABLE IF NOT EXISTS studio_presence (
                    project_id TEXT NOT NULL, user_id TEXT NOT NULL, document_id TEXT NOT NULL DEFAULT '',
                    cursor_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL, PRIMARY KEY(project_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS studio_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                    action TEXT NOT NULL, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL,
                    details_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    def upsert_user(self, user_id: str, display_name: str, email: str = "") -> Dict[str, Any]:
        user_id = str(user_id or "").strip()
        if not user_id:
            raise ValueError("user_id is required")
        with self.repository._connect() as connection:
            connection.execute(
                "INSERT INTO studio_users VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,email=excluded.email",
                (user_id, str(display_name or user_id)[:120], str(email or "")[:254], utc_now()),
            )
        return {"user_id": user_id, "display_name": str(display_name or user_id), "email": str(email or "")}

    def set_member(self, project_id: str, user_id: str, role: str, *, actor_id: str) -> Dict[str, Any]:
        if role not in ROLES:
            raise ValueError(f"Role must be one of {sorted(ROLES)}")
        with self.repository._connect() as connection:
            member_count = connection.execute("SELECT COUNT(*) count FROM project_members WHERE project_id=?", (project_id,)).fetchone()["count"]
            if member_count:
                actor = connection.execute("SELECT role FROM project_members WHERE project_id=? AND user_id=?", (project_id, actor_id)).fetchone()
                if not actor or actor["role"] not in {"lead", "admin"}:
                    raise PermissionError("Only a lead or admin can change project membership")
            if not connection.execute("SELECT 1 FROM studio_users WHERE user_id=?", (user_id,)).fetchone():
                raise LookupError(f"Studio user not found: {user_id}")
            connection.execute(
                "INSERT INTO project_members VALUES(?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role",
                (project_id, user_id, role),
            )
        self._audit(project_id, actor_id, "member.role", "user", user_id, {"role": role})
        return {"project_id": project_id, "user_id": user_id, "role": role}

    def require(self, project_id: str, user_id: str, allowed: set[str]) -> str:
        with self.repository._connect() as connection:
            row = connection.execute("SELECT role FROM project_members WHERE project_id=? AND user_id=?", (project_id, user_id)).fetchone()
        if not row or row["role"] not in allowed:
            raise PermissionError(f"This action requires one of: {', '.join(sorted(allowed))}")
        return row["role"]

    def acquire_lock(self, project_id: str, asset_id: str, owner_id: str, ttl_seconds: int = 300) -> Dict[str, Any]:
        self.require(project_id, owner_id, {"artist", "lead", "admin"})
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=max(30, min(3600, int(ttl_seconds))))
        token = f"lock_{uuid.uuid4().hex}"
        with self.repository._connect() as connection:
            existing = connection.execute("SELECT * FROM asset_locks WHERE project_id=? AND asset_id=?", (project_id, asset_id)).fetchone()
            if existing and datetime.fromisoformat(existing["expires_at"].replace("Z", "+00:00")) > now and existing["owner_id"] != owner_id:
                raise ValueError(f"Asset is locked by {existing['owner_id']}")
            connection.execute("DELETE FROM asset_locks WHERE project_id=? AND asset_id=?", (project_id, asset_id))
            connection.execute("INSERT INTO asset_locks VALUES(?,?,?,?,?,?)", (
                project_id, asset_id, owner_id, token, now.isoformat().replace("+00:00", "Z"), expires.isoformat().replace("+00:00", "Z"),
            ))
        self._audit(project_id, owner_id, "lock.acquire", "asset", asset_id, {"expires_at": expires.isoformat()})
        return {"project_id": project_id, "asset_id": asset_id, "owner_id": owner_id, "token": token, "expires_at": expires.isoformat().replace("+00:00", "Z")}

    def release_lock(self, project_id: str, asset_id: str, owner_id: str, token: str = "") -> bool:
        with self.repository._connect() as connection:
            row = connection.execute("SELECT * FROM asset_locks WHERE project_id=? AND asset_id=?", (project_id, asset_id)).fetchone()
            if not row:
                return False
            if row["owner_id"] != owner_id and row["token"] != token:
                self.require(project_id, owner_id, {"lead", "admin"})
            connection.execute("DELETE FROM asset_locks WHERE project_id=? AND asset_id=?", (project_id, asset_id))
        self._audit(project_id, owner_id, "lock.release", "asset", asset_id, {})
        return True

    def comment(self, project_id: str, asset_id: str, revision_id: str, author_id: str, body: str,
                location: Dict[str, Any] | None = None, parent_comment_id: str = "") -> Dict[str, Any]:
        self.require(project_id, author_id, ROLES)
        body = str(body or "").strip()
        if not body or len(body) > 10_000:
            raise ValueError("Comment body must contain 1 to 10000 characters")
        comment_id, now = f"comment_{uuid.uuid4().hex}", utc_now()
        with self.repository._connect() as connection:
            connection.execute("INSERT INTO asset_comments VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                comment_id, project_id, asset_id, revision_id or None, author_id, body,
                json.dumps(location or {}, sort_keys=True), parent_comment_id or None, 0, now, now,
            ))
        self._audit(project_id, author_id, "comment.create", "asset", asset_id, {"comment_id": comment_id, "revision_id": revision_id})
        return {"comment_id": comment_id, "asset_id": asset_id, "revision_id": revision_id, "author_id": author_id, "body": body, "location": location or {}, "resolved": False, "created_at": now}

    def review(self, project_id: str, asset_id: str, revision_id: str, state: str, actor_id: str,
               assignee_id: str = "", note: str = "") -> Dict[str, Any]:
        if state not in REVIEW_STATES:
            raise ValueError(f"Review state must be one of {sorted(REVIEW_STATES)}")
        allowed = {"artist", "lead", "admin"} if state in {"draft", "in_review"} else {"reviewer", "lead", "admin"}
        self.require(project_id, actor_id, allowed)
        review_id, now = f"review_{uuid.uuid4().hex}", utc_now()
        with self.repository._connect() as connection:
            connection.execute("INSERT INTO asset_reviews VALUES(?,?,?,?,?,?,?,?,?)", (
                review_id, project_id, asset_id, revision_id, state, assignee_id or None, actor_id, str(note or "")[:4000], now,
            ))
        self._audit(project_id, actor_id, "review.state", "asset", asset_id, {"revision_id": revision_id, "state": state, "assignee_id": assignee_id})
        return {"review_id": review_id, "asset_id": asset_id, "revision_id": revision_id, "state": state, "actor_id": actor_id, "assignee_id": assignee_id, "note": note, "updated_at": now}

    def heartbeat(self, project_id: str, user_id: str, document_id: str = "", cursor: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self.require(project_id, user_id, ROLES)
        now = utc_now()
        with self.repository._connect() as connection:
            connection.execute(
                "INSERT INTO studio_presence VALUES(?,?,?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET document_id=excluded.document_id,cursor_json=excluded.cursor_json,updated_at=excluded.updated_at",
                (project_id, user_id, document_id, json.dumps(cursor or {}, sort_keys=True), now),
            )
        return {"project_id": project_id, "user_id": user_id, "document_id": document_id, "cursor": cursor or {}, "updated_at": now}

    def activity(self, project_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self.repository._connect() as connection:
            rows = connection.execute("SELECT * FROM studio_audit WHERE project_id=? ORDER BY sequence DESC LIMIT ?", (project_id, max(1, min(1000, int(limit))))).fetchall()
        return [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]

    @staticmethod
    def diff(before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
        changes: List[Dict[str, Any]] = []
        def walk(left: Any, right: Any, path: str) -> None:
            if isinstance(left, dict) and isinstance(right, dict):
                for key in sorted(set(left) | set(right)):
                    walk(left.get(key), right.get(key), f"{path}.{key}" if path else key)
            elif left != right:
                changes.append({"path": path, "before": left, "after": right})
        walk(before, after, "")
        return changes

    def _audit(self, project_id: str, actor_id: str, action: str, subject_type: str, subject_id: str, details: Dict[str, Any]) -> None:
        with self.repository._connect() as connection:
            connection.execute("INSERT INTO studio_audit(project_id,actor_id,action,subject_type,subject_id,details_json,created_at) VALUES(?,?,?,?,?,?,?)", (
                project_id, actor_id, action, subject_type, subject_id, json.dumps(details, sort_keys=True), utc_now(),
            ))
