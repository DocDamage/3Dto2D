import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_project_paths_resolve_and_display_root_relative():
    from services.project_path_service import ProjectPaths

    resolved = ProjectPaths.resolve_root_path("output/example.png")

    assert resolved == (APP / "output" / "example.png").resolve()
    assert ProjectPaths.relative_display(resolved) == "output/example.png"


def test_project_paths_relative_guard_blocks_outside_root(tmp_path):
    from services.project_path_service import ProjectPaths

    outside = tmp_path / "outside.png"

    assert ProjectPaths.is_relative_to(APP / "output", APP)
    assert not ProjectPaths.is_relative_to(outside, APP)
