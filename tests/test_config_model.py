import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_config_model_coerces_defaults_and_profiles():
    from services.config_model import SpriteForgeConfig

    model = SpriteForgeConfig.from_dict({
        "paths": {"comfyui_dir": "vendor/ComfyUI"},
        "comfy": {"port": "8189", "extra_args": ["--listen"]},
        "sprite_defaults": {"fps": "12", "cell_size": "64x64", "drop_loop_duplicate": "true"},
        "profiles": {
            "tiny": {"width": "256", "height": "256", "frames": "9"},
        },
    })

    assert model.paths.comfyui_dir == "vendor/ComfyUI"
    assert model.comfy.port == 8189
    assert model.comfy.extra_args == ["--listen"]
    assert model.sprite_defaults.fps == 12
    assert model.sprite_defaults.drop_loop_duplicate is True
    assert model.profiles["tiny"].width == 256
    assert model.warnings == []


def test_config_model_reports_validation_warnings():
    from services.config_model import SpriteForgeConfig

    model = SpriteForgeConfig.from_dict({
        "sprite_defaults": {"cell_size": "bad"},
        "profiles": {"odd": {"width": 257, "height": 256}},
    })

    assert "sprite_defaults.cell_size should look like WIDTHxHEIGHT" in model.warnings
    assert "profiles.odd dimensions should be divisible by 8" in model.warnings


def test_config_model_explains_effective_profile():
    from services.config_model import SpriteForgeConfig

    model = SpriteForgeConfig.from_dict({
        "wan_defaults": {"width": 512, "height": 512, "frames": 17},
        "sprite_defaults": {"cell_size": "64x64", "fps": 10},
        "profiles": {"quality": {"width": 768, "height": 512, "frames": 33}},
    })

    named = model.effective_profile("quality")
    fallback = model.effective_profile("missing")

    assert named["schema"] == "spriteforge.effective_profile.v1"
    assert named["source"] == "profiles"
    assert named["settings"]["width"] == 768
    assert named["sprite_defaults"]["cell_size"] == "64x64"
    assert fallback["source"] == "wan_defaults"
    assert fallback["settings"]["frames"] == 17


def test_config_effective_profile_endpoint(monkeypatch, tmp_path):
    from spriteforge_web import app
    import services.config_service as config_mod

    config_path = tmp_path / "spriteforge_config.json"
    config_path.write_text(
        '{"profiles":{"small":{"width":256,"height":256,"frames":9}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(config_mod, "CONFIG_PATH", config_path)

    app.config["TESTING"] = True
    response = app.test_client().get("/api/config/effective-profile?profile=small")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["source"] == "profiles"
    assert payload["settings"]["width"] == 256
