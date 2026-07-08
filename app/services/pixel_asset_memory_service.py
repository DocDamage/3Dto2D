from __future__ import annotations

import json
from typing import Any, Dict, Optional

from services.experiment_service import ExperimentService
from services.web_helpers_library import _library_save


class PixelAssetMemoryService:
    """Bridge Pixel Studio assets into SpriteForge's existing memory surfaces."""

    @staticmethod
    def remember_asset(asset: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        outputs = asset.get("outputs", {}) if isinstance(asset.get("outputs"), dict) else {}
        qa = asset.get("qa", {}) if isinstance(asset.get("qa"), dict) else {}
        project_name = str(params.get("project_name") or params.get("project") or "").strip()
        prompt = str(asset.get("prompt") or params.get("prompt") or "")
        negative = str(asset.get("negative") or params.get("negative") or "")
        asset_id = str(asset.get("asset_id") or "")
        asset_type = str(asset.get("asset_type") or "pixel_asset")
        png_path = str(outputs.get("png") or "")

        run_id = ExperimentService.append_run(
            job_id=f"pixel_asset:{asset_id}",
            prompt=prompt,
            negative=negative,
            model_tier=str(asset.get("provider") or ""),
            profile=f"pixel_studio:{asset_type}",
            sprite_action=str(asset.get("mode") or "reference_batch"),
            direction="pixel_asset",
            workflow_hash=str(asset.get("batch_id") or ""),
            sprite_folder=png_path,
            project_name=project_name,
            qa_score=float(qa.get("color_count", 0) or 0),
            qa_passed=bool(qa.get("ok", False)),
            notes=json.dumps({
                "kind": "pixel_asset",
                "asset_id": asset_id,
                "batch_id": asset.get("batch_id", ""),
                "asset_type": asset_type,
                "style_profile_id": asset.get("style_profile_id", ""),
                "metadata": outputs.get("metadata", ""),
            }),
        )

        memory: Dict[str, Any] = {"experiment_run_id": run_id}

        if project_name:
            title_prompt = prompt.strip() or asset_type.replace("_", " ")
            title = f"{asset_type.replace('_', ' ').title()}: {title_prompt[:48]}"
            library_payload = {
                "id": asset_id,
                "title": title,
                "category": "pixel_asset",
                "content": json.dumps({
                    "asset_id": asset_id,
                    "batch_id": asset.get("batch_id", ""),
                    "asset_type": asset_type,
                    "prompt": prompt,
                    "style_profile_id": asset.get("style_profile_id", ""),
                    "metadata": outputs.get("metadata", ""),
                }),
                "reference_path": png_path,
            }
            try:
                library_result = _library_save(project_name, library_payload)
                memory["library_asset_id"] = library_result.get("asset", {}).get("id", asset_id)
            except Exception as exc:
                memory["library_error"] = str(exc)

        return memory

    @staticmethod
    def pixel_experiment_rows(limit: int = 200) -> list[Dict[str, Any]]:
        rows = []
        for record in ExperimentService.get_history(limit=limit):
            notes = record.get("notes", "")
            try:
                parsed = json.loads(notes) if isinstance(notes, str) and notes else {}
            except json.JSONDecodeError:
                parsed = {}
            if parsed.get("kind") == "pixel_asset" or str(record.get("job_id", "")).startswith("pixel_asset:"):
                item = dict(record)
                item["pixel_asset"] = parsed
                rows.append(item)
        return rows
