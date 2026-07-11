"""Repeatable large-project performance benchmark for roadmap release gates."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, Dict

from services.asset_repository_service import AssetRepositoryService
from services.batch_matrix_service import BatchMatrixService
from services.workflow_builder_service import WorkflowBuilderService


def run_roadmap_benchmark(*, asset_count: int = 1000, timeline_frames: int = 2000,
                          matrix_cells: int = 5000, root: Path | None = None) -> Dict[str, Any]:
    owned_temp = tempfile.TemporaryDirectory(prefix="spriteforge_benchmark_") if root is None else None
    project = Path(root or owned_temp.name) / "project"
    repository = AssetRepositoryService(project)
    started = time.perf_counter()
    for index in range(max(1, int(asset_count))):
        repository.new_asset(project_id="benchmark", name=f"Asset {index:06d}", asset_type="sprite", action=f"action_{index % 20}", direction=f"dir_{index % 8}")
    insert_seconds = time.perf_counter() - started
    started = time.perf_counter()
    page = repository.list_assets("benchmark", limit=min(asset_count, 1000))
    asset_query_ms = (time.perf_counter() - started) * 1000
    timeline = [{"source_index": index, "duration_ms": 83, "anchors": {}, "hitboxes": []} for index in range(timeline_frames)]
    started = time.perf_counter()
    reversed_timeline = list(reversed(timeline))
    timeline_operation_ms = (time.perf_counter() - started) * 1000
    first_dimension = min(100, max(1, matrix_cells))
    second_dimension = max(1, min(100, (matrix_cells + first_dimension - 1) // first_dimension))
    started = time.perf_counter()
    experiment = BatchMatrixService(repository).create("benchmark", "Large matrix", {
        "seed": list(range(first_dimension)), "variant": list(range(second_dimension)),
    })
    matrix_create_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    filtered = BatchMatrixService(repository).get(experiment["experiment_id"], status="queued", limit=500)
    matrix_filter_ms = (time.perf_counter() - started) * 1000
    result = {
        "schema": "spriteforge.performance_report.v1", "inputs": {
            "asset_count": asset_count, "timeline_frames": timeline_frames, "matrix_cells_requested": matrix_cells,
        },
        "measurements": {
            "asset_insert_seconds": round(insert_seconds, 4), "asset_query_ms": round(asset_query_ms, 3),
            "timeline_reverse_ms": round(timeline_operation_ms, 3), "matrix_create_ms": round(matrix_create_ms, 3),
            "matrix_filter_ms": round(matrix_filter_ms, 3),
        },
        "counts": {"assets_returned": len(page), "timeline_frames": len(reversed_timeline), "matrix_cells": experiment["estimate"]["cell_count"], "filtered_cells": len(filtered["cells"])},
    }
    result["thresholds"] = {
        "asset_query_under_500ms": asset_query_ms < 500,
        "timeline_operation_under_100ms": timeline_operation_ms < 100,
        "matrix_filter_under_500ms": matrix_filter_ms < 500,
    }
    result["ok"] = all(result["thresholds"].values())
    if owned_temp is not None:
        owned_temp.cleanup()
    return result
