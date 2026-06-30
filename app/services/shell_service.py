#!/usr/bin/env python3
"""Low-level shell utilities: subprocess wrappers, git helpers, venv management."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def print_cmd(cmd: Sequence[str], cwd: Optional[Path] = None) -> None:
    where = f" (cwd={cwd})" if cwd else ""
    print("$ " + " ".join(f'\"{c}\"' if " " in str(c) else str(c) for c in cmd) + where, flush=True)


def run(cmd: Sequence[str], cwd: Optional[Path] = None, check: bool = True, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    unified = sys.modules.get("spriteforge_unified")
    if unified and hasattr(unified, "run"):
        if unified.run is not run:
            return unified.run(cmd)
    print_cmd(cmd, cwd)
    return subprocess.run(list(map(str, cmd)), cwd=str(cwd) if cwd else None, check=check, env=env)


def capture(cmd: Sequence[str], cwd: Optional[Path] = None, timeout: float = 20.0) -> Tuple[int, str]:
    try:
        p = subprocess.run(list(map(str, cmd)), cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def which(exe: str) -> Optional[str]:
    return shutil.which(exe)


def python_launcher(prefer: str = "3.12") -> List[str]:
    if os.name == "nt" and which("py"):
        for ver in [prefer, "3.13", "3.12", "3.11", ""]:
            cmd = ["py"] + ([f"-{ver}"] if ver else []) + ["-c", "import sys; print(sys.version)"]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                return ["py"] + ([f"-{ver}"] if ver else [])
            except Exception:
                pass
    return [sys.executable]


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv(venv: Path, prefer_python: str = "3.12") -> Path:
    py = venv_python(venv)
    if py.exists():
        return py
    venv.parent.mkdir(parents=True, exist_ok=True)
    run(python_launcher(prefer_python) + ["-m", "venv", str(venv)])
    return py


def install_requirements(py: Path, req: Path, optional: bool = False) -> None:
    if req.exists():
        run([str(py), "-m", "pip", "install", "-r", str(req)], check=not optional)
    elif not optional:
        raise FileNotFoundError(req)


def git_clone_or_pull(url: str, dest: Path) -> None:
    if dest.exists() and (dest / ".git").exists():
        run(["git", "pull", "--ff-only"], cwd=dest, check=False)
    elif dest.exists() and any(dest.iterdir()):
        tmp = dest.parent / f".{dest.name}_clone_{int(time.time())}"
        print(f"Repairing non-git folder by cloning into a temporary directory: {tmp}")
        run(["git", "clone", url, str(tmp)])
        try:
            shutil.copytree(tmp, dest, dirs_exist_ok=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", url, str(dest)])


def git_rev(path: Path) -> Optional[str]:
    if not (path / ".git").exists():
        return None
    rc, out = capture(["git", "rev-parse", "--short", "HEAD"], cwd=path)
    return out.strip() if rc == 0 else None