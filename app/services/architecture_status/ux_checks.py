from typing import Any

from services.architecture_status.base import (
    APP,
    SERVICES,
    WEB,
    REPO_ROOT,
)


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
