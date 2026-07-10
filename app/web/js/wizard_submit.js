(function () {
  'use strict';

  async function recommendWizardProfile(quality) {
    try {
      const recRes = await api(`/api/advisor?quality=${encodeURIComponent(quality || 'balanced')}`);
      if (recRes && recRes.tier) return recRes;
    } catch (e) {
      if (quality === 'quality') return { tier: 'wan22_5b', profile: 'wan22_5b_local' };
      if (quality === 'fast') return { tier: 'wan21_safe', profile: 'debug' };
    }
    return { tier: 'wan21_safe', profile: 'auto' };
  }

  async function buildWizardGenerationPlan(context) {
    const templates = window.SpriteForgeWizardTemplates?.templates || {};
    const prompts = window.SpriteForgeWizardTemplates?.perspectivePrompts || {};
    const template = templates[context.templateName] || templates.platformer || { style: '' };
    const perspectivePrompt = prompts[context.perspective] || prompts.side_view || '';
    const rec = await recommendWizardProfile(context.quality);
    const name = context.name || 'hero';
    const payload = {
      name,
      character: context.desc,
      description: context.desc,
      style: `${template.style}, ${perspectivePrompt}`.replace(/^,\s*/, '').trim(),
      sprite_action: context.actions[0] || 'idle',
      actions: context.actions.join(','),
      direction: context.direction,
      directions: context.directions.join(','),
      perspective: context.perspective,
      reference_image: context.referenceImage,
      style_image: context.styleImage,
      tier: rec.tier || 'wan21_safe',
      profile: rec.profile || 'auto',
      start_comfy: true,
      quality_check: true
    };

    if (context.goal === 'pack') return { action: 'queue_create', view: 'tasks', payload };
    if (context.goal === 'convert') {
      return {
        action: 'convert_video',
        view: 'tasks',
        payload: {
          input: context.video,
          fps: 12,
          cell_size: '512x512',
          key_color: 'auto',
          drop_loop_duplicate: true,
          preview_gif: true,
          report: true
        }
      };
    }
    if (context.goal === 'release') {
      return {
        action: 'release_package',
        view: 'tasks',
        payload: { name: `${name}_sprite_pack`, sprites: context.selectedSpriteDir || '' }
      };
    }
    return { action: 'generate_sprite', view: 'tasks', payload };
  }

  function evaluateWizardPreflight(statusData) {
    if (!statusData) return { unknown: true, checks: {}, reasons: [] };
    const checks = {
      comfy: !!statusData.comfy_running,
      models: !!(statusData.models && statusData.models.ok),
      disk: (statusData.disk ? parseFloat(statusData.disk.free_gb) : 0) >= 5,
      job: !(statusData.job && statusData.job.running)
    };
    const reasons = [];
    if (!checks.comfy) reasons.push('The creation engine needs to be started in Settings.');
    if (!checks.models) reasons.push('SpriteForge is still finishing its art-tool setup.');
    if (!checks.disk) reasons.push('At least 5 GB of free space is needed.');
    if (!checks.job) reasons.push('Another creation is already in progress.');
    return { unknown: false, checks, reasons, ok: reasons.length === 0 };
  }

  function validateWizardStep(step, context) {
    if (step === 1) return { ok: true };
    if (step === 2) {
      if (!context.name) return { ok: false, message: 'Character name is required.', focus: 'wiz_name' };
      if (String(context.desc || '').length < 5) {
        return { ok: false, message: 'Character description must be at least 5 characters long.', focus: 'wiz_character' };
      }
      return { ok: true };
    }
    if (step === 3) {
      if (context.goal === 'convert' && !context.video) {
        return { ok: false, message: 'Please specify a video file path to convert.', focus: 'wiz_video_path' };
      }
      if (context.goal !== 'convert' && (!context.actions || context.actions.length === 0)) {
        return { ok: false, message: 'Please select at least one animation.' };
      }
    }
    return { ok: true };
  }

  window.SpriteForgeWizardSubmit = {
    recommendWizardProfile,
    buildWizardGenerationPlan,
    evaluateWizardPreflight,
    validateWizardStep
  };
})();
