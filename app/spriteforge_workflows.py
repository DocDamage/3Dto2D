#!/usr/bin/env python3
"""ComfyUI workflow slot mapper and patcher for SpriteForge.

This reduces brittleness by inspecting exported API workflows and writing a mapping
of likely prompt/model/seed/size/reference/video-output fields.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

NEGATIVE_HINTS = ["bad", "negative", "deformed", "worst", "low quality", "watermark", "text", "extra limbs"]
POSITIVE_HINTS = ["masterpiece", "character", "sprite", "walking", "full body", "best quality"]


def load_workflow(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_nodes(wf: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    for k, v in wf.items():
        if str(k).startswith("_") or not isinstance(v, dict):
            continue
        yield str(k), v


def text_score(text: str, hints: Sequence[str]) -> int:
    t = text.lower()
    return sum(1 for h in hints if h in t)


def input_ref(node_id: str, input_name: str) -> str:
    return f"{node_id}.inputs.{input_name}"


def add_slot(slots: Dict[str, Any], group: str, ref: str, value: Any, class_type: str, confidence: str, note: str = "") -> None:
    slots.setdefault(group, []).append({
        "ref": ref,
        "current": value,
        "class_type": class_type,
        "confidence": confidence,
        "note": note,
    })


def detect_slots(wf: Dict[str, Any]) -> Dict[str, Any]:
    slots: Dict[str, Any] = {
        "positive_prompt": [],
        "negative_prompt": [],
        "seed": [],
        "steps": [],
        "cfg": [],
        "sampler": [],
        "scheduler": [],
        "width": [],
        "height": [],
        "frames": [],
        "fps": [],
        "model": [],
        "text_encoder": [],
        "vae": [],
        "clip_vision": [],
        "reference_image": [],
        "pose_input": [],
        "output_prefix": [],
        "video_output": [],
    }

    clip_nodes = []
    for nid, node in iter_nodes(wf):
        cls = str(node.get("class_type", ""))
        inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}

        if cls == "CLIPTextEncode" or ("text" in inputs and "clip" in inputs):
            txt = str(inputs.get("text", ""))
            clip_nodes.append((nid, cls, txt, text_score(txt, POSITIVE_HINTS), text_score(txt, NEGATIVE_HINTS)))

        for key, val in inputs.items():
            lk = key.lower()
            lcls = cls.lower()
            ref = input_ref(nid, key)
            if lk in {"seed", "noise_seed"}:
                add_slot(slots, "seed", ref, val, cls, "high")
            elif lk == "steps":
                add_slot(slots, "steps", ref, val, cls, "high")
            elif lk in {"cfg", "guidance_scale"}:
                add_slot(slots, "cfg", ref, val, cls, "high")
            elif lk in {"sampler", "sampler_name"}:
                add_slot(slots, "sampler", ref, val, cls, "high")
            elif lk == "scheduler":
                add_slot(slots, "scheduler", ref, val, cls, "high")
            elif lk == "width":
                add_slot(slots, "width", ref, val, cls, "high" if "latent" in lcls or "video" in lcls else "medium")
            elif lk == "height":
                add_slot(slots, "height", ref, val, cls, "high" if "latent" in lcls or "video" in lcls else "medium")
            elif lk in {"length", "frames", "num_frames", "video_length"}:
                add_slot(slots, "frames", ref, val, cls, "high")
            elif lk in {"fps", "frame_rate"}:
                add_slot(slots, "fps", ref, val, cls, "high")
            elif lk in {"unet_name", "model_name", "ckpt_name"} and "loader" in lcls:
                add_slot(slots, "model", ref, val, cls, "high")
            elif lk in {"clip_name", "text_encoder_name"} and "loader" in lcls:
                add_slot(slots, "text_encoder", ref, val, cls, "high")
            elif lk in {"vae_name"}:
                add_slot(slots, "vae", ref, val, cls, "high")
            elif "clip" in lk and "vision" in (lk + lcls):
                add_slot(slots, "clip_vision", ref, val, cls, "medium")
            elif lk in {"image", "start_image", "end_image", "reference_image"}:
                conf = "high" if "loadimage" in lcls or "image" in lcls else "medium"
                add_slot(slots, "reference_image", ref, val, cls, conf)
            elif any(tok in lk for tok in ["pose", "openpose", "directory", "folder", "video", "path", "frame_dir"]):
                if any(tok in lcls + lk for tok in ["pose", "openpose", "control", "video", "vhs"]):
                    add_slot(slots, "pose_input", ref, val, cls, "medium")
            elif lk in {"filename_prefix", "filename", "prefix"}:
                conf = "high" if any(tok in lcls for tok in ["save", "video", "webm", "vhs"]) else "medium"
                add_slot(slots, "output_prefix", ref, val, cls, conf)

        if any(tok in cls.lower() for tok in ["savewebm", "videocombine", "saveanimated", "vhs_video"]):
            add_slot(slots, "video_output", nid, cls, cls, "high", "video/image save node")

    # Choose positive/negative prompt candidates from CLIPTextEncode nodes.
    if clip_nodes:
        neg_sorted = sorted(clip_nodes, key=lambda x: (x[4], -x[3]), reverse=True)
        pos_sorted = sorted(clip_nodes, key=lambda x: (x[3], -x[4]), reverse=True)
        neg_id = neg_sorted[0][0] if neg_sorted and neg_sorted[0][4] > 0 else None
        pos_id = pos_sorted[0][0] if pos_sorted else clip_nodes[0][0]
        if neg_id == pos_id and len(clip_nodes) > 1:
            pos_id = [x[0] for x in clip_nodes if x[0] != neg_id][0]
        for nid, cls, txt, ps, ns in clip_nodes:
            if nid == pos_id:
                add_slot(slots, "positive_prompt", input_ref(nid, "text"), txt, cls, "high", f"positive_score={ps} negative_score={ns}")
            elif nid == neg_id or (neg_id is None and nid != pos_id and len(slots["negative_prompt"]) == 0):
                add_slot(slots, "negative_prompt", input_ref(nid, "text"), txt, cls, "high" if neg_id == nid else "medium", f"positive_score={ps} negative_score={ns}")
            else:
                # Keep extra text encodes visible but lower confidence.
                add_slot(slots, "positive_prompt", input_ref(nid, "text"), txt, cls, "low", f"extra text node positive_score={ps} negative_score={ns}")

    preferred = {}
    for group, items in slots.items():
        if isinstance(items, list) and items:
            # high-confidence first, then shortest node id path.
            order = {"high": 0, "medium": 1, "low": 2}
            preferred[group] = sorted(items, key=lambda x: (order.get(x.get("confidence", "low"), 3), x.get("ref", "")))[0]
    return {"slots": slots, "preferred": preferred}


def set_ref(wf: Dict[str, Any], ref: str, value: Any) -> bool:
    # ref format: node.inputs.key
    parts = ref.split(".")
    if len(parts) != 3 or parts[1] != "inputs":
        return False
    nid, _inputs, key = parts
    if nid not in wf or not isinstance(wf[nid], dict):
        return False
    wf[nid].setdefault("inputs", {})[key] = value
    return True


def patch_workflow(wf: Dict[str, Any], mapping: Dict[str, Any], values: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    out = json.loads(json.dumps(wf))
    preferred = mapping.get("preferred", mapping)
    results: Dict[str, bool] = {}
    for key, value in values.items():
        if value is None:
            continue
        slot = preferred.get(key)
        if isinstance(slot, dict) and slot.get("ref"):
            results[key] = set_ref(out, slot["ref"], value)
        else:
            results[key] = False
    return out, results


def cmd_slots(args: argparse.Namespace) -> None:
    path = Path(args.workflow)
    wf = load_workflow(path)
    mapping = detect_slots(wf)
    out = Path(args.output) if args.output else path.with_suffix(".slots.json")
    out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Workflow slots: {out}")
    for group, slot in mapping.get("preferred", {}).items():
        print(f"{group}: {slot.get('ref')} [{slot.get('confidence')}] {slot.get('class_type')}")


def cmd_patch(args: argparse.Namespace) -> None:
    wf_path = Path(args.workflow)
    wf = load_workflow(wf_path)
    if args.mapping:
        mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    else:
        mapping = detect_slots(wf)
    seed = args.seed
    if seed is not None and seed < 0:
        seed = random.randint(1, 2**48 - 1)
    values = {
        "positive_prompt": args.prompt,
        "negative_prompt": args.negative,
        "seed": seed,
        "steps": args.steps,
        "cfg": args.cfg,
        "sampler": args.sampler,
        "scheduler": args.scheduler,
        "width": args.width,
        "height": args.height,
        "frames": args.frames,
        "fps": args.fps,
        "output_prefix": args.output_prefix,
        "reference_image": args.reference_image,
        "model": args.model,
        "text_encoder": args.text_encoder,
        "vae": args.vae,
        "clip_vision": args.clip_vision,
    }
    patched, results = patch_workflow(wf, mapping, values)
    if args.dry_run:
        print(json.dumps(results, indent=2))
        return
    out = Path(args.output) if args.output else wf_path.with_name(wf_path.stem + "_patched.json")
    out.write_text(json.dumps(patched, indent=2), encoding="utf-8")
    print(f"Patched workflow: {out}")
    print(json.dumps(results, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ComfyUI workflow slot mapper/patcher")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("slots", help="Inspect an exported ComfyUI API workflow")
    s.add_argument("--workflow", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_slots)

    s = sub.add_parser("patch", help="Patch an exported ComfyUI API workflow using detected or saved slots")
    s.add_argument("--workflow", required=True)
    s.add_argument("--mapping", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--prompt", default=None)
    s.add_argument("--negative", default=None)
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--steps", type=int, default=None)
    s.add_argument("--cfg", type=float, default=None)
    s.add_argument("--sampler", default=None)
    s.add_argument("--scheduler", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--fps", type=int, default=None)
    s.add_argument("--output-prefix", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--text-encoder", default=None)
    s.add_argument("--vae", default=None)
    s.add_argument("--clip-vision", default=None)
    s.set_defaults(func=cmd_patch)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
