#!/usr/bin/env python3
"""Small VRAM guard for local WAN jobs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple


def query_nvidia_smi() -> Tuple[bool, str, Optional[int], Optional[int]]:
    if not shutil.which("nvidia-smi"):
        return False, "nvidia-smi not found in PATH", None, None
    try:
        p = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return False, str(exc), None, None
    out = (p.stdout or p.stderr or "").strip()
    if p.returncode != 0:
        return False, out, None, None
    line = out.splitlines()[0]
    parts = [x.strip() for x in line.split(",")]
    if len(parts) < 4:
        return False, out, None, None
    try:
        total = int(float(parts[1])); free = int(float(parts[2]))
    except Exception:
        return False, out, None, None
    return True, line, total, free


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Check free VRAM before WAN generation")
    p.add_argument("--min-total-mib", type=int, default=11000)
    p.add_argument("--min-free-mib", type=int, default=8500)
    p.add_argument("--json", default=None)
    p.add_argument("--warn-only", action="store_true")
    args = p.parse_args(argv)
    ok, detail, total, free = query_nvidia_smi()
    status = "pass"
    messages = []
    if not ok:
        status = "fail"; messages.append(detail)
    else:
        if total is not None and total < args.min_total_mib:
            status = "fail"; messages.append(f"Total VRAM {total} MiB is below target {args.min_total_mib} MiB")
        if free is not None and free < args.min_free_mib:
            status = "warn" if status == "pass" else status
            messages.append(f"Free VRAM {free} MiB is below target {args.min_free_mib} MiB; close GPU-heavy apps or lower the profile")
    data = {"status": status, "detail": detail, "total_mib": total, "free_mib": free, "messages": messages}
    print(json.dumps(data, indent=2))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(data, indent=2), encoding="utf-8")
    if args.warn_only:
        return 0
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
