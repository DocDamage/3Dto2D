from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List


def open_command_for_platform(platform: str, target: Path) -> List[str]:
    if platform == "darwin":
        return ["open", str(target)]
    return ["xdg-open", str(target)]


def open_path(path: Path) -> None:
    target = Path(path).resolve()
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(open_command_for_platform(sys.platform, target))
