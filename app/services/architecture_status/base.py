import json
import re
from pathlib import Path
from typing import Any

from spriteforge_utils import ROOT as APP_ROOT

APP = APP_ROOT if APP_ROOT.name == "app" else APP_ROOT / "app"
REPO_ROOT = APP.parent
SERVICES = APP / "services"
WEB = APP / "web"

ROOT_DEFINITION_PATTERN = re.compile(
    r"^ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)?\s*$",
    re.M,
)
SILENT_EXCEPTION_PATTERN = re.compile(
    r"except (?:Exception(?:\s+as\s+\w+)?|KeyError(?:\s+as\s+\w+)?):\s*(?:\n\s*pass\s*(?:#.*)?$|pass\s*(?:#.*)?$)",
    re.M,
)
TOP_LEVEL_FUNCTION_PATTERN = re.compile(
    r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
    re.M,
)
CSS_SELECTOR_PATTERN = re.compile(r"(^|})\s*([^{}@][^{}]*)\s*\{", re.S)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _app_python_files() -> list[Path]:
    return [
        path
        for path in APP.rglob("*.py")
        if "vendor" not in path.parts and "__pycache__" not in path.parts
    ]


def _phase_status(name: str, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks = {key: bool(value.get("ok")) for key, value in items.items()}
    return {"name": name, "ok": all(checks.values()), "checks": checks}


def _read_parser_source() -> str:
    content = (APP / "spriteforge_unified_parser.py").read_text(encoding="utf-8", errors="ignore")
    cli_dir = APP / "cli"
    if cli_dir.exists():
        for path in sorted(cli_dir.glob("*.py")):
            content += "\n" + path.read_text(encoding="utf-8", errors="ignore")
    return content

