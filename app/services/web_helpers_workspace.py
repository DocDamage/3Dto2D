#!/usr/bin/env python3
"""Project workspace summaries."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.project_service import ProjectService
from services.experiment_service import ExperimentService

from services.web_helpers_sprite_preview import sprite_outputs
from services.web_helpers_listings import (
    _list_queues, _list_releases, _list_packs, _list_quality_reports,
)
from services.web_helpers_library import _project_asset_counts


def _project_workspace(project_meta: Optional[Dict[str, str]]) -> Dict[str, Any]:
    experiments = [
        rec for rec in ExperimentService.get_history()
        if ProjectService.item_matches_project(rec, project_meta)
    ] if project_meta else ExperimentService.get_history()
    outputs = sprite_outputs(500, project_meta)
    queues = _list_queues(project_meta)
    releases = _list_releases(project_meta)
    packs = _list_packs(project_meta)
    quality = _list_quality_reports(project_meta)
    assets = _project_asset_counts(project_meta)
    return {
        "active": project_meta,
        "outputs": len(outputs),
        "experiments": len(experiments),
        "queues": len(queues),
        "releases": len(releases),
        "quality": len(quality),
        **assets,
        "packs": len(packs),
        "starred": sum(1 for rec in experiments if rec.get("starred")),
    }