from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from services.trained_lora_registry_service import DEFAULT_REGISTRY_PATH, load_registry, save_registry, set_default_lora
from spriteforge_utils import ROOT, load_json, safe_name

DEFAULT_OUTPUT = ROOT / "output" / "training_runs"
logger = logging.getLogger(__name__)

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


def recommend_lora_training_defaults(vram_gb: Any = None, model_family: str = "sdxl") -> Dict[str, Any]:
    """Recommend conservative LoRA settings from available GPU VRAM."""
    try:
        vram = float(vram_gb)
    except (TypeError, ValueError):
        vram = 0.0
    family = (model_family or "sdxl").strip().lower()
    if family == "flux":
        if vram >= 24:
            preset = {"resolution": 1024, "max_train_steps": 1600, "network_dim": 16, "batch_size": 1, "learning_rate": "4e-4"}
            tier = "flux_high_vram"
        elif vram >= 16:
            preset = {"resolution": 768, "max_train_steps": 1200, "network_dim": 12, "batch_size": 1, "learning_rate": "3e-4"}
            tier = "flux_balanced"
        else:
            preset = {"resolution": 512, "max_train_steps": 800, "network_dim": 8, "batch_size": 1, "learning_rate": "2e-4"}
            tier = "flux_low_vram"
    else:
        family = "sdxl"
        if vram >= 16:
            preset = {"resolution": 1024, "max_train_steps": 1600, "network_dim": 32, "batch_size": 1, "learning_rate": "1e-4"}
            tier = "sdxl_high_vram"
        elif vram >= 10:
            preset = {"resolution": 768, "max_train_steps": 1200, "network_dim": 16, "batch_size": 1, "learning_rate": "1e-4"}
            tier = "sdxl_balanced"
        else:
            preset = {"resolution": 512, "max_train_steps": 800, "network_dim": 8, "batch_size": 1, "learning_rate": "8e-5"}
            tier = "sdxl_low_vram"
    return {
        "schema": "spriteforge.lora_training_defaults.v1",
        "model_family": family,
        "vram_gb": vram,
        "tier": tier,
        "repeats": 10,
        "gradient_checkpointing": True,
        "cache_latents_to_disk": True,
        "recommendation": preset,
        "notes": "Conservative defaults; inspect dataset quality and trainer docs before long runs.",
    }


def _trainer_workdir(trainer: str, trainer_root: Path) -> Path:
    if trainer == "kohya" and (trainer_root / "sd-scripts" / "sdxl_train_network.py").exists():
        return (trainer_root / "sd-scripts").resolve()
    return trainer_root.resolve()


def _training_python(trainer_root: Path) -> Path:
    candidates = [
        trainer_root / ".venv" / "Scripts" / "python.exe",
        trainer_root.parent / "kohya_ss" / ".venv" / "Scripts" / "python.exe",
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


def _top_tokens(captions_dir: Path, limit: int = 32) -> List[str]:
    counts: Counter[str] = Counter()
    for path in sorted(captions_dir.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception as exc:
            logger.debug("Skipping unreadable caption file %s while summarizing LoRA dataset: %s", path, exc)
            continue
        for token in re.findall(r"[a-z0-9_]{3,}", text):
            if token not in {"the", "and", "with", "from", "that", "this"}:
                counts[token] += 1
    return [token for token, _count in counts.most_common(limit)]


def _dominant_palette(images_dir: Path, colors: int = 8) -> List[List[int]]:
    aggregate: Counter[tuple[int, int, int]] = Counter()
    for path in sorted(images_dir.glob("*.png")):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as exc:
            logger.debug("Skipping unreadable training image %s while summarizing LoRA palette: %s", path, exc)
            continue
        small = img.resize((64, 64), Image.Resampling.BILINEAR)
        quant = small.convert("RGB").quantize(colors=max(2, colors), method=Image.Quantize.FASTOCTREE)
        pal = quant.getpalette() or []
        for count, idx in (quant.getcolors(maxcolors=1024) or []):
            base = idx * 3
            if base + 2 < len(pal):
                rgb = (int(pal[base]), int(pal[base + 1]), int(pal[base + 2]))
                aggregate[rgb] += int(count)
    return [[r, g, b] for (r, g, b), _count in aggregate.most_common(colors)]


def _run_native_training(
    run_dir: Path,
    dataset_dir: Path,
    dataset_manifest: Dict[str, Any],
    name: str,
    model_family: str,
    base_model: str,
    trigger: str,
    resolution: int,
    sample_count: int,
    max_train_steps: int,
    registry_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    images_dir = dataset_dir / "images"
    captions_dir = dataset_dir / "captions"

    tokens = _top_tokens(captions_dir)
    palette = _dominant_palette(images_dir)

    native_dir = run_dir / "native_model"
    native_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = native_dir / f"{safe_name(name)}.spriteforge_lora.json"

    artifact = {
        "schema": "spriteforge.native_lora.v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "name": name,
        "model_family": model_family,
        "base_model": base_model,
        "trigger": trigger,
        "resolution": int(resolution),
        "sample_count": int(sample_count),
        "max_train_steps": int(max_train_steps),
        "style_metadata": {
            "base_caption": str(dataset_manifest.get("base_caption") or ""),
            "source_dir": str(dataset_manifest.get("source_dir") or str(dataset_dir.resolve())),
            "cell_size": dataset_manifest.get("cell_size") if dataset_manifest.get("cell_size") is not None else None,
        },
        "dataset_provenance": {
            "dataset_dir": str(dataset_dir.resolve()),
            "source_dataset": str(dataset_manifest.get("source_dir") or ""),
            "created_at": str(dataset_manifest.get("created_at") or ""),
            "sample_count": int(dataset_manifest.get("sample_count") or sample_count),
        },
        "token_profile": tokens,
        "palette_profile": palette,
        "notes": "Native SpriteForge style adapter artifact generated without external trainer stacks.",
    }
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    dataset_kind = str(dataset_manifest.get("dataset_kind") or "").strip().lower()
    registry_role = "tile_style" if dataset_kind in {"autotile", "tiles", "tileset", "tile_training"} else "character_style"

    set_default_lora(
        role=registry_role,
        filename=artifact_path.name,
        label=f"{name} (Native)",
        trigger=trigger,
        base_model=base_model,
        source_path=str(artifact_path),
        installed_path=str(artifact_path),
        notes="Native SpriteForge adapter generated via --native-only --run.",
        metadata={
            "schema": "spriteforge.trained_lora_metadata.v1",
            "runtime_backend": "native",
            "artifact_schema": artifact["schema"],
            "model_family": model_family,
            "resolution": int(resolution),
            "sample_count": int(sample_count),
            "max_train_steps": int(max_train_steps),
            "style_metadata": artifact["style_metadata"],
            "dataset_provenance": artifact["dataset_provenance"],
            "token_profile": tokens,
            "palette_profile": palette,
        },
        registry_path=registry_path,
    )

    return {
        "runtime_backend": "native",
        "native_artifact": str(artifact_path),
        "native_token_count": len(tokens),
        "native_palette_count": len(palette),
        "registry_path": str(Path(registry_path).resolve()) if registry_path else "",
    }


def register_external_lora_checkpoint(
    checkpoint_path: Path | str,
    run_dir: Path | str | None = None,
    role: str = "",
    label: str = "",
    notes: str = "",
    make_default: bool = True,
    registry_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Register a finished external trainer checkpoint in the shared LoRA registry."""
    checkpoint = Path(checkpoint_path).resolve()
    if not checkpoint.exists() or checkpoint.suffix.lower() not in {".safetensors", ".pt", ".ckpt"}:
        raise FileNotFoundError(f"LoRA checkpoint not found: {checkpoint}")

    resolved_run_dir = Path(run_dir).resolve() if run_dir else checkpoint.parent
    manifest_path = resolved_run_dir / "training_run.json"
    manifest = load_json(manifest_path, {}) if manifest_path.exists() else {}
    dataset_dir = Path(str(manifest.get("dataset_dir") or "")).resolve() if manifest.get("dataset_dir") else None
    dataset_manifest = {}
    if dataset_dir and (dataset_dir / "manifest.json").exists():
        dataset_manifest = load_json(dataset_dir / "manifest.json", {})

    dataset_kind = str(dataset_manifest.get("dataset_kind") or "").strip().lower()
    inferred_role = "tile_style" if dataset_kind in {"autotile", "tiles", "tileset", "tile_training"} else "character_style"
    registry_role = str(role or inferred_role).strip()
    trigger = str(manifest.get("trigger") or dataset_manifest.get("trigger") or "").strip()
    base_model = str(manifest.get("base_model") or "").strip()
    record_label = str(label or f"{manifest.get('name') or checkpoint.stem} (Kohya)").strip()
    record_notes = str(notes or "External trainer checkpoint registered after Kohya/AI Toolkit run completed.").strip()
    metadata = {
        "schema": "spriteforge.trained_lora_metadata.v1",
        "runtime_backend": "external",
        "trainer": manifest.get("trainer", ""),
        "model_family": manifest.get("model_family", ""),
        "resolution": manifest.get("resolution"),
        "sample_count": manifest.get("sample_count"),
        "max_train_steps": manifest.get("max_train_steps"),
        "dataset_provenance": {
            "dataset_dir": str(dataset_dir) if dataset_dir else "",
            "dataset_kind": dataset_kind,
            "source_dataset": str(dataset_manifest.get("source_dir") or ""),
            "sample_count": dataset_manifest.get("sample_count"),
        },
        "training_run": {
            "run_dir": str(resolved_run_dir),
            "manifest": str(manifest_path) if manifest_path.exists() else "",
            "checkpoint": str(checkpoint),
        },
    }

    if make_default:
        registry = set_default_lora(
            role=registry_role,
            filename=checkpoint.name,
            label=record_label,
            trigger=trigger,
            base_model=base_model,
            source_path=str(checkpoint),
            installed_path=str(checkpoint),
            notes=record_notes,
            metadata=metadata,
            registry_path=registry_path,
        )
    else:
        registry = load_registry(registry_path)
        record = {
            "role": registry_role,
            "filename": checkpoint.name,
            "label": record_label,
            "trigger": trigger,
            "base_model": base_model,
            "source_path": str(checkpoint),
            "installed_path": str(checkpoint),
            "notes": record_notes,
            "metadata": metadata,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        registry.setdefault("loras", {})[checkpoint.name] = record
        save_registry(registry, registry_path)

    return {
        "ok": True,
        "role": registry_role,
        "filename": checkpoint.name,
        "registry_path": str(Path(registry_path).resolve()) if registry_path else str(DEFAULT_REGISTRY_PATH),
        "default": bool(make_default),
        "record": registry["loras"][checkpoint.name],
    }


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
    native_only: bool = False,
    registry_path: Optional[Path | str] = None,
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
        "native_only": bool(native_only),
        "runtime_backend": "external",
    }
    (run_dir / "training_run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"LoRA training run: {run_dir}")
    print(f"Trainer: {selected_trainer} ({family})")
    print(f"Samples: {manifest['sample_count']}")
    print(f"Run script: {run_dir / 'run_train.bat'}")

    if selected_mode == "run":
        runtime_backend = "native" if native_only else "external"
        if native_only:
            native_result = _run_native_training(
                run_dir=run_dir,
                dataset_dir=dataset,
                dataset_manifest=dataset_manifest,
                name=run_name,
                model_family=family,
                base_model=model_ref,
                trigger=token,
                resolution=res,
                sample_count=int(dataset_manifest["sample_count"]),
                max_train_steps=steps,
                registry_path=registry_path,
            )
            manifest.update({"runtime_backend": runtime_backend, **native_result})
            (run_dir / "training_run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(f"Native training artifact: {native_result['native_artifact']}")
        else:
            if not trainer_workdir.exists():
                raise FileNotFoundError(f"Trainer folder not found: {trainer_workdir}. Prepare succeeded; install/configure the trainer, then run Start Training again.")
            if selected_trainer == "kohya" and not (trainer_workdir / "sdxl_train_network.py").exists():
                raise FileNotFoundError(f"Kohya SDXL trainer script not found: {trainer_workdir / 'sdxl_train_network.py'}")
            print("Starting trainer command:")
            print(subprocess.list2cmdline(train_command))
            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            subprocess.run(train_command, cwd=str(trainer_workdir), env=env, check=True)
            manifest["runtime_backend"] = runtime_backend

    return manifest


def default_output_dir(name: str = "sprite_lora") -> Path:
    return DEFAULT_OUTPUT / f"{safe_name(name)}_{time.strftime('%Y%m%d_%H%M%S')}"
