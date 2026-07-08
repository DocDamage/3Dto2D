from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 test environments
    import tomli as tomllib


ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_discovers_runtime_packages_and_assets():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    setuptools = data["tool"]["setuptools"]
    find = setuptools["packages"]["find"]

    assert setuptools["include-package-data"] is True
    assert "services*" in find["include"]
    assert "web_routes*" in find["include"]
    assert "web*" in find["include"]
    assert "config*" in find["include"]
    assert "workflows*" in find["include"]
    assert "vendor*" in find["exclude"]
    assert "output*" in find["exclude"]
    assert "input*" in find["exclude"]

    package_data = setuptools["package-data"]["*"]
    assert "*.html" in package_data
    assert "*.js" in package_data
    assert "*.css" in package_data
    assert "*.json" in package_data


def test_all_first_party_route_packages_are_importable():
    sys.path.insert(0, str(ROOT / "app"))
    import services.project_path_service  # noqa: F401
    import web_routes.api_errors  # noqa: F401


def test_launcher_requirements_mirror_pyproject_runtime_dependencies():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_deps = {
        dep.lower()
        for dep in data["project"]["dependencies"]
    }
    requirements = {
        line.strip().lower()
        for line in (ROOT / "app" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    assert requirements == pyproject_deps
