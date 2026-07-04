import json
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_database_service_migrates_json_records_and_searches(tmp_path):
    from services.database_service import DatabaseService

    history = tmp_path / "experiment_history.json"
    history.write_text(json.dumps([
        {
            "id": "run-1",
            "created_at": "2026-07-03T10:00:00",
            "prompt": "blue knight idle",
            "profile": "fast",
            "project_name": "demo",
            "qa_score": 91.5,
        },
        {
            "id": "run-2",
            "created_at": "2026-07-03T11:00:00",
            "prompt": "lava tile loop",
            "profile": "quality",
            "project_name": "tiles",
            "qa_score": 84.0,
        },
    ]), encoding="utf-8")

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    result = db.migrate_json_list(history, "experiment")

    assert result["ok"] is True
    assert result["imported"] == 2
    assert db.recent("experiment", limit=1)[0]["id"] == "run-2"
    matches = db.search("knight", kind="experiment")
    assert len(matches) == 1
    assert matches[0]["id"] == "run-1"


def test_database_service_upserts_jobs_with_metadata_search(tmp_path):
    from services.database_service import DatabaseService

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    record_id = db.upsert_record("job", {
        "id": "job-1",
        "started_at": "2026-07-03 12:00:00",
        "title": "Generate WAN sprite",
        "metadata": {"project_name": "demo", "sprite_action": "attack"},
    })

    assert record_id == "job-1"
    assert db.search("attack", kind="job")[0]["id"] == "job-1"
    assert db.counts_by_kind() == {"job": 1}


def test_database_service_counts_records_by_kind(tmp_path):
    from services.database_service import DatabaseService

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    db.upsert_record("job", {"id": "job-1", "title": "Generate"})
    db.upsert_record("experiment", {"id": "run-1", "prompt": "blue mage"})
    db.upsert_record("experiment", {"id": "run-2", "prompt": "green rogue"})

    assert db.counts_by_kind() == {"experiment": 2, "job": 1}


def test_database_service_counts_records_by_project(tmp_path):
    from services.database_service import DatabaseService

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    db.upsert_record("job", {"id": "job-1", "title": "Hero Job", "metadata": {"project_name": "hero"}})
    db.upsert_record("job", {"id": "job-2", "title": "Tile Job", "metadata": {"project_name": "tiles"}})
    db.upsert_record("experiment", {"id": "run-1", "prompt": "hero idle", "project_name": "hero"})

    assert db.counts_by_kind(project_name="hero") == {"experiment": 1, "job": 1}
    assert db.counts_by_kind(project_name="missing") == {}


def test_database_service_health_reports_integrity_and_fts_sync(tmp_path):
    from services.database_service import DatabaseService

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    db.upsert_record("job", {"id": "job-1", "title": "Generate"})
    health = db.health()

    assert health["schema"] == "spriteforge.database_health.v1"
    assert health["ok"] is True
    assert health["integrity_check"] == "ok"
    assert health["record_count"] == 1
    assert health["fts_record_count"] == 1
    assert health["fts_in_sync"] is True
    assert health["counts_by_kind"] == {"job": 1}


def test_database_default_migration_reports_counts(monkeypatch, tmp_path):
    import services.database_service as db_mod
    from services.database_service import DatabaseService

    root = tmp_path / "app"
    jobs_path = root / "output" / "jobs" / "job_history.json"
    experiments_path = root / "output" / "experiments" / "experiment_history.json"
    jobs_path.parent.mkdir(parents=True)
    experiments_path.parent.mkdir(parents=True)
    jobs_path.write_text(json.dumps([{"id": "job-1", "title": "Generate"}]), encoding="utf-8")
    experiments_path.write_text(json.dumps([{"id": "run-1", "prompt": "mage"}]), encoding="utf-8")
    monkeypatch.setattr(db_mod, "ROOT", root)

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    result = db.migrate_default_json()

    assert result["ok"] is True
    assert result["counts"] == {"experiment": 1, "job": 1}


def test_database_search_api_uses_sqlite_service(monkeypatch, tmp_path):
    from spriteforge_web import app
    from services.database_service import DatabaseService

    routes_misc = sys.modules["web_routes.routes_misc"]
    db_path = tmp_path / "spriteforge.sqlite3"
    db = DatabaseService(db_path)
    db.upsert_record("experiment", {
        "id": "run-7",
        "created_at": "2026-07-03T12:00:00",
        "prompt": "emerald ranger walk",
    })

    monkeypatch.setattr(routes_misc, "DatabaseService", lambda: DatabaseService(db_path))
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/database/search?q=emerald&kind=experiment")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["records"][0]["id"] == "run-7"


def test_database_recent_api_uses_sqlite_service(monkeypatch, tmp_path):
    from spriteforge_web import app
    from services.database_service import DatabaseService

    routes_misc = sys.modules["web_routes.routes_misc"]
    db_path = tmp_path / "spriteforge.sqlite3"
    db = DatabaseService(db_path)
    db.upsert_record("job", {"id": "job-1", "started_at": "2026-07-03 10:00:00", "title": "Old"})
    db.upsert_record("job", {"id": "job-2", "started_at": "2026-07-03 11:00:00", "title": "New"})

    monkeypatch.setattr(routes_misc, "DatabaseService", lambda: DatabaseService(db_path))
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/database/recent?kind=job&limit=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["kind"] == "job"
    assert payload["count"] == 1
    assert payload["records"][0]["id"] == "job-2"


def test_database_stats_api_reports_counts(monkeypatch, tmp_path):
    from spriteforge_web import app
    from services.database_service import DatabaseService

    routes_misc = sys.modules["web_routes.routes_misc"]
    db_path = tmp_path / "spriteforge.sqlite3"
    db = DatabaseService(db_path)
    db.upsert_record("job", {"id": "job-7", "title": "QA"})
    db.upsert_record("experiment", {"id": "run-9", "prompt": "idle"})

    monkeypatch.setattr(routes_misc, "DatabaseService", lambda: DatabaseService(db_path))
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/database/stats")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["counts"] == {"experiment": 1, "job": 1}
    assert payload["total"] == 2

    with app.test_client() as client:
        scoped = client.get("/api/database/stats?project=missing")

    scoped_payload = scoped.get_json()
    assert scoped_payload["ok"] is True
    assert scoped_payload["project_name"] == "missing"
    assert scoped_payload["counts"] == {}
    assert scoped_payload["total"] == 0


def test_database_health_api_reports_sqlite_state(monkeypatch, tmp_path):
    from spriteforge_web import app
    from services.database_service import DatabaseService

    routes_misc = sys.modules["web_routes.routes_misc"]
    db_path = tmp_path / "spriteforge.sqlite3"
    db = DatabaseService(db_path)
    db.upsert_record("job", {"id": "job-8", "title": "Health"})

    monkeypatch.setattr(routes_misc, "DatabaseService", lambda: DatabaseService(db_path))
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/database/health")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["schema"] == "spriteforge.database_health.v1"
    assert payload["record_count"] == 1
    assert payload["fts_in_sync"] is True


def test_database_search_sanitizes_punctuation_heavy_queries(tmp_path):
    from services.database_service import DatabaseService

    db = DatabaseService(tmp_path / "spriteforge.sqlite3")
    db.upsert_record("experiment", {
        "id": "run-8",
        "created_at": "2026-07-03T13:00:00",
        "prompt": "clockwork knight idle",
        "profile": "quality",
    })

    matches = db.search('"clockwork" + knight:', kind="experiment")

    assert len(matches) == 1
    assert matches[0]["id"] == "run-8"
