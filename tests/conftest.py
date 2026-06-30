#!/usr/bin/env python3
"""Shared test fixtures and configuration for the SpriteForge test suite."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest


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


@pytest.fixture(autouse=True)
def mock_root_in_app_dir(monkeypatch):
    """Ensure ROOT references the app directory during tests."""
    import app.spriteforge_utils as utils
    # Don't override - just ensure tests can import
    pass