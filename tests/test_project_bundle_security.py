import io
import json
import zipfile
from pathlib import Path

import pytest


def _bundle(entries: dict[str, bytes]) -> io.BytesIO:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    payload.seek(0)
    return payload


def test_project_export_rejects_paths_outside_projects_root(tmp_path):
    from services.project_bundle_service import resolve_project_directory

    root = tmp_path / "app"
    projects = root / "projects"
    outside = tmp_path / "outside"
    projects.mkdir(parents=True)
    outside.mkdir()
    (outside / "spriteforge_project.json").write_text('{"name":"outside"}', encoding="utf-8")

    with pytest.raises(ValueError, match="projects directory"):
        resolve_project_directory(root, projects, outside)


def test_project_import_rejects_parent_traversal(tmp_path):
    from services.project_bundle_service import import_project_bundle

    payload = _bundle({
        "spriteforge_project.json": json.dumps({"name": "safe"}).encode(),
        "../outside.txt": b"escape",
    })

    with pytest.raises(ValueError, match="Unsafe archive member"):
        import_project_bundle(payload, "safe.spriteforge", tmp_path / "projects")
    assert not (tmp_path / "outside.txt").exists()


def test_project_import_does_not_overwrite_existing_project(tmp_path):
    from services.project_bundle_service import import_project_bundle

    projects = tmp_path / "projects"
    existing = projects / "hero"
    existing.mkdir(parents=True)
    (existing / "keep.txt").write_text("keep", encoding="utf-8")
    payload = _bundle({
        "spriteforge_project.json": json.dumps({"name": "hero"}).encode(),
        "asset.txt": b"new",
    })

    result = import_project_bundle(payload, "hero.spriteforge", projects)

    assert result["project_dir"].name == "hero_2"
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (result["project_dir"] / "asset.txt").read_bytes() == b"new"
