import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_capability_report_contains_expected_entries():
    from services.feature_capability_service import capability_report

    report = capability_report()
    assert report["schema"] == "spriteforge.feature_capabilities.v1"
    ids = {row["id"] for row in report["entries"]}
    assert "wan_generation" in ids
    assert "video_to_sprite_conversion" in ids


def test_resolve_runtime_blocks_non_native_when_native_only():
    from services.feature_capability_service import resolve_runtime

    with pytest.raises(RuntimeError, match="not native-ready"):
        resolve_runtime("wan_generation", native_only=True)


def test_resolve_runtime_allows_external_when_not_native_only():
    from services.feature_capability_service import resolve_runtime

    runtime = resolve_runtime("wan_generation", native_only=False)
    assert runtime["runtime"] == "external"
    assert "ComfyUI" in runtime.get("external_apps", [])


def test_resolve_runtime_uses_external_default_for_lora():
    from services.feature_capability_service import resolve_runtime

    runtime = resolve_runtime("lora_training_run", native_only=False)
    assert runtime["runtime"] == "external"
    assert runtime["default_runtime"] == "external"


def test_resolve_runtime_prefers_native_for_lora_when_native_only():
    from services.feature_capability_service import resolve_runtime

    runtime = resolve_runtime("lora_training_run", native_only=True)
    assert runtime["runtime"] == "native"
    assert runtime["default_runtime"] == "external"


def test_resolve_runtime_prefers_native_when_available():
    from services.feature_capability_service import resolve_runtime

    runtime = resolve_runtime("video_to_sprite_conversion", native_only=True)
    assert runtime["runtime"] == "native"


def test_capability_report_exposes_runtime_state():
    from services.feature_capability_service import capability_report

    entries = {entry["id"]: entry for entry in capability_report()["entries"]}
    lora_entry = entries["lora_training_run"]
    assert lora_entry["runtime"] == "external"
    assert lora_entry["default_runtime"] == "external"
    assert "native_ready" in lora_entry
    assert "external_ready" in lora_entry


def test_feature_registry_covers_current_runtime_consumers():
    from services.feature_capability_service import FEATURES

    expected = {
        "video_to_sprite_conversion",
        "wan_generation",
        "lora_training_run",
    }

    assert expected <= set(FEATURES)
