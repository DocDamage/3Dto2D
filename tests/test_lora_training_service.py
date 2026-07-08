import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _write_dataset(tmp_path: Path) -> Path:
    from services.training_dataset_service import build_training_dataset

    source = tmp_path / "owned_assets"
    source.mkdir()
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 6, 24, 28), fill=(220, 80, 40, 255))
    img.save(source / "ember_knight_idle_front.png")

    dataset = tmp_path / "dataset"
    build_training_dataset(
        source_dir=source,
        output_dir=dataset,
        trigger="sakpix_style",
        base_caption="premium pixel art RPG character",
        cell_size="32x32",
    )
    return dataset


def test_lora_training_run_prepares_kohya_sdxl_files(tmp_path):
    from services.lora_training_service import build_lora_training_run

    dataset = _write_dataset(tmp_path)
    output = tmp_path / "runs" / "sakpix_sdxl"

    result = build_lora_training_run(
        dataset_dir=dataset,
        output_dir=output,
        name="sakpix_sdxl",
        model_family="sdxl",
        trainer="kohya",
        base_model="C:/models/sdxl-base.safetensors",
        trigger="sakpix_style",
        resolution=768,
        max_train_steps=120,
        learning_rate="1e-4",
        network_dim=16,
        repeats=7,
        mode="prepare",
    )

    assert result["schema"] == "spriteforge.lora_training_run.v1"
    assert result["trainer"] == "kohya"
    assert result["model_family"] == "sdxl"
    assert result["mode"] == "prepare"
    assert result["sample_count"] == 1
    assert result["train_command"][0].endswith("python.exe") or result["train_command"][0].endswith("python")
    assert result["train_command"][1:3] == ["sdxl_train_network.py", "--config_file"]

    manifest = json.loads((output / "training_run.json").read_text(encoding="utf-8"))
    assert manifest["dataset_dir"] == str(dataset.resolve())
    assert manifest["base_model"] == "C:/models/sdxl-base.safetensors"

    dataset_config = (output / "dataset_config.toml").read_text(encoding="utf-8")
    assert str((dataset / "images").resolve()).replace("\\", "\\\\") in dataset_config
    assert "num_repeats = 7" in dataset_config
    assert "shuffle_caption = false" in dataset_config

    train_config = (output / "train_config.toml").read_text(encoding="utf-8")
    assert 'pretrained_model_name_or_path = "C:/models/sdxl-base.safetensors"' in train_config
    assert "max_train_steps = 120" in train_config
    assert "max_data_loader_n_workers = 0" in train_config
    assert "network_dim = 16" in train_config
    assert "network_train_unet_only = true" in train_config
    assert 'mixed_precision = "fp16"' in train_config
    assert 'save_precision = "fp16"' in train_config
    assert 'optimizer_type = "AdamW8bit"' in train_config
    assert "sdpa = true" in train_config
    assert "no_half_vae = true" in train_config
    assert "cache_latents_to_disk = true" in train_config
    assert "cache_text_encoder_outputs = true" in train_config
    assert "cache_text_encoder_outputs_to_disk = true" in train_config

    launch_script = (output / "run_train.bat").read_text(encoding="utf-8")
    assert "set PYTHONIOENCODING=utf-8" in launch_script
    assert (output / "README_LORA_TRAINING.md").exists()


def test_lora_training_recommends_vram_safe_defaults():
    from services.lora_training_service import recommend_lora_training_defaults

    low = recommend_lora_training_defaults(8, "sdxl")
    high = recommend_lora_training_defaults(24, "flux")

    assert low["schema"] == "spriteforge.lora_training_defaults.v1"
    assert low["tier"] == "sdxl_low_vram"
    assert low["recommendation"]["resolution"] == 512
    assert low["recommendation"]["network_dim"] == 8
    assert high["tier"] == "flux_high_vram"
    assert high["recommendation"]["resolution"] == 1024
    assert high["recommendation"]["batch_size"] == 1


def test_lora_training_run_prepares_flux_ai_toolkit_files(tmp_path):
    from services.lora_training_service import build_lora_training_run

    dataset = _write_dataset(tmp_path)
    output = tmp_path / "runs" / "sakpix_flux"

    result = build_lora_training_run(
        dataset_dir=dataset,
        output_dir=output,
        name="sakpix_flux",
        model_family="flux",
        trainer="ai_toolkit",
        base_model="black-forest-labs/FLUX.1-dev",
        trigger="sakpix_style",
        resolution=512,
        max_train_steps=80,
        learning_rate="4e-4",
        network_dim=8,
        repeats=5,
        mode="prepare",
    )

    assert result["trainer"] == "ai_toolkit"
    assert result["model_family"] == "flux"
    assert result["train_command"][0].endswith("python.exe") or result["train_command"][0].endswith("python")
    assert "run.py" in result["train_command"]

    config = (output / "flux_lora_config.yaml").read_text(encoding="utf-8")
    assert "name: sakpix_flux" in config
    assert "model_family: flux" in config
    assert str((dataset / "images").resolve()).replace("\\", "\\\\") in config


def test_lora_training_run_external_run_executes_without_native_only_when_trainer_available(tmp_path, monkeypatch):
    from services.lora_training_service import build_lora_training_run

    dataset = _write_dataset(tmp_path)
    output = tmp_path / "runs" / "external_run"
    trainer_root = tmp_path / "kohya_ss"
    trainer_script_root = trainer_root / "sd-scripts"
    trainer_script_root.mkdir(parents=True)
    (trainer_script_root / "sdxl_train_network.py").write_text("print('ok')", encoding="utf-8")
    python_dir = trainer_root / ".venv" / "Scripts"
    python_dir.mkdir(parents=True)
    (python_dir / "python.exe").write_text("", encoding="utf-8")
    calls = []

    def fake_run(command, cwd=None, env=None, check=False):
        calls.append({"command": list(command), "cwd": str(cwd or "")})
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr("services.lora_training_service.subprocess.run", fake_run)

    result = build_lora_training_run(
        dataset_dir=dataset,
        output_dir=output,
        name="external_run",
        model_family="sdxl",
        trainer="kohya",
        trainer_dir=trainer_root,
        base_model="stabilityai/stable-diffusion-xl-base-1.0",
        trigger="sakpix_style",
        mode="run",
        native_only=False,
    )

    assert result["runtime_backend"] == "external"
    assert result["native_only"] is False
    assert result["train_command"][0].endswith("python.exe") or result["train_command"][0].endswith("python")
    assert result["train_command"][1:3] == ["sdxl_train_network.py", "--config_file"]
    assert calls, "Expected external training command execution path to be hit."


def test_lora_training_run_uses_nested_kohya_sd_scripts_workdir(tmp_path):
    from services.lora_training_service import build_lora_training_run

    dataset = _write_dataset(tmp_path)
    trainer_root = tmp_path / "kohya_ss"
    script_dir = trainer_root / "sd-scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "sdxl_train_network.py").write_text("# fake trainer", encoding="utf-8")
    python_dir = trainer_root / ".venv" / "Scripts"
    python_dir.mkdir(parents=True)
    (python_dir / "python.exe").write_text("", encoding="utf-8")

    result = build_lora_training_run(
        dataset_dir=dataset,
        output_dir=tmp_path / "run",
        name="nested_kohya",
        model_family="sdxl",
        trainer="kohya",
        base_model="stabilityai/stable-diffusion-xl-base-1.0",
        trainer_dir=trainer_root,
        mode="prepare",
    )

    assert result["trainer_dir"] == str(trainer_root.resolve())
    assert result["trainer_workdir"] == str(script_dir.resolve())
    assert result["python"] == str((python_dir / "python.exe").resolve())


def test_lora_training_action_builds_unified_command(tmp_path):
    from services.web_helpers_cmd import build_action_command

    title, cmd = build_action_command({
        "action": "lora_training",
        "dataset_dir": str(tmp_path / "dataset"),
        "output": str(tmp_path / "run"),
        "name": "sakpix_sdxl",
        "model_family": "sdxl",
        "trainer": "kohya",
        "base_model": "C:/models/sdxl-base.safetensors",
        "trigger": "sakpix_style",
        "resolution": "768",
        "max_train_steps": "120",
        "learning_rate": "1e-4",
        "network_dim": "16",
        "repeats": "7",
        "mode": "run",
        "trainer_dir": "C:/tools/kohya_ss",
    })

    assert title == "Start LoRA training run"
    assert cmd[1:] == [
        "spriteforge_unified.py",
        "lora-train",
        "--dataset",
        str(tmp_path / "dataset"),
        "--output",
        str(tmp_path / "run"),
        "--name",
        "sakpix_sdxl",
        "--model-family",
        "sdxl",
        "--trainer",
        "kohya",
        "--base-model",
        "C:/models/sdxl-base.safetensors",
        "--trigger",
        "sakpix_style",
        "--resolution",
        "768",
        "--max-train-steps",
        "120",
        "--learning-rate",
        "1e-4",
        "--network-dim",
        "16",
        "--repeats",
        "7",
        "--trainer-dir",
        "C:/tools/kohya_ss",
        "--run",
    ]


def test_lora_training_native_run_executes_without_external_trainer(tmp_path):
    from services.lora_training_service import build_lora_training_run
    from services.trained_lora_registry_service import load_registry

    dataset = _write_dataset(tmp_path)
    output = tmp_path / "runs" / "native_run"
    registry = tmp_path / "trained_loras.json"

    result = build_lora_training_run(
        dataset_dir=dataset,
        output_dir=output,
        name="native_run",
        model_family="sdxl",
        trainer="kohya",
        trainer_dir=tmp_path / "missing_external_trainer",
        base_model="stabilityai/stable-diffusion-xl-base-1.0",
        trigger="sakpix_style",
        mode="run",
        native_only=True,
        registry_path=registry,
    )

    assert result["runtime_backend"] == "native"
    native_artifact = Path(result["native_artifact"])
    assert native_artifact.exists()

    artifact_data = json.loads(native_artifact.read_text(encoding="utf-8"))
    assert artifact_data["schema"] == "spriteforge.native_lora.v1"
    assert artifact_data["trigger"] == "sakpix_style"
    assert artifact_data["sample_count"] == 1
    assert artifact_data["resolution"] == 768
    assert artifact_data["style_metadata"]["base_caption"] == "premium pixel art RPG character"
    assert artifact_data["dataset_provenance"]["dataset_dir"] == str(dataset.resolve())

    run_manifest = json.loads((output / "training_run.json").read_text(encoding="utf-8"))
    assert run_manifest["runtime_backend"] == "native"
    assert run_manifest["native_only"] is True

    registry_data = load_registry(registry_path=registry)
    assert registry_data["defaults"]["character_style"]["filename"] == native_artifact.name
    metadata = registry_data["defaults"]["character_style"]["metadata"]
    assert metadata["schema"] == "spriteforge.trained_lora_metadata.v1"
    assert metadata["runtime_backend"] == "native"
    assert metadata["resolution"] == 768
    assert metadata["sample_count"] == 1
    assert metadata["style_metadata"]["base_caption"] == "premium pixel art RPG character"
    assert metadata["dataset_provenance"]["dataset_dir"] == str(dataset.resolve())
    assert metadata["token_profile"]
    assert metadata["palette_profile"]


def test_lora_training_native_autotile_registers_tile_style(tmp_path):
    from services.lora_training_service import build_lora_training_run
    from services.trained_lora_registry_service import load_registry

    dataset = _write_dataset(tmp_path)
    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_kind"] = "autotile"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    output = tmp_path / "runs" / "native_tiles"
    registry = tmp_path / "trained_loras.json"

    result = build_lora_training_run(
        dataset_dir=dataset,
        output_dir=output,
        name="native_tiles",
        model_family="sdxl",
        trainer="kohya",
        trainer_dir=tmp_path / "missing_external_trainer",
        base_model="stabilityai/stable-diffusion-xl-base-1.0",
        trigger="tile_style_token",
        mode="run",
        native_only=True,
        registry_path=registry,
    )

    native_artifact = Path(result["native_artifact"])
    registry_data = load_registry(registry_path=registry)
    assert registry_data["defaults"]["tile_style"]["filename"] == native_artifact.name
    assert registry_data["defaults"]["tile_style"]["trigger"] == "tile_style_token"
    assert "character_style" not in registry_data["defaults"]
