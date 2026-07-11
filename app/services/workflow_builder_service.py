"""Typed DAG workflows with preflight validation, caching, and restartable runs."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import deque
from typing import Any, Dict, List, Set

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import utc_now


WORKFLOW_SCHEMA = "spriteforge.workflow.v1"
NODE_TYPES = {
    "import": {"inputs": {}, "outputs": {"asset": "asset"}, "deterministic": True},
    "generate": {"inputs": {"reference": "asset?"}, "outputs": {"asset": "asset"}, "deterministic": False},
    "transform": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}, "deterministic": True},
    "background_remove": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}, "deterministic": True},
    "frame_extract": {"inputs": {"asset": "asset"}, "outputs": {"frames": "frames"}, "deterministic": True},
    "style_conform": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}, "deterministic": True},
    "qa": {"inputs": {"asset": "asset"}, "outputs": {"report": "qa_report"}, "deterministic": True},
    "conditional": {"inputs": {"report": "qa_report"}, "outputs": {"branch": "control"}, "deterministic": True},
    "approval": {"inputs": {"asset": "asset"}, "outputs": {"asset": "asset"}, "deterministic": False},
    "export": {"inputs": {"asset": "asset"}, "outputs": {"package": "export"}, "deterministic": True},
    "comfyui": {"inputs": {"asset": "asset?"}, "outputs": {"asset": "asset"}, "deterministic": False},
}


class WorkflowBuilderService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository
        with repository._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id),
                    status TEXT NOT NULL, inputs_json TEXT NOT NULL, outputs_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_node_runs (
                    run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE, node_id TEXT NOT NULL,
                    node_version INTEGER NOT NULL, input_hash TEXT NOT NULL, status TEXT NOT NULL,
                    output_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(run_id,node_id)
                );
                CREATE TABLE IF NOT EXISTS workflow_cache (
                    node_type TEXT NOT NULL, node_version INTEGER NOT NULL, input_hash TEXT NOT NULL,
                    output_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(node_type,node_version,input_hash)
                );
                """
            )

    def validate(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[Dict[str, str]] = []
        if not isinstance(workflow, dict):
            return {"ok": False, "errors": [{"path": "", "message": "Workflow must be an object"}]}
        nodes = workflow.get("nodes", [])
        edges = workflow.get("edges", [])
        if not isinstance(nodes, list) or not nodes:
            errors.append({"path": "nodes", "message": "At least one node is required"})
            nodes = []
        if not isinstance(edges, list):
            errors.append({"path": "edges", "message": "Edges must be a list"})
            edges = []
        by_id = {}
        for index, node in enumerate(nodes):
            node_id = str(node.get("id") or "") if isinstance(node, dict) else ""
            node_type = str(node.get("type") or "") if isinstance(node, dict) else ""
            if not node_id or node_id in by_id:
                errors.append({"path": f"nodes[{index}].id", "message": "Node ID is missing or duplicated"})
            elif node_type not in NODE_TYPES:
                errors.append({"path": f"nodes[{index}].type", "message": f"Unsupported node type: {node_type}"})
            else:
                by_id[node_id] = node
        adjacency: Dict[str, Set[str]] = {node_id: set() for node_id in by_id}
        indegree = {node_id: 0 for node_id in by_id}
        connected_inputs: Set[tuple[str, str]] = set()
        for index, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append({"path": f"edges[{index}]", "message": "Edge must be an object"})
                continue
            source, target = str(edge.get("from") or ""), str(edge.get("to") or "")
            output, input_name = str(edge.get("output") or ""), str(edge.get("input") or "")
            if source not in by_id or target not in by_id:
                errors.append({"path": f"edges[{index}]", "message": "Edge references an unknown node"})
                continue
            source_contract = NODE_TYPES[by_id[source]["type"]]["outputs"]
            target_contract = NODE_TYPES[by_id[target]["type"]]["inputs"]
            if output not in source_contract or input_name not in target_contract:
                errors.append({"path": f"edges[{index}]", "message": "Edge references an unknown port"})
                continue
            expected = target_contract[input_name].rstrip("?")
            if source_contract[output] != expected:
                errors.append({"path": f"edges[{index}]", "message": f"Type mismatch: {source_contract[output]} cannot connect to {expected}"})
                continue
            if (target, input_name) in connected_inputs:
                errors.append({"path": f"edges[{index}]", "message": "Input port already has a connection"})
                continue
            connected_inputs.add((target, input_name))
            adjacency[source].add(target)
            indegree[target] += 1
        for node_id, node in by_id.items():
            for input_name, input_type in NODE_TYPES[node["type"]]["inputs"].items():
                if not input_type.endswith("?") and (node_id, input_name) not in connected_inputs:
                    errors.append({"path": f"nodes.{node_id}.inputs.{input_name}", "message": "Required input is not connected"})
        queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
        order = []
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for target in adjacency[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if len(order) != len(by_id):
            errors.append({"path": "edges", "message": "Workflow must be acyclic"})
        return {"ok": not errors, "errors": errors, "order": order, "node_count": len(nodes), "edge_count": len(edges)}

    def save(self, project_id: str, workflow: Dict[str, Any]) -> Dict[str, Any]:
        validation = self.validate(workflow)
        if not validation["ok"]:
            raise ValueError("; ".join(f"{item['path']}: {item['message']}" for item in validation["errors"]))
        now = utc_now()
        payload = json.loads(json.dumps(workflow))
        workflow_id = str(payload.get("workflow_id") or f"workflow_{uuid.uuid4().hex}")
        payload.update({
            "schema": WORKFLOW_SCHEMA, "schema_version": 1, "workflow_id": workflow_id,
            "project_id": project_id, "name": str(payload.get("name") or "Untitled workflow"),
            "node_versions": {node["id"]: int(node.get("version", 1)) for node in payload["nodes"]},
            "updated_at": now,
        })
        payload.setdefault("created_at", now)
        with self.repository._connect() as connection:
            connection.execute(
                "INSERT INTO workflows VALUES(?,?,?,?,?,?) ON CONFLICT(workflow_id) DO UPDATE SET name=excluded.name,payload_json=excluded.payload_json,updated_at=excluded.updated_at",
                (workflow_id, project_id, payload["name"], json.dumps(payload, sort_keys=True), payload["created_at"], now),
            )
        return payload

    def get(self, workflow_id: str) -> Dict[str, Any]:
        with self.repository._connect() as connection:
            row = connection.execute("SELECT payload_json FROM workflows WHERE workflow_id=?", (workflow_id,)).fetchone()
        if not row:
            raise LookupError(f"Workflow not found: {workflow_id}")
        return json.loads(row["payload_json"])

    def run(self, workflow_id: str, inputs: Dict[str, Any] | None = None, *, restart_from: str = "") -> Dict[str, Any]:
        workflow = self.get(workflow_id)
        validation = self.validate(workflow)
        if not validation["ok"]:
            raise ValueError("Workflow is no longer valid")
        run_id, now = f"run_{uuid.uuid4().hex}", utc_now()
        context = dict(inputs or {})
        node_results = dict(context.pop("_node_results", {}))
        run_status = "completed"
        with self.repository._connect() as connection:
            connection.execute(
                "INSERT INTO workflow_runs(run_id,workflow_id,status,inputs_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (run_id, workflow_id, "running", json.dumps(context, sort_keys=True), now, now),
            )
        by_id = {node["id"]: node for node in workflow["nodes"]}
        incoming = {node_id: [] for node_id in by_id}
        for edge in workflow["edges"]:
            incoming[edge["to"]].append(edge)
        skipping = bool(restart_from)
        for node_id in validation["order"]:
            if skipping and node_id != restart_from:
                continue
            skipping = False
            node = by_id[node_id]
            node_inputs = {edge["input"]: node_results.get(edge["from"], {}).get(edge["output"]) for edge in incoming[node_id]}
            node_inputs.update(node.get("parameters", {}))
            version = int(node.get("version", 1))
            input_hash = hashlib.sha256(json.dumps(node_inputs, sort_keys=True, default=str).encode()).hexdigest()
            contract = NODE_TYPES[node["type"]]
            cached = None
            if contract["deterministic"]:
                with self.repository._connect() as connection:
                    cached = connection.execute(
                        "SELECT output_json FROM workflow_cache WHERE node_type=? AND node_version=? AND input_hash=?",
                        (node["type"], version, input_hash),
                    ).fetchone()
            if cached:
                output, status = json.loads(cached["output_json"]), "cached"
            elif node["type"] in {"generate", "comfyui"}:
                output = self._submit_provider_job(workflow, node, node_inputs)
                status, run_status = "queued", "waiting"
            elif node["type"] == "approval":
                output, status, run_status = {"approval_required": True, **node_inputs}, "waiting", "waiting"
            else:
                output, status = self._local_output(node, node_inputs), "completed"
                if contract["deterministic"]:
                    with self.repository._connect() as connection:
                        connection.execute(
                            "INSERT OR REPLACE INTO workflow_cache VALUES(?,?,?,?,?)",
                            (node["type"], version, input_hash, json.dumps(output, sort_keys=True), utc_now()),
                        )
            node_results[node_id] = output
            with self.repository._connect() as connection:
                connection.execute(
                    "INSERT INTO workflow_node_runs VALUES(?,?,?,?,?,?,?)",
                    (run_id, node_id, version, input_hash, status, json.dumps(output, sort_keys=True), ""),
                )
            if run_status == "waiting":
                break
        with self.repository._connect() as connection:
            connection.execute(
                "UPDATE workflow_runs SET status=?,outputs_json=?,updated_at=? WHERE run_id=?",
                (run_status, json.dumps(node_results, sort_keys=True), utc_now(), run_id),
            )
        return {"schema": "spriteforge.workflow_run.v1", "run_id": run_id, "status": run_status, "nodes": node_results}

    def synchronize_run(self, run_id: str) -> Dict[str, Any]:
        """Resolve provider jobs and continue downstream nodes without repeating upstream work."""
        from services.job_service import JobService

        with self.repository._connect() as connection:
            run = connection.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
            if not run:
                raise LookupError(f"Workflow run not found: {run_id}")
            waiting = connection.execute(
                "SELECT * FROM workflow_node_runs WHERE run_id=? AND status IN ('queued','waiting') ORDER BY rowid DESC LIMIT 1", (run_id,)
            ).fetchone()
        if not waiting:
            return {"run_id": run_id, "status": run["status"], "changed": False, "nodes": json.loads(run["outputs_json"])}
        outputs = json.loads(run["outputs_json"])
        node_output = json.loads(waiting["output_json"])
        job_id = str(node_output.get("job_id") or "")
        if not job_id:
            return {"run_id": run_id, "status": "waiting", "changed": False, "nodes": outputs}
        job = JobService.get_job(job_id)
        if not job or job.get("phase") == "running":
            return {"run_id": run_id, "status": "waiting", "changed": False, "nodes": outputs}
        if job.get("phase") != "completed":
            with self.repository._connect() as connection:
                connection.execute("UPDATE workflow_node_runs SET status='failed',error=? WHERE run_id=? AND node_id=?", (str(job.get("stage_detail") or "Provider job failed"), run_id, waiting["node_id"]))
                connection.execute("UPDATE workflow_runs SET status='failed',updated_at=? WHERE run_id=?", (utc_now(), run_id))
            return {"run_id": run_id, "status": "failed", "changed": True, "job": job}
        metadata = job.get("metadata", {}) if isinstance(job.get("metadata"), dict) else {}
        outputs[waiting["node_id"]] = {"asset": {"sprite_folder": metadata.get("sprite_folder", ""), "job_id": job_id}}
        with self.repository._connect() as connection:
            connection.execute("UPDATE workflow_node_runs SET status='completed',output_json=? WHERE run_id=? AND node_id=?", (json.dumps(outputs[waiting["node_id"]], sort_keys=True), run_id, waiting["node_id"]))
            connection.execute("UPDATE workflow_runs SET status='completed',outputs_json=?,updated_at=? WHERE run_id=?", (json.dumps(outputs, sort_keys=True), utc_now(), run_id))
        workflow = self.get(run["workflow_id"])
        order = self.validate(workflow)["order"]
        index = order.index(waiting["node_id"])
        if index + 1 < len(order):
            continuation = self.run(run["workflow_id"], {"_node_results": outputs}, restart_from=order[index + 1])
            return {"run_id": run_id, "status": continuation["status"], "changed": True, "continuation": continuation}
        return {"run_id": run_id, "status": "completed", "changed": True, "nodes": outputs}

    @staticmethod
    def _submit_provider_job(workflow: Dict[str, Any], node: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        from services.job_service import JobService
        from web_helpers import build_action_command

        parameters = dict(node.get("parameters", {}))
        generation = parameters.get("generation") if isinstance(parameters.get("generation"), dict) else parameters
        payload = dict(generation)
        payload.setdefault("action", "generate_sprite")
        reference = inputs.get("reference") or inputs.get("asset")
        if reference and "reference_image" not in payload:
            payload["reference_image"] = reference.get("path") if isinstance(reference, dict) else reference
        title, command = build_action_command(payload)
        metadata = {
            "workflow_id": workflow["workflow_id"], "workflow_node_id": node["id"],
            "provider_adapter": node["type"], "generation_request": payload,
        }
        ok, job_id = JobService.start_job(title, command, metadata=metadata)
        if not ok:
            raise RuntimeError(job_id)
        return {"job_id": job_id, "job_request": payload, "provider": node["type"]}

    @staticmethod
    def _local_output(node: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        node_type = node["type"]
        if node_type == "import":
            return {"asset": inputs.get("asset") or inputs.get("path") or inputs}
        if node_type in {"transform", "background_remove", "style_conform"}:
            return {"asset": {"input": inputs.get("asset"), "operation": node_type, "parameters": node.get("parameters", {})}}
        if node_type == "frame_extract":
            return {"frames": {"source": inputs.get("asset"), "parameters": node.get("parameters", {})}}
        if node_type == "qa":
            return {"report": {"asset": inputs.get("asset"), "passed": True, "findings": []}}
        if node_type == "conditional":
            report = inputs.get("report") or {}
            return {"branch": "passed" if report.get("passed") else "failed"}
        if node_type == "export":
            return {"package": {"asset": inputs.get("asset"), "preset": node.get("parameters", {}).get("preset", "generic")}}
        return {}
