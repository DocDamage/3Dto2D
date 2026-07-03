from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import safe_name

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output" / "training_runs"

TRAINER_DEFAULTS = {
    "kohya": ROOT / "vendor" / "kohya_ss",
    "ai_toolkit": ROOT / "vendor" / "ai-toolkit",
}

COMFY_PYTHON = ROOT / "vendor" / "ComfyUI" / ".venv" / "Scripts" / "python.exe"


def _toml_string(value: str | Path) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _yaml_string(value: str | Path) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _as_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
        return parsed if parsed >= minimum else default
    except (TypeError, ValueError):
        return default


def _trainer_for(model_family: str, trainer: str) -> str:
    model = (model_family or "sdxl").strip().lower()
    selected = (trainer or "auto").strip().lower()
    if selected == "auto":
        return "ai_toolkit" if model == "flux" else "kohya"
    if selected not in {"kohya", "ai_toolkit"}:
        raise ValueError("trainer must be auto, kohya, or ai_toolkit.")
    return selected


def _trainer_workdir(trainer: str, trainer_root: Path) -> Path:
    if trainer == "kohya" and (trainer_root / "sd-scripts" / "sdxl_train_network.py").exists():
        return (trainer_root / "sd-scripts").resolve()
    return trainer_root.resolve()


def _training_python(trainer_root: Path) -> Path:
    candidates = [
        trainer_root / ".venv" / "Scripts" / "python.exe",
        trainer_root.parent / ".venv" / "Scripts" / "python.exe",
        COMFY_PYTHON,
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return Path(sys.executable).resolve()


def _load_dataset(dataset_dir: Path) -> Dict[str, Any]:
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"Training dataset folder not found: {dataset_dir}")
    images_dir = dataset_dir / "images"
    captions_dir = dataset_dir / "captions"
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Training dataset is missing images folder: {images_dir}")
    if not captions_dir.is_dir():
        raise FileNotFoundError(f"Training dataset is missing captions folder: {captions_dir}")

    manifest_path = dataset_dir / "manifest.json"
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample_count = int(manifest.get("sample_count") or len(list(images_dir.glob("*.png"))))
    if sample_count <= 0:
        raise ValueError("Training dataset does not contain any PNG samples.")
    manifest["sample_count"] = sample_count
    return manifest


def _write_kohya_configs(
    run_dir: Path,
    dataset_dir: Path,
    name: str,
    base_model: str,
    trigger: str,
    resolution: int,
    max_train_steps: int,
    learning_rate: str,
    network_dim: int,
    repeats: int,
    batch_size: int,
    python_exe: Path,
) -> List[str]:
    dataset_config = f"""[general]
shuffle_caption = false
caption_extension = ".txt"
keep_tokens = 1

[[datasets]]
resolution = {resolution}
batch_size = {batch_size}
enable_bucket = true
bucket_no_upscale = false

[[datasets.subsets]]
image_dir = {_toml_string((dataset_dir / "images").resolve())}
caption_extension = ".txt"
num_repeats = {repeats}
class_tokens = {_toml_string(trigger)}
"""
    (run_dir / "dataset_config.toml").write_text(dataset_config, encoding="utf-8")

    alpha = max(1, network_dim)
    train_config = f"""pretrained_model_name_or_path = {_toml_string(base_model)}
dataset_config = {_toml_string((run_dir / "dataset_config.toml").resolve())}
output_dir = {_toml_string(run_dir.resolve())}
output_name = {_toml_string(name)}
save_model_as = "safetensors"
network_module = "networks.lora"
network_dim = {network_dim}
network_alpha = {alpha}
network_train_unet_only = true
learning_rate = {learning_rate}
train_batch_size = {batch_size}
max_train_steps = {max_train_steps}
max_data_loader_n_workers = 0
mixed_precision = "fp16"
save_precision = "fp16"
optimizer_type = "AdamW8bit"
lr_scheduler = "cosine"
gradient_checkpointing = true
sdpa = true
no_half_vae = true
cache_latents = true
cache_latents_to_disk = true
cache_text_encoder_outputs = true
cache_text_encoder_outputs_to_disk = true
"""
    (run_dir / "train_config.toml").write_text(train_config, encoding="utf-8")
    return [str(python_exe), "sdxl_train_network.py", "--config_file", str((run_dir / "train_config.toml").resolve())]


def _write_ai_toolkit_configs(
    run_dir: Path,
    dataset_dir: Path,
    name: str,
    base_model: str,
    trigger: str,
    resolution: int,
    max_train_steps: int,
    learning_rate: str,
    network_dim: int,
    repeats: int,
    batch_size: int,
    python_exe: Path,
) -> List[str]:
    config = f"""# SpriteForge Flux LoRA starter config for AI Toolkit.
name: {name}
model_family: flux
trigger_word: {trigger}
base_model: "{_yaml_string(base_model)}"
dataset_path: "{_yaml_string((dataset_dir / "images").resolve())}"
caption_ext: ".txt"
output_dir: "{_yaml_string(run_dir.resolve())}"
resolution: {resolution}
batch_size: {batch_size}
num_repeats: {repeats}
train_steps: {max_train_steps}
learning_rate: {learning_rate}
lora_rank: {network_dim}
save_every: 250
sample_every: 250
sample_prompt: "{trigger}, premium pixel art RPG character, transparent background"
notes: "Generated by SpriteForge. Review against your installed AI Toolkit config schema before long training runs."
"""
    config_path = run_dir / "flux_lora_config.yaml"
    config_path.write_text(config, encoding="utf-8")
    return [str(python_exe), "run.py", str(config_path.resolve())]


def _write_launch_script(run_dir: Path, trainer: str, trainer_dir: Path, train_command: List[str]) -> None:
    command = subprocess.list2cmdline(train_command)
    script = f"""@echo off
setlocal
set PYTHONIOENCODING=utf-8
set TRAINER_DIR={trainer_dir}
if not exist "%TRAINER_DIR%" (
  echo Trainer folder not found: %TRAINER_DIR%
  echo Install or clone the {trainer} trainer there, or rerun with a different trainer folder.
  exit /b 1
)
cd /d "%TRAINER_DIR%"
{command}
"""
    (run_dir / "run_train.bat").write_text(script, encoding="utf-8")


def _write_notes(run_dir: Path, trainer: str, model_family: str, name: str, mode: str) -> None:
    notes = f"""# SpriteForge LoRA Training Run

Run name: `{name}`
Trainer: `{trainer}`
Model family: `{model_family}`
Mode prepared: `{mode}`

Files:

- `training_run.json`: SpriteForge manifest for this run.
- `dataset_config.toml` and `train_config.toml`: Kohya SDXL configs when using Kohya.
- `flux_lora_config.yaml`: Flux AI Toolkit starter config when using AI Toolkit.
- `run_train.bat`: Windows launcher for the selected trainer.

Use Prepare first, inspect the generated config, then Start Training when your trainer folder and base model are correct.
Keep trained LoRAs private unless the asset license explicitly allows model-training redistribution.
"""
    (run_dir / "README_LORA_TRAINING.md").write_text(notes, encoding="utf-8")


def build_lora_training_run(
    dataset_dir: Path | str,
    output_dir: Path | str,
    name: str = "sprite_lora",
    model_family: str = "sdxl",
    trainer: str = "auto",
    base_model: str = "",
    trigger: str = "sakpix_style",
    resolution: int | str = 768,
    max_train_steps: int | str = 1200,
    learning_rate: str = "1e-4",
    network_dim: int | str = 16,
    repeats: int | str = 10,
    batch_size: int | str = 1,
    trainer_dir: Optional[Path | str] = None,
    mode: str = "prepare",
) -> Dict[str, Any]:
    dataset = Path(dataset_dir).resolve()
    dataset_manifest = _load_dataset(dataset)
    run_name = safe_name(name or f"{model_family}_sprite_lora")
    run_dir = Path(output_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    family = (model_family or "sdxl").strip().lower()
    if family not in {"sdxl", "flux"}:
        raise ValueError("model_family must be sdxl or flux.")
    selected_trainer = _trainer_for(family, trainer)
    selected_mode = (mode or "prepare").strip().lower()
    if selected_mode not in {"prepare", "run"}:
        raise ValueError("mode must be prepare or run.")

    res = _as_int(resolution, 768)
    steps = _as_int(max_train_steps, 1200)
    dim = _as_int(network_dim, 16)
    repeat_count = _as_int(repeats, 10)
    train_batch_size = _as_int(batch_size, 1)
    model_ref = str(base_model or "").strip()
    if not model_ref:
        model_ref = "CHOOSE_BASE_MODEL_PATH_OR_HF_ID"
    token = str(trigger or dataset_manifest.get("trigger") or "sakpix_style").strip()
    trainer_root = Path(trainer_dir).resolve() if trainer_dir else TRAINER_DEFAULTS[selected_trainer].resolve()
    trainer_workdir = _trainer_workdir(selected_trainer, trainer_root)
    python_exe = _training_python(trainer_root)

    if selected_trainer == "kohya":
        train_command = _write_kohya_configs(
            run_dir, dataset, run_name, model_ref, token, res, steps,
            learning_rate, dim, repeat_count, train_batch_size, python_exe,
        )
    else:
        train_command = _write_ai_toolkit_configs(
            run_dir, dataset, run_name, model_ref, token, res, steps,
            learning_rate, dim, repeat_count, train_batch_size, python_exe,
        )

    _write_launch_script(run_dir, selected_trainer, trainer_workdir, train_command)
    _write_notes(run_dir, selected_trainer, family, run_name, selected_mode)

    manifest: Dict[str, Any] = {
        "schema": "spriteforge.lora_training_run.v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_dir": str(dataset),
        "output_dir": str(run_dir),
        "name": run_name,
        "model_family": family,
        "trainer": selected_trainer,
        "trainer_dir": str(trainer_root),
        "trainer_workdir": str(trainer_workdir),
        "python": str(python_exe),
        "base_model": model_ref,
        "trigger": token,
        "resolution": res,
        "max_train_steps": steps,
        "learning_rate": learning_rate,
        "network_dim": dim,
        "repeats": repeat_count,
        "batch_size": train_batch_size,
        "sample_count": int(dataset_manifest["sample_count"]),
        "mode": selected_mode,
        "train_command": train_command,
    }
    (run_dir / "training_run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"LoRA training run: {run_dir}")
    print(f"Trainer: {selected_trainer} ({family})")
    print(f"Samples: {manifest['sample_count']}")
    print(f"Run script: {run_dir / 'run_train.bat'}")

    if selected_mode == "run":
        if not trainer_workdir.exists():
            raise FileNotFoundError(f"Trainer folder not found: {trainer_workdir}. Prepare succeeded; install/configure the trainer, then run Start Training again.")
        if selected_trainer == "kohya" and not (trainer_workdir / "sdxl_train_network.py").exists():
            raise FileNotFoundError(f"Kohya SDXL trainer script not found: {trainer_workdir / 'sdxl_train_network.py'}")
        print("Starting trainer command:")
        print(subprocess.list2cmdline(train_command))
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        subprocess.run(train_command, cwd=str(trainer_workdir), env=env, check=True)

    return manifest


def default_output_dir(name: str = "sprite_lora") -> Path:
    return DEFAULT_OUTPUT / f"{safe_name(name)}_{time.strftime('%Y%m%d_%H%M%S')}"
