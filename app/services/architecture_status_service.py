import json
import re
import time
from pathlib import Path
from typing import Any

from spriteforge_utils import ROOT as APP_ROOT


APP = APP_ROOT if APP_ROOT.name == "app" else APP_ROOT / "app"
REPO_ROOT = APP.parent
SERVICES = APP / "services"
WEB = APP / "web"


ROOT_DEFINITION_PATTERN = re.compile(
    r"^ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)?\s*$",
    re.M,
)
SILENT_EXCEPTION_PATTERN = re.compile(
    r"except (?:Exception(?:\s+as\s+\w+)?|KeyError(?:\s+as\s+\w+)?):\s*(?:\n\s*pass\s*(?:#.*)?$|pass\s*(?:#.*)?$)",
    re.M,
)
TOP_LEVEL_FUNCTION_PATTERN = re.compile(
    r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
    re.M,
)
CSS_SELECTOR_PATTERN = re.compile(r"(^|})\s*([^{}@][^{}]*)\s*\{", re.S)
CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, Any] | None = None
_CACHE_TIME = 0.0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _app_python_files() -> list[Path]:
    return [
        path
        for path in APP.rglob("*.py")
        if "vendor" not in path.parts and "__pycache__" not in path.parts
    ]


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


def _performance_status() -> dict[str, Any]:
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    dashboard_source = (WEB / "js" / "app_dashboard.js").read_text(encoding="utf-8", errors="ignore")
    main_source = (WEB / "js" / "app_main.js").read_text(encoding="utf-8", errors="ignore")
    websocket_source = (SERVICES / "websocket_service.py").read_text(encoding="utf-8", errors="ignore")
    comfy_source = (SERVICES / "comfy_service.py").read_text(encoding="utf-8", errors="ignore")
    model_source = (SERVICES / "model_service.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "heartbeat_endpoint": '@routes_misc.route("/api/heartbeat"' in routes_source,
        "lightweight_heartbeat_client": "async function refreshHeartbeat" in main_source and "api('/api/heartbeat')" in main_source and "setInterval(refreshHeartbeat, interval)" in main_source,
        "progress_stream_endpoint": '@routes_misc.route("/api/progress/stream"' in routes_source,
        "progress_events_endpoint": '@routes_misc.route("/api/progress/events"' in routes_source and 'request.args.get("after")' in routes_source and "ProgressEventHub.recent(after=after" in routes_source,
        "progress_transport_endpoint": '@routes_misc.route("/api/progress/transport"' in routes_source,
        "progress_transport_descriptor": "def progress_transport_status" in websocket_source and '"browser_transport": "sse"' in websocket_source,
        "progress_event_replay": "MAX_EVENT_HISTORY" in websocket_source and "deque(maxlen=MAX_EVENT_HISTORY)" in websocket_source and "def recent(cls, after: int = 0" in websocket_source,
        "dashboard_eventsource": "new EventSource('/api/progress/stream')" in dashboard_source,
        "dashboard_polling_fallback": "dashboardActivityFallbackTimer" in dashboard_source and "setInterval(refreshDashboardActivityFeed, 5000)" in dashboard_source and "dashboardActivitySource.onerror" in dashboard_source,
        "desktop_completion_notifications": "new Notification(title" in dashboard_source and "Notification.requestPermission()" in dashboard_source and "job.failed" in dashboard_source,
        "comfy_running_cache": "_running_cache_ttl" in comfy_source and "force_refresh" in comfy_source,
        "gpu_info_cache": "_gpu_info_cache" in comfy_source and "get_gpu_info(force_refresh" in comfy_source,
        "cache_metadata": "def _cache_meta" in comfy_source and '"from_cache"' in comfy_source and "def _cache_meta" in model_source and '"ttl_seconds"' in model_source,
        "model_summary_cache": "_summary_cache" in model_source and "get_summary(force_refresh" in model_source,
        "disk_summary_cache": "_disk_cache" in model_source and "get_disk_summary(force_refresh" in model_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _design_system_status() -> dict[str, Any]:
    variables_source = (WEB / "css" / "base_variables.css").read_text(encoding="utf-8", errors="ignore")
    components_source = (WEB / "css" / "components.css").read_text(encoding="utf-8", errors="ignore")
    theme_source = (WEB / "theme.css").read_text(encoding="utf-8", errors="ignore")
    styles_source = (WEB / "styles.css").read_text(encoding="utf-8", errors="ignore")
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "base_variables_first": '@import url("css/base_variables.css");' in styles_source.splitlines()[0],
        "spacing_scale": all(token in variables_source for token in ["--space-1", "--space-2", "--space-3", "--space-4", "--space-6", "--space-8", "--space-12", "--space-16"]),
        "font_tokens": "--font-ui: Inter" in variables_source and "--font-mono" in variables_source and "JetBrains Mono" in variables_source,
        "theme_tokens": "body.theme-light" in variables_source and "body.theme-light" in theme_source,
        "skeleton_primitives": "--skeleton-base" in variables_source and ".skeleton-stack" in components_source and "@keyframes skeleton-sheen" in components_source,
        "theme_toggle": 'id="themeToggle"' in index_source and "js/theme_toggle.js" in index_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _pipeline_powerups_status() -> dict[str, Any]:
    pipeline_source = (SERVICES / "sprite_processing_pipeline.py").read_text(encoding="utf-8", errors="ignore")
    interpolation_source = (SERVICES / "sprite_interpolation.py").read_text(encoding="utf-8", errors="ignore")
    chroma_source = (SERVICES / "sprite_chroma_alpha.py").read_text(encoding="utf-8", errors="ignore")
    temporal_source = (SERVICES / "sprite_temporal_smooth.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8", errors="ignore")
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    animation_component = (WEB / "components" / "animation_player.html").read_text(encoding="utf-8", errors="ignore")
    animation_script = (WEB / "js" / "animation_player.js").read_text(encoding="utf-8", errors="ignore")
    animation_css = (WEB / "animation_player.css").read_text(encoding="utf-8", errors="ignore")
    frame_component = (WEB / "components" / "frame_editor.html").read_text(encoding="utf-8", errors="ignore")
    frame_script = (WEB / "js" / "frame_editor.js").read_text(encoding="utf-8", errors="ignore")
    frame_css = (WEB / "frame_editor.css").read_text(encoding="utf-8", errors="ignore")
    frame_repack_source = (SERVICES / "frame_repack_service.py").read_text(encoding="utf-8", errors="ignore")
    cmd_source = (SERVICES / "web_helpers_cmd.py").read_text(encoding="utf-8", errors="ignore")
    parser_source = (APP / "spriteforge_unified_parser.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "animation_player_view": "animation_player.css" in index_source and "js/animation_player.js" in index_source and "animation-player-view" in animation_component,
        "animation_player_controls": all(token in animation_component for token in ["animationPlayBtn", "animationSpeedSlider", "animationFrameScrubber", "animationOnionSlider"]),
        "animation_player_canvas_loop": "requestAnimationFrame" in animation_script and "drawImage" in animation_script,
        "animation_player_hit_markers": "animationHitFrameLegend" in animation_component and "function hitFrameLabel" in animation_script and ".animation-tick.hit-frame" in animation_css,
        "animation_player_webm_recording": "MediaRecorder.isTypeSupported" in animation_script and "video/webm;codecs=vp9" in animation_script and "WebM recording is not supported by this browser" in animation_script,
        "frame_editor_view": "frame_editor.css" in index_source and "js/frame_editor.js" in index_source and "frame-editor-view" in frame_component,
        "frame_editor_repack_api": '@routes_sprites.route("/api/repack-sheet"' in routes_source and "async function repack()" in frame_script,
        "frame_editor_multi_select_retime": "frameEditorDurationHint" in frame_component and "selected.forEach(index" in frame_script and "frame-editor-duration-hint" in frame_css,
        "frame_editor_repack_history": "spriteforge.frame_repack_history.v1" in frame_repack_source and "deleted_source_indices" in frame_repack_source and "duration_overrides" in frame_repack_source,
        "rife_interpolation": 'engine == "rife"' in interpolation_source and "fallback" in interpolation_source and "blend" in interpolation_source,
        "depth_anything_matting": 'matting_engine == "depth-anything"' in pipeline_source and "def try_depth_anything" in chroma_source,
        "temporal_smoothing": "def stabilize_temporal_coherence" in temporal_source and "temporal_smooth_info" in pipeline_source,
        "multi_resolution_exports": "--resolution-hierarchy" in parser_source and "resolutions" in pipeline_source and "resolution_export" in pipeline_source,
        "web_command_forwarding": all(token in cmd_source for token in ["--temporal-smooth", "--resolution-hierarchy", "--interpolation-engine"]),
    }
    return {"ok": all(checks.values()), "checks": checks}


def _keyboard_ux_status() -> dict[str, Any]:
    shortcuts_source = (WEB / "js" / "keyboard_shortcuts.js").read_text(encoding="utf-8", errors="ignore")
    command_palette_source = (WEB / "js" / "command_palette.js").read_text(encoding="utf-8", errors="ignore")
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "shortcut_module_loaded": "js/keyboard_shortcuts.js" in index_source,
        "command_palette_loaded": "js/command_palette.js" in index_source and "commandPaletteModal" in index_source,
        "command_palette_shortcut": "ctrlKey || e.metaKey" in command_palette_source and "key.toLowerCase() === 'k'" in command_palette_source,
        "alt_number_navigation": "event.altKey && key >= '1' && key <= '9'" in shortcuts_source and "primaryShortcutViews" in shortcuts_source,
        "playback_shortcuts": "togglePreviewPlayback" in shortcuts_source and "animationPlayBtn" in shortcuts_source,
        "frame_step_shortcuts": "moveFrame(-1)" in shortcuts_source and "moveFrame(1)" in shortcuts_source,
        "action_shortcuts": all(token in shortcuts_source for token in ["runExportShortcut", "runQualityShortcut", "runGenerateShortcut", "runSaveShortcut"]),
        "cheat_sheet": "shortcutCheatSheet" in shortcuts_source and "toggleShortcutHelp" in shortcuts_source,
        "shortcut_metadata": "cmd.shortcut" in command_palette_source and "shortcutTag.textContent = cmd.shortcut" in command_palette_source,
        "command_risk_metadata": "cmd.risk_level" in command_palette_source and "cmd.confirmation_message" in command_palette_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _dashboard_generate_ux_status() -> dict[str, Any]:
    dashboard_source = (WEB / "components" / "dashboard.html").read_text(encoding="utf-8", errors="ignore")
    generate_source = (WEB / "components" / "generate.html").read_text(encoding="utf-8", errors="ignore")
    dashboard_script = (WEB / "js" / "app_dashboard.js").read_text(encoding="utf-8", errors="ignore")
    forms_source = (WEB / "js" / "app_forms.js").read_text(encoding="utf-8", errors="ignore")
    drag_drop_source = (WEB / "js" / "drag_drop.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "dashboard_hero_stats": "dashboard-hero-stats" in dashboard_source and all(token in dashboard_source for token in ["dashboardStatSprites", "dashboardStatQa", "dashboardStatProject", "dashboardStatDisk"]),
        "dashboard_recent_gallery": 'id="gallery"' in dashboard_source and "Recent Sprites" in dashboard_source,
        "dashboard_quick_actions": "quick-actions-grid dashboard-actions" in dashboard_source and all(token in dashboard_source for token in ["dashActionCreate", "dashActionReview", "dashActionExport"]),
        "dashboard_activity_feed": "dashboardActivityFeed" in dashboard_source and "new EventSource('/api/progress/stream')" in dashboard_script,
        "generate_prompt_preview": "generatePromptPreviewPanel" in generate_source and "refreshGeneratePromptPreview" in forms_source,
        "generate_quality_indicator": "generatePromptQuality" in generate_source and "prompt-quality-badge" in generate_source and "/api/prompt/lint" in forms_source,
        "generate_reference_preview": "generateReferencePreview" in generate_source and "refreshGenerateReferencePreview" in forms_source,
        "generate_drag_drop_refresh": "typeof refreshGenerateReferencePreview === 'function'" in drag_drop_source and "Preview updates after upload" in drag_drop_source,
        "visual_preset_shortcuts": all(token in generate_source for token in ["btnGoalPixelArt", "btnGoalSmooth2D", "btnGoalLocalQuality"]),
        "estimated_generation_inputs": all(token in generate_source for token in ['name="tier"', 'name="profile"', 'name="cell_size"', 'name="interpolate_fps"']),
    }
    return {"ok": all(checks.values()), "checks": checks}


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


def _easy_mode_status() -> dict[str, Any]:
    ui_source = (SERVICES / "easy_ui_mixin.py").read_text(encoding="utf-8", errors="ignore")
    helper_source = (SERVICES / "easy_helpers.py").read_text(encoding="utf-8", errors="ignore")
    actions_source = (SERVICES / "easy_actions_mixin.py").read_text(encoding="utf-8", errors="ignore")
    app_source = (APP / "spriteforge_easy.py").read_text(encoding="utf-8", errors="ignore")
    utils_source = (APP / "spriteforge_utils.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "tkinter_retained_option_a": "tk.Tk" in app_source and "Easy Mode modernization: Option A active" in ui_source,
        "dark_theme_polish": "apply_dark_theme(self)" in app_source and "def apply_dark_theme" in utils_source and 'style.theme_use("clam")' in utils_source,
        "header_progress_bar": "self.progress_bar = ttk.Progressbar" in ui_source,
        "progress_parser_hook": "parse_progress_percent" in ui_source and "def parse_progress_percent" in helper_source,
        "embedded_preview": "recent_preview_label" in ui_source and "def load_sprite_preview" in helper_source,
        "web_studio_handoff": "def open_web_studio" in actions_source and '"spriteforge_unified.py", "web"' in actions_source,
        "web_studio_button": "Open Web Studio" in ui_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _plugin_sdk_status() -> dict[str, Any]:
    plugin_source = (SERVICES / "plugin_manager.py").read_text(encoding="utf-8", errors="ignore")
    marketplace_source = (SERVICES / "marketplace_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    release_source = (WEB / "components" / "release.html").read_text(encoding="utf-8", errors="ignore")
    marketplace_ui_source = (WEB / "js" / "marketplace_gallery.js").read_text(encoding="utf-8", errors="ignore")
    marketplace_css_source = (WEB / "marketplace_gallery.css").read_text(encoding="utf-8", errors="ignore")
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "sdk_version_constant": "PLUGIN_SDK_VERSION" in plugin_source,
        "sdk_contract": "def plugin_sdk_contract" in plugin_source,
        "sdk_scaffold": "def plugin_scaffold" in plugin_source,
        "manifest_validation": "def validate_plugin_manifest" in plugin_source and "spriteforge.plugin_manifest_validation.v1" in plugin_source,
        "sdk_endpoint": '@routes_misc.route("/api/plugins/sdk"' in routes_source and "plugin_scaffold(plugin_id)" in routes_source,
        "sdk_starter_ui": "pluginSdkId" in release_source and "pluginSdkSummary" in release_source and "pluginSdkScaffold" in release_source,
        "sdk_starter_fetch": "function loadPluginSdkStarter" in marketplace_ui_source and "/api/plugins/sdk?id=" in marketplace_ui_source,
        "sdk_starter_styles": ".plugin-sdk-card" in marketplace_css_source and ".plugin-sdk-scaffold" in marketplace_css_source,
        "compatibility_function": "def plugin_compatibility" in plugin_source,
        "manifest_compatible_field": '"compatible": compatibility["compatible"]' in plugin_source,
        "incompatible_plugins_not_loaded": 'not metadata.get("compatible", False)' in plugin_source,
        "marketplace_schema": "MARKETPLACE_SCHEMA" in marketplace_source,
        "marketplace_import_planning": "def plan_marketplace_import" in marketplace_source,
        "marketplace_import_copy": "def import_marketplace_bundle" in marketplace_source and "shutil.copy2" in marketplace_source,
        "marketplace_share_manifest": "def build_marketplace_share_manifest" in marketplace_source,
        "marketplace_share_checks": "share_checks" in marketplace_source and "license_declared" in marketplace_source and "local_import_plan_ok" in marketplace_source,
        "marketplace_bundle_integrity": "def _bundle_integrity" in marketplace_source and '"sha256"' in marketplace_source,
        "marketplace_share_compatibility": "spriteforge.marketplace_share_compatibility.v1" in marketplace_source and "PLUGIN_SDK_VERSION" in marketplace_source,
        "marketplace_workspace_escape_guard": "source.relative_to(root)" in marketplace_source,
        "marketplace_endpoints": all(route in routes_source for route in ['"/api/marketplace/gallery"', '"/api/marketplace/import"', '"/api/marketplace/share-manifest"']),
        "marketplace_ui_assets": "marketplace_gallery.css" in index_source and "js/marketplace_gallery.js" in index_source,
        "marketplace_release_panel": "marketplaceList" in release_source and "marketplaceShareManifest" in release_source and "marketplaceShareResult" in release_source,
        "marketplace_import_ui": "data-market-import" in marketplace_ui_source and "/api/marketplace/import" in marketplace_ui_source,
        "marketplace_share_ui": "buildMarketplaceShareManifest" in marketplace_ui_source and "/api/marketplace/share-manifest" in marketplace_ui_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _cloud_hub_status() -> dict[str, Any]:
    cloud_source = (SERVICES / "cloud_hub_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    component_source = (WEB / "components" / "cloud_hub.html").read_text(encoding="utf-8", errors="ignore")
    script_source = (WEB / "js" / "cloud_hub.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "node_registry": "CLOUD_NODES_PATH" in cloud_source,
        "capacity_selection": "active_jobs" in cloud_source and "max_jobs" in cloud_source,
        "dispatch_planning": "def plan_cloud_dispatch" in cloud_source,
        "queue_assignment_planning": "def plan_cloud_queue_assignments" in cloud_source and "spriteforge_cloud_queue_assignment_v1" in cloud_source,
        "queue_dispatch_handoff": "def _dispatch_handoff" in cloud_source and "spriteforge_cloud_queue_dispatch_v1" in cloud_source and '"capacity_snapshot"' in cloud_source,
        "dispatch_plan_in_status": '"dispatch_plan": dispatch_plan' in cloud_source,
        "queue_plan_in_status": '"queue_plan": queue_plan' in cloud_source,
        "cloud_nodes_api": '@routes_misc.route("/api/cloud/nodes"' in routes_source,
        "cloud_queue_api": '@routes_misc.route("/api/cloud/queue-plan"' in routes_source,
        "ui_assets": "cloud_hub.css" in index_source and "js/cloud_hub.js" in index_source and 'data-view="cloud_hub"' in index_source,
        "node_management_ui": all(token in component_source for token in ["cloudHubNodes", "cloudHubNodeMaxJobs", "cloudHubNodeStatus", "cloudHubSave"]),
        "node_operator_controls": all(token in script_source for token in ["data-cloud-state", "data-cloud-status=\"draining\"", "data-cloud-enabled=\"false\"", "function updateCloudHubNodeState"]),
        "provider_readiness_ui": "cloudImageProviders" in component_source and "/api/cloud/image-providers" in script_source,
        "cloud_image_plan_ui": "cloudImagePlanPreview" in component_source and "renderCloudImagePlan" in script_source and "/api/cloud/image-generation-plan" in script_source,
        "queue_distribution_ui": "cloudQueuePlanPreview" in component_source and "renderCloudQueuePlan" in script_source and "Planning remote queue distribution" in script_source,
        "queue_dispatch_ui": "row.dispatch?.command_hint" in script_source and "queue_position" in script_source,
        "loading_skeletons": "renderCloudHubSkeleton" in script_source and "skeleton-stack" in script_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _cloud_image_generation_status() -> dict[str, Any]:
    cloud_image_source = (SERVICES / "cloud_image_generation_service.py").read_text(encoding="utf-8", errors="ignore")
    parser_source = (APP / "spriteforge_unified_parser.py").read_text(encoding="utf-8", errors="ignore")
    cmd_source = (SERVICES / "web_helpers_cmd.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "local_env_keys": "def resolve_api_key" in cloud_image_source and "provider_key_names" in cloud_image_source,
        "openai_provider": "def _openai_generate" in cloud_image_source and "gpt-image-1" in cloud_image_source,
        "gemini_provider": "def _gemini_generate" in cloud_image_source and "imagen-3.0-generate-002" in cloud_image_source,
        "secret_safe_plan": "def build_cloud_generation_plan" in cloud_image_source and "secret_values_exposed" in cloud_image_source,
        "generation_contract": "spriteforge.cloud_generation_contract.v1" in cloud_image_source and "one_frame_per_request" in cloud_image_source and "secret_values_persisted" in cloud_image_source,
        "prompt_hardening": "def hardened_prompt" in cloud_image_source and "DEFAULT_CONSTRAINTS" in cloud_image_source,
        "chroma_alpha": "apply_chroma_key" in cloud_image_source,
        "nearest_neighbor": "Image.Resampling.NEAREST" in cloud_image_source,
        "palette_quantization": "apply_native_pixel_cleanup" in cloud_image_source,
        "grid_stitching": "pack_sheet(processed" in cloud_image_source,
        "frame_provenance": "frame_sources" in cloud_image_source and "hardened_prompt" in cloud_image_source and "processed_frame" in cloud_image_source,
        "cleanup_metrics": "def _frame_cleanup_metrics" in cloud_image_source and "spriteforge.cloud_frame_cleanup.v1" in cloud_image_source,
        "cli_command": 'sub.add_parser("cloud-image-sprite"' in parser_source,
        "web_command": 'if action == "cloud_image_sprite"' in cmd_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _qa_advisor_status() -> dict[str, Any]:
    advisor_source = (SERVICES / "qa_advisor_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8", errors="ignore")
    qa_source = (WEB / "js" / "qa.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "advisor_endpoint": '@routes_sprites.route("/api/qa/advisor"' in routes_source,
        "feedback_endpoint": '@routes_sprites.route("/api/qa/advisor/feedback"' in routes_source,
        "feedback_persistence": "qa_advisor_feedback.json" in advisor_source,
        "learning_summary": "learning_summary" in advisor_source,
        "learned_preference": "learned_preference" in advisor_source,
        "advice_reranking": "advice.sort" in advisor_source,
        "learning_summary_ui": "qa-advisor-learning" in qa_source and "promoted_codes" in qa_source and "deprioritized_codes" in qa_source,
        "repair_action_mapping": "REPAIR_ACTIONS" in advisor_source and "repair_action" in advisor_source,
        "repair_plan_payload": "def _repair_plan" in advisor_source and '"automation_ready"' in advisor_source and "row.repair_plan" in qa_source,
        "repair_plan_runbook": '"runbook"' in advisor_source and '"verification"' in advisor_source and "def _command_tokens" in advisor_source,
        "repair_plan_contract": "spriteforge.qa_repair_plan.v1" in advisor_source and "def _repair_plan_id" in advisor_source and '"risk_level"' in advisor_source,
        "repair_action_ui": "qa-advisor-repair" in qa_source and "button_id" in qa_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _tilemap_status() -> dict[str, Any]:
    tilemap_source = (SERVICES / "tilemap_service.py").read_text(encoding="utf-8", errors="ignore")
    parser_source = (APP / "spriteforge_unified_parser.py").read_text(encoding="utf-8", errors="ignore")
    cmd_source = (SERVICES / "web_helpers_cmd.py").read_text(encoding="utf-8", errors="ignore")
    training_source = (WEB / "components" / "training.html").read_text(encoding="utf-8", errors="ignore")
    forms_source = (WEB / "js" / "app_forms.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "autotile_16_generation": "def generate_16_autotiles" in tilemap_source,
        "wang_16_generation": "def generate_wang_tiles" in tilemap_source,
        "engine_layout_metadata": "def build_autotile_engine_layouts" in tilemap_source,
        "engine_manifest": "def build_tilemap_engine_manifest" in tilemap_source and "spriteforge.tilemap_engine_manifest.v1" in tilemap_source,
        "engine_tile_index_table": '"tiles": tiles' in tilemap_source and '"atlas_coords"' in tilemap_source and '"terrain_peering_bits"' in tilemap_source,
        "godot_layout": '"godot"' in tilemap_source and "terrain_set" in tilemap_source,
        "rpg_maker_layout": '"rpg_maker"' in tilemap_source and "A2-compatible" in tilemap_source,
        "tilemap_cli": 'sub.add_parser("tilemap"' in parser_source,
        "tilemap_web_action": 'action == "tilemap"' in cmd_source and '"wang_16"' in cmd_source,
        "tilemap_generator_ui": "tilemapGeneratorForm" in training_source and "runAction('tilemap'" in forms_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _skeletal_export_status() -> dict[str, Any]:
    skeletal_source = (SERVICES / "skeletal_export_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8", errors="ignore")
    parser_source = (APP / "spriteforge_unified_parser.py").read_text(encoding="utf-8", errors="ignore")
    forms_source = (WEB / "js" / "app_forms.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "export_service": "def export_skeletal_parts" in skeletal_source,
        "spine_json": "spine.json" in skeletal_source,
        "dragonbones_json": "dragonbones.json" in skeletal_source,
        "manifest_path_returned": '"skeletal_manifest"' in skeletal_source and '"skeletal_manifest"' in routes_source,
        "manifest_ui_link": "Open skeletal manifest" in forms_source and "exported.segmentation?.method" in forms_source,
        "part_metadata": "part_metadata" in skeletal_source,
        "segmentation_provenance": "def _segmentation_provenance" in skeletal_source and '"segmentation"' in skeletal_source,
        "frame_bounds": '"frame_bounds"' in skeletal_source,
        "pivot_metadata": '"mode": "alpha-bottom-center"' in skeletal_source,
        "engine_import_contract": "def _engine_import_contract" in skeletal_source and '"texture_filter": "nearest"' in skeletal_source and '"coordinate_space"' in skeletal_source,
        "dragonbones_transform": '"transform"' in skeletal_source,
        "api_endpoint": '@routes_sprites.route("/api/sprite/export_skeletal"' in routes_source,
        "cli_command": 'sub.add_parser("export-skeletal"' in parser_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _archetype_status() -> dict[str, Any]:
    presets_source = (WEB / "js" / "app_presets.js").read_text(encoding="utf-8", errors="ignore")
    generate_source = (WEB / "components" / "generate.html").read_text(encoding="utf-8", errors="ignore")
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    jobs_source = (APP / "web_routes" / "routes_jobs.py").read_text(encoding="utf-8", errors="ignore")
    config_path = APP / "config" / "character_archetypes.json"
    checks = {
        "archetype_config": config_path.exists(),
        "archetype_api": '@routes_misc.route("/api/archetypes"' in routes_source,
        "visual_cards": "archetype-card-portrait" in presets_source,
        "apply_to_generate": "function applyArchetype" in presets_source,
        "customize_before_apply": "archetypeCustomizePanel" in index_source and "customizedArchetypePayload" in presets_source,
        "provenance_fields": 'name="archetype_id"' in generate_source and 'name="archetype_palette_hint"' in generate_source and 'name="archetype_customized"' in generate_source,
        "provenance_stamping": "function setArchetypeProvenance" in presets_source,
        "job_metadata_provenance": "spriteforge.archetype_generation_provenance.v1" in jobs_source and 'metadata["archetype"] = archetype_provenance' in jobs_source,
        "prompt_preview_refresh": "refreshGeneratePromptPreview" in presets_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _lora_training_status() -> dict[str, Any]:
    registry_source = (SERVICES / "trained_lora_registry_service.py").read_text(encoding="utf-8", errors="ignore")
    service_source = (SERVICES / "lora_training_service.py").read_text(encoding="utf-8", errors="ignore")
    dataset_source = (SERVICES / "training_dataset_service.py").read_text(encoding="utf-8", errors="ignore")
    progress_source = (SERVICES / "lora_training_progress_service.py").read_text(encoding="utf-8", errors="ignore")
    training_source = (WEB / "components" / "training.html").read_text(encoding="utf-8", errors="ignore")
    forms_source = (WEB / "js" / "app_forms.js").read_text(encoding="utf-8", errors="ignore")
    components_source = (WEB / "css" / "components.css").read_text(encoding="utf-8", errors="ignore")
    routes_misc_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    routes_jobs_source = (APP / "web_routes" / "routes_jobs.py").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "registry": "trained_loras.json" in registry_source,
        "registry_metadata": "spriteforge.trained_lora_metadata.v1" in service_source and '"metadata": metadata' in registry_source,
        "dataset_preview_service": "def preview_training_dataset" in dataset_source,
        "dataset_preview_ui": "trainingDatasetPreview" in training_source and "function previewTrainingDataset" in forms_source,
        "dataset_preview_endpoint": '@routes_misc.route("/api/training-dataset/preview"' in routes_misc_source,
        "visual_dataset_builder": "trainingDatasetDropzone" in training_source and "function initTrainingDatasetBuilder" in forms_source and ".training-dataset-dropzone" in components_source,
        "dataset_builder_drop_paste": "event.dataTransfer" in forms_source and "event.clipboardData" in forms_source and "source_dir" in forms_source,
        "progress_endpoint": '@routes_jobs.route("/api/lora/progress"' in routes_jobs_source,
        "progress_summary": "def summarize_lora_training_progress" in progress_source,
        "loss_chart_ui": "loraLossChart" in training_source,
        "sample_gallery_ui": "loraSampleGallery" in training_source,
        "compare_plan_service": "def plan_lora_comparison" in registry_source,
        "compare_plan_metadata": '"metadata": record.get("metadata")' in registry_source,
        "compare_plan_endpoint": '@routes_misc.route("/api/lora/compare-plan"' in routes_misc_source,
        "compare_plan_ui": "loraComparePlanResult" in training_source and "buildLoraComparePlan" in forms_source,
        "gpu_defaults_service": "def recommend_lora_training_defaults" in service_source,
        "gpu_defaults_endpoint": '@routes_misc.route("/api/lora/recommended-defaults"' in routes_misc_source,
        "gpu_defaults_ui": "applyLoraGpuDefaults" in training_source and "function applyLoraGpuDefaults" in forms_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _scene_compositor_status() -> dict[str, Any]:
    service_source = (SERVICES / "scene_compositor_service.py").read_text(encoding="utf-8", errors="ignore")
    validation_source = (SERVICES / "export_validation_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_projects.py").read_text(encoding="utf-8", errors="ignore")
    ui_source = (WEB / "js" / "scene_compositor.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "manifest_builder": "def build_scene_manifest" in service_source,
        "grid_snapping": "snap_to_grid" in service_source,
        "z_ordering": 'layers.sort(key=lambda layer: (int(layer["z"])' in service_source,
        "godot_scene_export": "def _godot_scene_text" in service_source,
        "scene_handoff": "def _scene_handoff" in service_source and "spriteforge.scene_handoff.v1" in service_source and '"dependencies"' in service_source,
        "scene_handoff_validation": "def _validate_scene_manifest" in validation_source and "scene handoff schema valid" in validation_source,
        "animation_export_plan": "def _composite_animation_plan" in service_source,
        "gif_webm_paths": "composite.gif" in service_source and "composite.webm" in service_source,
        "api_endpoint": '@routes_projects.route("/api/scene_compositor/preview"' in routes_source,
        "ui_canvas": "sceneCompositorCanvas" in ui_source,
        "ui_background_layer": "sceneCompositorBackgroundImage" in ui_source and "background_image" in ui_source and "backgroundImage" in ui_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _compare_player_status() -> dict[str, Any]:
    index_source = (WEB / "index.html").read_text(encoding="utf-8", errors="ignore")
    component_source = (WEB / "components" / "compare_player.html").read_text(encoding="utf-8", errors="ignore")
    script_source = (WEB / "js" / "compare_player.js").read_text(encoding="utf-8", errors="ignore")
    experiments_source = (WEB / "js" / "experiments.js").read_text(encoding="utf-8", errors="ignore")
    css_source = (WEB / "compare_player.css").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "view_assets": "compare_player.css" in index_source and "js/compare_player.js" in index_source and 'id="view-compare_player"' in index_source,
        "variant_slots": all(token in component_source for token in ['id="compareSpriteA"', 'id="compareSpriteB"', 'id="compareSpriteC"', 'id="compareSpriteD"']),
        "synced_playback": "requestAnimationFrame(tick)" in script_source and "compareFrameScrubber" in component_source,
        "pixel_diff_overlay": "renderDiff" in script_source and "changed pixels" in script_source and 'id="compareDiffCanvas"' in component_source,
        "qa_metrics_table": "renderMetricsTable" in script_source and "variantQaMetric" in script_source and "compareMetricsBody" in component_source,
        "winner_flow": "/api/experiments/pick-winner" in script_source and "/api/experiments/star" in script_source and "selected winner" in script_source,
        "history_handoff": "showView('compare_player')" in experiments_source and "setComparePlayerSelection(selected)" in experiments_source,
        "pixelated_styles": ".compare-variant-grid" in css_source and "image-rendering: pixelated" in css_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _palette_pipeline_status() -> dict[str, Any]:
    harmonizer_source = (SERVICES / "palette_harmonizer_service.py").read_text(encoding="utf-8", errors="ignore")
    project_palette_source = (SERVICES / "project_palette_service.py").read_text(encoding="utf-8", errors="ignore")
    pipeline_source = (SERVICES / "sprite_processing_pipeline.py").read_text(encoding="utf-8", errors="ignore")
    cmd_source = (SERVICES / "web_helpers_cmd.py").read_text(encoding="utf-8", errors="ignore")
    editor_source = (WEB / "js" / "palette_harmonizer.js").read_text(encoding="utf-8", errors="ignore")
    components_source = (WEB / "css" / "components.css").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "project_palette_lock": "def normalize_palette_lock" in project_palette_source,
        "palette_cli_forwarding": "_apply_project_palette_lock" in cmd_source,
        "pipeline_palette_quantization": "pixel_cleanup_palette" in pipeline_source,
        "harmonizer_report": "def harmonize_palette" in harmonizer_source,
        "palette_lock_audit": "palette_lock_audit.json" in harmonizer_source,
        "audit_schema": "spriteforge.palette_lock_audit.v1" in harmonizer_source,
        "palette_digest_provenance": "spriteforge.palette_harmonization_report.v1" in harmonizer_source and "def _palette_digest" in harmonizer_source,
        "visual_editor_ui": "paletteEditorColorsText" in editor_source and "paletteEditorSwatches" in editor_source and ".palette-editor-panel" in components_source,
        "palette_imports": "parseImportedPaletteText" in editor_source and "parseAsePalette" in editor_source and "Lospec JSON" in editor_source and "GIMP Palette" in editor_source,
        "hsl_color_wheel": "paletteHslWheel" in editor_source and "paletteHslToHex" in editor_source and "conic-gradient" in components_source,
        "live_quantized_preview": "refreshPaletteQuantizedPreview" in editor_source and "nearestPaletteRgb" in editor_source and "source left, snapped right" in editor_source,
        "project_lock_ui": "paletteHarmonizerLockProject" in editor_source and "source: 'palette_editor'" in editor_source and "/api/project/config" in editor_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _animated_exports_status() -> dict[str, Any]:
    service_source = (SERVICES / "animated_export_service.py").read_text(encoding="utf-8", errors="ignore")
    validation_source = (SERVICES / "export_validation_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8", errors="ignore")
    packs_source = (WEB / "components" / "packs.html").read_text(encoding="utf-8", errors="ignore")
    forms_source = (WEB / "js" / "app_forms.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "format_registry": 'ANIMATED_EXPORT_FORMATS = ("apng", "webp", "lottie")' in service_source,
        "apng_export": "export_apng(frames, out_path" in service_source,
        "webp_export": "export_webp_anim(frames, out_path" in service_source,
        "lottie_export": "export_lottie_json(frames, out_path" in service_source,
        "manifest_schema": "spriteforge.animated_export.v1" in service_source,
        "manifest_sidecar": "manifest_path.write_text" in service_source,
        "retimed_frame_manifest": "def _frame_durations_ms" in service_source and "sheet.json duration_ms" in service_source and '"timing_source": timing_source' in service_source,
        "engine_import_hints": "def _engine_import_hints" in service_source and '"texture_filter": "nearest"' in service_source and '"per_frame_duration_ms"' in service_source,
        "audio_cue_export_validation": "def _validate_audio_cues_manifest" in validation_source and "audio_cues.json cue timing matches fps" in validation_source,
        "tilemap_export_validation": "def _validate_tilemap_manifest" in validation_source and "tilemap engine import targets present" in validation_source,
        "skeletal_export_validation": "def _validate_skeletal_manifest" in validation_source and "skeletal spine slot order matches manifest" in validation_source,
        "cloud_generation_export_validation": "def _validate_cloud_generation_manifest" in validation_source and "cloud_generation.json cleanup metrics valid" in validation_source,
        "release_zip_restriction_validation": "def _restricted_zip_members" in validation_source and "Release zip excludes restricted/heavy files" in validation_source,
        "api_endpoint": '@routes_sprites.route("/api/sprite/export_animation"' in routes_source,
        "ui_formats": '<option value="apng">APNG</option>' in packs_source and '<option value="webp">Animated WebP</option>' in packs_source and '<option value="lottie">Lottie JSON</option>' in packs_source,
        "ui_submit": "/api/sprite/export_animation" in forms_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _lighting_preview_status() -> dict[str, Any]:
    service_source = (SERVICES / "lighting_preview_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8", errors="ignore")
    component_source = (WEB / "components" / "lighting_preview.html").read_text(encoding="utf-8", errors="ignore")
    script_source = (WEB / "js" / "lighting_preview.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "movable_light_canvas": "renderLightingPreview" in script_source and "pointerdown" in script_source,
        "normal_map_input": "sheet_normal.png" in script_source,
        "specular_ao_compositing": "sheet_specular.png" in script_source and "sheet_ao.png" in script_source and "specMask" in script_source and "aoMask" in script_source,
        "gif_export_service": "def export_lighting_preview_gif" in service_source,
        "gif_export_map_compositing": "def _map_light_frame" in service_source and "normal_specular_ao" in service_source and "spriteforge.lighting_preview_render.v1" in service_source,
        "manifest_schema": "spriteforge.lighting_preview.v1" in service_source,
        "api_endpoint": '@routes_sprites.route("/api/sprite/export_lighting_preview"' in routes_source,
        "ui_export_button": 'id="lightingExportGif"' in component_source,
        "ui_submit": "/api/sprite/export_lighting_preview" in script_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _experiment_analytics_status() -> dict[str, Any]:
    service_source = (SERVICES / "experiment_service.py").read_text(encoding="utf-8", errors="ignore")
    routes_source = (APP / "web_routes" / "routes_misc.py").read_text(encoding="utf-8", errors="ignore")
    history_source = (WEB / "components" / "history.html").read_text(encoding="utf-8", errors="ignore")
    script_source = (WEB / "js" / "experiments.js").read_text(encoding="utf-8", errors="ignore")
    checks = {
        "analytics_service": "def analytics" in service_source and "best_runs" in service_source,
        "prompt_search_service": "def search_prompts" in service_source,
        "winning_prompt_pack_service": "def winning_prompt_pack" in service_source,
        "winning_prompt_pack_contract": "spriteforge.winning_prompt_entry.v1" in service_source and "selection_contract" in service_source,
        "analytics_endpoint": '@routes_misc.route("/api/experiments/analytics"' in routes_source,
        "prompt_search_endpoint": '@routes_misc.route("/api/experiments/prompts"' in routes_source,
        "winning_prompt_endpoint": '@routes_misc.route("/api/experiments/winning-prompts"' in routes_source,
        "recommendations_service": '"recommendations": recommendations' in service_source,
        "ui_charts": "expScoreDistribution" in history_source and "expScoreTrend" in history_source,
        "ui_recommendations": "expRecommendations" in history_source and "experiment-recommendation" in script_source,
        "ui_prompt_reuse": "usePromptHistoryRow" in script_source and "data-prompt-pin" in script_source,
        "ui_winning_prompt_export": "exportWinningPrompts" in script_source and "winningPromptPackResult" in history_source,
    }
    return {"ok": all(checks.values()), "checks": checks}


def _phase_status(name: str, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks = {key: bool(value.get("ok")) for key, value in items.items()}
    return {"name": name, "ok": all(checks.values()), "checks": checks}


def architecture_status(force: bool = False) -> dict[str, Any]:
    global _CACHE, _CACHE_TIME

    now = time.monotonic()
    if not force and _CACHE is not None and now - _CACHE_TIME < CACHE_TTL_SECONDS:
        return _CACHE

    service_manifest = _load_json(SERVICES / "service_architecture.json")
    css_manifest = _load_json(WEB / "css" / "css_architecture.json")
    js_manifest = _load_json(WEB / "js" / "js_architecture.json")
    wizard_manifest = _load_json(WEB / "js" / "wizard_architecture.json")

    canonical_root = _canonical_root_status()
    silent_exceptions = _silent_service_exception_status()
    json_persistence = _json_persistence_status()
    duplicate_js_functions = _duplicate_js_function_status()
    duplicate_css_selectors = _duplicate_css_selector_status()
    job_runner = _job_runner_status()
    database_layer = _database_layer_status()
    config_model = _config_model_status()
    feature_capabilities = _feature_capability_status()
    performance = _performance_status()
    design_system = _design_system_status()
    pipeline_powerups = _pipeline_powerups_status()
    keyboard_ux = _keyboard_ux_status()
    dashboard_generate_ux = _dashboard_generate_ux_status()
    security = _security_status()
    tests = _test_suite_status()
    easy_mode = _easy_mode_status()
    plugin_sdk = _plugin_sdk_status()
    cloud_hub = _cloud_hub_status()
    cloud_image_generation = _cloud_image_generation_status()
    qa_advisor = _qa_advisor_status()
    tilemap = _tilemap_status()
    skeletal_export = _skeletal_export_status()
    archetypes = _archetype_status()
    lora_training = _lora_training_status()
    scene_compositor = _scene_compositor_status()
    compare_player = _compare_player_status()
    palette_pipeline = _palette_pipeline_status()
    animated_exports = _animated_exports_status()
    lighting_preview = _lighting_preview_status()
    experiment_analytics = _experiment_analytics_status()

    service_files = [
        filename
        for domain in service_manifest.get("domains", [])
        for filename in domain.get("files", [])
    ]
    css_files = [
        filename
        for layer in css_manifest.get("cascade_order", [])
        for filename in layer.get("files", [])
    ]
    css_entrypoint_files = css_manifest.get("entrypoint_links", [])
    actual_css_files = [
        path.name
        for path in WEB.glob("*.css")
    ] + [
        f"css/{path.name}"
        for path in (WEB / "css").glob("*.css")
    ]
    tracked_css_files = set(css_files) | set(css_entrypoint_files)
    unmanaged_css_files = sorted(set(actual_css_files) - tracked_css_files)
    js_files = [
        filename
        for layer in js_manifest.get("script_order", [])
        for filename in layer.get("files", [])
    ]

    guardrails = {
        "canonical_root": canonical_root,
        "silent_service_exceptions": silent_exceptions,
        "json_persistence": json_persistence,
        "duplicate_js_top_level_functions": duplicate_js_functions,
        "duplicate_css_selectors": duplicate_css_selectors,
    }
    phase0 = _phase_status("Critical Technical Debt", {
        "canonical_root": canonical_root,
        "silent_service_exceptions": silent_exceptions,
        "json_persistence": json_persistence,
        "duplicate_js_top_level_functions": duplicate_js_functions,
        "duplicate_css_selectors": duplicate_css_selectors,
        "design_system": design_system,
    })
    phase1 = _phase_status("Core Pipeline Power-Ups", {
        "pipeline_powerups": pipeline_powerups,
    })
    phase2 = _phase_status("UI/UX Revolution", {
        "design_system": design_system,
        "dashboard_generate_ux": dashboard_generate_ux,
        "keyboard_ux": keyboard_ux,
        "performance": performance,
        "lighting_preview": lighting_preview,
        "palette_pipeline": palette_pipeline,
    })
    phase3 = _phase_status("Production Pipeline Features", {
        "compare_player": compare_player,
        "palette_pipeline": palette_pipeline,
        "animated_exports": animated_exports,
        "archetypes": archetypes,
        "scene_compositor": scene_compositor,
        "lora_training": lora_training,
        "experiment_analytics": experiment_analytics,
    })
    phase4 = _phase_status("Architecture & Reliability", {
        "job_runner": job_runner,
        "database_layer": database_layer,
        "config_model": config_model,
        "feature_capabilities": feature_capabilities,
        "performance": performance,
        "security": security,
        "tests": tests,
        "easy_mode": easy_mode,
    })
    phase5 = _phase_status("Advanced Features", {
        "qa_advisor": qa_advisor,
        "tilemap": tilemap,
        "skeletal_export": skeletal_export,
        "cloud_hub": cloud_hub,
        "cloud_image_generation": cloud_image_generation,
        "plugin_sdk": plugin_sdk,
    })
    roadmap_phases = {
        "ok": all(phase["ok"] for phase in [phase0, phase1, phase2, phase3, phase4, phase5]),
        "phases": {
            "phase_0": phase0,
            "phase_1": phase1,
            "phase_2": phase2,
            "phase_3": phase3,
            "phase_4": phase4,
            "phase_5": phase5,
        },
    }

    status = {
        "ok": all(item["ok"] for item in guardrails.values()) and roadmap_phases["ok"],
        "schema": "spriteforge.architecture_status.v1",
        "manifests": {
            "services": {
                "schema": service_manifest.get("schema"),
                "domains_count": len(service_manifest.get("domains", [])),
                "files_tracked": len(service_files),
            },
            "css": {
                "schema": css_manifest.get("schema"),
                "layers": [layer.get("layer") for layer in css_manifest.get("cascade_order", [])],
                "files_tracked": len(css_files),
                "entrypoint_links_tracked": len(css_entrypoint_files),
                "target_structure": css_manifest.get("target_structure", []),
                "debt_items": len(css_manifest.get("debt_register", [])),
                "unmanaged_files": unmanaged_css_files,
                "duplicate_selectors_count": duplicate_css_selectors.get("duplicates_count", 0),
            },
            "js": {
                "schema": js_manifest.get("schema"),
                "layers": [layer.get("layer") for layer in js_manifest.get("script_order", [])],
                "files_tracked": len(js_files),
                "migration_target": js_manifest.get("migration_target"),
            },
            "wizard": {
                "schema": wizard_manifest.get("schema"),
                "current_entry": wizard_manifest.get("current_entry"),
                "split_targets": [target.get("file") for target in wizard_manifest.get("target_split", [])],
            },
        },
        "backend": {
            "job_runner": job_runner,
            "database_layer": database_layer,
            "config_model": config_model,
            "feature_capabilities": feature_capabilities,
        },
        "performance": performance,
        "design_system": design_system,
        "pipeline_powerups": pipeline_powerups,
        "keyboard_ux": keyboard_ux,
        "dashboard_generate_ux": dashboard_generate_ux,
        "security": security,
        "tests": tests,
        "easy_mode": easy_mode,
        "plugin_sdk": plugin_sdk,
        "cloud_hub": cloud_hub,
        "cloud_image_generation": cloud_image_generation,
        "qa_advisor": qa_advisor,
        "tilemap": tilemap,
        "skeletal_export": skeletal_export,
        "archetypes": archetypes,
        "lora_training": lora_training,
        "scene_compositor": scene_compositor,
        "compare_player": compare_player,
        "palette_pipeline": palette_pipeline,
        "animated_exports": animated_exports,
        "lighting_preview": lighting_preview,
        "experiment_analytics": experiment_analytics,
        "roadmap_phases": roadmap_phases,
        "guardrails": guardrails,
    }
    _CACHE = status
    _CACHE_TIME = now
    return status
