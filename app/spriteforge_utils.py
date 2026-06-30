import json
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent

def natural_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]

def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "spriteforge_asset"

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
