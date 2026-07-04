import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_architecture_status_summarizes_manifests_and_guardrails():
    from services.architecture_status_service import architecture_status

    status = architecture_status(force=True)

    assert status["schema"] == "spriteforge.architecture_status.v1"
    assert status["ok"] is True
    assert status["manifests"]["services"]["schema"] == "spriteforge.service_architecture.v1"
    assert status["manifests"]["services"]["domains_count"] >= 8
    assert status["manifests"]["css"]["schema"] == "spriteforge.css_architecture.v1"
    assert "overrides" in status["manifests"]["css"]["layers"]
    assert status["manifests"]["css"]["debt_items"] >= 3
    assert "overrides/*.css" in status["manifests"]["css"]["target_structure"]
    assert status["manifests"]["css"]["entrypoint_links_tracked"] >= 20
    assert status["manifests"]["css"]["unmanaged_files"] == []
    assert status["manifests"]["css"]["duplicate_selectors_count"] > 0
    assert status["guardrails"]["duplicate_css_selectors"]["ok"] is True
    assert status["guardrails"]["duplicate_css_selectors"]["unmanaged_duplicates"] == {}
    assert status["guardrails"]["json_persistence"]["ok"] is True
    assert status["guardrails"]["json_persistence"]["checks"]["save_json_uses_lock"] is True
    assert status["guardrails"]["json_persistence"]["checks"]["unique_temp_files"] is True
    assert status["manifests"]["js"]["migration_target"] == "es-modules-no-bundler"
    assert status["manifests"]["wizard"]["current_entry"] == "js/wizard.js"
    assert status["backend"]["job_runner"]["ok"] is True
    assert status["backend"]["job_runner"]["nested_worker_removed"] is True
    assert status["backend"]["job_runner"]["phase_contract"] is True
    assert status["backend"]["job_runner"]["stage_contract"] is True
    assert status["backend"]["database_layer"]["ok"] is True
    assert status["backend"]["database_layer"]["checks"]["fts_schema"] is True
    assert status["backend"]["database_layer"]["checks"]["migration_endpoint"] is True
    assert status["backend"]["database_layer"]["checks"]["search_sanitizer"] is True
    assert status["backend"]["database_layer"]["checks"]["recent_endpoint"] is True
    assert status["backend"]["database_layer"]["checks"]["stats_endpoint"] is True
    assert status["backend"]["database_layer"]["checks"]["health_endpoint"] is True
    assert status["backend"]["database_layer"]["checks"]["health_report"] is True
    assert status["backend"]["database_layer"]["checks"]["counts_by_kind"] is True
    assert status["backend"]["config_model"]["ok"] is True
    assert status["backend"]["config_model"]["checks"]["effective_profile_explain"] is True
    assert status["backend"]["config_model"]["checks"]["effective_profile_endpoint"] is True
    assert status["backend"]["feature_capabilities"]["ok"] is True
    assert status["backend"]["feature_capabilities"]["checks"]["selection_reason_report"] is True
    assert status["backend"]["feature_capabilities"]["checks"]["opt_in_flags_report"] is True
    assert status["performance"]["ok"] is True
    assert status["performance"]["checks"]["heartbeat_endpoint"] is True
    assert status["performance"]["checks"]["lightweight_heartbeat_client"] is True
    assert status["performance"]["checks"]["progress_stream_endpoint"] is True
    assert status["performance"]["checks"]["progress_events_endpoint"] is True
    assert status["performance"]["checks"]["progress_transport_descriptor"] is True
    assert status["performance"]["checks"]["progress_event_replay"] is True
    assert status["performance"]["checks"]["dashboard_eventsource"] is True
    assert status["performance"]["checks"]["dashboard_polling_fallback"] is True
    assert status["performance"]["checks"]["desktop_completion_notifications"] is True
    assert status["performance"]["checks"]["comfy_running_cache"] is True
    assert status["performance"]["checks"]["cache_metadata"] is True
    assert status["design_system"]["ok"] is True
    assert status["design_system"]["checks"]["spacing_scale"] is True
    assert status["design_system"]["checks"]["skeleton_primitives"] is True
    assert status["pipeline_powerups"]["ok"] is True
    assert status["pipeline_powerups"]["checks"]["animation_player_view"] is True
    assert status["pipeline_powerups"]["checks"]["animation_player_hit_markers"] is True
    assert status["pipeline_powerups"]["checks"]["frame_editor_multi_select_retime"] is True
    assert status["pipeline_powerups"]["checks"]["frame_editor_repack_history"] is True
    assert status["pipeline_powerups"]["checks"]["rife_interpolation"] is True
    assert status["pipeline_powerups"]["checks"]["temporal_smoothing"] is True
    assert status["pipeline_powerups"]["checks"]["multi_resolution_exports"] is True
    assert status["keyboard_ux"]["ok"] is True
    assert status["keyboard_ux"]["checks"]["command_palette_shortcut"] is True
    assert status["keyboard_ux"]["checks"]["alt_number_navigation"] is True
    assert status["keyboard_ux"]["checks"]["cheat_sheet"] is True
    assert status["keyboard_ux"]["checks"]["command_risk_metadata"] is True
    assert status["dashboard_generate_ux"]["ok"] is True
    assert status["dashboard_generate_ux"]["checks"]["dashboard_hero_stats"] is True
    assert status["dashboard_generate_ux"]["checks"]["generate_prompt_preview"] is True
    assert status["dashboard_generate_ux"]["checks"]["generate_reference_preview"] is True
    assert status["security"]["ok"] is True
    assert status["security"]["checks"]["frame_filename_sanitizer"] is True
    assert status["security"]["checks"]["frame_save_uses_sanitizer"] is True
    assert status["security"]["checks"]["palette_harmonize_rate_limited"] is True
    assert status["security"]["checks"]["audio_cue_write_rate_limited"] is True
    assert status["tests"]["ok"] is True
    assert status["tests"]["checks"]["sample_sheet_json_fixture"] is True
    assert status["tests"]["checks"]["synthetic_rgba_frames"] is True
    assert status["tests"]["checks"]["mock_comfy_system_stats"] is True
    assert status["tests"]["checks"]["process_common_matting_parameterized"] is True
    assert status["easy_mode"]["ok"] is True
    assert status["easy_mode"]["checks"]["tkinter_retained_option_a"] is True
    assert status["easy_mode"]["checks"]["dark_theme_polish"] is True
    assert status["easy_mode"]["checks"]["web_studio_handoff"] is True
    assert status["easy_mode"]["checks"]["embedded_preview"] is True
    assert status["plugin_sdk"]["ok"] is True
    assert status["plugin_sdk"]["checks"]["sdk_contract"] is True
    assert status["plugin_sdk"]["checks"]["sdk_starter_ui"] is True
    assert status["plugin_sdk"]["checks"]["manifest_validation"] is True
    assert status["plugin_sdk"]["checks"]["sdk_starter_fetch"] is True
    assert status["plugin_sdk"]["checks"]["sdk_starter_styles"] is True
    assert status["plugin_sdk"]["checks"]["compatibility_function"] is True
    assert status["plugin_sdk"]["checks"]["marketplace_import_planning"] is True
    assert status["plugin_sdk"]["checks"]["marketplace_share_manifest"] is True
    assert status["plugin_sdk"]["checks"]["marketplace_share_checks"] is True
    assert status["plugin_sdk"]["checks"]["marketplace_endpoints"] is True
    assert status["plugin_sdk"]["checks"]["marketplace_release_panel"] is True
    assert status["cloud_hub"]["ok"] is True
    assert status["cloud_hub"]["checks"]["dispatch_planning"] is True
    assert status["cloud_hub"]["checks"]["node_management_ui"] is True
    assert status["cloud_hub"]["checks"]["node_operator_controls"] is True
    assert status["cloud_hub"]["checks"]["queue_distribution_ui"] is True
    assert status["cloud_image_generation"]["ok"] is True
    assert status["cloud_image_generation"]["checks"]["secret_safe_plan"] is True
    assert status["cloud_image_generation"]["checks"]["frame_provenance"] is True
    assert status["cloud_image_generation"]["checks"]["generation_contract"] is True
    assert status["qa_advisor"]["ok"] is True
    assert status["qa_advisor"]["checks"]["learning_summary"] is True
    assert status["qa_advisor"]["checks"]["learning_summary_ui"] is True
    assert status["qa_advisor"]["checks"]["repair_plan_payload"] is True
    assert status["qa_advisor"]["checks"]["repair_action_mapping"] is True
    assert status["tilemap"]["ok"] is True
    assert status["tilemap"]["checks"]["engine_layout_metadata"] is True
    assert status["tilemap"]["checks"]["engine_manifest"] is True
    assert status["tilemap"]["checks"]["engine_tile_index_table"] is True
    assert status["tilemap"]["checks"]["tilemap_web_action"] is True
    assert status["tilemap"]["checks"]["tilemap_generator_ui"] is True
    assert status["skeletal_export"]["ok"] is True
    assert status["skeletal_export"]["checks"]["pivot_metadata"] is True
    assert status["skeletal_export"]["checks"]["segmentation_provenance"] is True
    assert status["skeletal_export"]["checks"]["manifest_path_returned"] is True
    assert status["skeletal_export"]["checks"]["manifest_ui_link"] is True
    assert status["skeletal_export"]["checks"]["engine_import_contract"] is True
    assert status["archetypes"]["ok"] is True
    assert status["archetypes"]["checks"]["provenance_stamping"] is True
    assert status["archetypes"]["checks"]["job_metadata_provenance"] is True
    assert status["archetypes"]["checks"]["customize_before_apply"] is True
    assert status["lora_training"]["ok"] is True
    assert status["lora_training"]["checks"]["dataset_preview_service"] is True
    assert status["lora_training"]["checks"]["visual_dataset_builder"] is True
    assert status["lora_training"]["checks"]["dataset_builder_drop_paste"] is True
    assert status["lora_training"]["checks"]["compare_plan_service"] is True
    assert status["lora_training"]["checks"]["gpu_defaults_service"] is True
    assert status["scene_compositor"]["ok"] is True
    assert status["scene_compositor"]["checks"]["animation_export_plan"] is True
    assert status["scene_compositor"]["checks"]["ui_background_layer"] is True
    assert status["scene_compositor"]["checks"]["scene_handoff"] is True
    assert status["compare_player"]["ok"] is True
    assert status["compare_player"]["checks"]["pixel_diff_overlay"] is True
    assert status["compare_player"]["checks"]["winner_flow"] is True
    assert status["palette_pipeline"]["ok"] is True
    assert status["palette_pipeline"]["checks"]["palette_lock_audit"] is True
    assert status["palette_pipeline"]["checks"]["visual_editor_ui"] is True
    assert status["palette_pipeline"]["checks"]["palette_imports"] is True
    assert status["palette_pipeline"]["checks"]["hsl_color_wheel"] is True
    assert status["palette_pipeline"]["checks"]["live_quantized_preview"] is True
    assert status["palette_pipeline"]["checks"]["project_lock_ui"] is True
    assert status["animated_exports"]["ok"] is True
    assert status["animated_exports"]["checks"]["manifest_schema"] is True
    assert status["animated_exports"]["checks"]["retimed_frame_manifest"] is True
    assert status["animated_exports"]["checks"]["engine_import_hints"] is True
    assert status["lighting_preview"]["ok"] is True
    assert status["lighting_preview"]["checks"]["movable_light_canvas"] is True
    assert status["lighting_preview"]["checks"]["specular_ao_compositing"] is True
    assert status["lighting_preview"]["checks"]["gif_export_service"] is True
    assert status["lighting_preview"]["checks"]["gif_export_map_compositing"] is True
    assert status["lighting_preview"]["checks"]["api_endpoint"] is True
    assert status["experiment_analytics"]["ok"] is True
    assert status["experiment_analytics"]["checks"]["winning_prompt_pack_service"] is True
    assert status["experiment_analytics"]["checks"]["recommendations_service"] is True
    assert status["experiment_analytics"]["checks"]["ui_recommendations"] is True
    assert status["roadmap_phases"]["ok"] is True
    assert status["roadmap_phases"]["phases"]["phase_0"]["ok"] is True
    assert status["roadmap_phases"]["phases"]["phase_1"]["checks"]["pipeline_powerups"] is True
    assert status["roadmap_phases"]["phases"]["phase_3"]["checks"]["compare_player"] is True
    assert status["roadmap_phases"]["phases"]["phase_5"]["checks"]["plugin_sdk"] is True
    assert status["ok"] == (status["roadmap_phases"]["ok"] and all(item["ok"] for item in status["guardrails"].values()))
    assert status["guardrails"]["canonical_root"]["ok"] is True
    assert status["guardrails"]["silent_service_exceptions"]["ok"] is True
    assert status["guardrails"]["duplicate_js_top_level_functions"]["ok"] is True


def test_architecture_status_endpoint_returns_live_status():
    from flask import Flask
    from web_routes.routes_misc import routes_misc

    app = Flask(__name__)
    app.register_blueprint(routes_misc)

    response = app.test_client().get("/api/architecture/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["schema"] == "spriteforge.architecture_status.v1"
    assert payload["ok"] is True
