from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JobOutputEvent:
    progress_percent: Optional[float] = None
    stage: str = ""
    stage_label: str = ""
    stage_detail: str = ""
    stage_progress: Optional[float] = None
    prompt_id: str = ""
    source_video: str = ""
    sprite_output: str = ""
    oom_detected: bool = False


PROGRESS_PAT1 = re.compile(r"(\d+)%\s*\|")
PROGRESS_PAT2 = re.compile(r"(?:[Ss]tep|[Ss]teps|[Kk]sampler|progress)?[:\s]*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
PROGRESS_PAT3 = re.compile(r"(?:[Pp]rompt\s+)?progress[:\s]*(\d+)%", re.IGNORECASE)
PROMPT_ID_PAT = re.compile(r"prompt id[:\s]+([0-9a-fA-F-]+)", re.IGNORECASE)
SOURCE_VIDEO_PAT = re.compile(r"^(?:Source|Resolved|Chosen)\s+video:\s*(.+)$", re.IGNORECASE)
SPRITE_OUTPUT_PAT = re.compile(r"^(?:Sprite output|Converted to sprite):\s*(.+)$", re.IGNORECASE)


def _parse_progress(line: str) -> Optional[float]:
    for pattern in (PROGRESS_PAT3, PROGRESS_PAT1):
        match = pattern.search(line)
        if match:
            return max(0.0, min(100.0, float(match.group(1))))
    match = PROGRESS_PAT2.search(line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        if total > 0:
            return max(0.0, min(100.0, round((current / total) * 100.0, 1)))
    return None


def _infer_stage(line: str) -> tuple[str, str, str, Optional[float]]:
    text = line.lower()
    if "queued comfyui prompt" in text or "prompt id:" in text:
        return "queued_comfy", "Queued in ComfyUI", "Prompt accepted by ComfyUI.", 12
    if "waiting for exact comfyui prompt history output" in text:
        return "wan_sampling", "Generating video", "ComfyUI is running the WAN workflow.", 18
    if "resolved output" in text or "history output" in text or "chosen output" in text:
        return "resolve_output", "Resolving output", "Finding the exact video produced by this prompt.", 62
    if "converting" in text and ("video" in text or "spritesheet" in text):
        return "convert_video", "Converting video", "Extracting frames and preparing the sprite sheet.", 72
    if "sprite output" in text or "sheet:" in text or "preview:" in text or "metadata:" in text:
        return "pack_sprite", "Packing sprite", "Writing sheet, preview, and metadata.", 88
    if "quality" in text or "qa report" in text:
        return "qa", "Quality check", "Running quality analysis and writing the report.", 92
    if "lora training run" in text or "trainer:" in text:
        return "lora_training", "LoRA training", "Preparing or running the LoRA trainer.", 55
    if "download" in text:
        return "download", "Downloading", "Downloading or checking model files.", 35
    if "install" in text:
        return "install", "Installing", "Installing or updating dependencies.", 35
    if "error:" in text or "traceback" in text or "returned non-zero" in text:
        return "error", "Error detected", line[-180:], None
    return "", "", "", None


def parse_job_output_line(line: str) -> JobOutputEvent:
    text = str(line or "").strip()
    stage, label, detail, stage_progress = _infer_stage(text)
    prompt_match = PROMPT_ID_PAT.search(text)
    source_match = SOURCE_VIDEO_PAT.search(text)
    sprite_match = SPRITE_OUTPUT_PAT.search(text)
    return JobOutputEvent(
        progress_percent=_parse_progress(text),
        stage=stage,
        stage_label=label,
        stage_detail=detail,
        stage_progress=stage_progress,
        prompt_id=prompt_match.group(1) if prompt_match else "",
        source_video=source_match.group(1).strip() if source_match else "",
        sprite_output=sprite_match.group(1).strip() if sprite_match else "",
        oom_detected="cuda out of memory" in text.lower() or "outofmemoryerror" in text.lower(),
    )
