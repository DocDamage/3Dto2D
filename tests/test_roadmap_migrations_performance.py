import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_previous_two_project_generations_migrate_without_data_loss():
    from services.roadmap_models import migrate_project_manifest
    for version in ("schema_v0", "schema_v1"):
        source = json.loads((ROOT / "tests" / "fixtures" / "projects" / version / "spriteforge_project.json").read_text(encoding="utf-8"))
        migrated, changed = migrate_project_manifest(source)
        assert changed is True
        assert migrated["schema"] == "spriteforge.project.v2"
        assert migrated["schema_version"] == 2
        for key, value in source.items():
            if key != "schema":
                assert migrated[key] == value


def test_large_project_benchmark_contract(tmp_path):
    from services.roadmap_performance_service import run_roadmap_benchmark
    report = run_roadmap_benchmark(asset_count=100, timeline_frames=2000, matrix_cells=5000, root=tmp_path)
    assert report["schema"] == "spriteforge.performance_report.v1"
    assert report["counts"]["assets_returned"] == 100
    assert report["counts"]["timeline_frames"] == 2000
    assert report["counts"]["matrix_cells"] >= 5000
    assert report["ok"] is True
