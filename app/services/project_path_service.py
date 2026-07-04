from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from spriteforge_utils import ROOT as APP_ROOT

logger = logging.getLogger(__name__)


class ProjectPaths:
    """Central path helpers for app-root-relative files.

    This keeps security-sensitive path checks in one place while allowing
    legacy modules to migrate gradually away from ad-hoc ``ROOT / value`` use.
    """

    root: Path = APP_ROOT

    @staticmethod
    def resolve_root_path(value: str | Path) -> Path:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (ProjectPaths.root / path).resolve()

    @staticmethod
    def is_relative_to(path: Path, base: Path) -> bool:
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def relative_display(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ProjectPaths.root.resolve())).replace("\\", "/")
        except Exception as exc:
            logger.debug("Could not render project-relative path %s: %s", path, exc)
            return str(path).replace("\\", "/")

    @staticmethod
    def first_existing_file(candidates: Iterable[str | Path]) -> Optional[Path]:
        for candidate in candidates:
            path = ProjectPaths.resolve_root_path(candidate)
            if path.exists() and path.is_file():
                return path
        return None
