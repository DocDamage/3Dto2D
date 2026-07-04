from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.web_helpers_cmd import build_action_command


def test_tile_training_dataset_action_builds_autotile_command() -> None:
    title, cmd = build_action_command({
        "action": "tile_training_dataset",
        "source_dir": r"G:\Stage Assets",
        "trigger": "sakpix_tiles",
        "cell_size": "auto",
        "max_samples_per_source": "24",
    })

    assert title == "Build auto-tile training dataset"
    assert "spriteforge_unified.py" in cmd
    assert "autotile-dataset" in cmd
    assert "--source" in cmd
    assert r"G:\Stage Assets" in cmd
    assert "--max-samples-per-source" in cmd
    assert "24" in cmd


def test_tile_training_dataset_action_requires_source() -> None:
    try:
        build_action_command({"action": "tile_training_dataset"})
    except ValueError as exc:
        assert "No tile-set source folder selected" in str(exc)
    else:
        raise AssertionError("Expected missing source to raise ValueError")
