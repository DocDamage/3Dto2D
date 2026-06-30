from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class VramFallback:
    command: List[str]
    label: str
    detail: str


def _set_arg(cmd: List[str], flag: str, value: str) -> None:
    if flag in cmd:
        idx = cmd.index(flag)
        if idx + 1 < len(cmd):
            cmd[idx + 1] = value
            return
    cmd.extend([flag, value])


def _scale_size(value: str) -> str:
    try:
        w, h = map(int, value.lower().split("x", 1))
    except Exception:
        return value
    return f"{max(128, w // 2)}x{max(128, h // 2)}"


def _scale_resolutions(value: str) -> str:
    return ",".join(_scale_size(part.strip()) for part in value.split(",") if part.strip())


def progressive_vram_fallback(cmd: List[str], attempt: int) -> VramFallback:
    new_cmd = list(cmd)
    if attempt <= 1:
        _set_arg(new_cmd, "--tier", "wan21_safe")
        _set_arg(new_cmd, "--profile", "wan22_5b_debug" if "wan22" in " ".join(cmd) else "debug")
        _set_arg(new_cmd, "--vram-fallback", "fp8")
        return VramFallback(new_cmd, "fp8_quantization", "Switched to the safest local tier/profile and enabled fp8 fallback hints.")
    if attempt == 2:
        _set_arg(new_cmd, "--batch-size", "1")
        _set_arg(new_cmd, "--vram-fallback", "batch")
        return VramFallback(new_cmd, "reduced_batch", "Forced batch size to 1 to reduce peak VRAM.")
    if attempt == 3:
        if "--cell-size" in new_cmd and new_cmd.index("--cell-size") + 1 < len(new_cmd):
            idx = new_cmd.index("--cell-size")
            new_cmd[idx + 1] = _scale_size(new_cmd[idx + 1])
        if "--resolutions" in new_cmd and new_cmd.index("--resolutions") + 1 < len(new_cmd):
            idx = new_cmd.index("--resolutions")
            new_cmd[idx + 1] = _scale_resolutions(new_cmd[idx + 1])
        _set_arg(new_cmd, "--vram-fallback", "resolution")
        return VramFallback(new_cmd, "reduced_resolution", "Halved sprite and WAN resolution targets.")
    _set_arg(new_cmd, "--cpu-offload", "true")
    _set_arg(new_cmd, "--vram-fallback", "cpu_offload")
    return VramFallback(new_cmd, "cpu_offload", "Requested CPU/offload mode for the final retry.")
