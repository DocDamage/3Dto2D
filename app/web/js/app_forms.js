// app_forms.js — Form submit wiring, runAction triggers, and recommended action
// Extracted from app_main.js

function runRecommended(){
  if(!recommendedAction){ toast('No recommendation available yet.'); return; }
  if(recommendedAction==='launch_comfy'){ api('/api/launch_comfy',{method:'POST'}).then(()=>toast('ComfyUI launch requested')).then(refreshAll); return; }
  if(recommendedAction==='generate_debug'){
    showView('generate');
    const f=$('#generateForm');
    if(f.querySelector('[name="profile"]')) f.querySelector('[name="profile"]').value='debug';
    if(f.querySelector('[name="sprite_action"]')) f.querySelector('[name="sprite_action"]').value='idle';
    if(f.querySelector('[name="direction"]')) f.querySelector('[name="direction"]').value='front';
    toast('Debug settings loaded. Click Generate WAN → Sprite when ready.');
    return;
  }
  if(recommendedAction==='qa_report'){ showView('quality'); toast('Select a sprite, then run QA.'); return; }
  if(recommendedAction==='release_package'){ showView('release'); toast('Add sprite folders, then build a release ZIP.'); return; }
  runAction(recommendedAction); showView('logs');
}

const EXISTING_SPRITE_MODEL_PRESETS = {
  local_5b: { tier: 'wan22_5b', mode: 'auto', profile: 'wan22_5b_3060_best' },
  pixel_animate_14b: { tier: 'wan22_14b_cloud', mode: 'i2v', profile: 'i2v_cloud_24gb_plus' },
  safe: { tier: 'wan21_safe', mode: 'auto', profile: 'auto' }
};

const EXISTING_SPRITE_PERSPECTIVES = {
  match_source: 'match the camera perspective of the uploaded source sprite',
  side: 'side-view game sprite camera',
  front: 'front-facing game sprite camera',
  back: 'back-facing game sprite camera',
  three_quarter: 'three-quarter game sprite camera',
  top_down: 'top-down RPG sprite camera',
  isometric: 'isometric 2.5D sprite camera, angled at 30 degrees',
  orthographic: 'orthographic game sprite camera, no perspective distortion'
};

function csvValues(value) {
  return String(value || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);
}

function firstCsvValue(value, fallback) {
  return csvValues(value)[0] || fallback;
}

function inferSpriteName(source, fallback) {
  const explicit = String(fallback || '').trim();
  if (explicit) return explicit;
  const file = String(source || '').split(/[\\/]/).pop() || 'existing_sprite';
  return file.replace(/\.[^.]+$/, '') || 'existing_sprite';
}

function setFieldValue(input, value) {
  if (!input) return;
  if (typeof setInputValue === 'function') {
    setInputValue(input, value);
    return;
  }
  input.value = value;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

function buildExistingSpritePayload() {
  const form = $('#generateForm');
  if (!form) return null;
  const data = formData(form);
  const source = String(data.existing_sprite_source || data.reference_image || '').trim();
  if (!source) {
    toast('Upload or paste a source sprite image first.');
    $('#existingSpritePanel')?.setAttribute('open', '');
    $('#existingSpriteSource')?.focus();
    return null;
  }

  const modelChoice = data.existing_sprite_model || 'local_5b';
  const modelPreset = modelChoice === 'current_form'
    ? { tier: data.tier || 'wan22_5b', mode: data.mode || 'auto', profile: data.profile || 'auto' }
    : (EXISTING_SPRITE_MODEL_PRESETS[modelChoice] || EXISTING_SPRITE_MODEL_PRESETS.local_5b);
  const actions = csvValues(data.existing_sprite_actions || data.default_actions || data.sprite_action || 'idle').join(',');
  const directions = csvValues(data.existing_sprite_directions || data.default_directions || data.direction || 'right').join(',');
  const action = firstCsvValue(actions, data.sprite_action || 'idle');
  const direction = firstCsvValue(directions, data.direction || 'right');
  const perspective = data.existing_sprite_perspective || 'match_source';
  const perspectiveText = EXISTING_SPRITE_PERSPECTIVES[perspective] || EXISTING_SPRITE_PERSPECTIVES.match_source;
  const spriteName = inferSpriteName(source, data.existing_sprite_name || data.preset_select || data.preset_name);
  const character = String(data.existing_sprite_description || data.character || 'single full body game sprite').trim();
  const baseStyle = String(data.style || 'polished 2D game sprite, crisp silhouette, consistent outfit').trim();
  const addonHint = modelChoice === 'pixel_animate_14b'
    ? ', pixel-art sprite animation adapter friendly motion, clean short sprite sequence'
    : '';
  const style = `${baseStyle}, preserve the uploaded source sprite identity, exact outfit, palette, proportions, silhouette, and readable shape language, ${perspectiveText}, locked camera${addonHint}`;
  const negative = String(data.negative || '').trim()
    || 'changing outfit, changing face, changing proportions, camera movement, zoom, cuts, close up, extra limbs, missing limbs, messy silhouette, text, watermark';

  setFieldValue($('#generationReferenceImage'), source);
  setFieldValue(form.querySelector('[name="sprite_action"]'), action);
  setFieldValue(form.querySelector('[name="direction"]'), direction);

  return {
    ...data,
    source_sprite: source,
    reference_image: source,
    existing_sprite_name: spriteName,
    existing_sprite_actions: actions,
    existing_sprite_directions: directions,
    character,
    style,
    negative,
    sprite_action: action,
    direction,
    default_actions: actions,
    default_directions: directions,
    tier: modelPreset.tier,
    mode: modelPreset.mode,
    profile: modelPreset.profile
  };
}

let generatePromptPreviewTimer = null;

function buildGeneratePromptPreview(data) {
  const override = String(data.prompt || '').trim();
  if (override) return override;
  return [
    data.character,
    `${data.sprite_action || 'idle'} animation`,
    `${data.direction || 'right'} direction`,
    data.style,
    data.extra_prompt,
    'single full body 2D game sprite, locked camera, centered character, clean readable silhouette',
  ].filter(Boolean).map(part => String(part).trim()).filter(Boolean).join(', ');
}

function renderGeneratePromptLint(result) {
  const badge = $('#generatePromptQuality');
  const list = $('#generatePromptLint');
  if (badge) {
    const score = Number(result.score ?? result.overall_score ?? 0);
    badge.textContent = Number.isFinite(score) ? `quality ${Math.round(score)}` : 'quality check';
    badge.className = 'prompt-quality-badge ' + (score >= 80 ? 'good' : score >= 55 ? 'warn' : 'bad');
  }
  if (!list) return;
  clearNode(list);
  const suggestions = result.suggestions || result.recommendations || result.warnings || [];
  if (!suggestions.length) {
    appendText(list, 'small', 'Prompt looks ready for a sprite generation pass.');
    return;
  }
  suggestions.slice(0, 4).forEach(item => {
    appendText(list, 'small', typeof item === 'string' ? item : (item.message || item.title || JSON.stringify(item)));
  });
}

function generateReferencePreviewUrl(path) {
  const value = String(path || '').trim();
  if (!value || !/\.(png|jpe?g|webp|gif)$/i.test(value)) return '';
  if (/^(https?:|\/file\/|data:image\/)/i.test(value)) return value;
  if (/^[a-z]:[\\/]/i.test(value)) return '';
  return '/file/' + value.replace(/^\.?[\\/]+/, '').replace(/\\/g, '/');
}

function refreshGenerateReferencePreview() {
  const ref = String($('#generationReferenceImage')?.value || '').trim();
  const style = String($('#generationStyleImage')?.value || '').trim();
  const source = ref || style;
  const img = $('#generateReferencePreviewImage');
  const empty = $('#generateReferencePreviewEmpty');
  const title = $('#generateReferencePreviewTitle');
  const status = $('#generateReferencePreviewStatus');
  const url = generateReferencePreviewUrl(source);
  if (img) {
    img.classList.toggle('hidden', !url);
    if (url) img.src = url;
    else img.removeAttribute('src');
  }
  if (empty) empty.classList.toggle('hidden', !!url);
  if (title) title.textContent = ref ? 'Character reference ready' : (style ? 'Style reference ready' : 'No reference selected');
  if (status) {
    if (!source) status.textContent = 'Supports workspace PNG, JPG, WebP, and GIF paths.';
    else if (url) status.textContent = source;
    else status.textContent = 'Preview unavailable for absolute local paths; generation can still use the path.';
  }
}

function refreshGeneratePromptPreview() {
  const form = $('#generateForm');
  if (!form) return;
  const data = formData(form);
  const prompt = buildGeneratePromptPreview(data);
  const preview = $('#generatePromptPreview');
  if (preview) preview.textContent = prompt || 'Prompt preview will appear here.';
  clearTimeout(generatePromptPreviewTimer);
  generatePromptPreviewTimer = setTimeout(async () => {
    if (!prompt) return;
    try {
      const result = await api('/api/prompt/lint', {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          negative: data.negative || '',
          action: data.sprite_action || '',
          full_payload: data,
        }),
      });
      renderGeneratePromptLint(result);
    } catch (err) {
      const badge = $('#generatePromptQuality');
      if (badge) {
        badge.textContent = 'lint unavailable';
        badge.className = 'prompt-quality-badge muted';
      }
    }
    try {
      const params = new URLSearchParams({
        tier: data.tier || '',
        profile: data.profile || '',
        sprite_action: data.sprite_action || '',
      });
      const estimate = await api('/api/generation/estimate?' + params.toString());
      const eta = estimate.eta || {};
      const target = $('#generateEstimate');
      if (target) {
        target.textContent = eta.sample_count
          ? `Runtime estimate: ${eta.label} from ${eta.sample_count} similar run${eta.sample_count === 1 ? '' : 's'}.`
          : `Runtime estimate: ${eta.label || 'learning from first run'}.`;
      }
    } catch (err) {
      const target = $('#generateEstimate');
      if (target) target.textContent = 'Runtime estimate unavailable.';
    }
  }, 350);
}

function initFormBindings() {
  // Nav, jump, run, open binders
  $$('.nav').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
  $$('[data-jump]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.jump)));
  $$('[data-run]').forEach(b=>b.addEventListener('click',()=>runAction(b.dataset.run)));
  $$('[data-open]').forEach(b=>b.addEventListener('click',()=>openPath(b.dataset.open)));
  initTrainingTabs();

  if ($('#refreshOutputs')) $('#refreshOutputs').addEventListener('click', refreshAll);
  if ($('#cancelJob')) $('#cancelJob').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
  if ($('#cancelJob2')) $('#cancelJob2').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
  if ($('#copyLog')) $('#copyLog').addEventListener('click',()=>navigator.clipboard.writeText(lastLogText||'').then(()=>toast('Log copied')));
  if ($('#launchComfy')) $('#launchComfy').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });

  // Generation form
  if ($('#generateForm')) $('#generateForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('generate_sprite', formData(e.currentTarget)); showView('logs'); });
  if ($('#generateForm')) {
    $('#generateForm').addEventListener('input', refreshGeneratePromptPreview);
    $('#generateForm').addEventListener('change', refreshGeneratePromptPreview);
    $('#generationReferenceImage')?.addEventListener('input', refreshGenerateReferencePreview);
    $('#generationStyleImage')?.addEventListener('input', refreshGenerateReferencePreview);
    $('#generationReferenceImage')?.addEventListener('change', refreshGenerateReferencePreview);
    $('#generationStyleImage')?.addEventListener('change', refreshGenerateReferencePreview);
    refreshGenerateReferencePreview();
    refreshGeneratePromptPreview();
  }
  if ($('#btnPreviewGenerate')) {
    $('#btnPreviewGenerate').addEventListener('click', () => {
      const data = formData($('#generateForm'));
      runAction('generate_sprite', { ...data, preview: true });
      showView('logs');
    });
  }
  if ($('#btnGenerateExistingSprite')) {
    $('#btnGenerateExistingSprite').addEventListener('click', () => {
      const payload = buildExistingSpritePayload();
      if (!payload) return;
      runAction('generate_sprite', payload);
      showView('logs');
    });
  }
  if ($('#btnCreateExistingSpritePack')) {
    $('#btnCreateExistingSpritePack').addEventListener('click', () => {
      const payload = buildExistingSpritePayload();
      if (!payload) return;
      runAction('animate_existing_sprite', payload);
      showView('logs');
    });
  }
  if ($('#convertForm')) $('#convertForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('convert_video', formData(e.currentTarget)); showView('logs'); });

  // Quality actions
  $$('[data-quality]').forEach(btn=>btn.addEventListener('click',()=>{
    const data=formData($('#qualityForm')); const mode=btn.dataset.quality;
    if(mode==='validate'){
      runAction('validate_export', {...data, engine: null}); showView('logs'); return;
    }
    const action = mode==='qa'?'qa_report':mode==='fix'?'autofix':mode==='godot'?'export_godot':mode==='unity'?'export_unity':'export_unreal';
    runAction(action, data); showView('logs');
  }));
  if ($('#packForm')) $('#packForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('character_pack', formData(e.currentTarget)); showView('logs'); });
  if ($('#atlasForm')) $('#atlasForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('atlas', formData(e.currentTarget)); showView('logs'); });
  if ($('#animatedExportUseSelected')) $('#animatedExportUseSelected').addEventListener('click', () => {
    const input = $('#animatedExportForm [name="path"]');
    if (input && selectedSpriteDir) input.value = selectedSpriteDir;
    else toast('Select a sprite output first.');
  });
  if ($('#animatedExportForm')) $('#animatedExportForm').addEventListener('submit', async e => {
    e.preventDefault();
    const result = $('#animatedExportResult');
    const data = formData(e.currentTarget);
    if (!data.path) {
      toast('Enter a sprite folder to export.');
      return;
    }
    if (result) result.textContent = 'Exporting animation...';
    try {
      const exported = await api('/api/sprite/export_animation', { method: 'POST', body: JSON.stringify(data) });
      if (result) {
        clearNode(result);
        appendText(result, 'b', `${(exported.format || data.format || 'animation').toUpperCase()} export ready`);
        appendText(result, 'code', exported.path || '');
        if (exported.path) {
          const link = document.createElement('a');
          link.className = 'mini link-button';
          link.href = '/file/' + exported.path;
          link.textContent = 'Open export';
          result.appendChild(link);
        }
      }
      toast('Animated export ready.');
    } catch (err) {
      if (result) result.textContent = 'Animated export failed.';
      toast(err.message || 'Animated export failed.');
    }
  });
  if ($('#skeletalExportUseSelected')) $('#skeletalExportUseSelected').addEventListener('click', () => {
    const input = $('#skeletalExportForm [name="path"]');
    if (input && selectedSpriteDir) input.value = selectedSpriteDir;
    else toast('Select a sprite output first.');
  });
  if ($('#skeletalExportForm')) $('#skeletalExportForm').addEventListener('submit', async e => {
    e.preventDefault();
    const result = $('#skeletalExportResult');
    const data = formData(e.currentTarget);
    if (!data.path) {
      toast('Enter a sprite folder to export.');
      return;
    }
    if (result) result.textContent = 'Exporting skeletal rig...';
    try {
      const exported = await api('/api/sprite/export_skeletal', { method: 'POST', body: JSON.stringify(data) });
      if (result) {
        clearNode(result);
        appendText(result, 'b', 'Skeletal export ready');
        const parts = Array.isArray(exported.parts) ? exported.parts : [];
        appendText(result, 'small', `${parts.length} part${parts.length === 1 ? '' : 's'} · ${exported.segmentation?.method || 'segmentation provenance unavailable'}`);
        ['spine_json', 'dragonbones_json', 'skeletal_manifest'].forEach(key => {
          if (!exported[key]) return;
          const link = document.createElement('a');
          link.className = 'mini link-button';
          link.href = '/file/' + exported[key];
          link.textContent = key === 'spine_json' ? 'Open Spine JSON' : key === 'dragonbones_json' ? 'Open DragonBones JSON' : 'Open skeletal manifest';
          result.appendChild(link);
        });
      }
      toast('Skeletal export ready.');
    } catch (err) {
      if (result) result.textContent = 'Skeletal export failed.';
      toast(err.message || 'Skeletal export failed.');
    }
  });
  if ($('#trainingDatasetForm')) $('#trainingDatasetForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('training_dataset', formData(e.currentTarget)); showView('logs'); });
  initTrainingDatasetBuilder();
  if ($('#previewTrainingDataset')) $('#previewTrainingDataset').addEventListener('click', previewTrainingDataset);
  if ($('#tileTrainingDatasetForm')) $('#tileTrainingDatasetForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('tile_training_dataset', formData(e.currentTarget)); showView('logs'); });
  if ($('#tilemapGeneratorForm')) $('#tilemapGeneratorForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('tilemap', formData(e.currentTarget)); showView('logs'); });
  $$('[data-lora-mode]').forEach(btn=>btn.addEventListener('click',()=>{
    const form = $('#loraTrainingForm');
    if (!form) return;
    runAction('lora_training', { ...formData(form), mode: btn.dataset.loraMode || 'prepare' });
    showView('logs');
  }));
  if ($('#refreshLoraProgress')) $('#refreshLoraProgress').addEventListener('click', refreshLoraProgress);
  if ($('#buildLoraComparePlan')) $('#buildLoraComparePlan').addEventListener('click', buildLoraComparePlan);
  if ($('#applyLoraGpuDefaults')) $('#applyLoraGpuDefaults').addEventListener('click', applyLoraGpuDefaults);

  // Release and queue forms
  if ($('#releaseForm')) $('#releaseForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('release_package', formData(e.currentTarget)); showView('logs'); });
  if ($('#queueForm')) $('#queueForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('queue_create', formData(e.currentTarget)); showView('logs'); });

  // Dropzone
  const dz=$('#dropzone'), vf=$('#videoFile');
  if (dz && vf) {
    ['dragenter','dragover'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add('drag')}));
    ['dragleave','drop'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove('drag')}));
    dz.addEventListener('drop',e=>{ const f=e.dataTransfer.files?.[0]; if(f) uploadFile(f).catch(err=>toast(err.message)); });
    vf.addEventListener('change',()=>{ const f=vf.files?.[0]; if(f) uploadFile(f).catch(err=>toast(err.message)); });
  }

  // Run next action / guided
  if($('#runNextAction')) $('#runNextAction').addEventListener('click', runRecommended);
  if($('#guidedRecommended')) $('#guidedRecommended').addEventListener('click', runRecommended);
  if($('#launchComfy2')) $('#launchComfy2').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });

  // Project select
  if($('#projectSelect')) $('#projectSelect').addEventListener('change', async e => {
    activeProjectPath = e.currentTarget.value || '';
    try{
      await api('/api/projects/active',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:activeProjectPath})});
      toast(activeProjectPath ? 'Project selected' : 'Global workspace selected');
      await refreshAll();
      if ($('#view-release')?.classList.contains('active') && typeof loadReleases === 'function') await loadReleases();
      if ($('#view-history')?.classList.contains('active') && typeof loadHistory === 'function') await loadHistory();
      if ($('#view-queues')?.classList.contains('active') && typeof loadQueues === 'function') await loadQueues();
      if ($('#view-packs')?.classList.contains('active')) {
        if (typeof loadPacks === 'function') await loadPacks();
        if (typeof loadPlanning === 'function') await loadPlanning();
      }
      if ($('#view-quality')?.classList.contains('active') && typeof loadQualityReports === 'function') await loadQualityReports();
      if ($('#view-convert')?.classList.contains('active') && typeof loadReferences === 'function') await loadReferences();
    }catch(err){ toast('Project select failed: '+err.message); }
  });
  if($('#createProjectBtn')) $('#createProjectBtn').addEventListener('click', createProject);
  if($('#projectNameInput')) $('#projectNameInput').addEventListener('keydown', e => {
    if(e.key === 'Enter'){ e.preventDefault(); createProject(); }
  });
}

async function previewTrainingDataset() {
  const form = $('#trainingDatasetForm');
  const target = $('#trainingDatasetPreview');
  if (!form) return;
  const payload = formData(form);
  if (!payload.source_dir) {
    toast('Choose a purchased sprite folder first.');
    return;
  }
  if (target) target.textContent = 'Previewing dataset without writing files...';
  try {
    const data = await api('/api/training-dataset/preview', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    if (!target) return;
    clearNode(target);
    appendText(target, 'b', `${data.estimated_sample_count || 0} samples from ${data.source_image_count || 0} source image${data.source_image_count === 1 ? '' : 's'}`);
    appendText(target, 'small', `Trigger ${data.trigger || 'n/a'} · cell ${data.cell_size || 'no slicing'} · read-only preview`);
    const actionKeys = Object.keys(data.action_counts || {}).slice(0, 6);
    if (actionKeys.length) appendText(target, 'small', `Actions: ${actionKeys.map(key => `${key} (${data.action_counts[key]})`).join(', ')}`);
    (data.samples || []).slice(0, 5).forEach(sample => {
      const row = document.createElement('div');
      row.className = 'training-dataset-preview-row';
      if (sample.thumbnail_data_uri) {
        const img = document.createElement('img');
        img.src = sample.thumbnail_data_uri;
        img.alt = sample.source_name || 'dataset preview crop';
        row.appendChild(img);
      }
      appendText(row, 'b', `${sample.source_name || 'source'} #${sample.frame_index}`);
      appendText(row, 'span', sample.caption || '');
      appendText(row, 'small', `${sample.size || ''}${sample.direction ? ' · ' + sample.direction : ''}`);
      target.appendChild(row);
    });
    toast('Training dataset preview ready.');
  } catch (err) {
    if (target) target.textContent = err.message || 'Could not preview dataset.';
    toast(err.message || 'Could not preview dataset.');
  }
}

function initTrainingDatasetBuilder() {
  const zone = $('#trainingDatasetDropzone');
  const form = $('#trainingDatasetForm');
  const hint = $('#trainingDatasetDropHint');
  if (!zone || !form) return;
  const source = form.querySelector('[name="source_dir"]');
  const setHint = text => { if (hint) hint.textContent = text; };
  const applyPath = text => {
    const value = String(text || '').trim().replace(/^["']|["']$/g, '');
    if (!value) return false;
    if (source) source.value = value;
    setHint(`Source folder set to ${value}`);
    toast('Training dataset source folder set.');
    return true;
  };
  ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, event => {
    event.preventDefault();
    zone.classList.add('drag');
  }));
  ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, event => {
    event.preventDefault();
    zone.classList.remove('drag');
  }));
  zone.addEventListener('drop', event => {
    const textPath = event.dataTransfer?.getData('text/plain') || event.dataTransfer?.getData('text/uri-list') || '';
    if (applyPath(textPath)) return;
    const files = Array.from(event.dataTransfer?.files || []).filter(file => /\.(png|jpe?g|webp)$/i.test(file.name || ''));
    if (files.length) setHint(`${files.length} image file${files.length === 1 ? '' : 's'} detected. Paste the parent folder path to build locally.`);
  });
  zone.addEventListener('paste', event => {
    const textPath = event.clipboardData?.getData('text/plain') || '';
    if (applyPath(textPath)) event.preventDefault();
  });
  zone.addEventListener('keydown', event => {
    if (event.key === 'Enter' && source) source.focus();
  });
}

async function buildLoraComparePlan() {
  const result = $('#loraComparePlanResult');
  const prompt = $('#loraComparePrompt')?.value || '';
  const loras = $('#loraCompareNames')?.value || '';
  if (result) result.textContent = 'Building LoRA comparison plan...';
  try {
    const plan = await api('/api/lora/compare-plan', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        loras,
        base_payload: formData($('#generateForm') || document.createElement('form'))
      })
    });
    if (!result) return;
    clearNode(result);
    appendText(result, 'b', `${plan.variant_count} LoRA variant${plan.variant_count === 1 ? '' : 's'} planned`);
    (plan.variants || []).forEach(variant => {
      appendText(result, 'code', `${variant.slot}: ${variant.label} -> ${variant.payload.prompt}`);
    });
    if (plan.missing && plan.missing.length) {
      appendText(result, 'small', `Missing registry entries: ${plan.missing.join(', ')}`);
    }
    appendText(result, 'small', plan.compare_player?.next_step || 'Generate variants, then open Compare Player.');
  } catch (err) {
    if (result) result.textContent = err.message || 'Could not build LoRA comparison plan.';
    toast(err.message || 'Could not build LoRA comparison plan.');
  }
}

async function applyLoraGpuDefaults() {
  const form = $('#loraTrainingForm');
  const hint = $('#loraGpuDefaultsHint');
  if (!form) return;
  const family = form.querySelector('[name="model_family"]')?.value || 'sdxl';
  if (hint) hint.textContent = 'Reading GPU and calculating LoRA defaults...';
  try {
    const data = await api('/api/lora/recommended-defaults?model_family=' + encodeURIComponent(family));
    const rec = data.recommendation || {};
    [
      ['resolution', rec.resolution],
      ['max_train_steps', rec.max_train_steps],
      ['learning_rate', rec.learning_rate],
      ['network_dim', rec.network_dim],
      ['repeats', data.repeats],
      ['batch_size', rec.batch_size],
    ].forEach(([name, value]) => {
      const field = form.querySelector(`[name="${name}"]`);
      if (field && value !== undefined && value !== null) field.value = String(value);
    });
    if (hint) hint.textContent = `${data.tier}: ${rec.resolution}px, rank ${rec.network_dim}, ${rec.max_train_steps} steps, batch ${rec.batch_size}.`;
    toast('Applied conservative LoRA GPU defaults.');
  } catch (err) {
    if (hint) hint.textContent = err.message || 'Could not apply GPU defaults.';
    toast(err.message || 'Could not apply LoRA GPU defaults.');
  }
}

async function refreshLoraProgress() {
  const input = $('#loraProgressPath');
  const summary = $('#loraProgressSummary');
  const gallery = $('#loraSampleGallery');
  const path = String(input?.value || '').trim();
  if (!path) {
    toast('Enter a training run folder.');
    return;
  }
  try {
    const data = await api('/api/lora/progress?path=' + encodeURIComponent(path));
    if (summary) {
      summary.textContent = `Step ${data.current_step || 0}${data.max_steps ? '/' + data.max_steps : ''} · loss ${data.last_loss ?? 'n/a'} · ${data.checkpoints.length} checkpoints`;
    }
    drawLoraLossChart(data.loss_points || []);
    if (gallery) {
      clearNode(gallery);
      (data.samples || []).forEach(sample => {
        const img = document.createElement('img');
        img.src = sample.url + '?t=' + Date.now();
        img.alt = sample.name;
        gallery.appendChild(img);
      });
    }
  } catch (err) {
    if (summary) summary.textContent = err.message || 'Could not load training progress.';
  }
}

function drawLoraLossChart(points) {
  const canvas = $('#loraLossChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = 'rgba(255,255,255,0.04)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!points.length) return;
  const losses = points.map(p => Number(p.loss)).filter(Number.isFinite);
  const minLoss = Math.min(...losses);
  const maxLoss = Math.max(...losses);
  ctx.strokeStyle = '#74f0c0';
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, idx) => {
    const x = (idx / Math.max(1, points.length - 1)) * canvas.width;
    const norm = (Number(point.loss) - minLoss) / Math.max(0.0001, maxLoss - minLoss);
    const y = canvas.height - 12 - norm * (canvas.height - 24);
    if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function initTrainingTabs() {
  const root = $('#view-training');
  if (!root) return;
  const buttons = Array.from(root.querySelectorAll('[data-training-tab]'));
  const panels = Array.from(root.querySelectorAll('[data-training-panel]'));
  if (!buttons.length || !panels.length) return;

  const activate = (name) => {
    buttons.forEach(btn => {
      const active = btn.dataset.trainingTab === name;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    panels.forEach(panel => {
      panel.classList.toggle('active', panel.dataset.trainingPanel === name);
    });
  };

  buttons.forEach(btn => {
    btn.addEventListener('click', () => activate(btn.dataset.trainingTab));
  });
}
