(function () {
  window.openWizard = function openWizard() {
    if (typeof window.openWizard.impl === 'function') {
      return window.openWizard.impl.apply(null, arguments);
    }
    window.openWizard.pendingArgs = Array.from(arguments);
  };

  window.closeWizard = function closeWizard() {
    if (typeof window.closeWizard.impl === 'function') {
      return window.closeWizard.impl.apply(null, arguments);
    }
  };

  window.spriteForgeScriptList = function spriteForgeScriptList() {
    return [
      'js/globals.js?v=training-lora-launcher',
      'js/project.js',
      'js/gallery.js',
      'js/editor_history.js',
      'js/editor.js',
      'js/sprite_preview.js?v=generate-compact-fit2',
      'js/animation_player.js',
      'js/compare_player.js',
      'js/lighting_preview.js',
      'js/cloud_hub.js',
      'js/frame_editor.js',
      'js/prompt_builder.js?v=prompt-autofix',
      'js/seed_gallery.js',
      'js/frame_review.js',
      'js/palette_harmonizer.js',
      'js/keyboard_shortcuts.js',
      'js/theme_toggle.js',
      'js/mobile_nav.js',
      'js/drag_drop.js?v=reference-upload-buttons',
      'js/audio_cues.js',
      'js/state_machine.js',
      'js/marketplace_gallery.js',
      'js/scene_compositor.js',
      'js/consistency_lock.js?v=generate-existing-sprite',
      'js/experiments.js',
      'js/qa.js?v=quality-lab-compact',
      'js/app_views.js',
      'js/app_notifications.js',
      'js/app_presets.js?v=sakpix-training-polish',
      'js/app_status.js',
      'js/app_jobs.js?v=generate-compact-fit2',
      'js/app_forms.js?v=lpc-production-upgrade',
      'js/app_listings.js?v=generate-compact-fit2',
      'js/wizard_templates.js',
      'js/wizard_state.js',
      'js/wizard_submit.js',
      'js/wizard_ui.js',
      'js/wizard.js?v=wizard-reference-upload-buttons',
      'js/app_dashboard.js?v=dashboard-fit-no-window-resize',
      'js/command_palette.js',
      'js/pixel_studio.js',
      'js/ux_enhancements.js?v=sprite-lab-visible',
      'js/app_main.js?v=quality-lab-compact',
    ];
  };

  function loadSequentially(scripts, idx) {
    if (idx >= scripts.length) return;
    const script = document.createElement('script');
    script.async = false;
    script.src = scripts[idx];
    script.onload = () => loadSequentially(scripts, idx + 1);
    script.onerror = () => {
      console.error('Failed to load script:', scripts[idx]);
      loadSequentially(scripts, idx + 1);
    };
    document.body.appendChild(script);
  }

  window.viewComponentsLoaded.then(() => {
    if (window.location.protocol === 'file:') return;
    loadSequentially(window.spriteForgeScriptList(), 0);
  });
})();
