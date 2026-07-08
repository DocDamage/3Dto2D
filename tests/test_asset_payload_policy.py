from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def test_optional_asset_payloads_are_ignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "CuteSCKR_uncut/" in ignored
    assert "app/input/lpc_assets/" in ignored
    assert (ROOT / "docs" / "ASSET_PAYLOADS.md").exists()


def test_large_optional_payloads_are_not_tracked():
    blocked_prefixes = (
        "CuteSCKR_uncut/",
        "app/input/lpc_assets/",
        "app/vendor/",
        "output/",
        "app/output/",
    )
    allowed_marker_files = {
        "app/vendor/NOT_BUNDLED_README.txt",
    }
    offenders = [
        path
        for path in _git_ls_files()
        if path.startswith(blocked_prefixes) and path not in allowed_marker_files
    ]

    assert offenders == []


def test_tracked_text_files_do_not_pin_user_machine_paths():
    forbidden = (
        "C:" + "\\Users\\",
        "C:" + "/Users/",
        "G:" + "\\",
    )
    offenders: list[str] = []
    for relative in _git_ls_files():
        path = ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for marker in forbidden):
            offenders.append(relative)

    assert offenders == []
