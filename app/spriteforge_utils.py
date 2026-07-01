import json
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
WEB = ROOT / "web"
OUTPUT = ROOT / "output"
INPUT = ROOT / "input"
UPLOADS = INPUT / "uploaded_videos"
LOGS = ROOT / "logs"
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
ALLOWED_SUBDIRS = {"output", "input", "projects", "releases", "workflows", "examples"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}

def next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()

def natural_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]

def safe_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in "._-")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    return cleaned or "file"

def is_release_excluded(path: Path, root_dir: Path) -> bool:
    """
    Check if a file should be excluded from a release zip or project bundle.
    Returns True if the path contains folders/files matching excluded patterns:
    - uploads/uploaded_videos (unless it is a small reference image < 10MB)
    - outputs (e.g., outputs/ or releases/)
    - local projects (other projects than the one being zipped)
    - logs (e.g., logs/ or *.log)
    - vendor payloads (comfyui/, venv/, node_modules/, models/)
    """
    try:
        rel_path = path.relative_to(root_dir)
    except ValueError:
        rel_path = path
    parts = [p.lower() for p in rel_path.parts]
    name = path.name.lower()

    # 1. Vendor payloads & environments
    if any(p in parts for p in ("comfyui", "venv", ".venv", "node_modules", "vendor", "models")):
        return True

    # 2. Logs
    if "logs" in parts or name.endswith(".log") or name == "app.log":
        return True

    # 3. Git / IDE metadata
    if any(p.startswith(".") for p in parts) and not any(p in (".spriteforge", ".github") for p in parts):
        return True

    # 4. Uploads / heavy files
    if "uploaded_videos" in parts or "uploads" in parts:
        try:
            if path.is_file() and path.stat().st_size > 10_000_000:  # > 10MB
                return True
        except Exception:
            return True

    # 5. Heavy outputs/releases
    if "output" in parts or "releases" in parts:
        return True

    # 6. Overall size limit safety (e.g., any file over 50MB is suspicious for a release/project config)
    try:
        if path.is_file() and path.stat().st_size > 50_000_000:
            return True
    except Exception:
        pass

    return False

def audit_dir_exclusions(root_dir: Path) -> list[str]:
    """Scan root_dir for any files violating release/project exclusion rules."""
    violations = []
    for p in Path(root_dir).rglob("*"):
        if p.is_file() and is_release_excluded(p, root_dir):
            violations.append(str(p.relative_to(root_dir)))
    return violations


def load_meta(sprite_dir: Path) -> Dict[str, Any]:
    path = sprite_dir / "sheet.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_sprite_dir"] = str(sprite_dir)
    return data

def app_python() -> str:
    if os.name == "nt":
        p = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        p = ROOT / ".venv" / "bin" / "python"
    return str(p if p.exists() else Path(sys.executable))

PYTHON = app_python()

def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(temp_path), str(path))
    except Exception as e:
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            raise e
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

write_json = save_json

def get_app_version() -> str:
    try:
        version_file = ROOT / "VERSION.txt"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "v12 Final Polish Edition"

def apply_dark_theme(root) -> None:
    from tkinter import ttk
    import tkinter as tk

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    bg_color = "#1e1e1e"
    fg_color = "#e0e0e0"
    card_bg = "#2d2d2d"
    accent_color = "#00adb5"
    border_color = "#3a3a3a"
    select_bg = "#00adb5"
    select_fg = "#ffffff"

    style.configure(".",
        background=bg_color,
        foreground=fg_color,
        bordercolor=border_color,
        darkcolor=border_color,
        lightcolor=border_color,
        fieldbackground=card_bg,
        font=("Segoe UI", 9)
    )

    style.configure("TFrame", background=bg_color)
    style.configure("TLabelframe", background=bg_color, bordercolor=border_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground=accent_color, font=("Segoe UI", 10, "bold"))

    style.configure("TLabel", background=bg_color, foreground=fg_color)
    style.configure("TButton", background=card_bg, foreground=fg_color, bordercolor=border_color, focuscolor=accent_color)
    style.map("TButton",
        background=[("active", border_color), ("pressed", bg_color)],
        foreground=[("active", "#ffffff")]
    )

    style.configure("TEntry", fieldbackground=card_bg, foreground=fg_color, bordercolor=border_color, insertcolor=fg_color)
    style.map("TEntry", bordercolor=[("focus", accent_color)])

    style.configure("TCombobox", fieldbackground=card_bg, background=card_bg, foreground=fg_color, bordercolor=border_color, arrowcolor=fg_color, insertcolor=fg_color)
    style.map("TCombobox",
        bordercolor=[("focus", accent_color)],
        fieldbackground=[("readonly", card_bg)],
        foreground=[("readonly", fg_color)]
    )

    style.configure("TCheckbutton", background=bg_color, foreground=fg_color, indicatorbackground=card_bg, indicatorforeground=fg_color)
    style.map("TCheckbutton",
        indicatorbackground=[("selected", accent_color)],
        background=[("active", bg_color)]
    )

    style.configure("TNotebook", background=bg_color, bordercolor=border_color)
    style.configure("TNotebook.Tab", background=card_bg, foreground=fg_color, bordercolor=border_color, padding=(10, 4))
    style.map("TNotebook.Tab",
        background=[("selected", bg_color)],
        foreground=[("selected", accent_color), ("active", "#ffffff")]
    )

    style.configure("Treeview", background=card_bg, fieldbackground=card_bg, foreground=fg_color, bordercolor=border_color, rowheight=24)
    style.map("Treeview",
        background=[("selected", select_bg)],
        foreground=[("selected", select_fg)]
    )
    style.configure("Heading", background=border_color, foreground=fg_color, bordercolor=border_color)

    root.configure(bg=bg_color)
