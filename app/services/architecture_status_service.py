import time
from typing import Any

from services.architecture_status.base import (
    APP,
    REPO_ROOT,
    SERVICES,
    WEB,
    _load_json,
    _phase_status,
)
from services.architecture_status.core_checks import (
    _canonical_root_status,
    _silent_service_exception_status,
    _json_persistence_status,
    _duplicate_js_function_status,
    _duplicate_css_selector_status,
    _job_runner_status,
    _config_model_status,
    _feature_capability_status,
    _security_status,
    _database_layer_status,
    _test_suite_status,
)
from services.architecture_status.pipeline_checks import (
    _pipeline_powerups_status,
    _scene_compositor_status,
    _compare_player_status,
    _palette_pipeline_status,
    _animated_exports_status,
    _lighting_preview_status,
    _experiment_analytics_status,
    _tilemap_status,
    _skeletal_export_status,
    _archetype_status,
    _lora_training_status,
)
from services.architecture_status.ux_checks import (
    _performance_status,
    _design_system_status,
    _keyboard_ux_status,
    _dashboard_generate_ux_status,
    _easy_mode_status,
    _plugin_sdk_status,
    _cloud_hub_status,
    _cloud_image_generation_status,
    _qa_advisor_status,
)

CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, Any] | None = None
_CACHE_TIME = 0.0


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
