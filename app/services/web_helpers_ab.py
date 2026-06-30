import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from services.job_service import JobService
from services.experiment_service import ExperimentService
from services.project_service import ProjectService
from spriteforge_utils import load_json, save_json

def _ab_run_path() -> Path:
    import web_helpers
    p = web_helpers.ROOT / "output" / "experiments" / "ab_runs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _queue_dir() -> Path:
    import web_helpers
    p = web_helpers.ROOT / "output" / "jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _ab_run_create(payload: Dict[str, Any], build_action_command_fn) -> Dict[str, Any]:
    import web_helpers
    ab_id = str(uuid.uuid4())
    name = str(payload.get("name") or f"A/B Run {time.strftime('%Y%m%d_%H%M%S')}")
    
    variant_a = payload.get("variant_a", {})
    variant_b = payload.get("variant_b", {})
    
    title_a, cmd_a = build_action_command_fn(variant_a)
    title_b, cmd_b = build_action_command_fn(variant_b)
    
    q_data = {
        "schema": "spriteforge_queue_v12",
        "name": name,
        "ab_id": ab_id,
        "project_name": payload.get("project_name", ""),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "jobs": [
            {
                "id": f"ab_{ab_id}_A",
                "action": variant_a.get("action", "generate_sprite"),
                "command": cmd_a,
                "status": "pending",
                "variant_label": "Variant A"
            },
            {
                "id": f"ab_{ab_id}_B",
                "action": variant_b.get("action", "generate_sprite"),
                "command": cmd_b,
                "status": "pending",
                "variant_label": "Variant B"
            }
        ]
    }
    
    q_dir = _queue_dir()
    q_path = q_dir / f"ab_run_{ab_id}_queue.json"
    save_json(q_path, q_data)
    
    runs_path = _ab_run_path()
    runs = load_json(runs_path, [])
    runs.insert(0, {
        "id": ab_id,
        "name": name,
        "project_name": payload.get("project_name", ""),
        "queue_path": str(q_path.relative_to(web_helpers.ROOT)).replace("\\", "/"),
        "variant_a": variant_a,
        "variant_b": variant_b,
        "created_at": q_data["created_at"]
    })
    save_json(runs_path, runs)
    
    cmd = [sys.executable, "spriteforge_queue.py", "run", "--queue", str(q_path), "--continue-on-error"]
    ok, job_id_or_err = JobService.start_job(f"A/B Run Queue: {name}", cmd, metadata={"ab_id": ab_id})
    return {"ok": ok, "ab_id": ab_id, "job_id": job_id_or_err if ok else None, "message": "A/B Run queue started." if ok else job_id_or_err}

def _ab_run_list() -> List[Dict[str, Any]]:
    return load_json(_ab_run_path(), [])

def _experiment_rows(project_meta: Optional[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows = ExperimentService.get_history()
    return [rec for rec in rows if ProjectService.item_matches_project(rec, project_meta)] if project_meta else rows

def _matching_experiment(sprite_rel: str) -> Optional[Dict[str, Any]]:
    wanted = sprite_rel.replace("\\", "/").strip("/")
    for rec in ExperimentService.get_history():
        if str(rec.get("sprite_folder") or "").replace("\\", "/").strip("/") == wanted:
            return rec
    return None
