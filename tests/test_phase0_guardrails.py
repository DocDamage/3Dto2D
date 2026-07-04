import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def _app_python_files() -> list[Path]:
    return [
        path
        for path in APP.rglob("*.py")
        if "vendor" not in path.parts
        and "__pycache__" not in path.parts
    ]


def test_app_uses_canonical_root_outside_allowed_bootstrap_files():
    allowed = {
        APP / "spriteforge_utils.py",
        APP / "scratch" / "extract_views.py",
        APP / "spriteforge_cloud.py",  # contains a standalone generated cloud-runner script string
    }
    pattern = re.compile(r"^ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)?\s*$", re.M)

    offenders = [
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in _app_python_files()
        if path not in allowed and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]

    assert offenders == []


def test_services_do_not_silently_swallow_broad_exceptions():
    pattern = re.compile(r"except Exception(?:\s+as\s+\w+)?:\s*(?:\n\s*pass\s*(?:#.*)?$|pass\s*(?:#.*)?$)", re.M)
    offenders = []
    for path in (APP / "services").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            offenders.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    assert offenders == []
