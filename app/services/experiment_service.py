"""Experiment history service for SpriteForge Studio.

Tracks every generation run as a rich record so the gallery doubles as
"what worked?" history rather than just recent files.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_PATH = ROOT / "output" / "experiments" / "experiment_history.json"


class ExperimentService:
    _lock = threading.RLock()

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load() -> List[Dict[str, Any]]:
        EXPERIMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if EXPERIMENT_PATH.exists():
            try:
                return json.loads(EXPERIMENT_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    @staticmethod
    def _save(records: List[Dict[str, Any]]) -> None:
        EXPERIMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            EXPERIMENT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def append_run(
        *,
        job_id: str = "",
        prompt: str = "",
        negative: str = "",
        seed: Optional[int] = None,
        model_tier: str = "",
        profile: str = "",
        sprite_action: str = "",
        direction: str = "",
        workflow_hash: str = "",
        output_video: str = "",
        sprite_folder: str = "",
        qa_score: Optional[float] = None,
        qa_passed: Optional[bool] = None,
        fix_applied: bool = False,
        notes: str = "",
    ) -> str:
        """Append a new run record and return its id."""
        run_id = str(uuid.uuid4())
        record: Dict[str, Any] = {
            "id": run_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "job_id": job_id,
            "prompt": prompt,
            "negative": negative,
            "seed": seed,
            "model_tier": model_tier,
            "profile": profile,
            "sprite_action": sprite_action,
            "direction": direction,
            "workflow_hash": workflow_hash,
            "output_video": output_video,
            "sprite_folder": sprite_folder,
            "qa_score": qa_score,
            "qa_passed": qa_passed,
            "fix_applied": fix_applied,
            "notes": notes,
        }
        with ExperimentService._lock:
            records = ExperimentService._load()
            records.insert(0, record)  # newest first
            ExperimentService._save(records)
        return run_id

    @staticmethod
    def get_history(limit: int = 200) -> List[Dict[str, Any]]:
        """Return the most recent *limit* experiment records."""
        with ExperimentService._lock:
            return ExperimentService._load()[:limit]

    @staticmethod
    def get_run(run_id: str) -> Optional[Dict[str, Any]]:
        """Return a single run record by id, or None."""
        with ExperimentService._lock:
            for rec in ExperimentService._load():
                if rec.get("id") == run_id:
                    return rec
            return None

    @staticmethod
    def update_note(run_id: str, notes: str) -> bool:
        """Update the notes field on an existing record. Returns True if found."""
        with ExperimentService._lock:
            records = ExperimentService._load()
            for rec in records:
                if rec.get("id") == run_id:
                    rec["notes"] = notes
                    ExperimentService._save(records)
                    return True
            return False

    @staticmethod
    def update_qa(run_id: str, qa_score: float, qa_passed: bool) -> bool:
        """Update QA fields on an existing record. Returns True if found."""
        with ExperimentService._lock:
            records = ExperimentService._load()
            for rec in records:
                if rec.get("id") == run_id:
                    rec["qa_score"] = qa_score
                    rec["qa_passed"] = qa_passed
                    ExperimentService._save(records)
                    return True
            return False
