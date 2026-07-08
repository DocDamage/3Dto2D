from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from spriteforge_utils import ROOT

logger = logging.getLogger(__name__)


def _safe_run_dir(root: Path, value: str) -> Path:
    raw = Path(str(value or ""))
    path = raw if raw.is_absolute() else root / raw
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Training run path must stay inside the SpriteForge workspace.") from exc
    if not resolved.is_dir():
        raise ValueError(f"Training run folder not found: {value}")
    return resolved


def _rel_url(root: Path, path: Path) -> str:
    return "/file/" + path.resolve().relative_to(root.resolve()).as_posix()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _loss_points(run_dir: Path) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for path in [run_dir / "loss.csv", run_dir / "logs" / "loss.csv"]:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
            for row in csv.DictReader(fh):
                step = _int(row.get("step") or row.get("global_step") or row.get("iteration"))
                loss = _float(row.get("loss") or row.get("train_loss") or row.get("loss/current"))
                if step is not None and loss is not None:
                    points.append({"step": step, "loss": loss})
        if points:
            return points[-500:]

    for path in [run_dir / "loss.jsonl", run_dir / "logs" / "loss.jsonl", run_dir / "trainer_state.jsonl"]:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.debug("Skipping invalid LoRA loss JSONL row in %s: %s", path, exc)
                continue
            step = _int(row.get("step") or row.get("global_step") or row.get("iteration"))
            loss = _float(row.get("loss") or row.get("train_loss"))
            if step is not None and loss is not None:
                points.append({"step": step, "loss": loss})
        if points:
            return points[-500:]
    return points


def _sample_images(root: Path, run_dir: Path) -> List[Dict[str, Any]]:
    candidates: List[Path] = []
    for folder in [run_dir / "samples", run_dir / "sample", run_dir]:
        if folder.exists():
            candidates.extend(sorted(folder.glob("*.png")))
            candidates.extend(sorted(folder.glob("*.jpg")))
            candidates.extend(sorted(folder.glob("*.webp")))
    rows = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        rows.append({"name": path.name, "path": resolved.relative_to(root.resolve()).as_posix(), "url": _rel_url(root, resolved)})
    return rows[-24:]


def _checkpoints(root: Path, run_dir: Path) -> List[Dict[str, Any]]:
    rows = []
    checkpoint_paths = []
    for suffix in ("*.safetensors", "*.pt", "*.ckpt"):
        checkpoint_paths.extend(sorted(run_dir.glob(suffix)))
    for path in sorted(checkpoint_paths, key=lambda item: item.stat().st_mtime):
        rows.append({
            "name": path.name,
            "path": path.resolve().relative_to(root.resolve()).as_posix(),
            "size_bytes": path.stat().st_size,
        })
    return rows[-24:]


def summarize_lora_training_progress(run_path: str, root: Path = ROOT) -> Dict[str, Any]:
    run_dir = _safe_run_dir(root, run_path)
    manifest_path = run_dir / "training_run.json"
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    losses = _loss_points(run_dir)
    last_loss = losses[-1]["loss"] if losses else None
    max_steps = _int(manifest.get("max_train_steps")) or _int(manifest.get("steps")) or None
    current_step = losses[-1]["step"] if losses else 0
    progress = round((current_step / max_steps) * 100.0, 1) if max_steps else None
    return {
        "ok": True,
        "run_path": run_dir.relative_to(root.resolve()).as_posix(),
        "manifest": manifest,
        "loss_points": losses,
        "last_loss": last_loss,
        "current_step": current_step,
        "max_steps": max_steps,
        "progress": progress,
        "samples": _sample_images(root, run_dir),
        "checkpoints": _checkpoints(root, run_dir),
    }
