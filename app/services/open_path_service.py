from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

__all__ = ["open_path"]


def open_command_for_platform(platform: str, target: Path) -> List[str]:
    if platform == "darwin":
        return ["open", str(target)]
    return ["xdg-open", str(target)]


def open_path(path: Path) -> None:
    root = Path(__file__).resolve().parent.parent
    target = Path(path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Access denied: Path is outside workspace root.")

    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(open_command_for_platform(sys.platform, target))
