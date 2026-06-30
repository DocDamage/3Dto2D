#!/usr/bin/env python3
"""
Web helper assets — thin re-export over split modules.

┌──────────────────────────────────────────────────┐
│ services/web_helpers_assets.py (re-export)       │
├──────────────────────────────────────────────────┤
│ services/web_helpers_library.py    (CRUD, refs)  │
│ services/web_helpers_listings.py   (queue, packs)│
│ services/web_helpers_sprite_preview.py (sprites) │
│ services/web_helpers_workspace.py   (workspace)  │
└──────────────────────────────────────────────────┘
"""
from services.web_helpers_library import (
    DynamicPath,
    ROOT, OUTPUT, INPUT, UPLOADS, ALLOWED_SUBDIRS,
    VIDEO_SUFFIXES, IMAGE_SUFFIXES, AUDIO_SUFFIXES,
    _is_relative_to, rel, safe_name,
    _library_list, _library_json_path, _library_save, _library_delete,
    _list_references, _list_planning_assets, _project_asset_counts,
)
from services.web_helpers_listings import (
    _resolve_queue_path, _get_failed_reason, _queue_progress, _queue_job_progress,
    _list_queues, _list_releases, _list_packs,
    _quality_source_path, _list_quality_reports,
)
from services.web_helpers_sprite_preview import (
    _resolve_sprite_output_dir, _comfy_output_root,
    _file_url, _safe_preview_file, _resolve_existing_file,
    _matching_experiment, _infer_source_video,
    _sprite_search_roots, sprite_outputs, sprite_preview_bundle,
    _qa_batch_summary,
)
from services.web_helpers_workspace import (
    _project_workspace,
)