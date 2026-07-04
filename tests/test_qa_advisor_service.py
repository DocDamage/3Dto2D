import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_qa_advisor_learns_from_feedback_decisions(tmp_path):
    from services.qa_advisor_service import advise_sprite_quality, record_advisor_feedback

    sprite_dir = tmp_path / "sprite"
    qa_dir = sprite_dir / "qa"
    qa_dir.mkdir(parents=True)
    (qa_dir / "qa_report.json").write_text(json.dumps({
        "score": 72,
        "metrics": {
            "loop_seam_rmse": 22,
            "foot_y_stdev_px": 4,
        },
    }), encoding="utf-8")

    record_advisor_feedback(sprite_dir, "foot_drift", "accepted")
    record_advisor_feedback(sprite_dir, "foot_drift", "accepted")
    record_advisor_feedback(sprite_dir, "loop_seam", "rejected")

    result = advise_sprite_quality(sprite_dir)

    assert result["learning_summary"]["feedback_count"] == 3
    assert "foot_drift" in result["learning_summary"]["promoted_codes"]
    assert "loop_seam" in result["learning_summary"]["deprioritized_codes"]
    assert result["next_best_action"]["code"] == "foot_drift"
    foot = next(row for row in result["advice"] if row["code"] == "foot_drift")
    loop = next(row for row in result["advice"] if row["code"] == "loop_seam")
    assert foot["learned_preference"]["preference"] == "promote"
    assert loop["learned_preference"]["preference"] == "deprioritize"


def test_qa_advisor_rejects_unknown_feedback_decision(tmp_path):
    from services.qa_advisor_service import record_advisor_feedback

    try:
        record_advisor_feedback(tmp_path, "loop_seam", "maybe")
    except ValueError as exc:
        assert "Decision must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid decision to be rejected")
