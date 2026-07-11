"""Capability-aware render-farm workers, quotas, leases, and artifact contracts."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


WORKER_STATES = {"ready", "busy", "draining", "offline"}


class WorkerPoolService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS farm_workers (
                    worker_id TEXT PRIMARY KEY, name TEXT NOT NULL, endpoint TEXT NOT NULL, state TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL, resources_json TEXT NOT NULL, active_leases INTEGER NOT NULL DEFAULT 0,
                    max_leases INTEGER NOT NULL DEFAULT 1, version TEXT NOT NULL, last_heartbeat TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS farm_quotas (
                    project_id TEXT PRIMARY KEY, max_concurrent INTEGER NOT NULL, max_daily_cost REAL NOT NULL,
                    max_storage_bytes INTEGER NOT NULL, consumed_daily_cost REAL NOT NULL DEFAULT 0,
                    consumed_storage_bytes INTEGER NOT NULL DEFAULT 0, reset_date TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS farm_leases (
                    lease_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, project_id TEXT NOT NULL, worker_id TEXT NOT NULL,
                    state TEXT NOT NULL, requirements_json TEXT NOT NULL, cost_estimate REAL NOT NULL,
                    leased_at TEXT NOT NULL, expires_at TEXT NOT NULL, completed_at TEXT,
                    output_contract_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_farm_leases_project_state ON farm_leases(project_id,state);
                """
            )

    def register(self, worker: Dict[str, Any]) -> Dict[str, Any]:
        worker_id = str(worker.get("worker_id") or f"worker_{uuid.uuid4().hex}")
        state = str(worker.get("state") or "ready")
        if state not in WORKER_STATES:
            raise ValueError("Invalid worker state")
        capabilities = sorted({str(item) for item in worker.get("capabilities", [])})
        resources = worker.get("resources", {}) if isinstance(worker.get("resources"), dict) else {}
        normalized = {
            "worker_id": worker_id, "name": str(worker.get("name") or worker_id),
            "endpoint": str(worker.get("endpoint") or "local"), "state": state,
            "capabilities": capabilities, "resources": {
                "cpu_threads": max(1, int(resources.get("cpu_threads", 1))),
                "ram_mb": max(0, int(resources.get("ram_mb", 0))),
                "gpu": str(resources.get("gpu") or ""), "vram_mb": max(0, int(resources.get("vram_mb", 0))),
                "disk_free_bytes": max(0, int(resources.get("disk_free_bytes", 0))),
            },
            "active_leases": max(0, int(worker.get("active_leases", 0))),
            "max_leases": max(1, int(worker.get("max_leases", 1))), "version": str(worker.get("version") or "1"),
            "last_heartbeat": utc_now(),
        }
        with self.repository._connect() as connection:
            connection.execute(
                """INSERT INTO farm_workers VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET
                   name=excluded.name,endpoint=excluded.endpoint,state=excluded.state,capabilities_json=excluded.capabilities_json,
                   resources_json=excluded.resources_json,max_leases=excluded.max_leases,version=excluded.version,last_heartbeat=excluded.last_heartbeat""",
                (worker_id, normalized["name"], normalized["endpoint"], state, json.dumps(capabilities), json.dumps(normalized["resources"], sort_keys=True), normalized["active_leases"], normalized["max_leases"], normalized["version"], normalized["last_heartbeat"]),
            )
        return normalized

    def heartbeat(self, worker_id: str, *, state: str | None = None, resources: Dict[str, Any] | None = None) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute("SELECT * FROM farm_workers WHERE worker_id=?", (worker_id,)).fetchone()
        if not row:
            raise LookupError(f"Worker not found: {worker_id}")
        return self.register({
            "worker_id": worker_id, "name": row["name"], "endpoint": row["endpoint"],
            "state": state or row["state"], "capabilities": json.loads(row["capabilities_json"]),
            "resources": resources or json.loads(row["resources_json"]), "active_leases": row["active_leases"],
            "max_leases": row["max_leases"], "version": row["version"],
        })

    def set_quota(self, project_id: str, *, max_concurrent: int = 4, max_daily_cost: float = 100,
                  max_storage_bytes: int = 100_000_000_000) -> Dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        with self.repository._connect() as connection:
            connection.execute(
                """INSERT INTO farm_quotas VALUES(?,?,?,?,0,0,?) ON CONFLICT(project_id) DO UPDATE SET
                   max_concurrent=excluded.max_concurrent,max_daily_cost=excluded.max_daily_cost,max_storage_bytes=excluded.max_storage_bytes""",
                (project_id, max(1, int(max_concurrent)), max(0, float(max_daily_cost)), max(1, int(max_storage_bytes)), today),
            )
        return {"project_id": project_id, "max_concurrent": max_concurrent, "max_daily_cost": max_daily_cost, "max_storage_bytes": max_storage_bytes}

    def route(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        required_caps = set(str(item) for item in requirements.get("capabilities", []))
        min_vram = max(0, int(requirements.get("vram_mb", 0)))
        min_disk = max(0, int(requirements.get("storage_bytes", 0)))
        preferred_gpu = str(requirements.get("gpu") or "").lower()
        candidates, rejected = [], []
        with self.repository._connect() as connection:
            rows = connection.execute("SELECT * FROM farm_workers").fetchall()
        now = datetime.now(timezone.utc)
        for row in rows:
            caps, resources = set(json.loads(row["capabilities_json"])), json.loads(row["resources_json"])
            reasons = []
            stale = now - datetime.fromisoformat(row["last_heartbeat"].replace("Z", "+00:00")) > timedelta(seconds=90)
            if stale or row["state"] not in {"ready", "busy"}: reasons.append("unavailable")
            if row["active_leases"] >= row["max_leases"]: reasons.append("at_capacity")
            if not required_caps.issubset(caps): reasons.append("missing_capability")
            if int(resources.get("vram_mb", 0)) < min_vram: reasons.append("insufficient_vram")
            if int(resources.get("disk_free_bytes", 0)) < min_disk: reasons.append("insufficient_disk")
            if reasons:
                rejected.append({"worker_id": row["worker_id"], "reasons": reasons})
                continue
            score = (
                0 if preferred_gpu and preferred_gpu in str(resources.get("gpu", "")).lower() else 1,
                row["active_leases"] / max(1, row["max_leases"]), -int(resources.get("vram_mb", 0)), row["worker_id"],
            )
            candidates.append((score, row, resources))
        candidates.sort(key=lambda item: item[0])
        selected = candidates[0] if candidates else None
        return {"ok": selected is not None, "selected": self._worker(selected[1]) if selected else None, "rejected": rejected}

    def lease(self, job_id: str, project_id: str, requirements: Dict[str, Any], *, cost_estimate: float = 0.0,
              seconds: int = 300) -> Dict[str, Any]:
        self._check_quota(project_id, cost_estimate)
        plan = self.route(requirements)
        if not plan["selected"]:
            raise RuntimeError("No capable worker is currently available")
        worker_id, now = plan["selected"]["worker_id"], datetime.now(timezone.utc)
        lease_id = f"lease_{uuid.uuid4().hex}"
        expires = now + timedelta(seconds=max(30, min(3600, int(seconds))))
        with self.repository._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            worker = connection.execute("SELECT * FROM farm_workers WHERE worker_id=?", (worker_id,)).fetchone()
            if worker["active_leases"] >= worker["max_leases"]:
                raise RuntimeError("Worker capacity changed while leasing")
            connection.execute("UPDATE farm_workers SET active_leases=active_leases+1,state='busy' WHERE worker_id=?", (worker_id,))
            connection.execute("INSERT INTO farm_leases VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                lease_id, job_id, project_id, worker_id, "leased", json.dumps(requirements, sort_keys=True), float(cost_estimate),
                now.isoformat().replace("+00:00", "Z"), expires.isoformat().replace("+00:00", "Z"), None, "{}",
            ))
        return {"lease_id": lease_id, "job_id": job_id, "worker_id": worker_id, "state": "leased", "expires_at": expires.isoformat().replace("+00:00", "Z"), "dispatch_endpoint": plan["selected"]["endpoint"]}

    def complete(self, lease_id: str, outputs: List[Dict[str, Any]], *, actual_cost: float = 0.0,
                 storage_bytes: int = 0) -> Dict[str, Any]:
        contract = self._output_contract(outputs)
        with self.repository._connect() as connection:
            lease = connection.execute("SELECT * FROM farm_leases WHERE lease_id=?", (lease_id,)).fetchone()
            if not lease or lease["state"] != "leased":
                raise LookupError("Active worker lease not found")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE farm_leases SET state='completed',completed_at=?,output_contract_json=? WHERE lease_id=?", (utc_now(), json.dumps(contract, sort_keys=True), lease_id))
            connection.execute("UPDATE farm_workers SET active_leases=MAX(0,active_leases-1),state=CASE WHEN active_leases<=1 THEN 'ready' ELSE state END WHERE worker_id=?", (lease["worker_id"],))
            connection.execute("UPDATE farm_quotas SET consumed_daily_cost=consumed_daily_cost+?,consumed_storage_bytes=consumed_storage_bytes+? WHERE project_id=?", (max(0, float(actual_cost)), max(0, int(storage_bytes)), lease["project_id"]))
        return {"lease_id": lease_id, "state": "completed", "outputs": contract}

    def _check_quota(self, project_id: str, cost: float) -> None:
        with self.repository._connect() as connection:
            quota = connection.execute("SELECT * FROM farm_quotas WHERE project_id=?", (project_id,)).fetchone()
            active = connection.execute("SELECT COUNT(*) count FROM farm_leases WHERE project_id=? AND state='leased'", (project_id,)).fetchone()["count"]
        if not quota:
            self.set_quota(project_id)
            return self._check_quota(project_id, cost)
        if active >= quota["max_concurrent"] or quota["consumed_daily_cost"] + cost > quota["max_daily_cost"]:
            raise RuntimeError("Project render-farm quota would be exceeded")

    @staticmethod
    def _output_contract(outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        normalized = []
        for output in outputs:
            digest = str(output.get("sha256") or "")
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
                raise ValueError("Every worker output requires a SHA-256 digest")
            normalized.append({"name": str(output.get("name") or "artifact"), "sha256": digest.lower(), "size_bytes": max(0, int(output.get("size_bytes", 0))), "media_type": str(output.get("media_type") or "application/octet-stream")})
        return {"schema": "spriteforge.worker_outputs.v1", "artifacts": normalized}

    @staticmethod
    def _worker(row: Any) -> Dict[str, Any]:
        return {"worker_id": row["worker_id"], "name": row["name"], "endpoint": row["endpoint"], "state": row["state"], "capabilities": json.loads(row["capabilities_json"]), "resources": json.loads(row["resources_json"]), "active_leases": row["active_leases"], "max_leases": row["max_leases"], "version": row["version"]}
