from __future__ import annotations

import time
from pathlib import Path
from typing import List


def command_sprite_folder(root: Path, cmd: List[str], started_at: str = "") -> str:
    explicit = _explicit_output_folder(root, cmd)
    if explicit:
        return explicit
    if not any(x in str(c) for x in ("generate-sprite", "generate_sprite") for c in cmd):
        return ""
    return _newest_sheet_folder(root, started_at)


def _explicit_output_folder(root: Path, cmd: List[str]) -> str:
    try:
        for idx, val in enumerate(cmd):
            if val in {"--output", "--sprite-dir"}:
                out_val = cmd[idx + 1]
                path = Path(out_val)
                if path.is_absolute():
                    return str(path.relative_to(root)).replace("\\", "/")
                return str(out_val).replace("\\", "/")
    except Exception:
        return ""
    return ""


def _newest_sheet_folder(root: Path, started_at: str) -> str:
    try:
        started = time.mktime(time.strptime(started_at, "%Y-%m-%d %H:%M:%S")) if started_at else 0
        candidate = max(
            (p for p in (root / "output").rglob("sheet.json") if p.stat().st_mtime > started),
            key=lambda p: p.stat().st_mtime,
            default=None,
        )
        return str(candidate.parent.relative_to(root)).replace("\\", "/") if candidate else ""
    except Exception:
        return ""
