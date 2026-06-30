import json
import sys
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.qa_threshold_service import resolve_qa_thresholds, threshold_cli_args, thresholds_for_preset


def test_named_preset_thresholds():
    thresholds = thresholds_for_preset(APP, "Animated Water Tile")

    assert thresholds["loop_rmse_threshold"] == 10.0
    assert thresholds["foot_drift_threshold"] == 999.0
    assert thresholds["center_drift_threshold"] == 999.0


def test_project_quality_gates_override_preset_thresholds(tmp_path):
    project = tmp_path / "projects" / "Hero"
    sprite_dir = project / "sprites" / "hero_walk"
    sprite_dir.mkdir(parents=True)
    (project / "spriteforge_project.json").write_text(
        json.dumps(
            {
                "preset": "Top-Down RPG Character",
                "quality_gates": {
                    "loop_seam_threshold": 12.5,
                    "max_foot_drift": 4.0,
                    "max_center_drift": 6.0,
                },
            }
        ),
        encoding="utf-8",
    )

    thresholds = resolve_qa_thresholds(tmp_path, sprite_dir)

    assert thresholds == {
        "loop_rmse_threshold": 12.5,
        "foot_drift_threshold": 4.0,
        "center_drift_threshold": 6.0,
    }


def test_threshold_cli_args_are_qc_report_flags():
    args = threshold_cli_args({"loop_rmse_threshold": 1.0, "foot_drift_threshold": 2.0, "center_drift_threshold": 3.0})

    assert args == [
        "--loop-rmse-threshold",
        "1.0",
        "--foot-drift-threshold",
        "2.0",
        "--center-drift-threshold",
        "3.0",
    ]


def test_unified_qa_report_forwards_resolved_thresholds(monkeypatch, tmp_path):
    import spriteforge_unified

    captured = {}
    monkeypatch.setattr(spriteforge_unified, "ROOT", tmp_path)
    monkeypatch.setattr(spriteforge_unified, "run", lambda cmd: captured.setdefault("cmd", cmd))
    sprite_dir = tmp_path / "output" / "hero"
    sprite_dir.mkdir(parents=True)

    spriteforge_unified.cmd_qa_report(
        Namespace(
            input=str(sprite_dir),
            output=None,
            duplicate_threshold=1.25,
            qa_preset="Classic Platformer (Side-Scroller)",
            loop_rmse_threshold=None,
            foot_drift_threshold=1.5,
            center_drift_threshold=None,
        )
    )

    cmd = captured["cmd"]
    assert "--loop-rmse-threshold" in cmd
    assert cmd[cmd.index("--loop-rmse-threshold") + 1] == "15.0"
    assert cmd[cmd.index("--foot-drift-threshold") + 1] == "1.5"
    assert cmd[cmd.index("--center-drift-threshold") + 1] == "5.0"
