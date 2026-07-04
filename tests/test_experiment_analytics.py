import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_experiment_service_analytics_ranks_runs(tmp_path, monkeypatch):
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    ExperimentService.append_run(
        prompt="hero knight walk",
        seed=42,
        profile="quality_local",
        sprite_action="walk",
        direction="right",
        qa_score=91.0,
        qa_passed=True,
        sprite_folder="output/hero_walk",
    )
    ExperimentService.append_run(
        prompt="hero knight idle",
        seed=42,
        profile="quality_local",
        sprite_action="idle",
        direction="front",
        qa_score=81.0,
        qa_passed=True,
    )
    ExperimentService.append_run(
        prompt="goblin run",
        seed=7,
        profile="debug",
        sprite_action="run",
        qa_score=44.0,
        qa_passed=False,
    )

    data = ExperimentService.analytics()

    assert data["ok"] is True
    assert data["total_runs"] == 3
    assert data["scored_runs"] == 3
    assert data["average_score"] == 72.0
    assert data["pass_rate"] == 66.7
    assert data["score_distribution"][0]["count"] == 1
    assert data["best_profiles"][0]["name"] == "quality_local"
    assert data["best_seeds"][0]["name"] == "42"
    assert data["best_runs"][0]["score"] == 91.0
    assert data["prompt_history"][0]["prompt"]
    assert data["recommendations"][0]["kind"] == "winning_prompt"
    assert "highest QA prompt" in data["recommendations"][0]["title"]
    pack = ExperimentService.winning_prompt_pack(limit=5)
    assert pack["schema"] == "spriteforge.winning_prompt_pack.v1"
    assert pack["selection_contract"]["entry_schema"] == "spriteforge.winning_prompt_entry.v1"
    assert pack["entry_count"] == 3
    assert pack["entries"][0]["schema"] == "spriteforge.winning_prompt_entry.v1"
    assert pack["entries"][0]["selection_rank"] == 1
    assert pack["entries"][0]["qa_score"] == 91.0
    assert pack["entries"][0]["qa_passed"] is True
    assert pack["entries"][0]["reuse"]["recommended"] is True
    assert "prompt" in pack["entries"][0]["reuse"]["prompt_fields"]
    search = ExperimentService.search_prompts("knight", limit=5)
    assert search["count"] == 2
    assert search["prompts"][0]["prompt"].startswith("hero knight")


def test_experiment_pick_winner_marks_matching_sprite_folder(tmp_path, monkeypatch):
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    run_id = ExperimentService.append_run(
        prompt="hero knight walk",
        sprite_action="walk",
        sprite_folder="output/hero_walk",
        qa_score=91.0,
    )

    result = ExperimentService.pick_winner(
        sprite_folder="output\\hero_walk",
        compared_sprites=["output/hero_walk", "output/hero_idle"],
        note="Best silhouette.",
    )
    record = ExperimentService.get_run(run_id)

    assert result["ok"] is True
    assert result["winner_recorded"] is True
    assert record["starred"] is True
    assert record["winner"] is True
    assert record["compare_winner"]["compared_sprites"] == ["output/hero_walk", "output/hero_idle"]
    assert "Best silhouette." in record["notes"]


def test_experiment_analytics_api(tmp_path, monkeypatch):
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService
    from spriteforge_web import app

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    ExperimentService.append_run(prompt="mage cast", seed=5, profile="quality_local", sprite_action="cast", qa_score=88.0, qa_passed=True)

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/experiments/analytics")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))

    assert data["ok"] is True
    assert data["total_runs"] == 1
    assert data["score_by_action"][0]["name"] == "cast"
    assert "project_workspace" in data

    with app.test_client() as client:
        search_response = client.get("/api/experiments/prompts?q=mage")
    search_data = json.loads(search_response.data.decode("utf-8"))
    assert search_response.status_code == 200
    assert search_data["ok"] is True
    assert search_data["prompts"][0]["prompt"] == "mage cast"

    with app.test_client() as client:
        pack_response = client.get("/api/experiments/winning-prompts")
    pack_data = json.loads(pack_response.data.decode("utf-8"))
    assert pack_response.status_code == 200
    assert pack_data["schema"] == "spriteforge.winning_prompt_pack.v1"
    assert pack_data["entries"][0]["prompt"] == "mage cast"

    with app.test_client() as client:
        winner_response = client.post("/api/experiments/pick-winner", json={
            "sprite_folder": "",
            "id": pack_data["entries"][0]["id"],
            "compared_sprites": ["output/a", "output/b"],
        })
    winner_data = winner_response.get_json()
    assert winner_response.status_code == 200
    assert winner_data["ok"] is True
    assert winner_data["winner_recorded"] is True


def test_experiment_analytics_ui_assets_are_present():
    html = (WEB / "components" / "history.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "experiments.js").read_text(encoding="utf-8")
    css = (WEB / "css" / "components_recipes_modal.css").read_text(encoding="utf-8")

    assert 'id="experimentAnalyticsPanel"' in html
    assert 'id="expScoreDistribution"' in html
    assert 'id="expRecommendations"' in html
    assert 'id="experimentPromptSearch"' in html
    assert 'id="exportWinningPrompts"' in html
    assert 'id="winningPromptPackResult"' in html
    assert "/api/experiments/analytics" in js
    assert "/api/experiments/prompts" in js
    assert "/api/experiments/winning-prompts" in js
    assert "exportWinningPrompts" in js
    assert "usePromptHistoryRow" in js
    assert "data-prompt-pin" in js
    assert "renderExperimentAnalytics" in js
    assert "experiment-recommendation" in js
    assert "renderPromptHistory" in js
    assert ".experiment-kpi-grid" in css
    assert ".experiment-recommendation" in css
    assert ".experiment-best-run" in css
    assert ".winning-prompt-pack-json" in css
