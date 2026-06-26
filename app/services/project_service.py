"""Project mode service for SpriteForge Studio."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
STATE_PATH = ROOT / "output" / "projects" / "project_state.json"
DEFAULT_ACTIONS = ["idle", "walk", "run", "attack_light", "hurt"]
DEFAULT_DIRECTIONS = ["right"]


def safe_name(value: str) -> str:
    cleaned = "".join(ch for ch in value.strip() if ch.isalnum() or ch in "._- ").strip().replace(" ", "_")
    return cleaned or "project"


class ProjectService:
    _lock = threading.RLock()

    @staticmethod
    def _manifest_path(project_dir: Path) -> Path:
        return project_dir / "spriteforge_project.json"

    @staticmethod
    def _state() -> Dict[str, Any]:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if STATE_PATH.exists():
            try:
                return json.loads(STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    @staticmethod
    def _save_state(state: Dict[str, Any]) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    @staticmethod
    def _summary(path: Path, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": data.get("name", path.parent.name),
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "root": str(path.parent.relative_to(ROOT)).replace("\\", "/"),
            "character": data.get("character", ""),
            "style": data.get("style", ""),
            "actions": data.get("actions", []),
            "directions": data.get("directions", []),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        }

    @staticmethod
    def metadata_for_path(value: str) -> Optional[Dict[str, str]]:
        path = ProjectService.resolve_project_path(value)
        if not path:
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return {
            "project_name": str(data.get("name") or path.parent.name),
            "project_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "project_root": str(path.parent.relative_to(ROOT)).replace("\\", "/"),
        }

    @staticmethod
    def item_matches_project(item: Dict[str, Any], project_meta: Optional[Dict[str, str]]) -> bool:
        if not project_meta:
            return True
        project_name = project_meta.get("project_name", "")
        project_path = project_meta.get("project_path", "")
        project_root = project_meta.get("project_root", "")

        if item.get("project_path") and item.get("project_path") == project_path:
            return True
        if item.get("project_root") and item.get("project_root") == project_root:
            return True
        if item.get("project_name") and item.get("project_name") == project_name:
            return True

        path = str(item.get("path") or item.get("sprite_folder") or "")
        name = str(item.get("name") or "")
        return bool(
            (project_root and (path == project_root or path.startswith(project_root + "/")))
            or (project_name and (name == project_name or name.startswith(project_name + "_")))
            or (project_name and (path.startswith(f"output/{project_name}_") or f"/{project_name}_" in path))
        )

    @staticmethod
    def list_projects() -> List[Dict[str, Any]]:
        with ProjectService._lock:
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            rows: List[Dict[str, Any]] = []
            for manifest in PROJECTS_DIR.glob("*/spriteforge_project.json"):
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    rows.append(ProjectService._summary(manifest, data))
                except Exception:
                    continue
            rows.sort(key=lambda row: (row.get("updated_at") or row.get("created_at") or "", row.get("name", "")), reverse=True)
            return rows

    @staticmethod
    def get_active_project() -> Optional[Dict[str, Any]]:
        with ProjectService._lock:
            active_path = str(ProjectService._state().get("active_project") or "")
            if not active_path:
                return None
            path = ProjectService.resolve_project_path(active_path)
            if not path:
                return None
            try:
                return ProjectService._summary(path, json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                return None

    @staticmethod
    def resolve_project_path(value: str) -> Optional[Path]:
        if not value:
            return None
        path = Path(value)
        target = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
        if target.is_dir():
            target = ProjectService._manifest_path(target)
        try:
            target.relative_to(PROJECTS_DIR.resolve())
        except ValueError:
            return None
        if target.name != "spriteforge_project.json" or not target.is_file():
            return None
        return target

    @staticmethod
    def set_active_project(value: str) -> Optional[Dict[str, Any]]:
        with ProjectService._lock:
            path = ProjectService.resolve_project_path(value)
            if not path:
                return None
            state = ProjectService._state()
            state["active_project"] = str(path.relative_to(ROOT)).replace("\\", "/")
            ProjectService._save_state(state)
            return ProjectService.get_active_project()

    @staticmethod
    def clear_active_project() -> None:
        with ProjectService._lock:
            state = ProjectService._state()
            state.pop("active_project", None)
            ProjectService._save_state(state)

    @staticmethod
    def create_project(
        *,
        name: str,
        character: str = "single full body original game character, consistent outfit, readable silhouette",
        style: str = "2D game sprite animation, crisp edges, readable silhouette, production sprite sheet style",
        actions: Optional[List[str]] = None,
        directions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        with ProjectService._lock:
            project_name = safe_name(name)
            project_dir = PROJECTS_DIR / project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            for folder in ["references", "posepacks", "prompts", "sprites", "exports", "quality", "queues", "releases"]:
                (project_dir / folder).mkdir(exist_ok=True)
            now = time.strftime("%Y-%m-%dT%H:%M:%S")
            manifest = ProjectService._manifest_path(project_dir)
            if manifest.exists():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                data["updated_at"] = now
            else:
                data = {
                    "schema": "spriteforge_project_v1",
                    "name": project_name,
                    "created_at": now,
                    "updated_at": now,
                    "character": character,
                    "style": style,
                    "background": "plain bright green chroma key background, evenly lit, no shadows on background",
                    "profile": "rtx3060_12gb",
                    "mode": "t2v",
                    "actions": actions or DEFAULT_ACTIONS,
                    "directions": directions or DEFAULT_DIRECTIONS,
                    "fps": 12,
                    "cell_size": "512x512",
                    "frames_by_action": {
                        "idle": 24,
                        "walk": 33,
                        "run": 25,
                        "attack_light": 24,
                        "attack_heavy": 32,
                        "cast": 32,
                        "jump": 24,
                        "hurt": 16,
                        "death": 40,
                    },
                    "quality_gates": {
                        "max_foot_drift": 2.0,
                        "max_flicker": 1.0,
                        "loop_seam_threshold": 15.0,
                        "required_frame_count": None,
                        "alpha_cleanliness": 0.05
                    }
                }
            manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return ProjectService.set_active_project(str(manifest)) or ProjectService._summary(manifest, data)
