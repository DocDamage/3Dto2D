#!/usr/bin/env python3
"""Actionable QA advisor for SpriteForge sprite outputs."""
from __future__ import annotations

import shlex
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import load_json, save_json

FEEDBACK_FILE = "qa/qa_advisor_feedback.json"
VALID_FEEDBACK_DECISIONS = {"accepted", "rejected", "dismissed"}


def _first_report(sprite_dir: Path) -> Dict[str, Any]:
    for rel in ("qa/qa_report.json", "qa_report.json", "quality/quality_report.json", "quality_report.json"):
        path = sprite_dir / rel
        if path.exists():
            data = load_json(path, {})
            if isinstance(data, dict):
                return data
    return {}


def _metric(report: Dict[str, Any], *names: str, default: Optional[float] = None) -> Optional[float]:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else report
    for name in names:
        value = metrics.get(name) if isinstance(metrics, dict) else None
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
    return default


REPAIR_ACTIONS = {
    "loop_seam": {"id": "fix_seam", "label": "Fix Seam", "button_id": "labRepairSeamBtn"},
    "foot_drift": {"id": "stabilize_feet", "label": "Stabilize Feet", "button_id": "labRepairStabilizeBtn"},
    "flicker": {"id": "reduce_flicker", "label": "Reduce Flicker", "button_id": "labRepairFlickerBtn"},
    "alpha_halo": {"id": "clean_background", "label": "Clean BG", "button_id": "labRepairCleanBtn"},
    "duplicate_frames": {"id": "open_frame_editor", "label": "Open Frame Editor", "view": "frame_editor"},
    "empty_frames": {"id": "open_frame_editor", "label": "Open Frame Editor", "view": "frame_editor"},
}


def _command_tokens(command_hint: str) -> List[str]:
    hint = str(command_hint or "").strip()
    if not hint or hint.lower().startswith("open ") or " or " in hint:
        return []
    try:
        return shlex.split(hint)
    except ValueError:
        return hint.split()


def _repair_plan_id(code: str, mode: str, command_hint: str, action: str) -> str:
    payload = "|".join([str(code or ""), str(mode or ""), str(command_hint or ""), str(action or "")])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _risk_level(mode: str, code: str) -> str:
    if mode == "manual_review":
        return "low"
    if code in {"empty_frames", "duplicate_frames"}:
        return "medium"
    return "low" if mode == "open_editor" else "medium"


def _repair_plan(code: str, command_hint: str, action: str) -> Dict[str, Any]:
    repair = REPAIR_ACTIONS.get(code, {})
    mode = "manual_review"
    if repair.get("button_id"):
        mode = "ui_quick_repair"
    elif repair.get("view"):
        mode = "open_editor"
    elif command_hint and command_hint not in {"Run QA after repair to confirm the issue is gone.", "export-engine or Release packaging"}:
        mode = "cli_hint"
    tokens = _command_tokens(command_hint)
    plan_id = _repair_plan_id(code, mode, command_hint, action)
    return {
        "schema": "spriteforge.qa_repair_plan.v1",
        "id": plan_id,
        "code": code,
        "mode": mode,
        "risk_level": _risk_level(mode, code),
        "requires_backup": mode in {"ui_quick_repair", "cli_hint"},
        "label": repair.get("label") or action,
        "command_hint": command_hint,
        "command": {
            "executable": tokens[0] if tokens else "",
            "args": tokens[1:] if len(tokens) > 1 else [],
            "shell_required": False,
        },
        "ui_button_id": repair.get("button_id", ""),
        "target_view": repair.get("view", ""),
        "automation_ready": bool(repair.get("button_id") or repair.get("view")),
        "runbook": [
            "Create a backup or keep the source sprite folder unchanged.",
            action,
            "Re-run QA and compare the updated report before release.",
        ],
        "verification": {
            "action": "qa_report",
            "expected": "matching issue metric improves or disappears",
        },
        "follow_up": "Run QA again after applying the repair.",
    }


def _add_advice(rows: List[Dict[str, Any]], *, severity: str, code: str, title: str, reason: str, action: str, command_hint: str) -> None:
    rows.append({
        "severity": severity,
        "code": code,
        "title": title,
        "reason": reason,
        "action": action,
        "command_hint": command_hint,
        "repair_action": REPAIR_ACTIONS.get(code, {}),
        "repair_plan": _repair_plan(code, command_hint, action),
    })


def _feedback_path(sprite_dir: Path) -> Path:
    return Path(sprite_dir) / FEEDBACK_FILE


def load_advisor_feedback(sprite_dir: Path) -> Dict[str, Any]:
    data = load_json(_feedback_path(sprite_dir), {})
    if not isinstance(data, dict):
        data = {}
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    counts: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "").strip()
        decision = str(entry.get("decision") or "").strip()
        if not code or decision not in VALID_FEEDBACK_DECISIONS:
            continue
        counts.setdefault(code, {"accepted": 0, "rejected": 0, "dismissed": 0})
        counts[code][decision] += 1
    preferences: Dict[str, Dict[str, Any]] = {}
    for code, count in counts.items():
        accepted = count.get("accepted", 0)
        rejected = count.get("rejected", 0)
        dismissed = count.get("dismissed", 0)
        score = accepted - rejected - (dismissed * 0.25)
        if accepted > rejected:
            preference = "promote"
        elif rejected > accepted:
            preference = "deprioritize"
        else:
            preference = "neutral"
        preferences[code] = {
            "preference": preference,
            "score": score,
            "accepted": accepted,
            "rejected": rejected,
            "dismissed": dismissed,
        }
    return {"entries": entries, "counts": counts, "preferences": preferences}


def record_advisor_feedback(sprite_dir: Path, code: str, decision: str, note: str = "") -> Dict[str, Any]:
    clean_code = str(code or "").strip()
    clean_decision = str(decision or "").strip().lower()
    if not clean_code:
        raise ValueError("Advice code is required.")
    if clean_decision not in VALID_FEEDBACK_DECISIONS:
        raise ValueError(f"Decision must be one of: {', '.join(sorted(VALID_FEEDBACK_DECISIONS))}.")
    data = load_json(_feedback_path(sprite_dir), {})
    if not isinstance(data, dict):
        data = {}
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    entries.append({
        "code": clean_code,
        "decision": clean_decision,
        "note": str(note or "").strip(),
    })
    payload = {"schema": "spriteforge.qa_advisor_feedback.v1", "entries": entries}
    save_json(_feedback_path(sprite_dir), payload)
    feedback = load_advisor_feedback(sprite_dir)
    return {"ok": True, "feedback": feedback}


def advise_sprite_quality(sprite_dir: Path, report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build prioritized repair guidance from existing QA metrics."""
    sprite_dir = Path(sprite_dir)
    report = report if report is not None else _first_report(sprite_dir)
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else report
    score = report.get("score")
    suggestions = list(report.get("suggestions") or [])
    issues = list(report.get("issues") or [])
    advice: List[Dict[str, Any]] = []

    loop = _metric(report, "loop_seam_rmse", "loop_diff", "loop_seam_diff")
    foot = _metric(report, "foot_y_stdev_px", "bottom_jitter_px")
    center = _metric(report, "center_x_stdev_px", "center_jitter_px")
    flicker = _metric(report, "brightness_stdev", "color_drift")
    alpha_clean = _metric(report, "alpha_cleanliness", "mean_edge_alpha_ratio")
    duplicate_ratio = _metric(report, "duplicate_ratio")
    empty_frames = _metric(report, "empty_frames", default=0.0)

    if loop is not None and loop > 15:
        _add_advice(
            advice,
            severity="high" if loop > 30 else "medium",
            code="loop_seam",
            title="Loop seam may pop",
            reason=f"Loop seam metric is {loop:.2f}, above the usual 15px comfort zone.",
            action="Blend loop frames, drop duplicate endpoints, or regenerate with an explicit seamless loop prompt.",
            command_hint="autofix-sprite --drop-loop-duplicate --blend-loop-frames 3",
        )
    if foot is not None and foot > 2:
        _add_advice(
            advice,
            severity="high" if foot > 5 else "medium",
            code="foot_drift",
            title="Foot anchor is drifting",
            reason=f"Foot drift is {foot:.2f}px stdev, which can make grounded animations slide.",
            action="Run anchor stabilization and prefer bottom-center anchoring on reconversion.",
            command_hint="autofix-sprite --stabilize-anchor",
        )
    if center is not None and center > 8:
        _add_advice(
            advice,
            severity="medium",
            code="center_drift",
            title="Character center is wandering",
            reason=f"Center drift is {center:.2f}px stdev.",
            action="Use locked-camera prompt wording, global crop, and simpler motion.",
            command_hint="generate-sprite --extra-prompt \"locked camera, no pan, stable centered character\"",
        )
    if flicker is not None and flicker > 1:
        _add_advice(
            advice,
            severity="medium",
            code="flicker",
            title="Lighting or color flicker detected",
            reason=f"Flicker metric is {flicker:.2f}.",
            action="Apply deflicker/temporal smoothing and lock lighting in the prompt.",
            command_hint="autofix-sprite --deflicker",
        )
    if alpha_clean is not None and alpha_clean > 0.05:
        _add_advice(
            advice,
            severity="medium",
            code="alpha_halo",
            title="Alpha edge cleanup recommended",
            reason=f"Alpha cleanliness metric is {alpha_clean:.4f}.",
            action="Solidify transparent RGB and inspect against dark/light backgrounds.",
            command_hint="autofix-sprite --solidify 2",
        )
    if duplicate_ratio is not None and duplicate_ratio > 0.25:
        _add_advice(
            advice,
            severity="low",
            code="duplicate_frames",
            title="Many frames may be duplicates",
            reason=f"Duplicate ratio is {duplicate_ratio:.2f}.",
            action="Trim held frames or lower the export FPS.",
            command_hint="repair-sprite --drop-duplicates",
        )
    if empty_frames and empty_frames > 0:
        _add_advice(
            advice,
            severity="high",
            code="empty_frames",
            title="Empty frames found",
            reason=f"{int(empty_frames)} empty or near-empty frame(s) were detected.",
            action="Review chroma key/background removal and delete bad frames before repacking.",
            command_hint="Open Frame Editor, delete empty frames, then Re-pack",
        )

    for issue in issues:
        code = str(issue.get("code") or issue.get("type") or "").strip()
        message = str(issue.get("message") or issue.get("detail") or "").strip()
        if code and not any(row["code"] == code for row in advice):
            _add_advice(
                advice,
                severity=str(issue.get("severity") or "medium"),
                code=code,
                title=code.replace("_", " ").title(),
                reason=message or "QA report flagged this issue.",
                action="Review the frame sequence and apply the matching quick repair.",
                command_hint="Run QA after repair to confirm the issue is gone.",
            )

    if not advice:
        _add_advice(
            advice,
            severity="good",
            code="ready",
            title="Sprite looks production-ready",
            reason="No major QA advisor triggers were found.",
            action="Export to your engine and test at the target in-game scale.",
            command_hint="export-engine or Release packaging",
        )

    feedback = load_advisor_feedback(sprite_dir)
    for row in advice:
        row["feedback"] = feedback["counts"].get(row["code"], {"accepted": 0, "rejected": 0, "dismissed": 0})
        learned = feedback["preferences"].get(row["code"], {
            "preference": "neutral",
            "score": 0,
            "accepted": 0,
            "rejected": 0,
            "dismissed": 0,
        })
        row["learned_preference"] = learned
        if learned["preference"] == "promote":
            row["title"] = f"{row['title']} (previously accepted)"
        elif learned["preference"] == "deprioritize":
            row["severity"] = "low" if row["severity"] != "good" else row["severity"]

    severity_rank = {"high": 0, "medium": 1, "low": 2, "good": 3}
    advice.sort(key=lambda row: (
        -float(row.get("learned_preference", {}).get("score", 0)),
        severity_rank.get(str(row.get("severity") or "medium"), 1),
    ))

    return {
        "ok": True,
        "sprite_dir": str(sprite_dir),
        "score": score,
        "metrics": metrics if isinstance(metrics, dict) else {},
        "advice": advice,
        "suggestions": suggestions,
        "next_best_action": advice[0],
        "report_found": bool(report),
        "feedback": feedback,
        "learning_summary": {
            "feedback_count": len(feedback["entries"]),
            "learned_codes": len(feedback["preferences"]),
            "promoted_codes": [
                code for code, pref in feedback["preferences"].items()
                if pref["preference"] == "promote"
            ],
            "deprioritized_codes": [
                code for code, pref in feedback["preferences"].items()
                if pref["preference"] == "deprioritize"
            ],
        },
    }
