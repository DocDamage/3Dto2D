"""Resumable batch-matrix planning and result curation."""
from __future__ import annotations

import itertools
import json
import uuid
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


MATRIX_SCHEMA = "spriteforge.batch_matrix.v1"
MAX_CELLS = 10_000


class BatchMatrixService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS batch_experiments (
                    experiment_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, status TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batch_cells (
                    cell_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL REFERENCES batch_experiments(experiment_id) ON DELETE CASCADE,
                    coordinate_json TEXT NOT NULL, status TEXT NOT NULL, rating INTEGER, tags_json TEXT NOT NULL DEFAULT '[]',
                    decision TEXT NOT NULL DEFAULT '', output_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '', job_id TEXT NOT NULL DEFAULT '',
                    UNIQUE(experiment_id, coordinate_json)
                );
                CREATE INDEX IF NOT EXISTS idx_batch_cells_experiment_status ON batch_cells(experiment_id,status);
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(batch_cells)").fetchall()}
            if "job_id" not in columns:
                connection.execute("ALTER TABLE batch_cells ADD COLUMN job_id TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def estimate(dimensions: Dict[str, Any], *, bytes_per_result: int = 1_000_000,
                 cost_per_result: float = 0.0) -> Dict[str, Any]:
        normalized = BatchMatrixService._dimensions(dimensions)
        count = 1
        for values in normalized.values():
            count *= len(values)
        return {
            "cell_count": count, "storage_bytes": count * max(0, int(bytes_per_result)),
            "estimated_cost": round(count * max(0.0, float(cost_per_result)), 4),
            "requires_confirmation": count > 100 or count * bytes_per_result > 1_000_000_000 or count * cost_per_result > 10,
            "within_limit": count <= MAX_CELLS,
        }

    def create(self, project_id: str, name: str, dimensions: Dict[str, Any], **estimates: Any) -> Dict[str, Any]:
        normalized = self._dimensions(dimensions)
        estimate = self.estimate(normalized, **estimates)
        if not estimate["within_limit"]:
            raise ValueError(f"Matrix exceeds the {MAX_CELLS} cell safety limit")
        experiment_id = f"matrix_{uuid.uuid4().hex}"
        now = utc_now()
        payload = {
            "schema": MATRIX_SCHEMA, "schema_version": 1, "experiment_id": experiment_id,
            "project_id": project_id, "name": str(name or "Batch experiment"),
            "dimensions": normalized, "estimate": estimate, "created_at": now,
        }
        keys = list(normalized)
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO batch_experiments VALUES(?,?,?,?,?,?)",
                (experiment_id, project_id, "planned", json.dumps(payload, sort_keys=True), now, now),
            )
            for values in itertools.product(*(normalized[key] for key in keys)):
                coordinate = dict(zip(keys, values))
                canonical = json.dumps(coordinate, sort_keys=True, separators=(",", ":"))
                connection.execute(
                    "INSERT INTO batch_cells(cell_id,experiment_id,coordinate_json,status) VALUES(?,?,?,?)",
                    (f"cell_{uuid.uuid4().hex}", experiment_id, canonical, "queued"),
                )
        return self.get(experiment_id)

    def get(self, experiment_id: str, *, status: str = "", limit: int = 500, offset: int = 0) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute("SELECT * FROM batch_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
            if not row:
                raise LookupError(f"Batch experiment not found: {experiment_id}")
            where, params = "experiment_id=?", [experiment_id]
            if status:
                where += " AND status=?"
                params.append(status)
            cells = connection.execute(
                f"SELECT * FROM batch_cells WHERE {where} ORDER BY rowid LIMIT ? OFFSET ?",
                (*params, max(1, min(2000, int(limit))), max(0, int(offset))),
            ).fetchall()
            counts = connection.execute(
                "SELECT status,COUNT(*) count FROM batch_cells WHERE experiment_id=? GROUP BY status", (experiment_id,)
            ).fetchall()
        payload = json.loads(row["payload_json"])
        payload.update({
            "status": row["status"], "counts": {item["status"]: item["count"] for item in counts},
            "cells": [self._cell(item) for item in cells],
        })
        return payload

    def update_cell(self, experiment_id: str, cell_id: str, *, status: str | None = None,
                    output: Dict[str, Any] | None = None, error: str = "", job_id: str | None = None) -> Dict[str, Any]:
        allowed = {"queued", "running", "completed", "failed", "cancelled"}
        if status and status not in allowed:
            raise ValueError("Invalid batch cell status")
        with self.repository._connect() as connection:
            row = connection.execute(
                "SELECT * FROM batch_cells WHERE experiment_id=? AND cell_id=?", (experiment_id, cell_id)
            ).fetchone()
            if not row:
                raise LookupError(f"Batch cell not found: {cell_id}")
            connection.execute(
                "UPDATE batch_cells SET status=?,output_json=?,error=?,job_id=? WHERE cell_id=?",
                (status or row["status"], json.dumps(output if output is not None else json.loads(row["output_json"]), sort_keys=True), str(error or ""), job_id if job_id is not None else row["job_id"], cell_id),
            )
        return self.cell(experiment_id, cell_id)

    def curate(self, experiment_id: str, cell_id: str, *, rating: int | None = None,
               tags: List[str] | None = None, decision: str = "") -> Dict[str, Any]:
        if rating is not None and rating not in range(1, 6):
            raise ValueError("Rating must be between 1 and 5")
        if decision not in {"", "rejected", "shortlisted", "promoted"}:
            raise ValueError("Invalid curation decision")
        clean_tags = sorted({str(tag).strip() for tag in (tags or []) if str(tag).strip()})[:50]
        with self.repository._connect() as connection:
            changed = connection.execute(
                "UPDATE batch_cells SET rating=?,tags_json=?,decision=? WHERE experiment_id=? AND cell_id=?",
                (rating, json.dumps(clean_tags), decision, experiment_id, cell_id),
            ).rowcount
        if not changed:
            raise LookupError(f"Batch cell not found: {cell_id}")
        return self.cell(experiment_id, cell_id)

    def retry_failed(self, experiment_id: str) -> int:
        with self.repository._connect() as connection:
            return connection.execute(
                "UPDATE batch_cells SET status='queued',error='',job_id='' WHERE experiment_id=? AND status='failed'", (experiment_id,)
            ).rowcount

    def submit_cell(self, experiment_id: str, cell_id: str, base_payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Submit one matrix cell through the canonical persistent JobService."""
        from services.job_service import JobService
        from web_helpers import build_action_command

        cell = self.cell(experiment_id, cell_id)
        if cell["status"] not in {"queued", "failed", "cancelled"}:
            raise ValueError(f"Cell cannot be submitted from status {cell['status']}")
        payload = dict(base_payload or {})
        payload.update(cell["coordinate"])
        payload.setdefault("action", "generate_sprite")
        if "prompts" in payload and "prompt" not in payload:
            payload["prompt"] = payload.pop("prompts")
        if "seeds" in payload and "seed" not in payload:
            payload["seed"] = payload.pop("seeds")
        title, command = build_action_command(payload)
        metadata = {"batch_experiment_id": experiment_id, "batch_cell_id": cell_id, "matrix_coordinate": cell["coordinate"], **payload}
        ok, job_id = JobService.start_job(title, command, metadata=metadata)
        if not ok:
            raise RuntimeError(job_id)
        return self.update_cell(experiment_id, cell_id, status="running", job_id=job_id)

    def synchronize_jobs(self, experiment_id: str) -> Dict[str, int]:
        """Refresh cell state/output from persistent job history after reloads."""
        from services.job_service import JobService

        experiment = self.get(experiment_id, limit=2000)
        changed = 0
        for cell in experiment["cells"]:
            if not cell.get("job_id") or cell["status"] not in {"running", "queued"}:
                continue
            job = JobService.get_job(cell["job_id"])
            if not job:
                continue
            phase = str(job.get("phase") or "")
            if phase == "completed":
                metadata = job.get("metadata", {}) if isinstance(job.get("metadata"), dict) else {}
                self.update_cell(experiment_id, cell["cell_id"], status="completed", output={
                    "job_id": cell["job_id"], "sprite_folder": metadata.get("sprite_folder", ""),
                    "visual_report": metadata.get("visual_report", {}), "qa_gate": metadata.get("qa_gate", {}),
                })
                changed += 1
            elif phase in {"failed", "cancelled"}:
                self.update_cell(experiment_id, cell["cell_id"], status=phase, error=str(job.get("stage_detail") or phase))
                changed += 1
        return {"changed": changed, "total": len(experiment["cells"])}

    def cancel_cell(self, experiment_id: str, cell_id: str) -> Dict[str, Any]:
        from services.job_service import JobService
        cell = self.cell(experiment_id, cell_id)
        if cell.get("job_id"):
            JobService.cancel_job(cell["job_id"])
        return self.update_cell(experiment_id, cell_id, status="cancelled", error="Cancelled by user")

    def promote(self, experiment_id: str, cell_id: str, *, name: str = "") -> Dict[str, Any]:
        """Promote a completed cell while preserving matrix provenance."""
        cell = self.cell(experiment_id, cell_id)
        if cell["status"] != "completed":
            raise ValueError("Only completed cells can be promoted")
        with self.repository._connect() as connection:
            experiment = connection.execute("SELECT project_id FROM batch_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        asset = self.repository.new_asset(
            project_id=experiment["project_id"], name=name or "Promoted matrix result", asset_type="sprite",
            action=str(cell["coordinate"].get("action") or ""), direction=str(cell["coordinate"].get("direction") or ""),
            variant=cell_id,
        )
        revision = self.repository.new_revision(asset["asset_id"], generation={
            **cell["coordinate"], "experiment_id": experiment_id, "matrix_cell_id": cell_id,
            "provider_job_id": cell.get("job_id", ""),
        }, metadata={"matrix_provenance": {"experiment_id": experiment_id, "cell_id": cell_id, "output": cell["output"]}})
        self.curate(experiment_id, cell_id, rating=cell.get("rating"), tags=cell.get("tags"), decision="promoted")
        return {"asset": asset, "revision": revision}

    def cell(self, experiment_id: str, cell_id: str) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute(
                "SELECT * FROM batch_cells WHERE experiment_id=? AND cell_id=?", (experiment_id, cell_id)
            ).fetchone()
        if not row:
            raise LookupError(f"Batch cell not found: {cell_id}")
        return self._cell(row)

    @staticmethod
    def _dimensions(dimensions: Dict[str, Any]) -> Dict[str, List[Any]]:
        if not isinstance(dimensions, dict) or not dimensions:
            raise ValueError("Matrix dimensions must be a non-empty object")
        result = {}
        for key, values in dimensions.items():
            if not isinstance(values, list) or not values:
                raise ValueError(f"Matrix dimension {key} must be a non-empty list")
            if len(values) > 100:
                raise ValueError(f"Matrix dimension {key} exceeds 100 values")
            result[str(key)] = values
        return result

    @staticmethod
    def _cell(row: Any) -> Dict[str, Any]:
        return {
            "cell_id": row["cell_id"], "experiment_id": row["experiment_id"],
            "coordinate": json.loads(row["coordinate_json"]), "status": row["status"],
            "rating": row["rating"], "tags": json.loads(row["tags_json"]),
            "decision": row["decision"], "output": json.loads(row["output_json"]), "error": row["error"],
            "job_id": row["job_id"] if "job_id" in row.keys() else "",
        }
