import argparse
import json
import sys
from pathlib import Path

from spriteforge_commands import (
    ROOT,
    run,
    cmd_status,
    cmd_doctor,
    cmd_install_spriteforge,
    cmd_install_all,
    cmd_install_comfy,
    cmd_install_nodes,
    cmd_install_manager,
    cmd_launch_comfy,
    cmd_open_comfy,
    cmd_submit_wan,
    cmd_generate_sprite,
    cmd_watch_output,
    cmd_convert_video,
    cmd_cloud_image_sprite,
    cmd_download_wan_native,
    cmd_model_report,
    cmd_model_tiers,
    cmd_download_model_tier,
    cmd_download_model_addon,
    cmd_qa_report,
    cmd_open_model_pages,
    cmd_validate_workflow,
    cmd_queue_status,
    cmd_history,
)

import cli.install
import cli.generation
import cli.model
import cli.pipeline


def cmd_training_dataset(args: argparse.Namespace) -> None:
    from services.training_dataset_service import build_training_dataset, default_output_dir

    output = args.output or str(default_output_dir(args.name or "sprite_dataset"))
    build_training_dataset(
        source_dir=args.source,
        output_dir=output,
        trigger=args.trigger,
        base_caption=args.base_caption,
        cell_size=args.cell_size,
    )


def cmd_autotile_dataset(args: argparse.Namespace) -> None:
    from services.tile_training_dataset_service import build_tile_training_dataset, default_output_dir

    output = args.output or str(default_output_dir(args.name or "sakpix_autotiles"))
    build_tile_training_dataset(
        source_dir=args.source,
        output_dir=output,
        trigger=args.trigger,
        base_caption=args.base_caption,
        cell_size=args.cell_size,
        max_samples_per_source=args.max_samples_per_source,
        include_all=args.include_all,
    )


def cmd_tilemap(args: argparse.Namespace) -> None:
    from services.tilemap_service import TilemapService

    if args.mode == "wang_16":
        result = TilemapService.generate_wang_tiles(
            args.north,
            args.east,
            args.south,
            args.west,
            args.output,
            tile_size=args.tile_size,
        )
    else:
        result = TilemapService.generate_16_autotiles(args.base, args.border, args.output)
    print(json.dumps(result, indent=2))


def cmd_remote_generate(args: argparse.Namespace) -> None:
    server = args.server
    if not server:
        from services.cloud_hub_service import cloud_hub_status

        hub = cloud_hub_status(prefer_id=args.cloud_node or "")
        selected = hub.get("selected")
        if not selected:
            raise SystemExit("No enabled cloud generation node configured. Use --server or add one through /api/cloud/nodes.")
        server = selected["url"]

    return run([sys.executable, str(ROOT / "spriteforge_remote.py"), "generate", "--server", server, "--workflow", args.workflow, "--prompt", args.prompt, "--output-prefix", args.output_prefix, "--timeout", str(args.timeout), "--cell-size", args.cell_size, "--key-color", args.key_color, "--seed", str(args.seed)] + (["--negative", args.negative] if args.negative else []) + (["--reference-image", args.reference_image] if args.reference_image else []) + (["--width", str(args.width)] if args.width else []) + (["--height", str(args.height)] if args.height else []) + (["--frames", str(args.frames)] if args.frames else []) + (["--video-fps", str(args.video_fps)] if args.video_fps else []) + (["--output", args.output] if args.output else []) + (["--convert"] if args.convert else []) + (args.extra or []))


def cmd_lora_train(args: argparse.Namespace) -> None:
    from services.feature_capability_service import resolve_runtime

    if args.run:
        resolve_runtime("lora_training_run", native_only=bool(getattr(args, "native_only", False)))

    from services.lora_training_service import build_lora_training_run, default_output_dir

    output = args.output or str(default_output_dir(args.name or f"{args.model_family}_lora"))
    build_lora_training_run(
        dataset_dir=args.dataset,
        output_dir=output,
        name=args.name,
        model_family=args.model_family,
        trainer=args.trainer,
        base_model=args.base_model,
        trigger=args.trigger,
        resolution=args.resolution,
        max_train_steps=args.max_train_steps,
        learning_rate=args.learning_rate,
        network_dim=args.network_dim,
        repeats=args.repeats,
        batch_size=args.batch_size,
        trainer_dir=args.trainer_dir,
        mode="run" if args.run else "prepare",
        native_only=bool(getattr(args, "native_only", False)),
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Unified ComfyUI + WAN + SpriteForge tool v12")
    sub = p.add_subparsers(dest="command", required=True)

    cli.install.add_parsers(sub)
    cli.generation.add_parsers(sub)
    cli.model.add_parsers(sub)
    cli.pipeline.add_parsers(sub)

    return p
