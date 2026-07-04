import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_lora_comparison_plan_builds_same_prompt_variants(tmp_path):
    from services.trained_lora_registry_service import plan_lora_comparison, set_default_lora

    registry = tmp_path / "trained_loras.json"
    set_default_lora(
        "style",
        "hero_a.safetensors",
        "Hero A",
        "hero_a_token",
        "wan22",
        metadata={"schema": "spriteforge.trained_lora_metadata.v1", "resolution": 768},
        registry_path=registry,
    )
    set_default_lora("style_b", "hero_b.safetensors", "Hero B", "hero_b_token", "wan22", registry_path=registry)

    plan = plan_lora_comparison(
        "idle knight sprite",
        ["hero_a.safetensors", "hero_b.safetensors"],
        registry_path=registry,
        base_payload={"sprite_action": "idle", "direction": "right"},
    )

    assert plan["schema"] == "spriteforge.lora_comparison_plan.v1"
    assert plan["variant_count"] == 2
    assert plan["variants"][0]["payload"]["prompt"] == "hero_a_token, idle knight sprite"
    assert plan["variants"][0]["metadata"]["resolution"] == 768
    assert plan["variants"][1]["payload"]["lora_name"] == "hero_b.safetensors"
    assert plan["variants"][1]["payload"]["sprite_action"] == "idle"
    assert plan["compare_player"]["max_variants"] == 4


def test_lora_comparison_plan_reports_missing_loras(tmp_path):
    from services.trained_lora_registry_service import plan_lora_comparison, set_default_lora

    registry = tmp_path / "trained_loras.json"
    set_default_lora("style", "hero_a.safetensors", "Hero A", "hero_a_token", "wan22", registry_path=registry)

    plan = plan_lora_comparison("idle knight sprite", ["hero_a.safetensors", "missing.safetensors"], registry_path=registry)

    assert plan["variant_count"] == 1
    assert plan["missing"] == ["missing.safetensors"]
