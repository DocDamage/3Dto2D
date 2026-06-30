from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


PROFILE_EXPLAINERS: Dict[str, Dict[str, str]] = {
    "wan22_5b_3060_best": {
        "label": "Wan 2.2 5B / RTX 3060 Best",
        "why_selected": "Chosen for RTX 3060-class 12 GB VRAM when Wan 2.2 5B files are present. It favors cleaner motion over raw speed.",
        "tradeoffs": "Moderate runtime and VRAM pressure. Use wan22_5b_debug if memory gets tight.",
        "risk_level": "medium",
    },
    "wan22_5b_local": {
        "label": "Wan 2.2 5B Local",
        "why_selected": "Chosen when the advanced local model is installed and the goal is balanced local quality.",
        "tradeoffs": "Good quality with less pressure than the quality profile.",
        "risk_level": "medium",
    },
    "wan22_5b_debug": {
        "label": "Wan 2.2 5B Debug",
        "why_selected": "Chosen after memory failures or for quick WAN checks before a full-quality run.",
        "tradeoffs": "Lower frame/step budget, faster failures, less polished output.",
        "risk_level": "low",
    },
    "sprite_fast": {
        "label": "Sprite Fast",
        "why_selected": "Chosen for draft iterations and safer low-VRAM local runs.",
        "tradeoffs": "Fastest usable local preview, but less detail and temporal consistency.",
        "risk_level": "low",
    },
    "debug": {
        "label": "Debug",
        "why_selected": "Chosen to prove the pipeline before spending time on a full WAN render.",
        "tradeoffs": "Not representative of final visual quality.",
        "risk_level": "low",
    },
}


def _parse_stamp(value: Any) -> Optional[float]:
    if not value:
        return None
    try:
        return time.mktime(time.strptime(str(value), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"about {hours}h {minutes}m"
    if minutes:
        return f"about {minutes}m {secs}s"
    return f"about {secs}s"


def apply_comfy_ws_message(job: Dict[str, Any], message: Dict[str, Any]) -> bool:
    """Apply one ComfyUI websocket event to a web job record."""
    data = message.get("data") if isinstance(message.get("data"), dict) else {}
    metadata = job.setdefault("metadata", {})
    expected_prompt = str(metadata.get("comfy_prompt_id") or "")
    prompt_id = str(data.get("prompt_id") or message.get("prompt_id") or "")
    if expected_prompt and prompt_id and prompt_id != expected_prompt:
        return False

    event_type = str(message.get("type") or "").lower()
    if event_type == "progress":
        try:
            value = float(data.get("value", 0))
            total = float(data.get("max", 0))
        except (TypeError, ValueError):
            return False
        if total <= 0:
            return False
        inner_pct = max(0.0, min(100.0, (value / total) * 100.0))
        whole_pct = 18.0 + inner_pct * 0.42
        job["progress"] = max(float(job.get("progress") or 0.0), min(99.0, whole_pct))
        job["progress_mode"] = "comfy_ws"
        job["stage"] = "wan_sampling"
        job["stage_label"] = "Generating video"
        job["stage_detail"] = f"ComfyUI sampler step {int(value)} of {int(total)}."
        metadata["comfy_progress"] = {"value": int(value), "max": int(total), "percent": round(inner_pct, 1)}
        return True
    if event_type == "executing":
        node = data.get("node")
        if node:
            metadata["comfy_current_node"] = node
            job["stage"] = "wan_sampling"
            job["stage_label"] = "Generating video"
            job["stage_detail"] = f"ComfyUI is executing {node}."
            job["progress_mode"] = "comfy_ws"
            job["progress"] = max(float(job.get("progress") or 0.0), 18.0)
            return True
    if event_type == "executed":
        node = data.get("node")
        if node:
            metadata["comfy_last_node"] = node
            return True
    if event_type in {"execution_error", "execution_interrupted"}:
        job["stage"] = "error"
        job["stage_label"] = "ComfyUI error"
        job["stage_detail"] = str(data.get("exception_message") or data.get("node_type") or "ComfyUI execution stopped.")
        job["progress_mode"] = "comfy_ws"
        return True
    return False


def estimate_job_eta(metadata: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if history is None:
        from services.job_service import JobService

        history = JobService.get_history()
    target = (
        str(metadata.get("tier") or ""),
        str(metadata.get("profile") or ""),
        str(metadata.get("sprite_action") or metadata.get("action") or ""),
    )
    durations: List[float] = []
    for job in history:
        meta = job.get("metadata") or {}
        key = (
            str(meta.get("tier") or ""),
            str(meta.get("profile") or ""),
            str(meta.get("sprite_action") or meta.get("action") or ""),
        )
        if key != target:
            continue
        started = _parse_stamp(job.get("started_at"))
        finished = _parse_stamp(job.get("finished_at"))
        if started and finished and finished > started:
            durations.append(finished - started)
    if not durations:
        return {"seconds": None, "label": "learning from first run", "sample_count": 0}
    seconds = int(round(sum(durations) / len(durations)))
    return {"seconds": seconds, "label": _format_duration(seconds), "sample_count": len(durations)}


def update_job_timing(job: Dict[str, Any]) -> Dict[str, Any]:
    started = _parse_stamp(job.get("started_at"))
    now = time.time()
    elapsed = int(round(max(0.0, now - started))) if started else 0
    progress = max(0.0, min(100.0, float(job.get("progress") or 0.0)))
    metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
    eta = metadata.get("eta") if isinstance(metadata.get("eta"), dict) else {}
    total = eta.get("seconds")
    remaining = None
    if isinstance(total, (int, float)) and total > 0:
        remaining = max(0, int(round(float(total) - elapsed)))
        label = f"{_format_duration(remaining)} remaining"
    else:
        label = str(eta.get("label") or "learning from this run")
    job["elapsed_seconds"] = elapsed
    job["remaining_seconds"] = remaining
    job["eta_label"] = label
    job["progress_percent"] = round(progress, 1)
    return job


def summarize_qa_gates(report: Dict[str, Any]) -> Dict[str, Any]:
    issues = report.get("issues") or []
    errors = [i for i in issues if str(i.get("level", "")).lower() in {"error", "fail", "failed"}]
    warnings = [i for i in issues if str(i.get("level", "")).lower() in {"warn", "warning"}]
    if errors:
        status = "fail"
        chosen = errors
    elif warnings:
        status = "warning"
        chosen = warnings
    else:
        status = "pass"
        chosen = []
    reasons = [str(item.get("message") or item.get("code") or "Quality gate needs attention.") for item in chosen]
    if not reasons:
        reasons = ["No blocking QA issues found."]
    return {"status": status, "reasons": reasons, "score": report.get("score"), "issue_count": len(issues)}


def build_visual_report(sprite_dir: Path) -> Dict[str, Any]:
    from PIL import Image, ImageStat

    sprite_dir = Path(sprite_dir)
    report_dir = sprite_dir / "visual_report"
    report_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = sprite_dir / "frames_processed"
    frame_files = sorted(frames_dir.glob("*.png")) if frames_dir.exists() else []
    if not frame_files:
        sheet = sprite_dir / "sheet.png"
        frame_files = [sheet] if sheet.exists() else []
    thumbs = []
    best = {"index": 0, "path": "", "score": 0.0}
    for idx, path in enumerate(frame_files[:64]):
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")
            bbox = alpha.getbbox()
            coverage = 0.0
            if bbox:
                l, t, r, b = bbox
                coverage = ((r - l) * (b - t)) / max(1, rgba.width * rgba.height)
            contrast = sum(ImageStat.Stat(rgba.convert("L")).stddev)
            score = float(coverage * 100.0 + contrast)
            if idx == 0 or score > best["score"]:
                best = {"index": idx, "path": str(path), "score": round(score, 2)}
            thumb = rgba.copy()
            thumb.thumbnail((128, 128))
            canvas = Image.new("RGB", (128, 128), (20, 24, 32))
            canvas.paste(thumb.convert("RGB"), ((128 - thumb.width) // 2, (128 - thumb.height) // 2), thumb)
            thumbs.append(canvas)
    cols = min(6, max(1, len(thumbs)))
    rows = max(1, int(math.ceil(len(thumbs) / cols)))
    sheet_img = Image.new("RGB", (cols * 128, rows * 128), (12, 16, 24))
    for idx, thumb in enumerate(thumbs):
        sheet_img.paste(thumb, ((idx % cols) * 128, (idx // cols) * 128))
    contact = report_dir / "contact_sheet.jpg"
    sheet_img.save(contact, quality=88)
    report = {
        "schema": "spriteforge_visual_report_v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "frame_count": len(frame_files),
        "best_frame": best,
        "contact_sheet": str(contact).replace("\\", "/"),
    }
    (report_dir / "visual_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def mark_review_decision(run_id: str, decision: str) -> Dict[str, Any]:
    from services.experiment_service import ExperimentService

    status = "reviewed"
    if decision == "star":
        ExperimentService.set_starred(run_id, True)
        status = "starred"
    elif decision == "reject":
        status = "rejected"
    with ExperimentService._lock:
        records = ExperimentService._load()
        for rec in records:
            if rec.get("id") == run_id:
                rec["review_status"] = status
                rec["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                ExperimentService._save(records)
                return rec
    raise KeyError(f"Experiment run {run_id} not found")


def restore_review_decision(run_id: str) -> Dict[str, Any]:
    from services.experiment_service import ExperimentService

    with ExperimentService._lock:
        records = ExperimentService._load()
        for rec in records:
            if rec.get("id") == run_id:
                rec["review_status"] = "reviewed"
                rec.pop("reviewed_at", None)
                ExperimentService._save(records)
                return rec
    raise KeyError(f"Experiment run {run_id} not found")


def rerun_similar_payload(run: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": "generate_sprite",
        "prompt": run.get("prompt") or "",
        "negative": run.get("negative") or "",
        "seed": -1,
        "tier": run.get("model_tier") or run.get("tier") or "wan22_5b",
        "profile": run.get("profile") or "auto",
        "sprite_action": run.get("sprite_action") or "idle",
        "direction": run.get("direction") or "right",
        "quality_check": True,
    }


def preflight_generation(
    payload: Dict[str, Any],
    *,
    models: Dict[str, Any],
    gpu: Dict[str, Any],
    disk: Dict[str, Any],
    comfy_running: bool,
) -> Dict[str, Any]:
    reasons: List[str] = []
    warnings: List[str] = []
    if payload.get("action") == "generate_sprite" and not comfy_running:
        reasons.append("ComfyUI is offline.")
    tier = str(payload.get("tier") or "")
    if tier == "wan22_5b" and not models.get("advanced_ok", models.get("ok", False)):
        reasons.append("Wan 2.2 5B model files are missing.")
    elif not models.get("ok", True):
        reasons.append("Required model files are missing.")
    free_gb = float(disk.get("free_gb") or 0)
    if free_gb < 5:
        reasons.append(f"Low disk space: {free_gb:.1f} GB free.")
    vram_gb = gpu.get("vram_gb")
    try:
        vram_val = float(vram_gb)
    except (TypeError, ValueError):
        vram_val = 0.0
    if tier == "wan22_5b" and vram_val and vram_val < 11:
        reasons.append(f"VRAM warning: Wan 2.2 5B is safer with 12 GB; detected {vram_val:.1f} GB.")
    status = "fail" if reasons else "warning" if warnings else "pass"
    return {"status": status, "reasons": reasons or warnings or ["Preflight checks look ready."], "warnings": warnings}


def safer_retry_payload(error_text: str, original: Dict[str, Any]) -> Dict[str, Any]:
    text = str(error_text or "").lower()
    payload = dict(original)
    if "out of memory" in text or "cuda" in text or "vram" in text:
        payload["action"] = "generate_sprite"
        payload["profile"] = "wan22_5b_debug" if "wan22" in str(payload.get("profile") or payload.get("tier") or "") else "debug"
        payload["cell_size"] = payload.get("cell_size") or "256x256"
        payload["quality_check"] = True
        return payload
    if "missing" in text and "model" in text:
        payload["action"] = "download_wan22" if "wan22" in str(payload.get("tier") or "") else "download_models"
        return payload
    if "comfyui" in text and ("offline" in text or "connection" in text or "refused" in text):
        return {"action": "launch_comfy"}
    payload["action"] = payload.get("action") or "generate_sprite"
    return payload


def explain_model_profile(tier: str, profile: str) -> Dict[str, Any]:
    info = PROFILE_EXPLAINERS.get(profile, {})
    return {
        "tier": tier,
        "profile": profile,
        "label": info.get("label", profile or tier or "Auto"),
        "why_selected": info.get("why_selected", "Selected from the current model tier, hardware, and quality goal."),
        "tradeoffs": info.get("tradeoffs", "Balanced defaults for the selected generation mode."),
        "risk_level": info.get("risk_level", "medium" if "wan22" in tier else "low"),
    }


def cleanup_suggestions(root: Path) -> List[Dict[str, Any]]:
    root = Path(root)
    suggestions: List[Dict[str, Any]] = []
    logs = root / "logs"
    if logs.exists():
        for item in logs.glob("*.log"):
            if item.name != "web_server.log":
                suggestions.append({"category": "Old Task Logs", "path": str(item), "size": item.stat().st_size})
    output = root / "output"
    if output.exists():
        for folder in output.iterdir():
            if folder.is_dir() and folder.name not in {"jobs", "packs", "temp"} and not (folder / "sheet.json").exists():
                size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
                suggestions.append({"category": "Failed / Incomplete Outputs", "path": str(folder), "size": size})
    return suggestions
