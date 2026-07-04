"""Experiment history service for SpriteForge Studio.

Tracks every generation run as a rich record so the gallery doubles as
"what worked?" history rather than just recent files.
"""
from __future__ import annotations

import logging
from collections import defaultdict
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from spriteforge_utils import ROOT, load_json, save_json

EXPERIMENT_PATH = ROOT / "output" / "experiments" / "experiment_history.json"
MAX_EXPERIMENT_HISTORY = 500
logger = logging.getLogger(__name__)


class ExperimentService:
    _lock = threading.RLock()

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load() -> List[Dict[str, Any]]:
        EXPERIMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        records = load_json(EXPERIMENT_PATH, [])
        if isinstance(records, list):
            return records
        logger.warning("Experiment history was not a list in %s; ignoring corrupt payload.", EXPERIMENT_PATH)
        return []

    @staticmethod
    def _save(records: List[Dict[str, Any]]) -> None:
        EXPERIMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        save_json(EXPERIMENT_PATH, records[:MAX_EXPERIMENT_HISTORY])

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
        project_name: str = "",
        project_path: str = "",
        project_root: str = "",
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
            "project_name": project_name,
            "project_path": project_path,
            "project_root": project_root,
            "qa_score": qa_score,
            "qa_passed": qa_passed,
            "fix_applied": fix_applied,
            "starred": False,
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
    def set_starred(run_id: str, starred: bool) -> bool:
        """Mark a run as starred/unstarred. Returns True if found."""
        with ExperimentService._lock:
            records = ExperimentService._load()
            for rec in records:
                if rec.get("id") == run_id:
                    rec["starred"] = bool(starred)
                    ExperimentService._save(records)
                    return True
            return False

    @staticmethod
    def pick_winner(
        *,
        run_id: str = "",
        sprite_folder: str = "",
        compared_sprites: Optional[List[str]] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """Mark an experiment as the selected compare-player winner."""
        normalized_folder = str(sprite_folder or "").replace("\\", "/").strip("/")
        compared = [
            str(path or "").replace("\\", "/").strip("/")
            for path in (compared_sprites or [])
            if str(path or "").strip()
        ][:4]
        with ExperimentService._lock:
            records = ExperimentService._load()
            matched: Optional[Dict[str, Any]] = None
            for rec in records:
                rec_folder = str(rec.get("sprite_folder") or "").replace("\\", "/").strip("/")
                if (run_id and rec.get("id") == run_id) or (normalized_folder and rec_folder == normalized_folder):
                    matched = rec
                    break
            if not matched:
                return {
                    "ok": False,
                    "winner_recorded": False,
                    "message": "No matching experiment record found for the selected sprite.",
                    "sprite_folder": normalized_folder,
                }
            matched["starred"] = True
            matched["winner"] = True
            matched["winner_selected_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            matched["compare_winner"] = {
                "sprite_folder": normalized_folder or matched.get("sprite_folder") or "",
                "compared_sprites": compared,
                "note": note or "Selected in N-way Compare Player.",
            }
            existing_notes = str(matched.get("notes") or "").strip()
            winner_note = note or f"Picked as compare winner among {len(compared) or 1} variant(s)."
            matched["notes"] = f"{existing_notes}\n{winner_note}".strip() if existing_notes else winner_note
            ExperimentService._save(records)
            return {
                "ok": True,
                "winner_recorded": True,
                "experiment": matched,
                "message": "Compare winner recorded in experiment history.",
            }

    @staticmethod
    def update_qa(run_id: str, qa_score: Optional[float], qa_passed: bool) -> bool:
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

    @staticmethod
    def update_qa_for_sprite(sprite_folder: str, qa_score: Optional[float], qa_passed: bool) -> bool:
        """Update the newest run matching *sprite_folder*. Returns True if found."""
        normalized = str(sprite_folder or "").replace("\\", "/").strip("/")
        if not normalized:
            return False
        with ExperimentService._lock:
            records = ExperimentService._load()
            for rec in records:
                rec_folder = str(rec.get("sprite_folder") or "").replace("\\", "/").strip("/")
                if rec_folder == normalized:
                    rec["qa_score"] = qa_score
                    rec["qa_passed"] = bool(qa_passed)
                    ExperimentService._save(records)
                    return True
            return False

    @staticmethod
    def export_history(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Return a stable export document for all experiment records."""
        with ExperimentService._lock:
            export_records = records if records is not None else ExperimentService._load()
            return {
                "schema": "spriteforge_experiment_history_v1",
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "count": len(export_records),
                "records": export_records,
            }

    @staticmethod
    def analytics(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Summarize experiment history for the in-app analytics dashboard."""
        with ExperimentService._lock:
            rows = list(records if records is not None else ExperimentService._load())

        scored = [rec for rec in rows if rec.get("qa_score") is not None]
        scores = [float(rec.get("qa_score") or 0.0) for rec in scored]
        passed = [rec for rec in rows if rec.get("qa_passed") is True]
        starred = [rec for rec in rows if rec.get("starred")]

        def avg(values: List[float]) -> Optional[float]:
            return round(sum(values) / len(values), 2) if values else None

        buckets = [
            {"label": "90-100", "min": 90, "max": 100, "count": 0},
            {"label": "75-89", "min": 75, "max": 89.999, "count": 0},
            {"label": "50-74", "min": 50, "max": 74.999, "count": 0},
            {"label": "0-49", "min": 0, "max": 49.999, "count": 0},
            {"label": "Unscored", "min": None, "max": None, "count": max(0, len(rows) - len(scored))},
        ]
        for score in scores:
            for bucket in buckets:
                if bucket["min"] is not None and bucket["min"] <= score <= float(bucket["max"]):
                    bucket["count"] += 1
                    break

        by_day: Dict[str, List[float]] = defaultdict(list)
        by_action: Dict[str, List[float]] = defaultdict(list)
        by_profile: Dict[str, List[float]] = defaultdict(list)
        by_seed: Dict[str, List[float]] = defaultdict(list)
        prompt_rows: List[Dict[str, Any]] = []
        for rec in rows:
            score_value = rec.get("qa_score")
            score = float(score_value) if score_value is not None else None
            day = str(rec.get("created_at") or "")[:10] or "unknown"
            action = str(rec.get("sprite_action") or "unknown")
            profile = str(rec.get("profile") or "unknown")
            seed = rec.get("seed")
            if score is not None:
                by_day[day].append(score)
                by_action[action].append(score)
                by_profile[profile].append(score)
                if seed not in (None, "", -1):
                    by_seed[str(seed)].append(score)
            prompt = str(rec.get("prompt") or rec.get("character") or "").strip()
            if prompt:
                prompt_rows.append({
                    "id": rec.get("id", ""),
                    "prompt": prompt[:240],
                    "action": action,
                    "direction": rec.get("direction") or "",
                    "score": score,
                    "starred": bool(rec.get("starred")),
                })

        def ranked(groups: Dict[str, List[float]], limit: int = 6) -> List[Dict[str, Any]]:
            rows_out = [
                {"name": name, "count": len(vals), "average_score": avg(vals), "best_score": round(max(vals), 2)}
                for name, vals in groups.items()
                if vals
            ]
            return sorted(rows_out, key=lambda item: (item["average_score"] or -1, item["count"]), reverse=True)[:limit]

        score_over_time = [
            {"date": day, "average_score": avg(vals), "count": len(vals)}
            for day, vals in sorted(by_day.items())
        ]
        best_runs = sorted(
            [
                {
                    "id": rec.get("id", ""),
                    "created_at": rec.get("created_at", ""),
                    "prompt": str(rec.get("prompt") or rec.get("character") or "")[:180],
                    "action": rec.get("sprite_action") or "",
                    "direction": rec.get("direction") or "",
                    "profile": rec.get("profile") or "",
                    "seed": rec.get("seed"),
                    "score": float(rec.get("qa_score")),
                    "sprite_folder": rec.get("sprite_folder") or "",
                    "starred": bool(rec.get("starred")),
                }
                for rec in scored
            ],
            key=lambda rec: rec["score"],
            reverse=True,
        )[:8]
        top_action = ranked(by_action, 1)[0] if by_action else None
        top_profile = ranked(by_profile, 1)[0] if by_profile else None
        top_seed = ranked(by_seed, 1)[0] if by_seed else None
        top_run = best_runs[0] if best_runs else None
        recommendations: List[Dict[str, Any]] = []
        if top_run:
            recommendations.append({
                "kind": "winning_prompt",
                "title": "Reuse the highest QA prompt",
                "detail": top_run.get("prompt") or "A top-scoring prompt is ready to reuse.",
                "score": top_run.get("score"),
                "run_id": top_run.get("id", ""),
            })
        if top_profile:
            recommendations.append({
                "kind": "profile",
                "title": f"Lean on profile {top_profile['name']}",
                "detail": f"{top_profile['average_score']} average QA across {top_profile['count']} scored run(s).",
                "score": top_profile.get("average_score"),
                "name": top_profile.get("name"),
            })
        if top_seed:
            recommendations.append({
                "kind": "seed",
                "title": f"Try seed {top_seed['name']} again",
                "detail": f"{top_seed['average_score']} average QA; good candidate for controlled variants.",
                "score": top_seed.get("average_score"),
                "name": top_seed.get("name"),
            })
        if top_action:
            recommendations.append({
                "kind": "action",
                "title": f"Action {top_action['name']} is performing well",
                "detail": f"{top_action['average_score']} average QA across {top_action['count']} run(s).",
                "score": top_action.get("average_score"),
                "name": top_action.get("name"),
            })

        return {
            "ok": True,
            "total_runs": len(rows),
            "scored_runs": len(scored),
            "average_score": avg(scores),
            "pass_rate": round((len(passed) / len(scored)) * 100, 1) if scored else None,
            "starred_runs": len(starred),
            "score_distribution": buckets,
            "score_over_time": score_over_time,
            "score_by_action": ranked(by_action),
            "best_profiles": ranked(by_profile),
            "best_seeds": ranked(by_seed),
            "best_runs": best_runs,
            "prompt_history": prompt_rows[:80],
            "recommendations": recommendations[:4],
            "insights": {
                "best_action": top_action,
                "best_profile": top_profile,
                "best_seed": top_seed,
            },
        }

    @staticmethod
    def search_prompts(
        query: str = "",
        *,
        records: Optional[List[Dict[str, Any]]] = None,
        limit: int = 40,
        starred_only: bool = False,
    ) -> Dict[str, Any]:
        """Search prompt memory rows across experiment history."""
        needle = str(query or "").strip().lower()
        with ExperimentService._lock:
            rows = list(records if records is not None else ExperimentService._load())
        matches: List[Dict[str, Any]] = []
        for rec in rows:
            prompt = str(rec.get("prompt") or rec.get("character") or "").strip()
            if not prompt:
                continue
            haystack = " ".join([
                prompt,
                str(rec.get("sprite_action") or ""),
                str(rec.get("direction") or ""),
                str(rec.get("profile") or ""),
                str(rec.get("notes") or ""),
            ]).lower()
            if starred_only and not rec.get("starred"):
                continue
            if needle and needle not in haystack:
                continue
            matches.append({
                "id": rec.get("id", ""),
                "prompt": prompt[:500],
                "negative": rec.get("negative") or rec.get("negative_prompt") or "",
                "action": rec.get("sprite_action") or "",
                "direction": rec.get("direction") or "",
                "profile": rec.get("profile") or "",
                "tier": rec.get("model_tier") or "",
                "seed": rec.get("seed"),
                "score": rec.get("qa_score"),
                "starred": bool(rec.get("starred")),
                "sprite_folder": rec.get("sprite_folder") or "",
                "created_at": rec.get("created_at") or "",
            })
        return {
            "ok": True,
            "query": query,
            "count": len(matches),
            "prompts": matches[:max(1, min(200, int(limit)))],
        }

    @staticmethod
    def winning_prompt_pack(records: Optional[List[Dict[str, Any]]] = None, limit: int = 24) -> Dict[str, Any]:
        """Build a portable prompt pack from pinned prompts and top QA runs."""
        with ExperimentService._lock:
            rows = list(records if records is not None else ExperimentService._load())
        candidates = []
        for rec in rows:
            prompt = str(rec.get("prompt") or rec.get("character") or "").strip()
            if not prompt:
                continue
            score = rec.get("qa_score")
            qa_score = float(score) if score is not None else None
            starred = bool(rec.get("starred"))
            candidates.append({
                "schema": "spriteforge.winning_prompt_entry.v1",
                "id": rec.get("id", ""),
                "name": f"{rec.get('sprite_action') or 'sprite'}_{rec.get('direction') or 'view'}_{rec.get('seed') or 'seed'}",
                "prompt": prompt,
                "negative": rec.get("negative") or rec.get("negative_prompt") or "",
                "action": rec.get("sprite_action") or "",
                "direction": rec.get("direction") or "",
                "profile": rec.get("profile") or "",
                "tier": rec.get("model_tier") or "",
                "seed": rec.get("seed"),
                "qa_score": qa_score,
                "qa_passed": rec.get("qa_passed"),
                "starred": starred,
                "winner": bool(rec.get("winner")),
                "sprite_folder": rec.get("sprite_folder") or "",
                "workflow_hash": rec.get("workflow_hash") or "",
                "created_at": rec.get("created_at") or "",
                "reuse": {
                    "recommended": starred or (qa_score is not None and qa_score >= 75),
                    "reason": "starred by user" if starred else ("high QA score" if qa_score is not None and qa_score >= 75 else "available prompt memory"),
                    "prompt_fields": ["prompt", "negative", "action", "direction", "profile", "seed"],
                },
            })
        candidates.sort(key=lambda row: (1 if row["starred"] else 0, float(row["qa_score"] or -1)), reverse=True)
        entries = candidates[:max(1, min(200, int(limit)))]
        for rank, entry in enumerate(entries, start=1):
            entry["selection_rank"] = rank
        return {
            "schema": "spriteforge.winning_prompt_pack.v1",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "entry_count": len(entries),
            "selection": "starred prompts first, then highest QA score",
            "selection_contract": {
                "sort": ["starred desc", "qa_score desc"],
                "max_entries": max(1, min(200, int(limit))),
                "entry_schema": "spriteforge.winning_prompt_entry.v1",
            },
            "entries": entries,
        }

    @staticmethod
    def clear_history(
        *,
        keep_starred: bool = True,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> int:
        """Clear experiment records and return the number removed."""
        with ExperimentService._lock:
            records = ExperimentService._load()
            kept: List[Dict[str, Any]] = []
            removed = 0
            for rec in records:
                in_scope = predicate(rec) if predicate else True
                if not in_scope or (keep_starred and rec.get("starred")):
                    kept.append(rec)
                else:
                    removed += 1
            ExperimentService._save(kept)
            return removed
