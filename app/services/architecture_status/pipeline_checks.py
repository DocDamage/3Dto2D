from typing import Any

from services.architecture_status.base import (
    APP,
    SERVICES,
    WEB,
)


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
        "format_capabilities_schema": "spriteforge.animated_export_format.v1" in service_source and "spriteforge.animated_export_format.v1" in validation_source,
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
    return {"ok": config_path.exists() and all(checks.values()), "checks": checks}


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
