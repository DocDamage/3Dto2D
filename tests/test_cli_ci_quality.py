import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent


def _write_sprite_output(path: Path, include_qa_score: bool = True) -> None:
    path.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(path / "sheet.png")
    payload = {
        "image": "sheet.png",
        "frame_width": 16,
        "frame_height": 16,
        "frame_count": 1,
        "columns": 1,
        "rows": 1,
        "fps": 12,
        "animation": "idle",
    }
    if include_qa_score:
        payload["extra"] = {"qa": {"overall_score": 92}}
    (path / "sheet.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_ci_check_cli_writes_json_and_junit(tmp_path):
    _write_sprite_output(tmp_path / "hero_idle")
    json_out = tmp_path / "ci.json"
    junit_out = tmp_path / "ci.xml"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "app" / "spriteforge_unified.py"),
            "ci-check",
            "--root",
            str(tmp_path),
            "--fail-under",
            "70",
            "--json",
            str(json_out),
            "--junit-xml",
            str(junit_out),
            "--quiet",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json_out.exists()
    assert junit_out.exists()
    assert json.loads(json_out.read_text(encoding="utf-8"))["passed"] == 1


def test_quality_batch_cli_writes_junit(tmp_path):
    _write_sprite_output(tmp_path / "hero_idle")
    out_dir = tmp_path / "quality_batch"
    junit_out = tmp_path / "quality.xml"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "app" / "spriteforge_unified.py"),
            "quality-batch",
            "--root",
            str(tmp_path),
            "--output",
            str(out_dir),
            "--fail-under",
            "0",
            "--junit-xml",
            str(junit_out),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (out_dir / "batch_quality.json").exists()
    assert junit_out.exists()


def test_ci_check_computes_missing_quality_sidecar(tmp_path):
    from services.ci_check_service import ci_check_directory

    _write_sprite_output(tmp_path / "hero_idle", include_qa_score=False)

    summary = ci_check_directory(tmp_path, fail_under=0)

    assert summary["total"] == 1
    assert summary["results"][0]["qa_source"] == "computed"
    assert (tmp_path / "hero_idle" / "quality" / "quality_report.json").exists()


def test_ci_check_skips_quarantined_sprite_output(tmp_path):
    from services.ci_check_service import ci_check_directory

    sprite_dir = tmp_path / "bad_take"
    _write_sprite_output(sprite_dir)
    (sprite_dir / ".spriteforge_ci_ignore").write_text("Rejected take; fixed copy supersedes it.\n", encoding="utf-8")

    summary = ci_check_directory(tmp_path, fail_under=99)

    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert summary["all_passed"] is True
    assert summary["results"][0]["status"] == "skipped"


def test_ci_check_ignores_engine_export_subfolders(tmp_path):
    from services.ci_check_service import ci_check_directory

    sprite_dir = tmp_path / "hero_idle"
    _write_sprite_output(sprite_dir)
    export_dir = sprite_dir / "godot_export"
    _write_sprite_output(export_dir)

    summary = ci_check_directory(tmp_path, fail_under=70)

    assert summary["total"] == 1
    assert summary["results"][0]["name"] == "hero_idle"


def test_release_gate_reads_nested_quality_report(tmp_path):
    from services.final_service import check_release_quality_gates, sprite_record

    sprite_dir = tmp_path / "hero_idle"
    _write_sprite_output(sprite_dir, include_qa_score=False)
    qa_dir = sprite_dir / "qa"
    qa_dir.mkdir()
    (qa_dir / "qa_report.json").write_text(
        json.dumps({"metrics": {"frame_count": 1, "foot_y_stdev_px": 0, "brightness_stdev": 0.1}}),
        encoding="utf-8",
    )
    quality_dir = sprite_dir / "quality"
    quality_dir.mkdir()
    (quality_dir / "quality_report.json").write_text(
        json.dumps(
            {
                "score": 88,
                "frame_count": 1,
                "bottom_jitter_px": 0,
                "color_drift": 0.02,
                "empty_frames": 0,
            }
        ),
        encoding="utf-8",
    )
    godot_dir = sprite_dir / "godot_export"
    godot_dir.mkdir()
    (godot_dir / "hero_idle.gd").write_text("extends Node2D\n", encoding="utf-8")

    gate = check_release_quality_gates([sprite_dir])

    assert gate["ok"] is True
    assert not any("Missing QA report" in warning for warning in gate["warnings"])
    assert sprite_record(sprite_dir)["qa_score"] == 88
