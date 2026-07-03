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

function initFormBindings() {
  // Nav, jump, run, open binders
  $$('.nav').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
  $$('[data-jump]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.jump)));
  $$('[data-run]').forEach(b=>b.addEventListener('click',()=>runAction(b.dataset.run)));
  $$('[data-open]').forEach(b=>b.addEventListener('click',()=>openPath(b.dataset.open)));

  if ($('#refreshOutputs')) $('#refreshOutputs').addEventListener('click', refreshAll);
  if ($('#cancelJob')) $('#cancelJob').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
  if ($('#cancelJob2')) $('#cancelJob2').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
  if ($('#copyLog')) $('#copyLog').addEventListener('click',()=>navigator.clipboard.writeText(lastLogText||'').then(()=>toast('Log copied')));
  if ($('#launchComfy')) $('#launchComfy').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });

  // Generation form
  if ($('#generateForm')) $('#generateForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('generate_sprite', formData(e.currentTarget)); showView('logs'); });
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
  if ($('#trainingDatasetForm')) $('#trainingDatasetForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('training_dataset', formData(e.currentTarget)); showView('logs'); });
  if ($('#tileTrainingDatasetForm')) $('#tileTrainingDatasetForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('tile_training_dataset', formData(e.currentTarget)); showView('logs'); });
  $$('[data-lora-mode]').forEach(btn=>btn.addEventListener('click',()=>{
    const form = $('#loraTrainingForm');
    if (!form) return;
    runAction('lora_training', { ...formData(form), mode: btn.dataset.loraMode || 'prepare' });
    showView('logs');
  }));

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
