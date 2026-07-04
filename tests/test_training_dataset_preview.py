import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_training_dataset_preview_is_read_only_and_summarizes_captions(tmp_path):
    from services.training_dataset_service import preview_training_dataset

    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGBA", (16, 8), (255, 0, 0, 255)).save(source / "hero_walk_front.png")

    preview = preview_training_dataset(source, trigger="sakpix_style", cell_size="8x8", limit=2)

    assert preview["schema"] == "spriteforge.training_dataset_preview.v1"
    assert preview["write_performed"] is False
    assert preview["source_image_count"] == 1
    assert preview["estimated_sample_count"] == 2
    assert preview["samples"][0]["caption"].startswith("sakpix_style")
    assert preview["samples"][0]["thumbnail_data_uri"].startswith("data:image/png;base64,")
    assert not (source / "images").exists()


def test_training_dataset_preview_endpoint(tmp_path):
    from flask import Flask
    from web_routes.routes_misc import routes_misc

    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(source / "mage_idle_right.png")

    app = Flask(__name__)
    app.register_blueprint(routes_misc)
    response = app.test_client().post(
        "/api/training-dataset/preview",
        json={"source_dir": str(source), "trigger": "sakpix_style", "cell_size": "8x8"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["estimated_sample_count"] == 1
    assert payload["samples"][0]["direction"] == "right"
    assert payload["samples"][0]["thumbnail_data_uri"].startswith("data:image/png;base64,")
