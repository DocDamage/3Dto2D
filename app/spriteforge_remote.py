#!/usr/bin/env python3
"""Remote ComfyUI runner for SpriteForge Studio.

This talks to a ComfyUI instance exposed over HTTP, submits an exported API workflow,
waits on /history, downloads the exact output video/image via /view, and optionally
runs SpriteForge conversion locally.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def api_get_json(base_url: str, endpoint: str, timeout: float = 10.0) -> Any:
    url = base_url.rstrip("/") + endpoint
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post_json(base_url: str, endpoint: str, payload: Dict[str, Any], timeout: float = 60.0) -> Any:
    url = base_url.rstrip("/") + endpoint
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode("utf-8")
        return json.loads(txt) if txt else {}


def set_clip_prompts(workflow: Dict[str, Any], positive: Optional[str], negative: Optional[str]) -> None:
    nodes = []
    for k, v in workflow.items():
        if isinstance(v, dict) and v.get("class_type") == "CLIPTextEncode":
            nodes.append((str(k), v.setdefault("inputs", {})))
    nodes.sort(key=lambda kv: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", kv[0])])
    if positive and nodes:
        nodes[0][1]["text"] = positive
    if negative and len(nodes) > 1:
        nodes[1][1]["text"] = negative


def set_seed(workflow: Dict[str, Any], seed: int) -> int:
    count = 0
    if seed < 0:
        seed = random.randint(1, 2**48 - 1)
    for v in workflow.values():
        if isinstance(v, dict):
            inputs = v.setdefault("inputs", {})
            for key in ["seed", "noise_seed"]:
                if key in inputs:
                    inputs[key] = seed
                    count += 1
    return seed


def patch_save_prefix(workflow: Dict[str, Any], prefix: str, fps: Optional[int]) -> None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    prefix = prefix.rstrip("/") + "_" + stamp
    for v in workflow.values():
        if not isinstance(v, dict):
            continue
        cls = str(v.get("class_type", ""))
        inputs = v.setdefault("inputs", {})
        if cls in {"SaveWEBM", "VHS_VideoCombine", "VideoCombine", "SaveAnimatedWEBP", "SaveImage"} or "filename_prefix" in inputs:
            for key in ["filename_prefix", "filename", "prefix"]:
                if key in inputs:
                    inputs[key] = prefix
            if fps:
                for key in ["fps", "frame_rate"]:
                    if key in inputs:
                        inputs[key] = fps
    workflow["_spriteforge"] = {"remote_output_prefix": prefix, "patched_at": stamp}


def patch_dimensions(workflow: Dict[str, Any], width: Optional[int], height: Optional[int], frames: Optional[int]) -> None:
    for v in workflow.values():
        if not isinstance(v, dict):
            continue
        inputs = v.setdefault("inputs", {})
        if width is not None and "width" in inputs:
            inputs["width"] = int(width)
        if height is not None and "height" in inputs:
            inputs["height"] = int(height)
        if frames is not None:
            for key in ["length", "frames", "num_frames", "video_length"]:
                if key in inputs:
                    inputs[key] = int(frames)


def multipart_upload_image(base_url: str, image_path: Path, subfolder: str = "SpriteForge", timeout: float = 120.0) -> str:
    """Upload image to ComfyUI /upload/image using a small urllib multipart implementation."""
    boundary = "----SpriteForgeBoundary" + uuid.uuid4().hex
    filename = image_path.name
    content_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    body = bytearray()

    def field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode())
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(image_path.read_bytes())
    body.extend(b"\r\n")
    field("type", "input")
    field("subfolder", subfolder)
    field("overwrite", "true")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        base_url.rstrip("/") + "/upload/image",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode("utf-8")
        try:
            data = json.loads(txt)
        except Exception:
            data = {}
    # Comfy LoadImage expects subfolder/name.
    return f"{subfolder}/{filename}".replace("\\", "/")


def patch_load_image(workflow: Dict[str, Any], image_name: str) -> int:
    count = 0
    for v in workflow.values():
        if not isinstance(v, dict):
            continue
        cls = str(v.get("class_type", ""))
        inputs = v.setdefault("inputs", {})
        if cls in {"LoadImage", "LoadImageMask", "LoadImageUpload"} or ("image" in inputs and isinstance(inputs.get("image"), str)):
            inputs["image"] = image_name
            if "upload" in inputs:
                inputs["upload"] = "image"
            count += 1
    return count


def submit_workflow(base_url: str, workflow: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"prompt": {k: v for k, v in workflow.items() if not str(k).startswith("_")}, "client_id": "spriteforge-remote-" + uuid.uuid4().hex}
    return api_post_json(base_url, "/prompt", payload, timeout=60)


def wait_history(base_url: str, prompt_id: str, timeout: float, poll: float) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            data = api_get_json(base_url, "/history/" + urllib.parse.quote(prompt_id), timeout=15)
            if isinstance(data, dict):
                if prompt_id in data:
                    return data[prompt_id]
                if "outputs" in data or "status" in data:
                    return data
        except Exception as exc:
            last = exc
        time.sleep(poll)
    raise TimeoutError(f"Timed out waiting for remote ComfyUI history for {prompt_id}. Last error: {last}")


def scan_file_records(obj: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if isinstance(obj, dict):
        if "filename" in obj:
            out.append({
                "filename": str(obj.get("filename")),
                "subfolder": str(obj.get("subfolder", "")),
                "type": str(obj.get("type", "output")),
            })
        for v in obj.values():
            out.extend(scan_file_records(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(scan_file_records(v))
    return out


def download_view(base_url: str, file_record: Dict[str, str], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    params = urllib.parse.urlencode({
        "filename": file_record["filename"],
        "subfolder": file_record.get("subfolder", ""),
        "type": file_record.get("type", "output"),
    })
    url = base_url.rstrip("/") + "/view?" + params
    local = out_dir / Path(file_record["filename"]).name
    with urllib.request.urlopen(url, timeout=300) as resp:
        local.write_bytes(resp.read())
    return local


def choose_video(records: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    for rec in records:
        if Path(rec["filename"]).suffix.lower() in VIDEO_EXTS:
            return rec
    for rec in records:
        if Path(rec["filename"]).suffix.lower() in IMAGE_EXTS:
            return rec
    return records[0] if records else None


def convert_local(path: Path, output_dir: Path, fps: int, cell_size: str, key_color: str, extra: List[str]) -> None:
    if path.suffix.lower() not in VIDEO_EXTS:
        print(f"Downloaded output is not a video; skipping SpriteForge conversion: {path}")
        return
    cmd = [sys.executable, str(ROOT / "spriteforge.py"), "video", "--input", str(path), "--output", str(output_dir), "--fps", str(fps), "--cell-size", cell_size, "--key-color", key_color, "--anchor", "bottom-center", "--solidify", "2", "--drop-loop-duplicate", "--preview-gif", "--report"] + extra
    print("$ " + " ".join(cmd))
    subprocess.check_call(cmd)


def cmd_generate(args: argparse.Namespace) -> None:
    base = args.server.rstrip("/")
    try:
        stats = api_get_json(base, "/system_stats", timeout=10)
        print("Remote ComfyUI is reachable.")
    except Exception as exc:
        raise RuntimeError(f"Could not reach remote ComfyUI at {base}: {exc}")

    workflow = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    set_clip_prompts(workflow, args.prompt, args.negative)
    seed = set_seed(workflow, args.seed)
    patch_dimensions(workflow, args.width, args.height, args.frames)
    patch_save_prefix(workflow, args.output_prefix, args.video_fps)

    if args.reference_image:
        remote_name = multipart_upload_image(base, Path(args.reference_image).resolve(), subfolder=args.upload_subfolder)
        count = patch_load_image(workflow, remote_name)
        print(f"Uploaded reference image and patched {count} LoadImage-like nodes: {remote_name}")

    queued_dir = Path(args.output or (ROOT / "output" / "remote_runs" / time.strftime("%Y%m%d_%H%M%S"))).resolve()
    queued_dir.mkdir(parents=True, exist_ok=True)
    (queued_dir / "patched_remote_workflow.json").write_text(json.dumps(workflow, indent=2), encoding="utf-8")

    resp = submit_workflow(base, workflow)
    prompt_id = str(resp.get("prompt_id")) if isinstance(resp, dict) and resp.get("prompt_id") else ""
    if not prompt_id:
        raise RuntimeError(f"Remote ComfyUI did not return prompt_id: {resp}")
    print(f"Prompt ID: {prompt_id}")
    entry = wait_history(base, prompt_id, timeout=args.timeout, poll=args.poll_seconds)
    (queued_dir / "history.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    records = scan_file_records(entry.get("outputs", entry))
    (queued_dir / "output_records.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    if not records:
        raise RuntimeError("No downloadable output records found in remote history.")
    chosen = choose_video(records)
    assert chosen is not None
    downloaded = download_view(base, chosen, queued_dir / "downloads")
    print(f"Downloaded: {downloaded}")
    manifest = {"server": base, "prompt_id": prompt_id, "seed": seed, "chosen": chosen, "downloaded": str(downloaded), "all_records": records}
    (queued_dir / "remote_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if args.convert:
        convert_local(downloaded, queued_dir / (downloaded.stem + "_sprite"), args.sprite_fps, args.cell_size, args.key_color, args.extra or [])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Submit/download/convert jobs from a remote ComfyUI server")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("generate")
    s.add_argument("--server", required=True, help="Remote ComfyUI base URL, e.g. http://1.2.3.4:8188")
    s.add_argument("--workflow", required=True, help="Exported ComfyUI API workflow JSON")
    s.add_argument("--prompt", required=True)
    s.add_argument("--negative", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--upload-subfolder", default="SpriteForge")
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--video-fps", type=int, default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output-prefix", default="SpriteForge/remote_sprite")
    s.add_argument("--output", default=None)
    s.add_argument("--timeout", type=float, default=7200)
    s.add_argument("--poll-seconds", type=float, default=5)
    s.add_argument("--convert", action="store_true")
    s.add_argument("--sprite-fps", type=int, default=12)
    s.add_argument("--cell-size", default="512x512")
    s.add_argument("--key-color", default="auto")
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_generate)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
