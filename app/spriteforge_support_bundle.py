#!/usr/bin/env python3
"""Collect a support zip without requiring the user to know where logs live."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterable, List, Sequence

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "support_bundles"
LOGS = ROOT / "logs"


def run_cmd(name: str, cmd: Sequence[str], timeout: int = 60) -> str:
    try:
        cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
        return f"$ {' '.join(cmd)}\nexit={cp.returncode}\n\nSTDOUT:\n{cp.stdout}\n\nSTDERR:\n{cp.stderr}\n"
    except Exception as exc:
        return f"$ {' '.join(cmd)}\nERROR: {exc}\n"


def redact_text(text: str) -> str:
    # Avoid accidentally collecting common secret patterns.
    for key in ["RUNPOD_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN", "OPENAI_API_KEY"]:
        text = text.replace(os.environ.get(key, ""), "[REDACTED]") if os.environ.get(key) else text
    return text


def add_file(z: zipfile.ZipFile, path: Path, arc: str | None = None) -> None:
    if path.exists() and path.is_file():
        z.write(path, arc or str(path.relative_to(ROOT)))


def add_tree(z: zipfile.ZipFile, folder: Path, prefix: str, patterns: Iterable[str] = ("*",), max_bytes: int = 5_000_000) -> None:
    if not folder.exists():
        return
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.stat().st_size > max_bytes:
            continue
        if any(p.match(pattern) for pattern in patterns):
            z.write(p, f"{prefix}/{p.relative_to(folder)}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bundle = OUT / f"spriteforge_support_bundle_{stamp}.zip"
    tmp = OUT / f"_support_tmp_{stamp}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    reports = {
        "system.txt": "\n".join([
            f"SpriteForge support bundle: {stamp}",
            f"Python: {sys.version}",
            f"Platform: {platform.platform()}",
            f"Executable: {sys.executable}",
            f"Root: {ROOT}",
            f"CWD: {Path.cwd()}",
        ]),
        "where_python.txt": run_cmd("where python", ["where", "python"] if os.name == "nt" else ["which", "python3"]),
        "where_git.txt": run_cmd("where git", ["where", "git"] if os.name == "nt" else ["which", "git"]),
        "nvidia_smi.txt": run_cmd("nvidia-smi", ["nvidia-smi"], timeout=30),
        "pip_freeze.txt": run_cmd("pip freeze", [sys.executable, "-m", "pip", "freeze"], timeout=60),
        "spriteforge_status.txt": run_cmd("status", [sys.executable, "spriteforge_unified.py", "status"], timeout=60),
        "model_report.txt": run_cmd("model-report", [sys.executable, "spriteforge_unified.py", "model-report"], timeout=60),
        "hardware_advisor.txt": run_cmd("hardware-advisor", [sys.executable, "spriteforge_unified.py", "hardware-advisor"], timeout=60),
        "doctor.txt": run_cmd("doctor", [sys.executable, "spriteforge_unified.py", "doctor"], timeout=120),
    }
    for name, content in reports.items():
        (tmp / name).write_text(redact_text(content), encoding="utf-8", errors="replace")

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        # Generated reports
        for p in tmp.iterdir():
            add_file(z, p, f"reports/{p.name}")
        # Safe config/docs/scripts metadata
        for rel in [
            "VERSION.txt", "requirements.txt", ".python_version",
            "config/spriteforge_config.json", "config/easy_mode.json", "config/easy_presets.json",
            "workflows/wan21_t2v_1_3b_native_api.json",
        ]:
            add_file(z, ROOT / rel)
        add_tree(z, LOGS, "logs", patterns=("*.log", "*.txt"), max_bytes=2_000_000)
        add_tree(z, ROOT / "output" / "diagnostics", "output_diagnostics", patterns=("*.txt", "*.json", "*.html"), max_bytes=5_000_000)
        # Include metadata for recent sprite outputs, but not huge videos/models.
        out_root = ROOT / "output"
        if out_root.exists():
            for p in out_root.rglob("sheet.json"):
                add_file(z, p, f"recent_outputs/{p.parent.name}/sheet.json")
            for p in out_root.rglob("report.html"):
                add_file(z, p, f"recent_outputs/{p.parent.name}/report.html")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Support bundle created:\n{bundle}")
    try:
        from services.open_path_service import open_path
        open_path(bundle.parent)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
