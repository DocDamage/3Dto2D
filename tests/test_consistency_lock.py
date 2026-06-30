import json
import importlib
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.consistency_lock_service import build_consistency_lock, apply_consistency_lock_to_command
from spriteforge_web import app


def test_build_consistency_lock_manifest(tmp_path):
    ref = tmp_path / "uploads" / "hero.png"
    ref.parent.mkdir()
    Image.new("RGBA", (8, 8), (32, 64, 128, 255)).save(ref)

    out = tmp_path / "locks" / "hero"
    result = build_consistency_lock(
        tmp_path,
        {
            "name": "Hero Knight",
            "reference_image": str(ref),
            "strength": "0.72",
            "mode": "ip_adapter",
        },
        out,
    )

    assert result["ok"] is True
    manifest = json.loads((out / "consistency_lock.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "Hero Knight"
    assert Path(manifest["reference_image"]) == ref.resolve()
    assert manifest["strength"] == 0.72
    assert "appearance consistency lock" in manifest["prompt_suffix"]


def test_consistency_lock_rejects_external_or_non_image_paths(tmp_path):
    external = tmp_path.parent / "outside.txt"
    external.write_text("nope", encoding="utf-8")

    for bad_path in (str(external), "../outside.txt"):
        try:
            build_consistency_lock(tmp_path, {"reference_image": bad_path}, tmp_path / "out")
        except ValueError as exc:
            assert "reference image" in str(exc).lower()
        else:
            raise AssertionError("bad reference image path should fail")


def test_apply_consistency_lock_to_command_adds_existing_generation_flags(tmp_path):
    ref = tmp_path / "ref.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(ref)
    lock = build_consistency_lock(tmp_path, {"reference_image": str(ref)}, tmp_path / "out")["lock"]

    cmd = apply_consistency_lock_to_command(["python", "spriteforge_unified.py", "generate-sprite"], lock)

    assert "--reference-image" in cmd
    assert str(ref.resolve()) in cmd
    assert "--extra-prompt" not in cmd


def test_consistency_lock_api_and_assets(tmp_path, monkeypatch):
    ref = tmp_path / "ref.png"
    Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(ref)
    routes_module = importlib.import_module("web_routes.routes_projects")
    monkeypatch.setattr(routes_module, "ROOT", tmp_path)

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/consistency_lock/save",
            data=json.dumps({"name": "hero", "reference_image": str(ref)}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["lock"]["reference_image"] == str(ref.resolve())

        html = client.get("/").data.decode("utf-8")
        assert "/web/consistency_lock.css" in html
        assert "/web/js/consistency_lock.js" in html
