import argparse
import sys
from pathlib import Path
from services.generation_commands import add_sprite_polish_args
from spriteforge_commands import (
    ROOT,
    run,
    cmd_submit_wan,
    cmd_generate_sprite,
    cmd_watch_output,
    cmd_convert_video,
    cmd_cloud_image_sprite,
)


ALL_DIRECTIONS = ["front", "front_right", "right", "back_right", "back", "back_left", "left", "front_left"]


def _csv_values(value, default=None):
    items = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return items or list(default or [])


def _expand_directions(value, default=None):
    directions = _csv_values(value, default or ["right"])
    if any(direction.lower() == "all" for direction in directions):
        return list(ALL_DIRECTIONS)
    return directions


def add_wan_args(s: argparse.ArgumentParser) -> None:
    s.add_argument("--workflow", default=None)
    s.add_argument("--tier", default=None, help="Model tier: wan21_safe, wan22_5b, or wan22_14b_cloud. Defaults to config default_model_tier. Aliases: safe, advanced, cloud.")
    s.add_argument("--mode", default="auto", choices=["auto", "t2v", "ti2v22", "i2v", "vace", "custom"], help="WAN mode. auto chooses the mode from --tier.")
    s.add_argument("--profile", default="auto", help="WAN preset. auto uses the profile recommended by --tier.")
    s.add_argument("--prompt", required=False)
    s.add_argument("--negative", default=None)
    s.add_argument("--action", default=None, help="Build prompt from sprite action: idle, walk, run, attack_light, attack_heavy, cast, jump, hurt, death")
    s.add_argument("--direction", default="right", help="Prompt direction: front, back, left, right, three_quarter")
    s.add_argument("--character", default=None, help="Character description used by automatic prompt builder")
    s.add_argument("--style", default=None)
    s.add_argument("--background", default=None)
    s.add_argument("--extra-prompt", default=None)
    s.add_argument("--reference-image", default=None, help="Image-to-video/reference image path. Patched into common LoadImage nodes.")
    s.add_argument("--clip-vision", default=None, help="CLIP vision model for I2V, default from config")
    s.add_argument("--pose-action", default=None, help="Generate a posepack for this action and attach/patch it when workflow supports pose input")
    s.add_argument("--pose-direction", default=None)
    s.add_argument("--pose-frames", type=int, default=None)
    s.add_argument("--pose-size", type=int, default=512)
    s.add_argument("--posepack", default=None, help="Existing posepack folder to attach/patch into a custom pose workflow")
    s.add_argument("--model", default=None)
    s.add_argument("--text-encoder", default=None)
    s.add_argument("--vae", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--video-fps", type=int, default=None)
    s.add_argument("--steps", type=int, default=None)
    s.add_argument("--cfg", type=float, default=None)
    s.add_argument("--shift", type=float, default=None)
    s.add_argument("--sampler", default=None)
    s.add_argument("--scheduler", default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output-prefix", default=None)
    s.add_argument("--resolutions", default=None)
    s.add_argument("--resolution-hierarchy", default=None)
    s.add_argument("--preview", action="store_true")
    s.add_argument("--style-image", default=None)
    s.add_argument("--batch-size", type=int, default=None, help="VRAM fallback hint for workflows with batch controls")
    s.add_argument("--vram-fallback", default=None, help="Internal retry hint: fp8, batch, resolution, or cpu_offload")
    s.add_argument("--cpu-offload", default=None, help="Internal retry hint for CPU/offload mode")


def add_parsers(sub: argparse._SubParsersAction) -> None:
    import spriteforge_unified_parser

    s = sub.add_parser("submit-wan", help="Submit the included native Wan 2.1 T2V API workflow to a running ComfyUI server")
    add_wan_args(s)
    s.set_defaults(func=cmd_submit_wan)

    s = sub.add_parser("generate-sprite", help="Submit Wan job, wait for exact ComfyUI history output, then convert to spritesheet")
    add_wan_args(s)
    s.add_argument("--start-comfy", action="store_true")
    s.add_argument("--stop-comfy", action="store_true")
    s.add_argument("--timeout", type=float, default=3600)
    s.add_argument("--comfy-timeout", type=float, default=180)
    s.add_argument("--poll-seconds", type=float, default=5)
    s.add_argument("--stable-seconds", type=float, default=5)
    s.add_argument("--no-history", action="store_true", help="Skip prompt_id /history tracking and use folder scan only")
    s.add_argument("--no-folder-fallback", action="store_true", help="Fail if prompt history does not resolve a usable output")
    s.add_argument("--quality-check", action="store_true", help="Run SpriteForge QC after converting the generated video")
    s.add_argument("--cell-size", default=None)
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--qa-threshold-loop-rmse", type=float, default=None)
    s.add_argument("--qa-threshold-foot-drift", type=float, default=None)
    s.add_argument("--qa-threshold-center-drift", type=float, default=None)
    s.add_argument("--power-of-two", action="store_true", help="Pad final sheet to power-of-two dimensions")
    add_sprite_polish_args(s, defaults=False)
    s.set_defaults(pack_mode="grid")
    s.add_argument("--lora-name", default=None, help="Filename of the LoRA model to load, e.g. wan2.2_pixel_animate.safetensors")
    s.add_argument("--output", default=None, help="Sprite output directory. Defaults to output/wan_sprite_<timestamp>.")
    s.add_argument("--native-only", action="store_true", help="Require native in-app backend only. Fail instead of using external ComfyUI runtime.")
    s.add_argument("--native-source-video", default=None, help="Use native in-app conversion from an existing source video instead of WAN generation.")
    s.set_defaults(func=cmd_generate_sprite)

    s = sub.add_parser("generate-batch", help="Generate multiple sprite actions and/or directions sequentially")
    add_wan_args(s)
    s.add_argument("--actions", default=None, help="Comma-separated actions to generate")
    s.add_argument("--directions", default=None, help="Comma-separated directions, or all")
    s.add_argument("--start-comfy", action="store_true")
    s.add_argument("--stop-comfy", action="store_true")
    s.add_argument("--timeout", type=float, default=3600)
    s.add_argument("--comfy-timeout", type=float, default=180)
    s.add_argument("--poll-seconds", type=float, default=5)
    s.add_argument("--stable-seconds", type=float, default=5)
    s.add_argument("--no-history", action="store_true")
    s.add_argument("--no-folder-fallback", action="store_true")
    s.add_argument("--quality-check", action="store_true")
    s.add_argument("--cell-size", default=None)
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--qa-threshold-loop-rmse", type=float, default=None)
    s.add_argument("--qa-threshold-foot-drift", type=float, default=None)
    s.add_argument("--qa-threshold-center-drift", type=float, default=None)
    s.add_argument("--power-of-two", action="store_true")
    add_sprite_polish_args(s, defaults=False)
    s.set_defaults(pack_mode="grid")
    s.add_argument("--lora-name", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--native-only", action="store_true")
    s.add_argument("--native-source-video", default=None)

    def _generate_batch(a):
        actions = _csv_values(a.actions, [a.action or "idle"])
        directions = _expand_directions(a.directions, [a.direction or "right"])
        base_output = str(a.output or "").strip()
        base_prefix = str(a.output_prefix or "").strip()
        for action in actions:
            for direction in directions:
                item = argparse.Namespace(**vars(a))
                item.action = action
                item.direction = direction
                if base_output:
                    stem = Path(base_output)
                    item.output = str(stem.parent / f"{stem.name}_{action}_{direction}")
                if base_prefix:
                    item.output_prefix = f"{base_prefix}_{action}_{direction}"
                print(f"Generating {action} / {direction}")
                cmd_generate_sprite(item)

    s.set_defaults(func=_generate_batch)

    s = sub.add_parser("watch-output", help="Watch ComfyUI output and convert new videos into sprites")
    s.add_argument("--folder", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--pattern", default="*.webm")
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--key-tolerance", type=float, default=None)
    s.add_argument("--anchor", default=None)
    s.add_argument("--pad", type=int, default=None)
    s.add_argument("--solidify", type=int, default=None)
    s.set_defaults(func=cmd_watch_output)

    s = sub.add_parser("convert-video", help="Convert one existing video to sprites")
    s.add_argument("--input", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_convert_video)

    s = sub.add_parser("cloud-image-sprite", help="Generate/process cloud image frames into an engine-ready spritesheet")
    s.add_argument("--prompt", required=True)
    s.add_argument("--provider", choices=["openai", "gemini"], default="openai")
    s.add_argument("--model", default=None)
    s.add_argument("--source-image", action="append", default=[], help="Use an existing cloud output PNG instead of calling an API.")
    s.add_argument("--frame-prompt", action="append", default=[], help="Optional per-frame pose suffix.")
    s.add_argument("--frames", type=int, default=1)
    s.add_argument("--size", default="1024x1024")
    s.add_argument("--cell-size", default="64x64")
    s.add_argument("--key-color", default="#ff00ff")
    s.add_argument("--palette-colors", type=int, default=24)
    s.add_argument("--no-palette-cleanup", action="store_true")
    s.add_argument("--columns", type=int, default=None)
    s.add_argument("--fps", type=float, default=12.0)
    s.add_argument("--animation", default="cloud_sprite")
    s.add_argument("--constraints", default=None)
    s.add_argument("--negative", default=None)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_cloud_image_sprite)

    s = sub.add_parser("build-prompt", help="Build a sprite-action prompt without running WAN")
    s.add_argument("--action", required=True)
    s.add_argument("--direction", default="right")
    s.add_argument("--character", default=None)
    s.add_argument("--style", default=None)
    s.add_argument("--background", default=None)
    s.add_argument("--extra", default="")
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_prompts.py"), "build", "--action", a.action, "--direction", a.direction] + (["--character", a.character] if a.character else []) + (["--style", a.style] if a.style else []) + (["--background", a.background] if a.background else []) + (["--extra", a.extra] if a.extra else []) + (["--reference"] if a.reference else []) + (["--pose-guided"] if a.pose_guided else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("make-posepack", help="Generate OpenPose-style guide frames for a sprite action")
    s.add_argument("--action", required=True)
    s.add_argument("--direction", default="right")
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--size", type=int, default=512)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_prompts.py"), "posepack", "--action", a.action, "--direction", a.direction, "--size", str(a.size)] + (["--frames", str(a.frames)] if a.frames else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("cloud-package", help="Package a GPU cloud job bundle")
    s.add_argument("--prompt", required=True)
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="quality_local")
    s.add_argument("--reference-image", default=None)
    s.add_argument("--posepack", default=None)
    s.add_argument("--workflow", default=None)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_cloud.py"), "package", "--prompt", a.prompt, "--mode", a.mode, "--profile", a.profile] + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--posepack", a.posepack] if a.posepack else []) + (["--workflow", a.workflow] if a.workflow else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("cloud-plan", help="Write a cloud GPU setup plan without storing API keys")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_cloud.py"), "runpod-plan"] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("remote-generate", help="Submit to a remote ComfyUI server, download exact output, and optionally convert to sprite locally")
    s.add_argument("--server", default=None, help="Explicit ComfyUI server URL; overrides cloud hub node selection")
    s.add_argument("--cloud-node", default="", help="Optional configured cloud hub node id to use when --server is omitted")
    s.add_argument("--workflow", required=True)
    s.add_argument("--prompt", required=True)
    s.add_argument("--negative", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--video-fps", type=int, default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output-prefix", default="SpriteForge/remote_sprite")
    s.add_argument("--output", default=None)
    s.add_argument("--timeout", type=float, default=7200)
    s.add_argument("--convert", action="store_true")
    s.add_argument("--cell-size", default="512x512")
    s.add_argument("--key-color", default="auto")
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=spriteforge_unified_parser.cmd_remote_generate)
