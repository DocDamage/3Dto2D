#!/usr/bin/env python3
"""Create a no-GPU sample sprite so users can verify the tool before installing WAN."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

from services.open_path_service import open_path as open_system_path

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "output" / "_demo_frames"
OUT = ROOT / "output" / "demo_sprite_no_gpu"


def open_path(path: Path) -> None:
    try:
        open_system_path(path)
    except Exception:
        pass


def make_frames() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    for p in FRAMES.glob("*.png"):
        p.unlink()
    for i in range(16):
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        phase = i / 16 * math.tau
        x = 128 + int(math.sin(phase) * 8)
        y = 152 + int(math.sin(phase * 2) * 5)
        # shadow
        d.ellipse((x - 36, 226, x + 36, 238), fill=(0, 0, 0, 45))
        # legs
        d.line((x - 10, y + 40, x - 22 - int(math.sin(phase)*8), 226), fill=(35, 35, 45, 255), width=8)
        d.line((x + 10, y + 40, x + 22 + int(math.sin(phase)*8), 226), fill=(35, 35, 45, 255), width=8)
        # body/head
        d.rectangle((x - 20, y - 18, x + 20, y + 48), fill=(38, 85, 190, 255))
        d.ellipse((x - 28, y - 82, x + 28, y - 26), fill=(75, 145, 255, 255))
        d.rectangle((x - 15, y - 28, x + 15, y - 18), fill=(55, 105, 220, 255))
        # arms
        d.line((x - 20, y - 10, x - 44, y + 28 + int(math.sin(phase)*10)), fill=(30, 60, 150, 255), width=7)
        d.line((x + 20, y - 10, x + 44, y + 28 - int(math.sin(phase)*10)), fill=(30, 60, 150, 255), width=7)
        # eyes
        d.ellipse((x - 10, y - 58, x - 5, y - 53), fill=(255,255,255,255))
        d.ellipse((x + 5, y - 58, x + 10, y - 53), fill=(255,255,255,255))
        img.save(FRAMES / f"demo_{i:04d}.png")


def main() -> int:
    print("Creating no-GPU demo frames...")
    make_frames()
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "spriteforge.py", "pack",
        "--input", str(FRAMES),
        "--output", str(OUT),
        "--fps", "12",
        "--cell-size", "256x256",
        "--animation", "demo_idle",
        "--anchor", "bottom-center",
        "--solidify", "2",
        "--preview-gif",
        "--report",
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))
    (OUT / "README_DEMO.txt").write_text(
        "This sprite was generated without ComfyUI, WAN, or a GPU.\n"
        "If sheet.png, sheet.json, preview.gif, and report.html exist, the sprite conversion side works.\n",
        encoding="utf-8",
    )
    print(f"\nDemo complete: {OUT}")
    print("Open preview.gif or report.html to verify the output.")
    open_path(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
