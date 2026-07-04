from typing import Any

from services.architecture_status.base import (
    APP,
    REPO_ROOT,
    SERVICES,
    WEB,
    ROOT_DEFINITION_PATTERN,
    SILENT_EXCEPTION_PATTERN,
    _load_json,
    _rel,
    _app_python_files,
)


def _canonical_root_status() -> dict[str, Any]:
    allowed = {
        APP / "spriteforge_utils.py",
        APP / "spriteforge_cloud.py",
    }
    offenders = [
        _rel(path)
        for path in _app_python_files()
        if path not in allowed
        and ROOT_DEFINITION_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    return {"ok": offenders == [], "offenders": offenders}


def _silent_service_exception_status() -> dict[str, Any]:
    offenders = []
    for path in SERVICES.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SILENT_EXCEPTION_PATTERN.search(text):
            offenders.append(_rel(path))
    return {"ok": offenders == [], "offenders": offenders}


def _json_persistence_status() -> dict[str, Any]:
    source = (APP / "spriteforge_utils.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "per_path_lock_registry": "_JSON_LOCKS" in source and "def _json_lock_for" in source,
        "reentrant_lock": "threading.RLock" in source,
        "save_json_uses_lock": "with lock:" in source and "os.replace" in source,
        "unique_temp_files": "os.getpid()" in source and "threading.get_ident()" in source,
        "load_json_uses_lock": "with _json_lock_for(path):" in source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _duplicate_js_function_status() -> dict[str, Any]:
    from services.architecture_status.base import TOP_LEVEL_FUNCTION_PATTERN
    allowed_duplicates = {
        "formatDuration": {"app_dashboard.js"},
    }
    seen: dict[str, set[str]] = {}
    for path in sorted((WEB / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in TOP_LEVEL_FUNCTION_PATTERN.findall(text):
            seen.setdefault(name, set()).add(path.name)

    duplicates = {
        name: sorted(files)
        for name, files in seen.items()
        if len(files) > 1 and files != allowed_duplicates.get(name, set())
    }
    return {"ok": duplicates == {}, "duplicates": duplicates}


def _duplicate_css_selector_status() -> dict[str, Any]:
    from services.architecture_status.base import CSS_SELECTOR_PATTERN
    allowed_override_files = {
        "css/accessibility.css",
        "css/app_compact_fit.css",
        "css/app_resizers.css",
        "css/guided_setup_extra.css",
        "css/inspector_ab_compare.css",
        "css/topbar_compact.css",
        "css/ux_enhancements.css",
        "css/wizard.css",
        "mobile_nav.css",
        "theme.css",
    }
    seen: dict[str, set[str]] = {}
    for path in sorted(list(WEB.glob("*.css")) + list((WEB / "css").glob("*.css"))):
        rel = path.relative_to(WEB).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in CSS_SELECTOR_PATTERN.finditer(text):
            raw = match.group(2).strip()
            for selector in [item.strip() for item in raw.split(",") if item.strip()]:
                if selector.startswith("@") or selector in {"from", "to"} or len(selector) > 160:
                    continue
                seen.setdefault(selector, set()).add(rel)

    duplicates = {
        selector: sorted(files)
        for selector, files in seen.items()
        if len(files) > 1
    }
    unmanaged = {
        selector: files
        for selector, files in duplicates.items()
        if not (set(files) & allowed_override_files)
    }
    return {
        "ok": unmanaged == {},
        "duplicates_count": len(duplicates),
        "unmanaged_duplicates": unmanaged,
        "allowed_override_files": sorted(allowed_override_files),
    }


def _job_runner_status() -> dict[str, Any]:
    source = (SERVICES / "job_service.py").read_text(encoding="utf-8", errors="ignore")
    return {
        "ok": "class JobRunner" in source and "class JobPhase" in source and "class JobStage" in source and "JobRunner(job, cmd).start()" in source and "def worker():" not in source and "queue.SimpleQueue" in source,
        "class_present": "class JobRunner" in source,
        "phase_contract": "class JobPhase" in source and "JobPhase.RUNNING" in source and "JobPhase.CANCELLED" in source,
        "stage_contract": "class JobStage" in source and "JobStage.QUEUED" in source and "JobStage.COMPLETE" in source,
        "start_job_uses_runner": "JobRunner(job, cmd).start()" in source,
        "nested_worker_removed": "def worker():" not in source,
        "retry_queue": "self.retry_queue" in source and "queue.SimpleQueue" in source and "self.retry_queue.put" in source,
    }


def _config_model_status() -> dict[str, Any]:
    model_source = (SERVICES / "config_model.py").read_text(encoding="utf-8", errors="ignore")
    config_source = (SERVICES / "config_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "typed_config_model": "class SpriteForgeConfig" in model_source and "class WanProfile" in model_source,
        "validation_warnings": "def validate" in model_source and "dimensions should be divisible by 8" in model_source,
        "effective_profile_explain": "def effective_profile" in model_source and "spriteforge.effective_profile.v1" in model_source,
        "config_service_bridge": "def explain_effective_profile" in config_source,
        "effective_profile_endpoint": '@routes_misc.route("/api/config/effective-profile"' in routes_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _feature_capability_status() -> dict[str, Any]:
    service_source = (SERVICES / "feature_capability_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "capability_endpoint": '@routes_misc.route("/api/features/capabilities"' in routes_source,
        "runtime_resolver": "def resolve_runtime" in service_source and "native_only" in service_source,
        "runtime_modes_report": '"runtime_modes"' in service_source and '"default_runtime"' in service_source,
        "selection_reason_report": '"selection_reason"' in service_source and "external_reason" in service_source,
        "opt_in_flags_report": '"opt_in_flags"' in service_source and "--native-only" in service_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _security_status() -> dict[str, Any]:
    routes_source = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8", errors="ignore")
    frame_source = (SERVICES / "frame_status_service.py").read_text(encoding="utf-8", errors="ignore")
    audio_source = (SERVICES / "audio_cue_service.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "frame_filename_sanitizer": "def sanitize_frame_filename" in frame_source,
        "frame_save_uses_sanitizer": "sanitize_frame_filename(frame_name)" in routes_source,
        "frame_save_rate_limited": '@route_rate_limited("sprite_frame_save"' in routes_source,
        "frame_status_rate_limited": '@route_rate_limited("sprite_frame_status"' in routes_source,
        "metadata_save_rate_limited": '@route_rate_limited("sprite_save_metadata"' in routes_source,
        "repack_rate_limited": '@route_rate_limited("sprite_repack_sheet"' in routes_source,
        "palette_harmonize_rate_limited": '@route_rate_limited("sprite_palette_harmonize"' in routes_source,
        "audio_cue_write_rate_limited": '@route_rate_limited("sprite_audio_cue_write"' in routes_source,
        "audio_cue_runtime_handoff": "def _engine_import_metadata" in audio_source and "time_seconds" in audio_source,
        "skeletal_output_workspace_guard": "def _resolve_workspace_output_dir" in routes_source and "output must stay inside the SpriteForge workspace" in routes_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _database_layer_status() -> dict[str, Any]:
    service_source = (SERVICES / "database_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "sqlite_service": "class DatabaseService" in service_source and "sqlite3.connect" in service_source,
        "records_schema": "CREATE TABLE IF NOT EXISTS records" in service_source,
        "fts_schema": "CREATE VIRTUAL TABLE IF NOT EXISTS records_fts" in service_source,
        "json_migration": "def migrate_default_json" in service_source and "migrate_json_list" in service_source,
        "search_sanitizer": "def _fts_query" in service_source and "re.findall" in service_source,
        "migration_endpoint": '@routes_misc.route("/api/database/migrate"' in routes_source,
        "search_endpoint": '@routes_misc.route("/api/database/search"' in routes_source,
        "recent_endpoint": '@routes_misc.route("/api/database/recent"' in routes_source,
        "stats_endpoint": '@routes_misc.route("/api/database/stats"' in routes_source,
        "health_endpoint": '@routes_misc.route("/api/database/health"' in routes_source,
        "counts_by_kind": "def counts_by_kind" in service_source,
        "health_report": "def health" in service_source and "PRAGMA integrity_check" in service_source and "fts_in_sync" in service_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _test_suite_status() -> dict[str, Any]:
    conftest_source = (REPO_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8", errors="ignore")
    matting_test = REPO_ROOT / "tests" / "test_process_common_matting_engines.py"
    matting_source = matting_test.read_text(encoding="utf-8", errors="ignore") if matting_test.exists() else ""
    checks = {
        "sample_sheet_json_fixture": "def sample_sheet_json" in conftest_source and '"frame_width"' in conftest_source and '"frames"' in conftest_source,
        "synthetic_rgba_frames": "def synthetic_rgba_frames" in conftest_source and "Image.new(\"RGBA\"" in conftest_source,
        "synthetic_sprite_factory": "def synthetic_sprite_factory" in conftest_source,
        "synthetic_frame_items": "def synthetic_frame_items" in conftest_source,
        "mock_comfy_system_stats": "def mock_comfy_system_stats" in conftest_source,
        "process_common_matting_parameterized": "pytest.mark.parametrize" in matting_source and "process_common" in matting_source,
    }
    return {"ok": all(checks.values()), "checks": checks}
