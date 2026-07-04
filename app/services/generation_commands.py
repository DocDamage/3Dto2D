from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from services.shell_service import run
from services.feature_capability_service import resolve_runtime
from services.wan_generation_service import (
    build_sprite_args,
    find_newest_video,
    is_comfy_running,
    output_files_from_history,
    queue_wan_prompt,
    wait_for_comfy,
    wait_for_existing_output,
    wait_for_history,
    write_run_manifest,
)

ROOT = Path(__file__).resolve().parent.parent


def _normalize_sprite_extra_args(extra: list[str] | None) -> list[str]:
    values = list(extra or [])
    while values and values[0] == "--":
        values.pop(0)
    return values


def _sprite_extra_from_generate_args(args: argparse.Namespace) -> list[str]:
    extra: list[str] = []
    for attr, flag in [
        ("matting_engine", "--matting-engine"),
        ("alpha_refine_radius", "--alpha-refine-radius"),
        ("temporal_alpha_strength", "--temporal-alpha-strength"),
        ("pixel_cleanup_colors", "--pixel-cleanup-colors"),
        ("pixel_cleanup_palette", "--pixel-cleanup-palette"),
        ("pixel_cleanup_dither_mode", "--pixel-cleanup-dither-mode"),
        ("interpolate_fps", "--interpolate-fps"),
        ("interpolation_engine", "--interpolation-engine"),
        ("interpolation_skip_patterns", "--interpolation-skip-patterns"),
        ("normal_map_engine", "--normal-map-engine"),
        ("pack_mode", "--pack-mode"),
        ("segment_parts", "--segment-parts"),
    ]:
        value = getattr(args, attr, None)
        if value not in (None, ""):
            extra += [flag, str(value)]
    for attr, flag in [
        ("alpha_refine", "--alpha-refine"),
        ("temporal_alpha_stabilize", "--temporal-alpha-stabilize"),
        ("pixel_cleanup", "--pixel-cleanup"),
        ("pixel_cleanup_dither", "--pixel-cleanup-dither"),
        ("interpolation_skip_pixel_art", "--interpolation-skip-pixel-art"),
        ("interpolation_skip_impact_frames", "--interpolation-skip-impact-frames"),
        ("generate_normal_maps", "--generate-normal-maps"),
    ]:
        if getattr(args, attr, False):
            extra.append(flag)
    return extra


def cmd_submit_wan(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
    cfg = load_config()
    if not is_comfy_running(cfg):
        raise RuntimeError(f"ComfyUI is not running at {cfg.base_url}. Launch it first.")
    queue_wan_prompt(args, cfg)


def cmd_generate_sprite(args: argparse.Namespace) -> None:
    native_source_video = str(getattr(args, "native_source_video", "") or "").strip()
    if native_source_video:
        resolve_runtime("video_to_sprite_conversion", native_only=True)
        from spriteforge_commands import load_config

        cfg = load_config()
        input_video = Path(native_source_video)
        if not input_video.exists():
            raise RuntimeError(f"Native source video not found: {input_video}")

        output_dir = Path(getattr(args, "output", None) or f"output/native_sprite_{time.strftime('%Y%m%d_%H%M%S')}")
        explicit_extra = _normalize_sprite_extra_args(getattr(args, "sprite_extra_args", None))
        sprite_cmd = build_sprite_args(input_video, output_dir.resolve(), cfg, explicit_extra + _sprite_extra_from_generate_args(args))
        run(sprite_cmd)
        print(f"Native sprite output: {output_dir}")
        return

    runtime = resolve_runtime("wan_generation", native_only=bool(getattr(args, "native_only", False)))
    if runtime.get("runtime") == "external":
        ext = ", ".join(runtime.get("external_apps") or [])
        print(f"[Capability] Using external generation backend: {ext}")

    from spriteforge_commands import load_config, start_comfy_background
    cfg = load_config()
    if not is_comfy_running(cfg):
        start_comfy_background(cfg)
        if not wait_for_comfy(cfg, timeout=180.0):
            raise RuntimeError("ComfyUI did not start within 180 seconds.")
    resp, patched, queued_path = queue_wan_prompt(args, cfg)
    prompt_id = resp.get("prompt_id") if isinstance(resp, dict) else None
    if not prompt_id:
        raise RuntimeError("Got no prompt_id from ComfyUI. Check logs.")
    entry_time = time.time()

    entry = wait_for_history(cfg, prompt_id, timeout=float(getattr(args, "timeout", 600) or 600), poll_seconds=10.0)
    outputs = output_files_from_history(cfg, entry)
    if not outputs:
        raise RuntimeError("No output files found in ComfyUI history entry.")
    video = wait_for_existing_output(outputs, stable_seconds=3.0) or find_newest_video(
        cfg.comfy_output, after_time=entry_time, prefix_hint=patched.get("_spriteforge", {}).get("output_prefix")
    )
    if video is None:
        raise RuntimeError("Could not locate a stable output video.")

    print(f"Source video: {video}")
    sprite_dir = Path(getattr(args, "output", None) or f"output/wan_sprite_{time.strftime('%Y%m%d_%H%M%S')}")
    explicit_extra = _normalize_sprite_extra_args(getattr(args, "sprite_extra_args", None))
    sprite_cmd = build_sprite_args(video, sprite_dir.resolve(), cfg, explicit_extra + _sprite_extra_from_generate_args(args))
    run(sprite_cmd)
    write_run_manifest(prompt_id, patched, resp, outputs, video, sprite_dir)
    print(f"Sprite output: {sprite_dir}")


def cmd_watch_output(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
    cfg = load_config()
    watch_dir = Path(args.folder or cfg.comfy_output)
    poll = float(getattr(args, "poll_seconds", 3) or 3)
    stable = float(getattr(args, "stable_seconds", 3) or 3)
    last_time = time.time()
    seen: set[Path] = set()

    print(f"Watching {watch_dir} for new videos. Press Ctrl+C to stop.")
    while True:
        try:
            vid = find_newest_video(watch_dir, after_time=last_time)
            if vid and vid not in seen:
                seen.add(vid)
                stamp = time.strftime("%Y%m%d_%H%M%S")
                out_dir = Path(args.output) if args.output else (ROOT / "output" / f"watch_{stamp}")
                cmd = build_sprite_args(vid, out_dir, cfg)
                print(f"New video: {vid.name} → {out_dir}")
                run(cmd)
                last_time = time.time()
            time.sleep(poll)
        except KeyboardInterrupt:
            print("Stopped.")
            return


def cmd_convert_video(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
    cfg = load_config()
    input_video = Path(args.input)
    output_dir = Path(args.output or f"output/convert_{time.strftime('%Y%m%d_%H%M%S')}")
    print(f"Source video: {input_video}")
    cmd = build_sprite_args(input_video, output_dir.resolve(), cfg, _normalize_sprite_extra_args(getattr(args, "extra", None)))
    run(cmd)
    print(f"Converted to sprite: {output_dir}")


def cmd_cloud_image_sprite(args: argparse.Namespace) -> None:
    from services.cloud_image_generation_service import build_cloud_sprite_sheet, default_output_dir

    output_dir = Path(args.output) if args.output else default_output_dir(args.prompt)
    manifest = build_cloud_sprite_sheet(
        prompt=args.prompt,
        output_dir=output_dir,
        provider=args.provider,
        model=args.model,
        source_images=args.source_image or [],
        frame_count=args.frames,
        frame_prompts=args.frame_prompt or [],
        size=args.size,
        cell_size=args.cell_size,
        key_color=args.key_color,
        palette_colors=None if args.no_palette_cleanup else args.palette_colors,
        columns=args.columns,
        fps=args.fps,
        animation_name=args.animation,
        constraints=args.constraints,
        negative=args.negative,
    )
    print(f"Cloud image sprite output: {manifest['output_dir']}")
