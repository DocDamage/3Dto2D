#!/usr/bin/env python3
"""WAN video generation service: prompt submission, output watching, history polling, sprite conversion."""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from . import comfy_workflow_service as wf_svc
    from . import model_install_service as model_svc
    from . import shell_service as shell
except ImportError:
    import comfy_workflow_service as wf_svc  # type: ignore
    import model_install_service as model_svc  # type: ignore
    import shell_service as shell  # type: ignore


ROOT = Path(__file__).resolve().parent.parent
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def api_get(url: str, timeout: float = 5.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
        try:
            return json.loads(data)
        except Exception:
            return data


def api_post_json(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode("utf-8")
        return json.loads(txt) if txt else {}


def is_comfy_running(cfg: dict) -> bool:
    try:
        api_get(cfg.base_url + "/system_stats", timeout=2.0)
        return True
    except Exception:
        return False


def wait_for_comfy(cfg: dict, timeout: float = 180.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_comfy_running(cfg):
            return True
        time.sleep(2)
    return False


def spriteforge_prompt_from_args(args: Any) -> Optional[Dict[str, Any]]:
    action = getattr(args, "action", None)
    if not action:
        return None
    try:
        import spriteforge_prompts as prompts  # type: ignore
        return prompts.build_prompt(
            action=action,
            direction=getattr(args, "direction", "right") or "right",
            character=getattr(args, "character", None) or prompts.DEFAULT_CHARACTER,
            style=getattr(args, "style", None) or prompts.DEFAULT_STYLE,
            background=getattr(args, "background", None) or prompts.DEFAULT_BACKGROUND,
            extra=getattr(args, "extra_prompt", None) or "",
            reference=bool(getattr(args, "reference_image", None)),
            pose_guided=bool(getattr(args, "pose_action", None) or getattr(args, "posepack", None)),
        )
    except Exception as exc:
        print(f"Could not build action prompt: {exc}")
        return None


def maybe_create_posepack(args: Any) -> Optional[Path]:
    if getattr(args, "posepack", None):
        return Path(args.posepack).resolve()
    action = getattr(args, "pose_action", None)
    if not action:
        return None
    try:
        import spriteforge_prompts as prompts  # type: ignore
        spec = prompts.ACTION_TEMPLATES.get(action, {})
        frames = int(getattr(args, "pose_frames", None) or getattr(args, "frames", None) or spec.get("frames", 24))
        direction = getattr(args, "pose_direction", None) or getattr(args, "direction", "right") or "right"
        out = ROOT / "output" / "posepacks" / f"{action}_{direction}_{time.strftime('%Y%m%d_%H%M%S')}"
        prompts.make_posepack(action, direction, frames, int(getattr(args, "pose_size", 512) or 512), out)
        print(f"Posepack created: {out}")
        return out
    except Exception as exc:
        print(f"Could not create posepack: {exc}")
        return None


def patch_wan_workflow(prompt: Dict[str, Any], args: Any, cfg: dict) -> Dict[str, Any]:
    out = json.loads(json.dumps(prompt))
    requested_mode = getattr(args, "mode", "auto") or "auto"
    wd = model_svc.merged_wan_defaults(cfg, getattr(args, "profile", None), mode=requested_mode, tier=getattr(args, "tier", None))
    mode = wd.get("mode") or ("t2v" if requested_mode == "auto" else requested_mode)

    prompt_pack = spriteforge_prompt_from_args(args)
    positive = args.prompt or (prompt_pack or {}).get("positive") or (
        "single full body original game character walking cycle, professional appealing character design, heroic adult proportions, "
        "clear readable face, distinctive outfit, strong shape language, cohesive color palette, side view, locked orthographic camera, "
        "centered, full body visible, plain bright green background, high quality 2D game sprite animation, crisp cel-shaded edges, clean silhouette"
    )
    negative = args.negative or (prompt_pack or {}).get("negative") or (
        "camera movement, zoom, cuts, close up, motion blur, changing outfit, changing identity, complex background, text, subtitles, "
        "watermark, deformed body, extra limbs, missing limbs, bad anatomy, childlike drawing, amateur doodle, crude sketch, scribbles, "
        "messy linework, ugly face, melted face, lumpy body, shapeless outfit, muddy colors, low quality"
    )

    pos_inputs, neg_inputs = wf_svc.clip_text_nodes(out)
    pos_inputs["text"] = positive
    neg_inputs["text"] = negative

    _, unet = wf_svc.node_inputs_by_id_or_class(out, "37", ["UNETLoader", "UNETLoaderGGUF"])
    wf_svc.set_input(unet, ["unet_name", "model_name", "ckpt_name"], args.model or wd.get("model", "wan2.1_t2v_1.3B_fp16.safetensors"))

    _, clip = wf_svc.node_inputs_by_id_or_class(out, "38", ["CLIPLoader", "DualCLIPLoader", "WanTextEncoderLoader"])
    wf_svc.set_input(clip, ["clip_name", "text_encoder_name", "model_name"], args.text_encoder or wd.get("text_encoder", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"))

    _, vae = wf_svc.node_inputs_by_id_or_class(out, "39", ["VAELoader"])
    wf_svc.set_input(vae, ["vae_name"], args.vae or wd.get("vae", "wan_2.1_vae.safetensors"))

    try:
        _, latent = wf_svc.node_inputs_by_id_or_class(out, "40", ["EmptyHunyuanLatentVideo", "Wan22ImageToVideoLatent", "EmptyWanVideoLatent", "EmptyLatentVideo", "EmptyLatentImage"])
    except KeyError:
        _, latent = wf_svc.node_inputs_by_id_or_class(out, "50", ["Wan22ImageToVideoLatent", "WanImageToVideo", "WanVaceToVideo", "WanReferenceToVideo"])
    wf_svc.set_input(latent, ["width"], int(args.width or wd.get("width", 832)))
    wf_svc.set_input(latent, ["height"], int(args.height or wd.get("height", 480)))
    if getattr(args, "preview", False):
        wf_svc.set_input(latent, ["length", "frames", "num_frames", "video_length"], 1)
    else:
        wf_svc.set_input(latent, ["length", "frames", "num_frames", "video_length"], int(args.frames or wd.get("frames", 33)))
    wf_svc.set_input(latent, ["batch_size"], 1)

    staged_reference = None
    staged_style = None
    if getattr(args, "reference_image", None):
        staged_reference = model_svc.stage_file_to_comfy_input(cfg, args.reference_image)
    if getattr(args, "style_image", None):
        staged_style = model_svc.stage_file_to_comfy_input(cfg, args.style_image)

    if staged_reference or staged_style:
        ref_patched, style_patched = wf_svc.patch_workflow_images(out, staged_reference, staged_style)
        print(f"Workflow image patching results: main reference patched = {ref_patched}, style reference patched = {style_patched}")

    clip_vision_name = getattr(args, "clip_vision", None) or wd.get("clip_vision")
    patched_clip_vision = wf_svc.patch_clip_vision_nodes(out, clip_vision_name)
    if patched_clip_vision:
        print(f"Patched CLIP vision nodes: {patched_clip_vision} -> {clip_vision_name}")

    posepack_path = maybe_create_posepack(args)
    patched_pose = 0
    if posepack_path:
        patched_pose = wf_svc.patch_posepack_nodes(out, str(posepack_path))
        print(f"Posepack available: {posepack_path} (patched {patched_pose} workflow fields)")

    seed = int(args.seed)
    if seed < 0:
        seed = random.randint(1, 2**48 - 1)
    _, sampler = wf_svc.node_inputs_by_id_or_class(out, "3", ["KSampler", "KSamplerAdvanced"])
    wf_svc.set_input(sampler, ["seed", "noise_seed"], seed)
    steps = int(args.steps or wd.get("steps", 30))
    if getattr(args, "preview", False):
        steps = min(steps, 10)
    wf_svc.set_input(sampler, ["steps"], steps)
    wf_svc.set_input(sampler, ["cfg", "guidance_scale"], float(args.cfg or wd.get("cfg", 6)))
    wf_svc.set_input(sampler, ["sampler_name", "sampler"], args.sampler or wd.get("sampler", "uni_pc"))
    wf_svc.set_input(sampler, ["scheduler"], args.scheduler or wd.get("scheduler", "simple"))

    try:
        _, sampling = wf_svc.node_inputs_by_id_or_class(out, "48", ["ModelSamplingSD3", "ModelSamplingAuraFlow", "ModelSamplingFlux"])
        wf_svc.set_input(sampling, ["shift"], float(args.shift or wd.get("shift", 8)))
    except KeyError:
        pass

    save_id, save = wf_svc.node_inputs_by_id_or_class(out, "47", ["SaveWEBM", "SaveVideo", "VHS_VideoCombine", "VideoCombine", "SaveAnimatedWEBP", "SaveImage"])
    prefix = args.output_prefix or wd.get("output_prefix", "SpriteForge/wan_sprite")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    prefix = prefix.rstrip("/") + f"_{stamp}"
    wf_svc.set_input(save, ["filename_prefix", "filename", "prefix"], prefix)
    wf_svc.set_input(save, ["fps", "frame_rate"], int(args.video_fps or wd.get("fps", 12)))

    out["_spriteforge"] = {
        "generated_at": stamp,
        "output_prefix": prefix,
        "seed": seed,
        "profile": wd.get("profile") or getattr(args, "profile", None),
        "model_tier": wd.get("model_tier") or getattr(args, "tier", None),
        "model_tier_label": wd.get("model_tier_label"),
        "mode": mode,
        "action": getattr(args, "action", None),
        "direction": getattr(args, "direction", None),
        "reference_image": staged_reference,
        "posepack": str(posepack_path) if posepack_path else None,
        "pose_nodes_patched": patched_pose if posepack_path else 0,
        "save_node": save_id,
        "workflow_patch_version": 11,
    }
    return out


def submit_prompt(cfg: dict, prompt: Dict[str, Any], client_id: Optional[str] = None) -> Any:
    payload: Dict[str, Any] = {"prompt": {k: v for k, v in prompt.items() if not str(k).startswith("_")}}
    if client_id:
        payload["client_id"] = client_id
    return api_post_json(cfg.base_url + "/prompt", payload, timeout=60.0)


def queue_wan_prompt(args: Any, cfg: dict) -> Tuple[Dict[str, Any], Dict[str, Any], Path]:
    workflow_path = model_svc.workflow_resolve(
        args.workflow, cfg,
        profile=getattr(args, "profile", None),
        mode=getattr(args, "mode", "auto"),
        tier=getattr(args, "tier", None)
    )
    prompt = json.loads(workflow_path.read_text(encoding="utf-8"))
    patched = patch_wan_workflow(prompt, args, cfg)

    queued_dir = ROOT / "output" / "queued_workflows"
    queued_dir.mkdir(parents=True, exist_ok=True)
    queued_path = queued_dir / f"wan_api_{time.strftime('%Y%m%d_%H%M%S')}.json"
    queued_path.write_text(json.dumps(patched, indent=2), encoding="utf-8")
    print(f"Saved patched API workflow: {queued_path}")

    resp = submit_prompt(cfg, patched, client_id=f"spriteforge-{os.getpid()}")
    prompt_id = resp.get("prompt_id") if isinstance(resp, dict) else None
    print("Queued ComfyUI prompt:")
    print(json.dumps(resp, indent=2))
    print(f"Output prefix: {patched.get('_spriteforge', {}).get('output_prefix')}")
    if prompt_id:
        print(f"Prompt ID: {prompt_id}")
    return resp, patched, queued_path


def history_entry(cfg: dict, prompt_id: str) -> Optional[Dict[str, Any]]:
    url = cfg.base_url + "/history/" + urllib.parse.quote(prompt_id)
    data = api_get(url, timeout=10)
    if isinstance(data, dict):
        if prompt_id in data:
            return data[prompt_id]
        if "outputs" in data or "status" in data:
            return data
    return None


def wait_for_history(cfg: dict, prompt_id: str, timeout: float, poll_seconds: float) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last_status = "queued"
    while time.time() < deadline:
        entry = history_entry(cfg, prompt_id)
        if entry:
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = str(status.get("status_str", "")).lower()
            completed = bool(status.get("completed"))
            if status_str and status_str != last_status:
                print(f"ComfyUI status: {status_str}")
                last_status = status_str
            if completed or status_str in {"success", "completed"} or entry.get("outputs"):
                if status_str in {"error", "failed"}:
                    raise RuntimeError(f"ComfyUI prompt failed: {json.dumps(status, indent=2)}")
                return entry
            if status_str in {"error", "failed"}:
                raise RuntimeError(f"ComfyUI prompt failed: {json.dumps(status, indent=2)}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Prompt {prompt_id} was not completed before timeout.")


def recursive_file_records(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        if "filename" in obj and isinstance(obj.get("filename"), str):
            yield obj
        for v in obj.values():
            yield from recursive_file_records(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from recursive_file_records(v)


def resolve_comfy_record(cfg: dict, rec: Dict[str, Any]) -> Path:
    typ = str(rec.get("type", "output")).lower()
    if typ == "input":
        base = cfg.comfy_input
    elif typ == "temp":
        base = cfg.comfy_temp
    else:
        base = cfg.comfy_output
    sub = str(rec.get("subfolder") or "")
    return base / sub / str(rec["filename"])


def output_files_from_history(cfg: dict, entry: Dict[str, Any]) -> List[Path]:
    paths: List[Path] = []
    for rec in recursive_file_records(entry.get("outputs", entry)):
        p = resolve_comfy_record(cfg, rec)
        if p.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS:
            paths.append(p)
    seen = set()
    deduped = []
    for p in paths:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def stable_file(path: Path, stable_seconds: float) -> bool:
    try:
        s1 = path.stat().st_size
        time.sleep(stable_seconds)
        s2 = path.stat().st_size
        return s1 > 0 and s1 == s2
    except FileNotFoundError:
        return False


def wait_for_existing_output(paths: Sequence[Path], stable_seconds: float, timeout: float = 120.0) -> Optional[Path]:
    deadline = time.time() + timeout
    videos = [p for p in paths if p.suffix.lower() in VIDEO_EXTS]
    images = [p for p in paths if p.suffix.lower() in IMAGE_EXTS]
    candidates = videos or images
    while time.time() < deadline:
        for p in candidates:
            if p.exists() and stable_file(p, stable_seconds):
                return p
        time.sleep(2)
    return None


def find_newest_video(folder: Path, after_time: float, prefix_hint: Optional[str] = None) -> Optional[Path]:
    if not folder.exists():
        return None
    candidates = []
    hint = Path(prefix_hint).name.lower() if prefix_hint else None
    for p in folder.rglob("*"):
        if p.suffix.lower() not in VIDEO_EXTS:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_mtime < after_time:
            continue
        rank = 1
        if hint and hint not in p.stem.lower():
            rank = 0
        candidates.append((rank, st.st_mtime, p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def build_sprite_args(input_video: Path, output_dir: Path, cfg: dict, extra: Optional[List[str]] = None) -> List[str]:
    sd = cfg.raw.get("sprite_defaults", {})
    cmd = [sys.executable, str(ROOT / "spriteforge.py"), "video", "--input", str(input_video), "--output", str(output_dir)]
    cmd += ["--fps", str(sd.get("fps", 12))]
    if sd.get("cell_size"):
        cmd += ["--cell-size", str(sd.get("cell_size"))]
    if sd.get("key_color"):
        cmd += ["--key-color", str(sd.get("key_color"))]
    cmd += ["--key-tolerance", str(sd.get("key_tolerance", 45))]
    cmd += ["--anchor", str(sd.get("anchor", "bottom-center"))]
    cmd += ["--pad", str(sd.get("pad", 24))]
    cmd += ["--solidify", str(sd.get("solidify", 2))]
    if sd.get("drop_loop_duplicate", True):
        cmd += ["--drop-loop-duplicate"]
    if sd.get("preview_gif", True):
        cmd += ["--preview-gif"]
    if sd.get("report", True):
        cmd += ["--report"]
    if extra:
        cmd += extra
    return cmd


def write_run_manifest(prompt_id: Optional[str], patched: Dict[str, Any], response: Dict[str, Any],
                       outputs: Sequence[Path], chosen: Optional[Path], sprite_dir: Optional[Path]) -> Path:
    runs_dir = ROOT / "output" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stem = prompt_id or time.strftime("%Y%m%d_%H%M%S")
    path = runs_dir / f"run_{stem}.json"
    data = {
        "prompt_id": prompt_id,
        "response": response,
        "spriteforge": patched.get("_spriteforge", {}),
        "history_outputs": [str(p) for p in outputs],
        "chosen_output": str(chosen) if chosen else None,
        "sprite_dir": str(sprite_dir) if sprite_dir else None,
        "written_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path