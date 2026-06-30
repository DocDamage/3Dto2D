"""Example SpriteForge plugin: add a tiny custom QA metric.

Drop Python files like this one into app/plugins/. SpriteForge loads them
automatically and calls hook functions when matching pipeline events happen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def on_qa_check(sprite_dir: Path, report: Dict[str, Any]) -> None:
    """Add a lightweight frame-count hint to the QA report in memory."""
    sprite_path = Path(sprite_dir)
    frame_dir = sprite_path / "frames_processed"
    frames = sorted(frame_dir.glob("frame_*.png")) if frame_dir.is_dir() else []
    plugin_metrics = report.setdefault("plugin_metrics", {})
    plugin_metrics["example_quality_metric"] = {
        "label": "Processed frame files",
        "value": len(frames),
        "ok": len(frames) > 0,
    }


def on_export_engine(sprite_dir: Path, engine: str, dest: Path) -> None:
    """Record where an engine export was written without changing assets."""
    notes = Path(dest) / "plugin_example_export_note.txt"
    notes.write_text(
        f"Example plugin observed export for {Path(sprite_dir).name} to {engine}.\n",
        encoding="utf-8",
    )
