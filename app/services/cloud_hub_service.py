import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from spriteforge_utils import ROOT, load_json, safe_name, save_json


CLOUD_HUB_SCHEMA = "spriteforge_cloud_hub_v1"
CLOUD_NODES_PATH = ROOT / "config" / "cloud_nodes.json"
CLOUD_QUEUE_ASSIGNMENT_SCHEMA = "spriteforge_cloud_queue_assignment_v1"
CLOUD_QUEUE_DISPATCH_SCHEMA = "spriteforge_cloud_queue_dispatch_v1"


def _clean_url(url: str) -> str:
    cleaned = str(url or "").strip().rstrip("/")
    if cleaned and not cleaned.startswith(("http://", "https://")):
        cleaned = "http://" + cleaned
    return cleaned


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def normalize_cloud_node(raw: dict[str, Any]) -> dict[str, Any]:
    url = _clean_url(str(raw.get("url") or raw.get("server") or ""))
    label = str(raw.get("label") or raw.get("name") or url or "Cloud ComfyUI").strip()
    node_id = safe_name(str(raw.get("id") or label or url or "cloud_node")).lower()
    try:
        priority = int(raw.get("priority", 100))
    except (TypeError, ValueError):
        priority = 100
    try:
        active_jobs = max(0, int(raw.get("active_jobs", 0)))
    except (TypeError, ValueError):
        active_jobs = 0
    try:
        max_jobs = max(1, int(raw.get("max_jobs", 1)))
    except (TypeError, ValueError):
        max_jobs = 1
    status = str(raw.get("status") or "ready").strip().lower()
    if status not in {"ready", "busy", "draining", "offline"}:
        status = "ready"

    last_status = raw.get("last_status") if isinstance(raw.get("last_status"), dict) else {}
    return {
        "id": node_id,
        "label": label,
        "url": url,
        "enabled": bool(raw.get("enabled", True)),
        "priority": priority,
        "status": status,
        "active_jobs": active_jobs,
        "max_jobs": max_jobs,
        "tags": _clean_list(raw.get("tags")),
        "capabilities": _clean_list(raw.get("capabilities") or ["comfyui", "remote_generate"]),
        "last_status": last_status,
    }


def load_cloud_nodes(path: Path = CLOUD_NODES_PATH) -> list[dict[str, Any]]:
    data = load_json(path, default={})
    if isinstance(data, list):
        nodes = data
    elif isinstance(data, dict):
        nodes = data.get("nodes", [])
    else:
        nodes = []
    return [normalize_cloud_node(node) for node in nodes if isinstance(node, dict)]


def save_cloud_nodes(nodes: list[dict[str, Any]], path: Path = CLOUD_NODES_PATH) -> dict[str, Any]:
    normalized = [normalize_cloud_node(node) for node in nodes]
    payload = {
        "schema": CLOUD_HUB_SCHEMA,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": normalized,
    }
    save_json(path, payload)
    return payload


def upsert_cloud_node(node: dict[str, Any], path: Path = CLOUD_NODES_PATH) -> dict[str, Any]:
    normalized = normalize_cloud_node(node)
    nodes = load_cloud_nodes(path)
    replaced = False
    for index, existing in enumerate(nodes):
        if existing["id"] == normalized["id"]:
            nodes[index] = normalized
            replaced = True
            break
    if not replaced:
        nodes.append(normalized)
    save_cloud_nodes(nodes, path)
    return normalized


def remove_cloud_node(node_id: str, path: Path = CLOUD_NODES_PATH) -> bool:
    clean_id = safe_name(str(node_id or "")).lower()
    nodes = load_cloud_nodes(path)
    kept = [node for node in nodes if node["id"] != clean_id]
    if len(kept) == len(nodes):
        return False
    save_cloud_nodes(kept, path)
    return True


def check_cloud_node(node: dict[str, Any], timeout: float = 1.5) -> dict[str, Any]:
    normalized = normalize_cloud_node(node)
    started = time.perf_counter()
    status = {
        "ok": False,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latency_ms": None,
        "message": "Not checked",
    }
    if not normalized["url"]:
        status["message"] = "Missing node URL"
        return status

    request = urllib.request.Request(normalized["url"] + "/system_stats", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status["ok"] = 200 <= int(getattr(response, "status", 200)) < 500
            status["message"] = "Reachable" if status["ok"] else f"HTTP {getattr(response, 'status', 'unknown')}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        status["message"] = str(exc)
    finally:
        status["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return status


def select_cloud_node(
    nodes: list[dict[str, Any]],
    capability: str = "remote_generate",
    prefer_id: str = "",
) -> dict[str, Any] | None:
    clean_prefer = safe_name(prefer_id).lower() if prefer_id else ""
    candidates = []
    for node in nodes:
        normalized = normalize_cloud_node(node)
        if not normalized["enabled"] or not normalized["url"]:
            continue
        if capability and capability not in normalized["capabilities"]:
            continue
        if clean_prefer and normalized["id"] == clean_prefer:
            return normalized
        status = normalized.get("last_status") or {}
        status_rank = 0 if status.get("ok") else 1
        capacity_rank = 0 if normalized["status"] == "ready" and normalized["active_jobs"] < normalized["max_jobs"] else 1
        latency = status.get("latency_ms")
        latency_rank = float(latency) if isinstance(latency, (int, float)) else 999999.0
        load_rank = normalized["active_jobs"] / max(1, normalized["max_jobs"])
        candidates.append((status_rank, capacity_rank, normalized["priority"], load_rank, latency_rank, normalized["label"].lower(), normalized))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[:6])[0][6]


def plan_cloud_dispatch(
    nodes: list[dict[str, Any]],
    capability: str = "remote_generate",
    prefer_id: str = "",
) -> dict[str, Any]:
    clean_prefer = safe_name(prefer_id).lower() if prefer_id else ""
    ranked: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for node in nodes:
        normalized = normalize_cloud_node(node)
        reasons: list[str] = []
        if not normalized["enabled"]:
            reasons.append("disabled")
        if not normalized["url"]:
            reasons.append("missing_url")
        if capability and capability not in normalized["capabilities"]:
            reasons.append(f"missing_capability:{capability}")
        if reasons:
            rejected.append({"id": normalized["id"], "label": normalized["label"], "reasons": reasons})
            continue

        status = normalized.get("last_status") or {}
        has_capacity = normalized["status"] == "ready" and normalized["active_jobs"] < normalized["max_jobs"]
        latency = status.get("latency_ms")
        load = normalized["active_jobs"] / max(1, normalized["max_jobs"])
        score = {
            "preferred": 0 if clean_prefer and normalized["id"] == clean_prefer else 1,
            "reachable": 0 if status.get("ok") else 1,
            "capacity": 0 if has_capacity else 1,
            "priority": normalized["priority"],
            "load": load,
            "latency_ms": float(latency) if isinstance(latency, (int, float)) else 999999.0,
        }
        reason = "preferred node requested" if score["preferred"] == 0 else "best available capacity/priority/latency"
        if not has_capacity:
            reason = "eligible but currently at capacity or not ready"
        ranked.append({
            "id": normalized["id"],
            "label": normalized["label"],
            "url": normalized["url"],
            "status": normalized["status"],
            "active_jobs": normalized["active_jobs"],
            "max_jobs": normalized["max_jobs"],
            "capabilities": normalized["capabilities"],
            "score": score,
            "reason": reason,
        })

    ranked.sort(key=lambda item: (
        item["score"]["preferred"],
        item["score"]["reachable"],
        item["score"]["capacity"],
        item["score"]["priority"],
        item["score"]["load"],
        item["score"]["latency_ms"],
        item["label"].lower(),
    ))
    selected = ranked[0] if ranked else None
    return {
        "ok": selected is not None,
        "schema": "spriteforge_cloud_dispatch_plan_v1",
        "capability": capability,
        "prefer_id": clean_prefer,
        "selected": selected,
        "ranked": ranked,
        "rejected": rejected,
        "message": "Cloud node selected." if selected else "No eligible cloud node is available.",
    }


def _normalize_queue_job(raw: dict[str, Any], index: int) -> dict[str, Any]:
    job_id = safe_name(str(raw.get("id") or raw.get("job_id") or f"job_{index + 1}")).lower()
    capability = str(raw.get("capability") or raw.get("type") or "remote_generate").strip() or "remote_generate"
    try:
        priority = int(raw.get("priority", 100))
    except (TypeError, ValueError):
        priority = 100
    return {
        "id": job_id,
        "label": str(raw.get("label") or raw.get("prompt") or job_id).strip(),
        "capability": capability,
        "priority": priority,
        "estimated_seconds": raw.get("estimated_seconds"),
        "source": str(raw.get("source") or "manual").strip() or "manual",
    }


def _dispatch_handoff(job: dict[str, Any], node: dict[str, Any], slot_index: int, queue_position: int) -> dict[str, Any]:
    return {
        "schema": CLOUD_QUEUE_DISPATCH_SCHEMA,
        "job_id": job["id"],
        "node_id": node["id"],
        "node_url": node["url"],
        "queue_position": queue_position,
        "slot_index": slot_index,
        "dispatch_url": node["url"].rstrip("/") + "/prompt",
        "command_hint": f"spriteforge remote-generate --cloud-node {node['id']} --prompt \"{job['label']}\"",
        "capacity_snapshot": {
            "active_jobs": node["active_jobs"],
            "max_jobs": node["max_jobs"],
            "planned_slot": slot_index,
        },
        "non_destructive": True,
    }


def plan_cloud_queue_assignments(
    jobs: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    capability: str = "remote_generate",
    prefer_id: str = "",
) -> dict[str, Any]:
    clean_prefer = safe_name(prefer_id).lower() if prefer_id else ""
    normalized_jobs = [
        _normalize_queue_job(job, index)
        for index, job in enumerate(jobs)
        if isinstance(job, dict)
    ]
    eligible_nodes = []
    rejected_nodes = []
    for node in nodes:
        normalized = normalize_cloud_node(node)
        reasons: list[str] = []
        if not normalized["enabled"]:
            reasons.append("disabled")
        if not normalized["url"]:
            reasons.append("missing_url")
        if normalized["status"] != "ready":
            reasons.append(f"status:{normalized['status']}")
        if normalized["active_jobs"] >= normalized["max_jobs"]:
            reasons.append("at_capacity")
        if capability and capability not in normalized["capabilities"]:
            reasons.append(f"missing_capability:{capability}")
        free_slots = max(0, normalized["max_jobs"] - normalized["active_jobs"])
        if reasons:
            rejected_nodes.append({"id": normalized["id"], "label": normalized["label"], "reasons": reasons})
            continue
        status = normalized.get("last_status") or {}
        latency = status.get("latency_ms")
        eligible_nodes.append({
            "node": normalized,
            "free_slots": free_slots,
            "assigned": 0,
            "latency_ms": float(latency) if isinstance(latency, (int, float)) else 999999.0,
        })

    eligible_nodes.sort(key=lambda item: (
        0 if clean_prefer and item["node"]["id"] == clean_prefer else 1,
        item["node"]["priority"],
        item["node"]["active_jobs"] / max(1, item["node"]["max_jobs"]),
        item["latency_ms"],
        item["node"]["label"].lower(),
    ))

    assignments: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    sorted_jobs = sorted(enumerate(normalized_jobs), key=lambda item: (item[1]["priority"], item[0]))
    for queue_position, (_index, job) in enumerate(sorted_jobs, start=1):
        if capability and job["capability"] != capability:
            unassigned.append({"job": job, "reasons": [f"job_capability:{job['capability']}"]})
            continue
        target = next((item for item in eligible_nodes if item["assigned"] < item["free_slots"]), None)
        if not target:
            unassigned.append({"job": job, "reasons": ["no_free_remote_slot"]})
            continue
        slot_index = target["node"]["active_jobs"] + target["assigned"] + 1
        target["assigned"] += 1
        assignments.append({
            "job": job,
            "node_id": target["node"]["id"],
            "node_label": target["node"]["label"],
            "node_url": target["node"]["url"],
            "queue_position": queue_position,
            "slot_index": slot_index,
            "dispatch": _dispatch_handoff(job, target["node"], slot_index, queue_position),
            "reason": "preferred node free slot" if clean_prefer and target["node"]["id"] == clean_prefer else "lowest priority/load eligible slot",
        })

    capacity_summary = [
        {
            "id": item["node"]["id"],
            "label": item["node"]["label"],
            "free_slots": item["free_slots"],
            "assigned": item["assigned"],
            "remaining_slots": max(0, item["free_slots"] - item["assigned"]),
        }
        for item in eligible_nodes
    ]
    return {
        "ok": True,
        "schema": CLOUD_QUEUE_ASSIGNMENT_SCHEMA,
        "dry_run": True,
        "non_destructive": True,
        "capability": capability,
        "prefer_id": clean_prefer,
        "job_count": len(normalized_jobs),
        "assignment_count": len(assignments),
        "assignments": assignments,
        "unassigned": unassigned,
        "capacity_summary": capacity_summary,
        "rejected_nodes": rejected_nodes,
        "message": f"Planned {len(assignments)} of {len(normalized_jobs)} queued job(s) across {len(capacity_summary)} ready node(s).",
    }


def cloud_hub_status(
    path: Path = CLOUD_NODES_PATH,
    check: bool = False,
    capability: str = "remote_generate",
    prefer_id: str = "",
) -> dict[str, Any]:
    nodes = load_cloud_nodes(path)
    if check:
        checked_nodes = []
        for node in nodes:
            updated = dict(node)
            updated["last_status"] = check_cloud_node(node)
            checked_nodes.append(updated)
        nodes = checked_nodes
        save_cloud_nodes(nodes, path)
    selected = select_cloud_node(nodes, capability=capability, prefer_id=prefer_id)
    dispatch_plan = plan_cloud_dispatch(nodes, capability=capability, prefer_id=prefer_id)
    queue_plan = plan_cloud_queue_assignments([], nodes, capability=capability, prefer_id=prefer_id)
    return {
        "ok": True,
        "schema": CLOUD_HUB_SCHEMA,
        "nodes": nodes,
        "selected": selected,
        "dispatch_plan": dispatch_plan,
        "queue_plan": queue_plan,
        "count": len(nodes),
    }
