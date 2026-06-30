from __future__ import annotations
import shutil
import sys
import os
from pathlib import Path
from typing import Dict, Any

from services.comfy_service import ComfyService
from services.model_service import ModelService
from spriteforge_utils import PYTHON, ROOT, OUTPUT, INPUT, PROJECTS

__all__ = ["run_self_test"]

def run_self_test() -> Dict[str, Any]:
    # 1. Python Check
    python_ok = Path(PYTHON).exists() or Path(sys.executable).exists()

    # 2. FFmpeg Check
    ffmpeg_ok = shutil.which("ffmpeg") is not None

    # 3. Pillow Check
    try:
        from PIL import Image
        pillow_ok = True
    except ImportError:
        pillow_ok = False

    # 4. ComfyUI Check
    comfy_running = ComfyService.is_running()

    # 5. Write Permissions Check
    write_ok = True
    for folder in [INPUT, OUTPUT, PROJECTS]:
        if folder.exists():
            if not os.access(folder, os.W_OK):
                write_ok = False

    # 6. Model & Disk & GPU Status
    model_summary = ModelService.get_summary()
    disk_summary = ModelService.get_disk_summary()
    gpu_info = ComfyService.get_gpu_info()

    overall_ok = (
        python_ok and ffmpeg_ok and pillow_ok and
        comfy_running and write_ok and model_summary.get("ok", True)
    )

    return {
        "ok": overall_ok,
        "checks": {
            "python": {"ok": python_ok, "details": str(PYTHON)},
            "ffmpeg": {"ok": ffmpeg_ok, "details": "Found" if ffmpeg_ok else "Not found in PATH"},
            "pillow": {"ok": pillow_ok, "details": "Installed" if pillow_ok else "Missing"},
            "comfyui": {"ok": comfy_running, "details": "Running" if comfy_running else "Unreachable"},
            "writable": {"ok": write_ok, "details": "Directories are writable" if write_ok else "Permission denied"},
            "models": {"ok": model_summary.get("ok", True), "details": model_summary},
            "disk": disk_summary,
            "gpu": gpu_info,
        }
    }
