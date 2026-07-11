"""Versioned deterministic export presets with QA gates and atomic publishing."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List

from services.asset_repository_service import AssetRepositoryService


PRESET_SCHEMA = "spriteforge.export_preset.v1"
BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    preset_id: {
        "schema": PRESET_SCHEMA, "schema_version": 1, "preset_id": preset_id,
        "name": name, "format": format_name, "scale": 1, "interpolation": "nearest",
        "padding": 0, "extrusion": 0, "trim": False, "max_texture_size": 4096,
        "naming": "{asset_id}/{logical_name}", "block_on_errors": True,
    }
    for preset_id, name, format_name in [
        ("godot", "Godot", "godot"), ("unity", "Unity", "unity"), ("unreal", "Unreal", "unreal"),
        ("rpg_maker", "RPG Maker", "rpg_maker"), ("lpc", "LPC", "lpc"),
        ("phaser", "Phaser / Web Atlas", "phaser"), ("generic_json", "Generic JSON Atlas", "json"),
        ("css", "CSS Sprite Sheet", "css"), ("raw", "Raw Frames + Metadata", "raw"),
    ]
}


class ExportPresetService:
    def __init__(self, repository: AssetRepositoryService):
        self.repository = repository

    @staticmethod
    def list_presets() -> List[Dict[str, Any]]:
        return [dict(value) for value in BUILTIN_PRESETS.values()]

    @staticmethod
    def validate_preset(preset: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(preset, dict):
            raise ValueError("Export preset must be an object")
        normalized = dict(preset)
        normalized.setdefault("schema", PRESET_SCHEMA)
        normalized.setdefault("schema_version", 1)
        preset_id = str(normalized.get("preset_id") or "").strip()
        if not preset_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in preset_id.lower()):
            raise ValueError("preset_id must contain only letters, numbers, underscore, or hyphen")
        normalized["preset_id"] = preset_id.lower()
        normalized["format"] = str(normalized.get("format") or "raw")
        normalized["interpolation"] = str(normalized.get("interpolation") or "nearest")
        if normalized["interpolation"] not in {"nearest", "linear"}:
            raise ValueError("interpolation must be nearest or linear")
        normalized["max_texture_size"] = max(64, min(16384, int(normalized.get("max_texture_size", 4096))))
        normalized["padding"] = max(0, min(128, int(normalized.get("padding", 0))))
        normalized["extrusion"] = max(0, min(32, int(normalized.get("extrusion", 0))))
        normalized["scale"] = max(1, min(16, int(normalized.get("scale", 1))))
        normalized["block_on_errors"] = bool(normalized.get("block_on_errors", True))
        return normalized

    def preview(self, project_id: str, preset: Dict[str, Any]) -> Dict[str, Any]:
        preset = self.validate_preset(preset)
        files, total = [], 0
        for asset in self.repository.list_assets(project_id, limit=1000):
            if not asset.get("current_revision_id"):
                continue
            revision = self.repository.get_revision(asset["current_revision_id"])
            for record in revision.get("files", []):
                logical = self._output_name(preset, asset, record)
                files.append({"path": logical, "size_bytes": int(record.get("size_bytes", 0)), "sha256": record.get("sha256", "")})
                total += int(record.get("size_bytes", 0))
        files.extend(self._derived_file_tree(preset))
        return {"schema": "spriteforge.export_preview.v1", "preset": preset, "files": files, "estimated_bytes": total}

    def export(self, project_id: str, preset: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
        preset = self.validate_preset(preset)
        preview = self.preview(project_id, preset)
        if not any(not item.get("derived") for item in preview["files"]):
            raise ValueError("Project has no exportable asset revisions")
        if preset["block_on_errors"]:
            errors = self._blocking_errors(project_id)
            if errors:
                raise ValueError(f"Export blocked by {errors} QA error(s)")
        output_dir = Path(output_dir).resolve()
        staging = output_dir.with_name(f".{output_dir.name}.{uuid.uuid4().hex}.staging")
        backup = output_dir.with_name(f".{output_dir.name}.{uuid.uuid4().hex}.backup")
        manifest_files = []
        previous_files: Dict[str, str] = {}
        previous_manifest = output_dir / "spriteforge-export.json"
        if previous_manifest.is_file():
            try:
                previous_files = {item["path"]: item["sha256"] for item in json.loads(previous_manifest.read_text(encoding="utf-8")).get("files", [])}
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                previous_files = {}
        try:
            staging.mkdir(parents=True, exist_ok=False)
            for asset in self.repository.list_assets(project_id, limit=1000):
                revision_id = asset.get("current_revision_id")
                if not revision_id:
                    continue
                revision = self.repository.get_revision(revision_id)
                for record in revision.get("files", []):
                    digest = str(record.get("sha256") or "")
                    source = self.repository.objects_dir / digest[:2] / digest[2:4] / digest
                    if not source.is_file():
                        raise FileNotFoundError(f"Managed object missing: {digest}")
                    relative = self._output_name(preset, asset, record)
                    target = staging / Path(relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    previous = output_dir / Path(relative)
                    if previous_files.get(relative) == digest and previous.is_file():
                        shutil.copyfile(previous, target)
                    else:
                        shutil.copyfile(source, target)
                    manifest_files.append({
                        "path": Path(relative).as_posix(), "sha256": digest, "asset_id": asset["asset_id"],
                        "revision_id": revision_id, "logical_name": record.get("name", ""),
                    })
            self._write_derived(staging, preset, manifest_files)
            manifest = {
                "schema": "spriteforge.deterministic_export.v1", "schema_version": 1,
                "project_id": project_id, "preset": preset, "files": sorted(manifest_files, key=lambda item: item["path"]),
            }
            manifest["logical_digest"] = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            (staging / "spriteforge-export.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if output_dir.exists():
                os.replace(output_dir, backup)
            os.replace(staging, output_dir)
            with self.repository._connect() as connection:
                connection.execute(
                    "INSERT INTO export_history(export_id,revision_id,preset_id,manifest_json,created_at) VALUES(?,?,?,?,datetime('now'))",
                    (f"export_{uuid.uuid4().hex}", manifest_files[0]["revision_id"] if manifest_files else self._any_revision(project_id), preset["preset_id"], json.dumps(manifest, sort_keys=True)),
                )
            shutil.rmtree(backup, ignore_errors=True)
            return {"ok": True, "output_dir": str(output_dir), "manifest": manifest}
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            if backup.exists():
                if output_dir.exists():
                    shutil.rmtree(output_dir, ignore_errors=True)
                os.replace(backup, output_dir)
            raise

    def _blocking_errors(self, project_id: str) -> int:
        with self.repository._connect() as connection:
            rows = connection.execute(
                """SELECT q.payload_json FROM qa_reports q JOIN revisions r ON r.revision_id=q.revision_id
                   JOIN assets a ON a.asset_id=r.asset_id WHERE a.project_id=? AND a.current_revision_id=r.revision_id""", (project_id,)
            ).fetchall()
        return sum(int(json.loads(row["payload_json"]).get("summary", {}).get("error", 0)) for row in rows)

    def _any_revision(self, project_id: str) -> str:
        assets = self.repository.list_assets(project_id, limit=1)
        if not assets or not assets[0].get("current_revision_id"):
            raise ValueError("Project has no exportable asset revisions")
        return assets[0]["current_revision_id"]

    @staticmethod
    def _output_name(preset: Dict[str, Any], asset: Dict[str, Any], record: Dict[str, Any]) -> str:
        template = str(preset.get("naming") or "{asset_id}/{logical_name}")
        value = template.format(
            asset_id=asset["asset_id"], name=asset.get("name", asset["asset_id"]),
            action=asset.get("action", ""), direction=asset.get("direction", ""),
            logical_name=Path(str(record.get("name") or "asset.bin")).name,
        )
        path = Path(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Export naming template produced an unsafe path")
        return path.as_posix()

    @staticmethod
    def _derived_file_tree(preset: Dict[str, Any]) -> List[Dict[str, Any]]:
        format_name = preset["format"]
        names = {"css": ["sprites.css"], "json": ["atlas.json"], "phaser": ["atlas.json"],
                 "godot": ["IMPORTING.md"], "unity": ["IMPORTING.md"], "unreal": ["IMPORTING.md"]}.get(format_name, [])
        return [{"path": name, "derived": True, "size_bytes": 0} for name in names] + [{"path": "spriteforge-export.json", "derived": True, "size_bytes": 0}]

    @staticmethod
    def _write_derived(staging: Path, preset: Dict[str, Any], files: List[Dict[str, Any]]) -> None:
        format_name = preset["format"]
        if format_name in {"json", "phaser"}:
            (staging / "atlas.json").write_text(json.dumps({"frames": {item["path"]: {"source": item["path"]} for item in files}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif format_name == "css":
            css = "\n".join(f'.sprite-{index} {{ background-image: url("{item["path"]}"); image-rendering: pixelated; }}' for index, item in enumerate(files)) + "\n"
            (staging / "sprites.css").write_text(css, encoding="utf-8")
        elif format_name in {"godot", "unity", "unreal"}:
            (staging / "IMPORTING.md").write_text(f"# {preset['name']} import\n\nUse nearest-neighbor filtering. Preset revision: {preset['schema_version']}.\n", encoding="utf-8")
