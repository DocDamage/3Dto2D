import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
WEB = APP / "web"


def test_qa_advisor_prioritizes_loop_and_foot_drift(tmp_path):
    from services.qa_advisor_service import advise_sprite_quality

    sprite_dir = tmp_path / "sprite"
    qa_dir = sprite_dir / "qa"
    qa_dir.mkdir(parents=True)
    (qa_dir / "qa_report.json").write_text(json.dumps({
        "score": 62.5,
        "metrics": {
            "loop_seam_rmse": 33.0,
            "foot_y_stdev_px": 4.2,
            "brightness_stdev": 1.8,
        },
        "suggestions": ["Existing suggestion"],
    }), encoding="utf-8")

    data = advise_sprite_quality(sprite_dir)

    assert data["ok"] is True
    assert data["score"] == 62.5
    assert data["next_best_action"]["code"] == "loop_seam"
    assert data["next_best_action"]["repair_action"]["button_id"] == "labRepairSeamBtn"
    assert data["next_best_action"]["repair_plan"]["schema"] == "spriteforge.qa_repair_plan.v1"
    assert len(data["next_best_action"]["repair_plan"]["id"]) == 16
    assert data["next_best_action"]["repair_plan"]["mode"] == "ui_quick_repair"
    assert data["next_best_action"]["repair_plan"]["automation_ready"] is True
    assert data["next_best_action"]["repair_plan"]["risk_level"] == "medium"
    assert data["next_best_action"]["repair_plan"]["requires_backup"] is True
    assert data["next_best_action"]["repair_plan"]["command"]["executable"] == "autofix-sprite"
    assert "--drop-loop-duplicate" in data["next_best_action"]["repair_plan"]["command"]["args"]
    assert data["next_best_action"]["repair_plan"]["verification"]["action"] == "qa_report"
    assert len(data["next_best_action"]["repair_plan"]["runbook"]) == 3
    assert {row["code"] for row in data["advice"]} >= {"loop_seam", "foot_drift", "flicker"}
    assert data["suggestions"] == ["Existing suggestion"]


def test_qa_advisor_ready_when_no_major_triggers(tmp_path):
    from services.qa_advisor_service import advise_sprite_quality

    data = advise_sprite_quality(tmp_path / "sprite", report={"score": 94, "metrics": {"loop_seam_rmse": 4, "foot_y_stdev_px": 0.4}})

    assert data["next_best_action"]["code"] == "ready"
    assert data["next_best_action"]["severity"] == "good"


def test_qa_advisor_records_feedback_counts(tmp_path):
    from services.qa_advisor_service import advise_sprite_quality, record_advisor_feedback

    sprite_dir = tmp_path / "sprite"
    sprite_dir.mkdir()

    record_advisor_feedback(sprite_dir, "loop_seam", "accepted", "worked")
    record_advisor_feedback(sprite_dir, "loop_seam", "rejected")
    data = advise_sprite_quality(sprite_dir, report={"score": 55, "metrics": {"loop_seam_rmse": 33}})

    feedback = data["advice"][0]["feedback"]
    assert feedback["accepted"] == 1
    assert feedback["rejected"] == 1
    assert data["feedback"]["entries"][0]["note"] == "worked"


def test_qa_advisor_api(tmp_path, monkeypatch):
    from spriteforge_web import app
    import web_helpers as web_mod

    sprite_dir = tmp_path / "output" / "hero"
    qa_dir = sprite_dir / "qa"
    qa_dir.mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text("{}", encoding="utf-8")
    (qa_dir / "qa_report.json").write_text(json.dumps({
        "score": 70,
        "metrics": {"alpha_cleanliness": 0.08},
    }), encoding="utf-8")
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/qa/advisor?path=output/hero")

    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["advice"][0]["code"] == "alpha_halo"


def test_qa_advisor_feedback_api(tmp_path, monkeypatch):
    from spriteforge_web import app
    import web_helpers as web_mod

    sprite_dir = tmp_path / "output" / "hero"
    sprite_dir.mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    app.config["TESTING"] = True
    with app.test_client() as client:
      response = client.post(
          "/api/qa/advisor/feedback",
          data=json.dumps({"path": "output/hero", "code": "alpha_halo", "decision": "accepted"}),
          content_type="application/json",
      )

    data = json.loads(response.data.decode("utf-8"))
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["feedback"]["counts"]["alpha_halo"]["accepted"] == 1


def test_quality_lab_has_qa_advisor_assets():
    html = (WEB / "components" / "quality.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "qa.js").read_text(encoding="utf-8")
    css = (WEB / "css" / "components_recipes_modal.css").read_text(encoding="utf-8")

    assert 'id="qaAdvisorBtn"' in html
    assert 'id="qaAdvisorPanel"' in html
    assert "/api/qa/advisor?path=" in js
    assert "/api/qa/advisor/feedback" in js
    assert "renderQaAdvisor" in js
    assert "qa-advisor-repair" in js
    assert "qa-advisor-learning" in js
    assert "promoted_codes" in js
    assert "deprioritized_codes" in js
    assert "row.repair_plan" in js
    assert "button_id" in js
    assert ".qa-advisor-item" in css
    assert ".qa-advisor-repair" in css
    assert ".qa-advisor-learning" in css
