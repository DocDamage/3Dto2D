#!/usr/bin/env python3
"""Shared test fixtures and configuration for the SpriteForge test suite."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, Sequence

import pytest
from PIL import Image


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory(prefix="sf_test_") as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_output_dir(temp_dir: Path) -> Path:
    """Create a temporary output directory inside the temp dir."""
    out = temp_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def sample_sheet_json() -> Dict[str, Any]:
    """Return a sample sheet.json for testing."""
    return {
        "image": "sheet.png",
        "animation": "test_idle",
        "frame_width": 256,
        "frame_height": 256,
        "frame_count": 8,
        "fps": 12.0,
        "columns": 4,
        "rows": 2,
        "spacing": 2,
        "margin": 4,
        "anchor": "bottom-center",
        "frames": [
            {
                "index": i,
                "name": f"test_idle_{i:04d}",
                "source_name": f"frame_{i:04d}.png",
                "source_index": i,
                "x": (i % 4) * 258,
                "y": (i // 4) * 258,
                "w": 256,
                "h": 256,
                "duration_ms": 83,
            }
            for i in range(8)
        ],
        "extra": {
            "qa": {
                "overall_score": 85.0,
                "loop_rmse": 5.2,
                "foot_drift": 0.8,
                "center_drift": 2.1,
                "flicker_score": 92.0,
                "duplicate_ratio": 0.0,
            }
        },
    }


@pytest.fixture
def sample_sprite_dir(temp_dir: Path, sample_sheet_json: Dict[str, Any]) -> Path:
    """Create a temporary sprite output directory with a sheet.json."""
    sprite_dir = temp_dir / "output" / "test_sprite_idle_right"
    sprite_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = sprite_dir / "sheet.json"
    sheet_path.write_text(json.dumps(sample_sheet_json, indent=2), encoding="utf-8")
    return sprite_dir


@pytest.fixture
def sample_qa_report() -> Dict[str, Any]:
    """Return a sample QA report dictionary."""
    return {
        "overall_score": 82.5,
        "loop_rmse": 8.3,
        "foot_drift": 1.2,
        "center_drift": 3.5,
        "flicker_score": 88.0,
        "duplicate_ratio": 0.05,
        "chroma_fidelity": 95.0,
        "passed_gates": {
            "loop_rmse": True,
            "foot_drift": True,
            "center_drift": True,
        },
        "warnings": [],
        "recommendations": [],
    }


@pytest.fixture
def sample_sprite_sprite_dir(temp_dir: Path, sample_sheet_json: Dict[str, Any], sample_qa_report: Dict[str, Any]) -> Path:
    """Create a temporary sprite directory with both sheet.json and qa_report.json."""
    sprite_dir = temp_dir / "output" / "test_hero_walk_right"
    sprite_dir.mkdir(parents=True, exist_ok=True)
    (sprite_dir / "sheet.json").write_text(
        json.dumps(sample_sheet_json, indent=2), encoding="utf-8"
    )
    # Add qa_report
    qa_data = dict(sample_sheet_json)
    qa_data["extra"]["qa"] = sample_qa_report
    (sprite_dir / "qa_report.json").write_text(
        json.dumps(sample_qa_report, indent=2), encoding="utf-8"
    )
    return sprite_dir


@pytest.fixture
def sample_prompt() -> str:
    """Return a sample WAN generation prompt."""
    return "single full body knight, locked camera, idle breathing animation, plain bright green chroma key background, game sprite, cel shaded, clean silhouette, 512x512"


@pytest.fixture
def sample_negative_prompt() -> str:
    """Return a sample negative prompt."""
    return "camera movement, zoom, cuts, rotation, bad anatomy, extra limbs, text, watermark, blur, distorted"


@pytest.fixture
def clean_config_dir(temp_dir: Path) -> Path:
    """Create a clean config directory with a minimal config."""
    config_dir = temp_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def experiment_dir(temp_dir: Path) -> Path:
    """Create an experiment history directory."""
    exp_dir = temp_dir / "output" / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    return exp_dir


@pytest.fixture
def sample_sprite_dirs(temp_dir: Path) -> list[Path]:
    """Create multiple sample sprite output directories."""
    out = temp_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    dirs = []
    for i, name in enumerate(["hero_idle_right", "hero_walk_right", "hero_attack_right"]):
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        sheet = {
            "image": "sheet.png",
            "animation": name,
            "frame_width": 256,
            "frame_height": 256,
            "frame_count": 8,
            "fps": 12.0,
            "columns": 4,
            "rows": 2,
            "extra": {
                "qa": {
                    "overall_score": 80.0 + i * 5,
                    "loop_rmse": 5.0 + i,
                }
            },
            "frames": [],
        }
        (d / "sheet.json").write_text(json.dumps(sheet, indent=2), encoding="utf-8")
        dirs.append(d)
    return dirs


@pytest.fixture
def synthetic_rgba_frames() -> Callable[..., list[Image.Image]]:
    """Factory for deterministic RGBA frame sequences."""
    def make_frames(
        *,
        size: tuple[int, int] = (16, 16),
        colors: Sequence[tuple[int, int, int, int]] | None = None,
    ) -> list[Image.Image]:
        palette = colors or [
            (220, 40, 40, 255),
            (40, 220, 40, 255),
            (40, 40, 220, 255),
        ]
        return [Image.new("RGBA", size, color) for color in palette]
    return make_frames


@pytest.fixture
def synthetic_frame_items(synthetic_rgba_frames: Callable[..., list[Image.Image]]) -> Callable[..., list[Any]]:
    """Factory for services.sprite_video_loader.FrameItem sequences."""
    def make_items(
        *,
        size: tuple[int, int] = (16, 16),
        colors: Sequence[tuple[int, int, int, int]] | None = None,
        prefix: str = "frame",
    ) -> list[Any]:
        from services.sprite_video_loader import FrameItem

        return [
            FrameItem(image=img, name=f"{prefix}_{idx:04d}", source_index=idx)
            for idx, img in enumerate(synthetic_rgba_frames(size=size, colors=colors))
        ]
    return make_items


@pytest.fixture
def mock_comfy_system_stats(monkeypatch) -> Dict[str, int]:
    """Mock ComfyUI /system_stats responses and count health-check calls."""
    calls = {"count": 0}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(_url, timeout):
        calls["count"] += 1
        return FakeResponse()

    monkeypatch.setattr("services.comfy_service.urllib.request.urlopen", fake_urlopen)
    return calls


@pytest.fixture
def synthetic_sprite_factory(tmp_path: Path) -> Callable[..., Path]:
    """Create a complete SpriteForge-like output folder with frames and sheet metadata."""
    def make_sprite(
        name: str = "hero_idle",
        *,
        root: Path | None = None,
        size: tuple[int, int] = (16, 16),
        colors: Sequence[tuple[int, int, int, int]] | None = None,
        fps: float = 12.0,
        animation: str = "idle",
        action: str | None = None,
        direction: str | None = None,
        durations_ms: Sequence[int] | None = None,
        frame_names: Sequence[str] | None = None,
        qa_report: Dict[str, Any] | None = None,
    ) -> Path:
        sprite_dir = (root or tmp_path) / name
        sprite_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = sprite_dir / "frames_processed"
        frames_dir.mkdir(parents=True, exist_ok=True)
        palette = colors or [
            (220, 40, 40, 255),
            (40, 220, 40, 255),
            (40, 40, 220, 255),
        ]
        width, height = size
        sheet = Image.new("RGBA", (width * len(palette), height), (0, 0, 0, 0))
        frames = []
        for idx, color in enumerate(palette):
            frame = Image.new("RGBA", size, color)
            frame.save(frames_dir / f"frame_{idx:04d}.png")
            sheet.alpha_composite(frame, (idx * width, 0))
            duration = int(durations_ms[idx]) if durations_ms and idx < len(durations_ms) else int(round(1000 / fps)) if fps else 0
            frame_name = str(frame_names[idx]) if frame_names and idx < len(frame_names) else f"{animation}_{idx:04d}"
            frames.append({
                "index": idx,
                "name": frame_name,
                "source_name": f"frame_{idx:04d}.png",
                "source_index": idx,
                "x": idx * width,
                "y": 0,
                "w": width,
                "h": height,
                "duration_ms": duration,
                "action": action or animation,
                "direction": direction or "right",
            })
        sheet.save(sprite_dir / "sheet.png")
        meta = {
            "image": "sheet.png",
            "animation": animation,
            "action": action or animation,
            "direction": direction or "right",
            "frame_width": width,
            "frame_height": height,
            "frame_count": len(palette),
            "fps": fps,
            "columns": len(palette),
            "rows": 1,
            "spacing": 0,
            "margin": 0,
            "frames": frames,
            "frame_durations_ms": [frame["duration_ms"] for frame in frames],
        }
        (sprite_dir / "sheet.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if qa_report is not None:
            qa_dir = sprite_dir / "qa"
            qa_dir.mkdir(exist_ok=True)
            (qa_dir / "qa_report.json").write_text(json.dumps(qa_report, indent=2), encoding="utf-8")
        return sprite_dir
    return make_sprite


@pytest.fixture(autouse=True)
def mock_root_in_app_dir(monkeypatch):
    """Ensure ROOT references the app directory during tests."""
    import app.spriteforge_utils as utils
    # Don't override - just ensure tests can import
    pass
