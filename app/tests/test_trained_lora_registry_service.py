from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.trained_lora_registry_service import load_registry, set_default_lora


def test_set_default_lora_records_role_metadata(tmp_path: Path) -> None:
    registry_path = tmp_path / "trained_loras.json"

    registry = set_default_lora(
        role="character_style",
        filename="sakpix_8dir_sdxl_continue.safetensors",
        label="SakPix 8-Direction Characters",
        trigger="sakpix_style",
        base_model="SDXL",
        source_path=r"C:\runs\sakpix_8dir_sdxl_continue.safetensors",
        installed_path=r"C:\ComfyUI\models\loras\sakpix_8dir_sdxl_continue.safetensors",
        notes="Continuation pass is the current default; original pass remains fallback.",
        registry_path=registry_path,
    )

    default = registry["defaults"]["character_style"]
    assert default["filename"] == "sakpix_8dir_sdxl_continue.safetensors"
    assert default["trigger"] == "sakpix_style"
    assert default["base_model"] == "SDXL"
    assert "created_at" in default

    loaded = load_registry(registry_path=registry_path)
    assert loaded["defaults"]["character_style"]["label"] == "SakPix 8-Direction Characters"
