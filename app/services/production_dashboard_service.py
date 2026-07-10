"""Canonical production-readiness aggregation for the dashboard."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

from services.asset_repository_service import AssetRepositoryService


class ProductionDashboardService:
    def __init__(self, repository: AssetRepositoryService, manifest: Dict[str, Any]):
        self.repository = repository
        self.manifest = manifest

    def summary(self) -> Dict[str, Any]:
        project_id = str(self.manifest["project_id"])
        assets = self.repository.list_assets(project_id, limit=1000)
        required = {(action, direction) for action in self.manifest.get("actions", []) for direction in self.manifest.get("directions", [])}
        present = {(asset.get("action", ""), asset.get("direction", "")) for asset in assets if asset.get("action") and asset.get("direction")}
        missing = [{"action": action, "direction": direction} for action, direction in sorted(required - present)]
        with self.repository._connect() as connection:
            qa = connection.execute(
                """SELECT q.payload_json FROM qa_reports q JOIN revisions r ON r.revision_id=q.revision_id
                   JOIN assets a ON a.asset_id=r.asset_id WHERE a.project_id=? AND a.current_revision_id=r.revision_id""",
                (project_id,),
            ).fetchall()
            batch = connection.execute(
                "SELECT status,COUNT(*) count FROM batch_cells GROUP BY status"
            ).fetchall() if self._table(connection, "batch_cells") else []
            workflows = connection.execute(
                "SELECT status,COUNT(*) count FROM workflow_runs GROUP BY status"
            ).fetchall() if self._table(connection, "workflow_runs") else []
            exports = connection.execute(
                "SELECT COUNT(*) count,MAX(created_at) latest FROM export_history"
            ).fetchone()
        reports = []
        import json
        for row in qa:
            reports.append(json.loads(row["payload_json"]))
        errors = sum(int(report.get("summary", {}).get("error", 0)) for report in reports)
        warnings = sum(int(report.get("summary", {}).get("warning", 0)) for report in reports)
        unvalidated = sum(1 for asset in assets if asset.get("current_revision_id")) - len(reports)
        disk = shutil.disk_usage(self.repository.project_dir)
        readiness_problems = len(missing) + errors + max(0, unvalidated)
        return {
            "schema": "spriteforge.production_dashboard.v1", "project_id": project_id,
            "completion": {
                "required": len(required), "present": len(required & present), "missing": missing,
                "percent": round((len(required & present) / len(required)) * 100, 1) if required else 100.0,
            },
            "assets": {"total": len(assets), "unvalidated": max(0, unvalidated)},
            "qa": {"errors": errors, "warnings": warnings, "reports": len(reports)},
            "jobs": {"batch": {row["status"]: row["count"] for row in batch}, "workflows": {row["status"]: row["count"] for row in workflows}},
            "exports": {"count": int(exports["count"]), "last_successful": exports["latest"] or ""},
            "storage": {"project_bytes": self._directory_size(self.repository.project_dir), "free_bytes": disk.free},
            "readiness": {"ready": readiness_problems == 0, "problem_count": readiness_problems},
            "actions": self._actions(missing, errors, unvalidated, exports["count"]),
        }

    @staticmethod
    def _actions(missing: list, errors: int, unvalidated: int, export_count: int) -> list:
        actions = []
        if missing:
            actions.append({"kind": "missing_animations", "count": len(missing), "view": "animation_player", "label": "Fill missing animations"})
        if unvalidated:
            actions.append({"kind": "validation", "count": unvalidated, "view": "qa_dashboard", "label": "Validate current revisions"})
        if errors:
            actions.append({"kind": "qa_errors", "count": errors, "view": "quality", "label": "Resolve blocking QA errors"})
        if not export_count:
            actions.append({"kind": "first_export", "count": 1, "view": "release", "label": "Create first deterministic export"})
        return actions

    @staticmethod
    def _directory_size(path: Path) -> int:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

    @staticmethod
    def _table(connection: Any, name: str) -> bool:
        return bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())
