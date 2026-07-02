from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from services.shell_service import run
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

def cmd_submit_wan(args: argparse.Namespace) -> None:
    from spriteforge_commands import load_config
    cfg = load_config()
    if not is_comfy_running(cfg):
        raise RuntimeError(f"ComfyUI is not running at {cfg.base_url}. Launch it first.")
    queue_wan_prompt(args, cfg)


def cmd_generate_sprite(args: argparse.Namespace) -> None:
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
    sprite_cmd = build_sprite_args(video, sprite_dir.resolve(), cfg, getattr(args, "sprite_extra_args", None))
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
    cmd = build_sprite_args(input_video, output_dir.resolve(), cfg, getattr(args, "extra", None))
    run(cmd)
    print(f"Converted to sprite: {output_dir}")
