import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_hardened_prompt_appends_sprite_constraints():
    from services.cloud_image_generation_service import hardened_prompt

    prompt = hardened_prompt("clockwork knight idle")

    assert "clockwork knight idle" in prompt
    assert "pixel art sprite" in prompt
    assert "solid magenta background" in prompt
    assert "Avoid:" in prompt
    assert "sprite sheet grid" in prompt


def test_hardened_prompt_does_not_duplicate_constraints():
    from services.cloud_image_generation_service import DEFAULT_CONSTRAINTS, DEFAULT_NEGATIVE, hardened_prompt

    prompt = hardened_prompt(f"clockwork knight idle, {DEFAULT_CONSTRAINTS}. Avoid: {DEFAULT_NEGATIVE}")

    assert prompt.count(DEFAULT_CONSTRAINTS) == 1
    assert prompt.count(DEFAULT_NEGATIVE) == 1


def test_cloud_image_provider_status_does_not_expose_secret_values(monkeypatch):
    from services.cloud_image_generation_service import cloud_image_provider_status

    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")

    status = cloud_image_provider_status("openai")

    provider = status["providers"]["openai"]
    assert provider["configured"] is True
    assert provider["configured_env_name"] == "OPENAI_API_KEY"
    assert "sk-secret-value" not in json.dumps(status)
    assert "huggingface" in cloud_image_provider_status()["providers"]


def test_provider_api_keys_save_and_delete_locally(tmp_path, monkeypatch):
    from services.cloud_image_generation_service import (
        cloud_image_provider_status,
        delete_provider_api_key,
        save_provider_api_key,
    )

    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    saved = save_provider_api_key("huggingface", "hf_test_secret_value", root=tmp_path)
    assert saved["env_name"] == "HUGGINGFACE_API_KEY"
    assert "hf_test_secret_value" in (tmp_path / ".env").read_text(encoding="utf-8")
    assert cloud_image_provider_status("huggingface")["providers"]["huggingface"]["configured"] is True

    removed = delete_provider_api_key("huggingface", root=tmp_path)
    assert "HUGGINGFACE_API_KEY" in removed["removed"]
    assert "hf_test_secret_value" not in ((tmp_path / ".env").read_text(encoding="utf-8") if (tmp_path / ".env").exists() else "")


def test_cloud_generation_plan_is_secret_safe_and_provider_specific(monkeypatch):
    from services.cloud_image_generation_service import build_cloud_generation_plan

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret-value")

    plan = build_cloud_generation_plan(
        prompt="mossy goblin idle",
        provider="gemini",
        frame_count=2,
        frame_prompts=["idle facing right", "idle blink"],
        cell_size="32x32",
    )

    dumped = json.dumps(plan)
    assert plan["schema"] == "spriteforge.cloud_generation_plan.v1"
    assert plan["provider"] == "gemini"
    assert plan["model"] == "imagen-3.0-generate-002"
    assert plan["provider_configured"] is True
    assert plan["configured_env_name"] == "GEMINI_API_KEY"
    assert plan["secret_values_exposed"] is False
    assert plan["frame_count"] == 2
    assert len(plan["hardened_prompts"]) == 2
    assert plan["generation_contract"]["schema"] == "spriteforge.cloud_generation_contract.v1"
    assert plan["generation_contract"]["cloud_api_opt_in"] is True
    assert plan["generation_contract"]["request_strategy"] == "one_frame_per_request"
    assert plan["generation_contract"]["planned_cloud_requests"] == 2
    assert plan["generation_contract"]["secrets_policy"]["secret_values_persisted"] is False
    assert "solid magenta background" in plan["hardened_prompts"][0]
    assert "nearest-neighbor" in json.dumps(plan["processing_steps"])
    assert "gemini-secret-value" not in dumped


def test_huggingface_plan_is_available_for_free_tier_preview(monkeypatch):
    from services.cloud_image_generation_service import build_cloud_generation_plan

    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf-secret-value")
    plan = build_cloud_generation_plan(prompt="tiny hero t-pose", provider="huggingface", frame_count=1)

    assert plan["provider"] == "huggingface"
    assert plan["provider_configured"] is True
    assert plan["model"] == "stabilityai/stable-diffusion-xl-base-1.0"
    assert "hf-secret-value" not in json.dumps(plan)


def test_cloud_image_source_processing_builds_engine_ready_sheet(tmp_path):
    from services.cloud_image_generation_service import build_cloud_sprite_sheet

    src = tmp_path / "source.png"
    img = Image.new("RGBA", (128, 128), (255, 0, 255, 255))
    for y in range(36, 110):
        for x in range(48, 82):
            img.putpixel((x, y), (30, 140, 220, 255))
    img.save(src)

    out = tmp_path / "sprite"
    manifest = build_cloud_sprite_sheet(
        prompt="blue test hero",
        output_dir=out,
        provider="openai",
        source_images=[str(src)],
        cell_size="32x32",
        palette_colors=None,
        animation_name="idle",
    )

    meta = json.loads((out / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(out / "sheet.png").convert("RGBA")

    assert manifest["schema"] == "spriteforge.cloud_image_sprite.v1"
    assert manifest["source"] == "local_images"
    assert manifest["model"] == "gpt-image-1"
    assert manifest["generation_contract"]["schema"] == "spriteforge.cloud_generation_contract.v1"
    assert manifest["generation_contract"]["cloud_api_opt_in"] is False
    assert manifest["generation_contract"]["request_strategy"] == "local_source_images_only"
    assert manifest["generation_contract"]["planned_cloud_requests"] == 0
    assert manifest["generation_contract"]["post_processing"]["downsample_interpolation"] == "nearest"
    assert manifest["processing"]["transparency_extraction"]["engine"] == "chroma_key"
    assert manifest["processing"]["downsampling"]["interpolation"] == "nearest"
    assert manifest["processing"]["assembly"]["grid_aligned"] is True
    assert manifest["processing"]["cleanup_metrics"]["per_frame"] is True
    assert manifest["frame_sources"][0]["source"] == "local_image"
    assert manifest["frame_sources"][0]["source_image"] == str(src)
    assert manifest["frame_sources"][0]["raw_frame"] == "frames_raw/raw_0000.png"
    assert manifest["frame_sources"][0]["processed_frame"] == "frames_processed/frame_0000.png"
    cleanup = manifest["frame_sources"][0]["cleanup_metrics"]
    assert cleanup["schema"] == "spriteforge.cloud_frame_cleanup.v1"
    assert cleanup["raw_size"] == "128x128"
    assert cleanup["processed_size"] == "32x32"
    assert cleanup["alpha_bbox"]
    assert 0 < cleanup["opaque_pixel_ratio"] < 1
    assert cleanup["unique_color_count"] >= 2
    assert meta["extra"]["frame_sources"][0]["processed_frame"] == "frames_processed/frame_0000.png"
    assert meta["extra"]["frame_sources"][0]["cleanup_metrics"]["processed_size"] == "32x32"
    assert meta["frame_width"] == 32
    assert meta["frame_height"] == 32
    assert meta["frame_count"] == 1
    assert sheet.size == (32, 32)
    assert sheet.getbbox() is not None
    assert sheet.getpixel((0, 0))[3] == 0
    assert (out / "frames_processed" / "frame_0000.png").exists()
    assert (out / "cloud_generation.json").exists()


def test_cloud_image_sprite_parser_and_web_command_forwarding():
    from spriteforge_unified import build_parser
    from web_helpers import build_action_command

    parsed = build_parser().parse_args([
        "cloud-image-sprite",
        "--prompt",
        "mage idle",
        "--provider",
        "gemini",
        "--cell-size",
        "64x64",
        "--source-image",
        "output/raw.png",
    ])

    assert parsed.provider == "gemini"
    assert parsed.cell_size == "64x64"
    assert parsed.source_image == ["output/raw.png"]

    title, cmd = build_action_command({
        "action": "cloud_image_sprite",
        "prompt": "mage idle",
        "provider": "openai",
        "cell_size": "64x64",
        "source_images": ["output/raw.png"],
        "frames": 2,
        "no_palette_cleanup": True,
    })

    assert title == "Generate cloud image sprite"
    assert "cloud-image-sprite" in cmd
    assert "--provider" in cmd
    assert "--source-image" in cmd
    assert "--no-palette-cleanup" in cmd


def test_cloud_image_generation_plan_endpoint():
    from flask import Flask
    from web_routes.routes_misc import routes_misc

    app = Flask(__name__)
    app.register_blueprint(routes_misc)

    response = app.test_client().post(
        "/api/cloud/image-generation-plan",
        json={"prompt": "tiny alchemist idle", "provider": "openai", "frames": 1, "cell_size": "32x32"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["schema"] == "spriteforge.cloud_generation_plan.v1"
    assert payload["provider"] == "openai"
    assert payload["frame_count"] == 1
    assert payload["cell_size"] == "32x32"
    assert payload["secret_values_exposed"] is False
    assert payload["generation_contract"]["schema"] == "spriteforge.cloud_generation_contract.v1"
    assert payload["generation_contract"]["request_strategy"] == "one_frame_per_request"
