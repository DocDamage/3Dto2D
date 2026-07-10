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

const GENERATE_ALL_DIRECTIONS = ['front', 'front_right', 'right', 'back_right', 'back', 'back_left', 'left', 'front_left'];

function labelFromToken(value) {
  return String(value || '')
    .split('_')
    .map(part => part ? part[0].toUpperCase() + part.slice(1) : '')
    .join(' ');
}

function generateChoiceValues(selector) {
  return $$(selector)
    .filter(input => input.checked)
    .map(input => input.value)
    .filter(Boolean);
}

function setGenerateChoiceHidden(form, name, value) {
  const input = form?.querySelector(`[name="${name}"]`);
  if (input) input.value = value;
}

function renderGenerateActionChoices(actions) {
  const fieldset = $('#generateActionChoices');
  if (!fieldset || !Array.isArray(actions) || !actions.length) return;
  const selected = new Set(generateChoiceValues('[data-generate-action]'));
  const currentHidden = csvValues($('#generateForm')?.querySelector('[name="default_actions"]')?.value || '');
  currentHidden.forEach(action => selected.add(action));
  clearNode(fieldset);
  const legend = document.createElement('legend');
  legend.textContent = 'Actions';
  fieldset.appendChild(legend);
  actions.forEach(action => {
    const label = document.createElement('label');
    label.className = 'choice-chip';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.dataset.generateAction = '';
    input.value = action;
    input.checked = selected.size ? selected.has(action) : action === 'walk';
    label.appendChild(input);
    label.append(labelFromToken(action));
    fieldset.appendChild(label);
  });
  syncGenerateChoices();
}

async function loadGenerateActionChoices() {
  try {
    const options = await api('/api/prompt_builder/options');
    renderGenerateActionChoices(options.actions || []);
  } catch (err) {
    console.warn('Could not load full action catalog:', err);
  }
}

function syncGenerateChoices() {
  const form = $('#generateForm');
  if (!form) return;
  const actionText = String(form.querySelector('[name="default_actions_text"]')?.value || '').trim();
  const directionText = String(form.querySelector('[name="default_directions_text"]')?.value || '').trim();
  const actions = actionText ? csvValues(actionText) : generateChoiceValues('[data-generate-action]');
  const allDirections = !!form.querySelector('[data-generate-direction-all]')?.checked;
  const directions = directionText
    ? csvValues(directionText)
    : (allDirections ? GENERATE_ALL_DIRECTIONS : generateChoiceValues('[data-generate-direction]'));
  const finalActions = actions.length ? actions : ['idle'];
  const finalDirections = directions.length ? directions : ['right'];
  setGenerateChoiceHidden(form, 'sprite_action', finalActions[0]);
  setGenerateChoiceHidden(form, 'direction', finalDirections[0]);
  setGenerateChoiceHidden(form, 'default_actions', finalActions.join(','));
  setGenerateChoiceHidden(form, 'default_directions', finalDirections.join(','));
}

function syncGenerateChoiceChecksFromHidden() {
  const form = $('#generateForm');
  if (!form) return;
  const actions = new Set(csvValues(form.querySelector('[name="default_actions"]')?.value || form.querySelector('[name="sprite_action"]')?.value || 'walk'));
  const directionsRaw = csvValues(form.querySelector('[name="default_directions"]')?.value || form.querySelector('[name="direction"]')?.value || 'right');
  const directions = new Set(directionsRaw);
  const knownActions = new Set($$('[data-generate-action]', form).map(input => input.value));
  const actionText = form.querySelector('[name="default_actions_text"]');
  const directionText = form.querySelector('[name="default_directions_text"]');
  const hasCustomActions = Array.from(actions).some(action => !knownActions.has(action));
  const hasCustomDirections = directionsRaw.some(direction => !GENERATE_ALL_DIRECTIONS.includes(direction));
  if (actionText) actionText.value = hasCustomActions ? Array.from(actions).join(',') : '';
  if (directionText) directionText.value = hasCustomDirections ? directionsRaw.join(',') : '';
  $$('[data-generate-action]', form).forEach(input => { input.checked = actions.has(input.value); });
  const allSelected = GENERATE_ALL_DIRECTIONS.every(direction => directions.has(direction));
  const allToggle = form.querySelector('[data-generate-direction-all]');
  if (allToggle) allToggle.checked = allSelected;
  $$('[data-generate-direction]', form).forEach(input => { input.checked = !allSelected && directions.has(input.value); });
  syncGenerateChoices();
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
  const actions = csvValues(data.default_actions || data.sprite_action || 'idle');
  const directions = csvValues(data.default_directions || data.direction || 'right');
  return [
    data.character,
    `${actions.join(', ') || 'idle'} animation${actions.length === 1 ? '' : 's'}`,
    `${directions.join(', ') || 'right'} direction${directions.length === 1 ? '' : 's'}`,
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
  syncGenerateChoices();
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

async function applyGeneratePromptAutofix(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const form = $('#generateForm');
  if (!form) return;
  syncGenerateChoices();
  const data = formData(form);
  try {
    const result = await api('/api/prompt/autofix', {
      method: 'POST',
      body: JSON.stringify({
        ...data,
        prompt: buildGeneratePromptPreview(data),
      }),
    });
    if (form.elements.prompt && result.prompt) form.elements.prompt.value = result.prompt;
    if (form.elements.negative && result.negative) form.elements.negative.value = result.negative;
    renderGeneratePromptLint(result.lint_after || result);
    refreshGeneratePromptPreview();
    toast('Prompt auto-fixed');
  } catch (err) {
    toast(err.message || 'Prompt auto-fix failed');
  }
}

async function loadProviderKeysPanel() {
  const grid = $('#providerKeyGrid');
  if (!grid) return;
  try {
    const data = await api('/api/cloud/image-providers');
    const providers = Object.values(data.providers || {});
    clearNode(grid);
    if (!providers.length) {
      appendText(grid, 'div', 'No providers configured.', 'empty compact');
      return;
    }
    providers.forEach(provider => {
      const card = document.createElement('article');
      card.className = 'provider-key-card';
      const head = document.createElement('div');
      head.className = 'provider-key-title';
      appendText(head, 'b', provider.label || provider.provider);
      const status = document.createElement('span');
      status.className = 'badge ' + (provider.configured ? 'ok' : 'warn');
      status.textContent = provider.configured ? 'Configured' : 'Missing';
      head.appendChild(status);
      card.appendChild(head);
      appendText(card, 'small', provider.image_generation || 'Provider availability depends on your account.');
      appendText(card, 'small', `Env: ${(provider.env_names || []).join(', ') || 'not available'}`);
      if (provider.free_tier) appendText(card, 'small', 'Free-tier capable: check current provider limits before running batches.');
      const input = document.createElement('input');
      input.type = 'password';
      input.placeholder = 'Paste API key';
      input.autocomplete = 'off';
      input.dataset.providerKeyInput = provider.provider;
      card.appendChild(input);
      const actions = document.createElement('div');
      actions.className = 'button-row compact-actions';
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'mini primary';
      save.dataset.saveProviderKey = provider.provider;
      save.textContent = 'Save key';
      actions.appendChild(save);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'mini danger';
      remove.dataset.removeProviderKey = provider.provider;
      remove.textContent = 'Remove';
      actions.appendChild(remove);
      card.appendChild(actions);
      grid.appendChild(card);
    });
  } catch (err) {
    clearNode(grid);
    appendText(grid, 'div', 'Could not load provider key status: ' + err.message, 'empty compact');
  }
}

async function saveProviderKey(provider) {
  const input = document.querySelector(`[data-provider-key-input="${provider}"]`);
  const apiKey = String(input?.value || '').trim();
  if (!apiKey) return toast('Paste an API key first.');
  await api('/api/cloud/image-provider-key', {
    method: 'POST',
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
  if (input) input.value = '';
  toast('API key saved locally');
  await loadProviderKeysPanel();
}

async function removeProviderKey(provider) {
  await api('/api/cloud/image-provider-key', {
    method: 'DELETE',
    body: JSON.stringify({ provider }),
  });
  toast('API key removed locally');
  await loadProviderKeysPanel();
}

const DEDICATED_LPC_CATEGORIES = [
  'body', 'hair', 'eyes', 'facial', 'beards', 'head', 'torso', 'arms',
  'legs', 'feet', 'hat', 'backpack', 'weapon', 'shield', 'quiver', 'cape',
  'shoulders', 'neck', 'dress'
];

const DEDICATED_LPC_SLOT_ALIASES = {
  ammo: 'quiver',
  back: 'backpack',
  mainhand: 'weapon',
  weapons: 'weapon',
  offhand: 'shield',
  waist: 'torso',
};

const DEDICATED_LPC_RACE_TOKENS = [
  'alien', 'boarman', 'frankenstein', 'goblin', 'human', 'jack', 'lizard',
  'minotaur', 'mouse', 'orc', 'pig', 'rabbit', 'rat', 'sheep', 'skeleton',
  'troll', 'vampire', 'wartotaur', 'wolf', 'zombie'
];

function dedicatedLpcCanonicalSlot(slot) {
  const key = String(slot || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
  return DEDICATED_LPC_SLOT_ALIASES[key] || key;
}

function dedicatedLpcBodyType() {
  const selectedBody = $('#lpcBody')?.value || 'regular';
  const gender = $('#lpcGender')?.value || 'male';
  return selectedBody === 'regular' ? gender : selectedBody;
}

function dedicatedLpcRaceKey() {
  const value = String($('[data-lpc-query="heads"]', $('#view-lpc'))?.value || 'human').toLowerCase();
  const tokens = value.replace(/^heads\s+/, '').split(/\s+/).filter(Boolean);
  return tokens.find(token => DEDICATED_LPC_RACE_TOKENS.includes(token)) || 'human';
}

function dedicatedLpcRaceCompatible(option, raceKey) {
  const words = `${option.value || ''} ${option.label || ''}`.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  const taggedRace = DEDICATED_LPC_RACE_TOKENS.find(token => words.includes(token));
  return !taggedRace || taggedRace === raceKey;
}

function dedicatedLpcCurrentPalette() {
  return $('#lpcPalette')?.value || 'default';
}

function dedicatedLpcStatus(text) {
  const target = $('#lpcStatus');
  if (target) target.textContent = text || 'Ready.';
}

let dedicatedLpcPreviewTimer = null;
let dedicatedLpcPreviewBusy = false;
let dedicatedLpcQueuedPreview = false;
let dedicatedLpcInitialPreviewDone = false;
let dedicatedLpcAnimationTimer = null;
let dedicatedLpcAnimationImage = null;
let dedicatedLpcAnimationData = null;
let dedicatedLpcAnimationFrame = 0;
let dedicatedLpcAnimationPlaying = true;
let dedicatedLpcPreviewPan = { x: 0, y: 0 };
let dedicatedLpcPreviewDrag = null;
let dedicatedLpcEditorPointer = null;
let dedicatedLpcEditor = {
  activeMode: 'preview',
  layerIndex: 0,
  layers: []
};

const DEDICATED_LPC_DIRECTION_ROWS = {
  back: 0,
  up: 0,
  left: 1,
  front: 2,
  down: 2,
  right: 3,
};

const DEDICATED_LPC_EDITOR_DIRECTIONS = ['back', 'left', 'front', 'right'];

function dedicatedLpcSetZoom(value) {
  const slider = $('#lpcZoom');
  const label = $('#lpcZoomLabel');
  const next = Math.max(1, Math.min(8, Number(value) || 3));
  if (slider) slider.value = String(next);
  if (label) label.textContent = `${Math.round(next * 100)}%`;
  dedicatedLpcApplyPreviewTransform();
}

function dedicatedLpcFps() {
  return Math.max(1, Math.min(24, Number($('#lpcFps')?.value || 6) || 6));
}

function dedicatedLpcFrameRow(direction, rows) {
  const row = DEDICATED_LPC_DIRECTION_ROWS[String(direction || 'front').toLowerCase()] ?? 2;
  return Math.min(Math.max(0, row), Math.max(0, rows - 1));
}

function dedicatedLpcApplyPreviewTransform() {
  const canvas = $('#lpcPreviewCanvas');
  const zoom = Math.max(1, Math.min(8, Number($('#lpcZoom')?.value || 3) || 3));
  if (canvas) canvas.style.transform = `translate(${dedicatedLpcPreviewPan.x}px, ${dedicatedLpcPreviewPan.y}px) scale(${zoom})`;
}

function dedicatedLpcSetPlaying(playing) {
  dedicatedLpcAnimationPlaying = !!playing;
  const button = $('#lpcPlayPause');
  if (button) button.textContent = dedicatedLpcAnimationPlaying ? 'Pause' : 'Play';
  dedicatedLpcRestartAnimationTimer();
}

function dedicatedLpcFreshSheetUrl(data) {
  const base = data?.sheet_url || (data?.sheet ? `/file/${data.sheet}` : '');
  if (!base) return '';
  const version = encodeURIComponent(`${data.created_at || ''}:${data.frame_count || ''}:${Date.now()}`);
  return `${base}${base.includes('?') ? '&' : '?'}v=${version}`;
}

function dedicatedLpcDrawFrame() {
  const canvas = $('#lpcPreviewCanvas');
  const ctx = canvas?.getContext('2d');
  const data = dedicatedLpcAnimationData;
  const image = dedicatedLpcAnimationImage;
  if (!canvas || !ctx || !data || !image || !image.complete || !image.naturalWidth) return;
  const frameWidth = Math.max(1, Number(data.frame_width || 64) || 64);
  const frameHeight = Math.max(1, Number(data.frame_height || 64) || 64);
  const columns = Math.max(1, Number(data.columns || Math.floor(image.naturalWidth / frameWidth) || 1));
  const rows = Math.max(1, Math.floor(image.naturalHeight / frameHeight) || 1);
  const row = dedicatedLpcFrameRow(data.preview_direction || $('#lpcDirection')?.value || 'front', rows);
  dedicatedLpcAnimationFrame = dedicatedLpcAnimationFrame % columns;
  canvas.width = frameWidth;
  canvas.height = frameHeight;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, frameWidth, frameHeight);
  ctx.drawImage(
    image,
    dedicatedLpcAnimationFrame * frameWidth,
    row * frameHeight,
    frameWidth,
    frameHeight,
    0,
    0,
    frameWidth,
    frameHeight
  );
  dedicatedLpcRenderEditorLayers(ctx, data.preview_direction || $('#lpcDirection')?.value || 'front', dedicatedLpcAnimationFrame);
  dedicatedLpcRenderEditor();
}

function dedicatedLpcFrameMetrics() {
  const data = dedicatedLpcAnimationData || {};
  const image = dedicatedLpcAnimationImage;
  const frameWidth = Math.max(1, Number(data.frame_width || 64) || 64);
  const frameHeight = Math.max(1, Number(data.frame_height || 64) || 64);
  const columns = Math.max(1, Number(data.columns || Math.floor((image?.naturalWidth || frameWidth) / frameWidth) || 1));
  const rows = Math.max(1, Math.floor((image?.naturalHeight || frameHeight) / frameHeight) || 1);
  const direction = $('#lpcDirection')?.value || data.preview_direction || 'front';
  return { frameWidth, frameHeight, columns, rows, direction, row: dedicatedLpcFrameRow(direction, rows) };
}

function dedicatedLpcEnsureEditorLayer() {
  if (!dedicatedLpcEditor.layers.length) {
    dedicatedLpcEditor.layers.push({
      id: `layer_${Date.now()}`,
      name: 'Edit Layer 1',
      visible: true,
      frames: {}
    });
    dedicatedLpcEditor.layerIndex = 0;
  }
  return dedicatedLpcEditor.layers[dedicatedLpcEditor.layerIndex] || dedicatedLpcEditor.layers[0];
}

function dedicatedLpcEditorFrameKey(direction, frameIndex) {
  return `${direction || 'front'}:${Math.max(0, Number(frameIndex) || 0)}`;
}

function dedicatedLpcEditorEnsureCanvas(layer, direction, frameIndex) {
  const { frameWidth, frameHeight } = dedicatedLpcFrameMetrics();
  const key = dedicatedLpcEditorFrameKey(direction, frameIndex);
  let canvas = layer.frames[key];
  if (!canvas || canvas.width !== frameWidth || canvas.height !== frameHeight) {
    canvas = document.createElement('canvas');
    canvas.width = frameWidth;
    canvas.height = frameHeight;
    layer.frames[key] = canvas;
  }
  return canvas;
}

function dedicatedLpcEditorTargetDirections() {
  return $('#lpcEditorApplyDirections')?.value === 'all'
    ? DEDICATED_LPC_EDITOR_DIRECTIONS
    : [$('#lpcDirection')?.value || 'front'];
}

function dedicatedLpcRenderEditorLayers(ctx, direction, frameIndex) {
  dedicatedLpcEditor.layers.forEach(layer => {
    if (!layer.visible) return;
    const layerCanvas = layer.frames[dedicatedLpcEditorFrameKey(direction, frameIndex)];
    if (layerCanvas) ctx.drawImage(layerCanvas, 0, 0);
  });
}

function dedicatedLpcRenderEditor() {
  const canvas = $('#lpcEditorCanvas');
  const ctx = canvas?.getContext('2d');
  const data = dedicatedLpcAnimationData;
  const image = dedicatedLpcAnimationImage;
  if (!canvas || !ctx) return;
  const { frameWidth, frameHeight, direction, row } = dedicatedLpcFrameMetrics();
  canvas.width = frameWidth;
  canvas.height = frameHeight;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, frameWidth, frameHeight);
  if (data && image && image.complete && image.naturalWidth) {
    ctx.drawImage(
      image,
      dedicatedLpcAnimationFrame * frameWidth,
      row * frameHeight,
      frameWidth,
      frameHeight,
      0,
      0,
      frameWidth,
      frameHeight
    );
  }
  dedicatedLpcRenderEditorLayers(ctx, direction, dedicatedLpcAnimationFrame);
}

function dedicatedLpcPaintEditorPixel(x, y) {
  const layer = dedicatedLpcEnsureEditorLayer();
  const { frameWidth, frameHeight } = dedicatedLpcFrameMetrics();
  const size = Math.max(1, Math.min(8, Number($('#lpcEditorSize')?.value || 1) || 1));
  const half = Math.floor(size / 2);
  const tool = $('#lpcEditorTool')?.value || 'brush';
  const color = $('#lpcEditorColor')?.value || '#f2a23a';
  const frameIndex = dedicatedLpcAnimationFrame;
  const points = [{ x, y }];
  if ($('#lpcEditorMirror')?.checked) points.push({ x: frameWidth - 1 - x, y });
  dedicatedLpcEditorTargetDirections().forEach(direction => {
    const layerCanvas = dedicatedLpcEditorEnsureCanvas(layer, direction, frameIndex);
    const layerCtx = layerCanvas.getContext('2d');
    layerCtx.imageSmoothingEnabled = false;
    layerCtx.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over';
    layerCtx.fillStyle = color;
    points.forEach(point => {
      const left = Math.max(0, Math.min(frameWidth - size, point.x - half));
      const top = Math.max(0, Math.min(frameHeight - size, point.y - half));
      layerCtx.fillRect(left, top, size, size);
    });
    layerCtx.globalCompositeOperation = 'source-over';
  });
  dedicatedLpcRenderEditor();
}

function dedicatedLpcEditorPointFromEvent(event) {
  const canvas = $('#lpcEditorCanvas');
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor(((event.clientX - rect.left) / rect.width) * canvas.width);
  const y = Math.floor(((event.clientY - rect.top) / rect.height) * canvas.height);
  if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return null;
  return { x, y };
}

function dedicatedLpcBeginEditorStroke(event) {
  if (dedicatedLpcEditor.activeMode !== 'editor') return;
  const point = dedicatedLpcEditorPointFromEvent(event);
  if (!point) return;
  event.preventDefault();
  dedicatedLpcSetPlaying(false);
  event.currentTarget?.setPointerCapture?.(event.pointerId);
  dedicatedLpcEditorPointer = event.pointerId;
  dedicatedLpcPaintEditorPixel(point.x, point.y);
}

function dedicatedLpcMoveEditorStroke(event) {
  if (dedicatedLpcEditorPointer !== event.pointerId) return;
  const point = dedicatedLpcEditorPointFromEvent(event);
  if (point) {
    event.preventDefault();
    dedicatedLpcPaintEditorPixel(point.x, point.y);
  }
}

function dedicatedLpcEndEditorStroke(event) {
  if (dedicatedLpcEditorPointer !== null && event.pointerId && dedicatedLpcEditorPointer !== event.pointerId) return;
  dedicatedLpcEditorPointer = null;
}

function dedicatedLpcRenderLayerList() {
  const list = $('#lpcEditorLayerList');
  if (!list) return;
  dedicatedLpcEnsureEditorLayer();
  clearNode(list);
  dedicatedLpcEditor.layers.forEach((layer, index) => {
    const row = document.createElement('label');
    row.className = `lpc-layer-row${index === dedicatedLpcEditor.layerIndex ? ' active' : ''}`;
    const visible = document.createElement('input');
    visible.type = 'checkbox';
    visible.checked = layer.visible !== false;
    visible.addEventListener('change', () => {
      layer.visible = visible.checked;
      dedicatedLpcRenderEditor();
    });
    const name = document.createElement('button');
    name.type = 'button';
    name.className = 'mini';
    name.textContent = layer.name;
    name.addEventListener('click', () => {
      dedicatedLpcEditor.layerIndex = index;
      dedicatedLpcRenderLayerList();
      dedicatedLpcRenderEditor();
    });
    row.append(visible, name);
    list.prepend(row);
  });
}

function dedicatedLpcAddEditorLayer() {
  dedicatedLpcEditor.layers.push({
    id: `layer_${Date.now()}_${dedicatedLpcEditor.layers.length + 1}`,
    name: `Edit Layer ${dedicatedLpcEditor.layers.length + 1}`,
    visible: true,
    frames: {}
  });
  dedicatedLpcEditor.layerIndex = dedicatedLpcEditor.layers.length - 1;
  dedicatedLpcRenderLayerList();
  dedicatedLpcRenderEditor();
}

function dedicatedLpcClearEditorLayer() {
  const layer = dedicatedLpcEnsureEditorLayer();
  layer.frames = {};
  dedicatedLpcRenderLayerList();
  dedicatedLpcRenderEditor();
}

function dedicatedLpcResetEditorLayers() {
  dedicatedLpcEditor.layers = [];
  dedicatedLpcEditor.layerIndex = 0;
  dedicatedLpcRenderLayerList();
  dedicatedLpcRenderEditor();
}

function dedicatedLpcSerializeEditorLayers() {
  return dedicatedLpcEditor.layers.map(layer => ({
    name: layer.name,
    visible: layer.visible !== false,
    frames: Object.entries(layer.frames || {}).map(([key, canvas]) => {
      const [direction, frame] = key.split(':');
      return {
        direction: direction || 'front',
        frame: Number(frame || 0) || 0,
        png: canvas.toDataURL('image/png')
      };
    })
  })).filter(layer => layer.frames.length);
}

async function dedicatedLpcBakeEditorLayers() {
  const data = dedicatedLpcAnimationData || {};
  const sheet = data.sheet || data.sheet_path || '';
  const layers = dedicatedLpcSerializeEditorLayers();
  if (!sheet) {
    toast('Compose the LPC character before baking edits.');
    return;
  }
  if (!layers.length) {
    toast('Draw something in the editor before baking.');
    return;
  }
  dedicatedLpcStatus('Baking LPC editor layers...');
  try {
    const baked = await api('/api/lpc/bake-edits', {
      method: 'POST',
      body: JSON.stringify({
        sheet,
        layers,
        name: `${$('#lpcCharacterName')?.value || data.name || 'lpc_character'}_edited`,
        preview_direction: $('#lpcDirection')?.value || 'front'
      })
    });
    dedicatedLpcResetEditorLayers();
    dedicatedLpcLoadAnimation(baked);
    dedicatedLpcStatus(`${baked.name || 'LPC edits'} baked · ${baked.applied_frames || 0} edited frames · ${baked.sheet || ''}`);
    toast('LPC edits baked to output.');
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not bake LPC edits.');
    toast(err.message || 'Could not bake LPC edits.');
  }
}

function dedicatedLpcDownloadEditorFrame() {
  dedicatedLpcRenderEditor();
  const canvas = $('#lpcEditorCanvas');
  if (!canvas) return;
  const link = document.createElement('a');
  const name = `${$('#lpcCharacterName')?.value || 'lpc'}_${$('#lpcDirection')?.value || 'front'}_${dedicatedLpcAnimationFrame}.png`
    .replace(/[^a-z0-9._-]+/gi, '_');
  link.download = name;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

function dedicatedLpcSetMode(mode) {
  dedicatedLpcEditor.activeMode = mode === 'editor' ? 'editor' : 'preview';
  $$('.lpc-mode-tab', $('#view-lpc')).forEach(button => {
    const active = button.dataset.lpcMode === dedicatedLpcEditor.activeMode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  [['preview', '#lpcPreviewPanel'], ['editor', '#lpcEditorPanel']].forEach(([panelMode, selector]) => {
    const panel = $(selector);
    if (panel) panel.hidden = panelMode !== dedicatedLpcEditor.activeMode;
  });
  dedicatedLpcRenderEditor();
}

function dedicatedLpcRestartAnimationTimer() {
  clearInterval(dedicatedLpcAnimationTimer);
  dedicatedLpcAnimationTimer = null;
  const data = dedicatedLpcAnimationData;
  const image = dedicatedLpcAnimationImage;
  const frameWidth = Math.max(1, Number(data?.frame_width || 64) || 64);
  const columns = Math.max(1, Number(data?.columns || Math.floor((image?.naturalWidth || frameWidth) / frameWidth) || 1));
  if (!dedicatedLpcAnimationPlaying || columns <= 1) return;
  dedicatedLpcAnimationTimer = setInterval(() => {
    dedicatedLpcAnimationFrame = (dedicatedLpcAnimationFrame + 1) % columns;
    dedicatedLpcDrawFrame();
  }, Math.round(1000 / dedicatedLpcFps()));
}

function dedicatedLpcLoadAnimation(data) {
  dedicatedLpcAnimationData = data;
  dedicatedLpcAnimationFrame = 0;
  clearInterval(dedicatedLpcAnimationTimer);
  const fallback = $('#lpcPreviewImage');
  if (fallback) {
    fallback.src = data.preview_frame_data_uri || data.thumbnail_data_uri || '';
    fallback.alt = data.name || 'Composed LPC character';
  }
  const sheetUrl = dedicatedLpcFreshSheetUrl(data);
  if (!sheetUrl) {
    dedicatedLpcAnimationImage = null;
    dedicatedLpcDrawFrame();
    return;
  }
  const image = new Image();
  dedicatedLpcAnimationImage = image;
  image.onload = () => {
    dedicatedLpcDrawFrame();
    dedicatedLpcRestartAnimationTimer();
  };
  image.src = sheetUrl;
}

function dedicatedLpcFillSelect(select, options) {
  if (!select) return;
  const first = select.options[0]
    ? { value: select.options[0].value, text: select.options[0].textContent || select.options[0].label || 'None' }
    : { value: '', text: 'None' };
  const current = select.value;
  clearNode(select);
  const base = document.createElement('option');
  base.value = first.value || '';
  base.textContent = first.text || 'None';
  select.appendChild(base);
  const query = String(select.dataset.lpcQuery || '').toLowerCase();
  const source = Array.isArray(options) ? options : [];
  let filtered = query
    ? source.filter(option => `${option.value || ''} ${option.label || ''}`.toLowerCase().includes(query))
    : source;
  if (query && !filtered.length) filtered = source;
  const slot = dedicatedLpcCanonicalSlot(select.dataset.lpcSlot);
  if (select.dataset.lpcQuery !== 'heads' && ['body', 'head'].includes(slot)) {
    const raceKey = dedicatedLpcRaceKey();
    filtered = filtered.filter(option => dedicatedLpcRaceCompatible(option, raceKey));
  }
  filtered.forEach(option => {
    const value = String(option.value || option.label || '').trim();
    if (!value) return;
    const item = document.createElement('option');
    item.value = value;
    item.textContent = option.body_type ? `${option.label || value} · ${option.body_type}` : (option.label || value);
    select.appendChild(item);
  });
  if ([...select.options].some(option => option.value === current)) select.value = current;
}

async function loadDedicatedLpcPickers(opts = {}) {
  const sourceDir = $('#lpcSourceDir')?.value || '';
  if (!sourceDir) return;
  if (!opts.silent) dedicatedLpcStatus('Loading LPC picker options...');
  const data = await api('/api/lpc/options', {
    method: 'POST',
    body: JSON.stringify({
      source_dir: sourceDir,
      categories: DEDICATED_LPC_CATEGORIES,
      limit_per_category: 420,
      action: $('#lpcAction')?.value || 'idle',
      body_type: dedicatedLpcBodyType(),
    })
  });
  $$('[data-lpc-slot]', $('#view-lpc')).forEach(select => {
    const slot = dedicatedLpcCanonicalSlot(select.dataset.lpcSlot);
    dedicatedLpcFillSelect(select, data.options?.[slot] || data.options?.[select.dataset.lpcSlot]);
  });
  if (!opts.silent) toast('LPC picker options loaded.');
  dedicatedLpcStatus(`${data.part_count || 0} LPC parts indexed across ${(data.categories || []).length} categories.`);
}

async function refreshDedicatedLpcContext() {
  await loadDedicatedLpcPickers({ silent: true });
  scheduleDedicatedLpcPreview(120);
}

function scheduleDedicatedLpcPreview(delay = 450) {
  if (!$('#view-lpc')) return;
  clearTimeout(dedicatedLpcPreviewTimer);
  dedicatedLpcPreviewTimer = setTimeout(() => {
    composeDedicatedLpcCharacter({ silent: true, reason: 'preview' }).catch(err => {
      dedicatedLpcStatus(err.message || 'Could not refresh LPC preview.');
    });
  }, delay);
}

async function loadDedicatedLpcPalettes() {
  const select = $('#lpcPalette');
  if (!select) return;
  try {
    const data = await api('/api/lpc/palettes');
    const current = select.value || 'default';
    clearNode(select);
    (data.palettes || []).forEach(palette => {
      const option = document.createElement('option');
      option.value = palette.id || 'default';
      option.textContent = palette.label || palette.id || 'Default';
      select.appendChild(option);
    });
    if ([...select.options].some(option => option.value === current)) select.value = current;
  } catch (err) {
    console.warn('Could not load LPC palettes:', err);
  }
}

async function loadDedicatedLpcPresets() {
  const select = $('#lpcPresetSelect');
  if (!select) return;
  try {
    const data = await api('/api/lpc/presets');
    const current = select.value;
    clearNode(select);
    const base = document.createElement('option');
    base.value = '';
    base.textContent = 'Unsaved';
    select.appendChild(base);
    (data.presets || []).forEach(preset => {
      const option = document.createElement('option');
      option.value = preset.id || preset.name || '';
      option.textContent = preset.label || preset.name || preset.id || 'Recipe';
      option.dataset.preset = JSON.stringify(preset);
      select.appendChild(option);
    });
    if ([...select.options].some(option => option.value === current)) select.value = current;
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not load LPC recipes.');
  }
}

function dedicatedLpcSetSelectValue(select, value) {
  if (!select || !value) return false;
  if (![...select.options].some(option => option.value === value)) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  select.value = value;
  return true;
}

function applyDedicatedLpcPreset() {
  const option = $('#lpcPresetSelect')?.selectedOptions?.[0];
  if (!option?.dataset.preset) return;
  const preset = JSON.parse(option.dataset.preset);
  if ($('#lpcAction')) $('#lpcAction').value = preset.action || 'idle';
  if ($('#lpcPalette')) $('#lpcPalette').value = preset.palette || 'default';
  if ($('#lpcCharacterName')) $('#lpcCharacterName').value = preset.label || preset.name || 'lpc_character';
  if ($('#lpcShowBody')) $('#lpcShowBody').checked = preset.include_body !== false;
  const bodyType = preset.body_type || 'male';
  if (['male', 'female'].includes(bodyType)) {
    if ($('#lpcGender')) $('#lpcGender').value = bodyType;
    if ($('#lpcBody')) $('#lpcBody').value = 'regular';
  } else if ($('#lpcBody')) {
    $('#lpcBody').value = bodyType;
  }
  $$('[data-lpc-slot]', $('#view-lpc')).forEach(select => { select.value = ''; });
  const raceSelect = $('[data-lpc-query="heads"]', $('#view-lpc'));
  dedicatedLpcSetSelectValue(raceSelect, 'human');
  const used = new Set();
  (preset.selections || []).forEach(selection => {
    const category = dedicatedLpcCanonicalSlot(selection.category);
    const query = String(selection.query || '').trim();
    if (!category || !query || (category === 'body' && query === 'bodies')) return;
    const candidates = $$('[data-lpc-slot]', $('#view-lpc')).filter(select => {
      if (used.has(select)) return false;
      const slot = dedicatedLpcCanonicalSlot(select.dataset.lpcSlot);
      const hint = String(select.dataset.lpcQuery || '').toLowerCase();
      return slot === category && (!hint || query.toLowerCase().includes(hint) || !selection.query);
    });
    const target = candidates[0] || $$('[data-lpc-slot]', $('#view-lpc')).find(select => !used.has(select) && dedicatedLpcCanonicalSlot(select.dataset.lpcSlot) === category);
    if (target && dedicatedLpcSetSelectValue(target, query)) used.add(target);
  });
  dedicatedLpcStatus(`Recipe loaded: ${preset.label || preset.name || preset.id}.`);
}

function dedicatedLpcSelectionPayload() {
  const selections = [];
  const body = dedicatedLpcBodyType();
  $$('[data-lpc-slot]', $('#view-lpc')).forEach(select => {
    const slot = dedicatedLpcCanonicalSlot(select.dataset.lpcSlot);
    const value = String(select.value || '').trim();
    if (!slot || !value) return;
    if (!$('#lpcShowAddons')?.checked && slot === 'body') return;
    selections.push({ category: slot, query: value });
  });
  return {
    source_dir: $('#lpcSourceDir')?.value || '',
    compose_action: $('#lpcAction')?.value || 'idle',
    action: $('#lpcAction')?.value || 'idle',
    preview_direction: $('#lpcDirection')?.value || 'front',
    body_type: body,
    compose_name: $('#lpcCharacterName')?.value || 'lpc_character',
    include_body: !!$('#lpcShowBody')?.checked,
    palette: dedicatedLpcCurrentPalette(),
    selections,
  };
}

function renderDedicatedLpcRules(data) {
  const panel = $('#lpcRulesPanel');
  if (!panel) return;
  clearNode(panel);
  const issues = data.issues || [];
  if (!issues.length) {
    const row = document.createElement('div');
    row.className = 'lpc-rule-item';
    appendText(row, 'b', `${(data.resolved || []).length} layer choices compatible`);
    appendText(row, 'small', `${data.body_type || 'body'} · ${data.action || 'idle'}`);
    panel.appendChild(row);
    return;
  }
  issues.slice(0, 8).forEach(issue => {
    const row = document.createElement('div');
    row.className = `lpc-rule-item ${issue.severity || ''}`;
    appendText(row, 'b', issue.message || 'LPC rule issue');
    if (issue.suggestion) appendText(row, 'small', issue.suggestion);
    panel.appendChild(row);
  });
}

async function checkDedicatedLpcRules(opts = {}) {
  const payload = dedicatedLpcSelectionPayload();
  if (!payload.source_dir) {
    toast('Choose the Universal LPC folder first.');
    return null;
  }
  if (!opts.silent) dedicatedLpcStatus('Checking LPC layer rules...');
  const data = await api('/api/lpc/rules', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  renderDedicatedLpcRules(data);
  if (!opts.silent) dedicatedLpcStatus(data.ok ? 'LPC selections are compatible.' : 'LPC selections need attention.');
  return data;
}

function dedicatedLpcRenderComposition(data) {
  const empty = $('#lpcPreviewEmpty');
  dedicatedLpcLoadAnimation(data);
  if (empty) empty.style.display = data.preview_frame_data_uri || data.thumbnail_data_uri || data.sheet ? 'none' : '';
  const layers = (data.layers || []).map(layer => `${layer.category}:${layer.variant || layer.relative_path}`).slice(0, 8);
  const missing = (data.missing || []).map(item => `${item.category}:${item.query}`).slice(0, 4);
  dedicatedLpcStatus(`${data.name || 'LPC character'} composed · ${data.action || 'idle'} · ${data.preview_direction || 'front'} · ${data.layers?.length || 0} layers · ${data.frame_count || 0} frames${layers.length ? ' · ' + layers.join(', ') : ''}${missing.length ? ' · Missing: ' + missing.join(', ') : ''}`);
  dedicatedLpcSetZoom($('#lpcZoom')?.value || 3);
}

async function composeDedicatedLpcCharacter(opts = {}) {
  const payload = dedicatedLpcSelectionPayload();
  if (!payload.source_dir) {
    if (!opts.silent) toast('Choose the Universal LPC folder first.');
    return;
  }
  if (dedicatedLpcPreviewBusy) {
    dedicatedLpcQueuedPreview = true;
    return;
  }
  dedicatedLpcPreviewBusy = true;
  dedicatedLpcStatus(opts.silent ? 'Refreshing LPC preview...' : 'Composing LPC character...');
  try {
    const data = await api('/api/lpc/compose', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    dedicatedLpcRenderComposition(data);
    if (data.rules) renderDedicatedLpcRules(data.rules);
    if (!opts.silent) toast('LPC character composed.');
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not compose LPC character.');
    if (!opts.silent) toast(err.message || 'Could not compose LPC character.');
  } finally {
    dedicatedLpcPreviewBusy = false;
    if (dedicatedLpcQueuedPreview) {
      dedicatedLpcQueuedPreview = false;
      scheduleDedicatedLpcPreview(120);
    }
  }
}

function renderDedicatedLpcBatchGallery(data) {
  const gallery = $('#lpcBatchGallery');
  if (!gallery) return;
  clearNode(gallery);
  (data.samples || []).slice(0, 12).forEach(sample => {
    const card = document.createElement('article');
    card.className = 'lpc-sample-card';
    if (sample.thumbnail_data_uri) {
      const img = document.createElement('img');
      img.src = sample.thumbnail_data_uri;
      img.alt = sample.name || 'LPC sample';
      card.appendChild(img);
    }
    appendText(card, 'b', sample.name || 'sample');
    appendText(card, 'small', `${sample.body_type || ''} ${sample.action || ''}`.trim() || `${sample.layers || 0} layers`);
    gallery.appendChild(card);
  });
}

function dedicatedLpcBatchCategories() {
  const picked = new Set();
  $$('[data-lpc-slot]', $('#view-lpc')).forEach(select => {
    const slot = dedicatedLpcCanonicalSlot(select.dataset.lpcSlot);
    if (slot && slot !== 'body') picked.add(slot);
  });
  return [...picked].filter(category => ['hair', 'torso', 'legs', 'feet', 'weapon', 'hat', 'arms', 'shield', 'backpack', 'quiver', 'cape', 'shoulders', 'neck', 'dress'].includes(category));
}

function dedicatedLpcSetBatchState(datasetDir, qaOk = false) {
  ['#lpcRunQa', '#lpcPrepareLora'].forEach(id => {
    const btn = $(id);
    if (!btn) return;
    btn.dataset.datasetDir = datasetDir || '';
    btn.dataset.qaOk = qaOk ? 'true' : 'false';
  });
  const qa = $('#lpcRunQa');
  if (qa) qa.disabled = !datasetDir;
  const lora = $('#lpcPrepareLora');
  if (lora) lora.disabled = !datasetDir || !qaOk;
}

async function buildDedicatedLpcBatch() {
  const payload = dedicatedLpcSelectionPayload();
  if (!payload.source_dir) {
    toast('Choose the Universal LPC folder first.');
    return;
  }
  dedicatedLpcStatus('Building LPC composed training batch...');
  try {
    const data = await api('/api/lpc/batch-compose', {
      method: 'POST',
      body: JSON.stringify({
        source_dir: payload.source_dir,
        batch_count: Math.max(1, Math.min(1000, Number($('#lpcBatchCount')?.value || 48))),
        batch_action: payload.action,
        batch_actions: 'idle,walk,slash,cast',
        body_type: payload.body_type,
        batch_body_types: 'male,female',
        batch_categories: dedicatedLpcBatchCategories(),
        palette: dedicatedLpcCurrentPalette(),
        trigger: 'lpc_composed',
      })
    });
    dedicatedLpcSetBatchState(data.output_dir || '', false);
    renderDedicatedLpcBatchGallery(data);
    const sample = (data.samples || [])[0];
    if (sample?.thumbnail_data_uri) {
      const img = $('#lpcPreviewImage');
      const empty = $('#lpcPreviewEmpty');
      if (img) img.src = sample.thumbnail_data_uri;
      if (empty) empty.style.display = 'none';
    }
    dedicatedLpcStatus(`${data.sample_count || 0} LPC training samples built · ${data.output_dir || ''}`);
    toast('LPC batch dataset ready.');
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not build LPC batch.');
    toast(err.message || 'Could not build LPC batch.');
  }
}

async function refreshDedicatedLpcBatchPreview(datasetDir) {
  if (!datasetDir) return;
  try {
    const data = await api('/api/lpc/dataset-preview', {
      method: 'POST',
      body: JSON.stringify({ dataset_dir: datasetDir, limit: 12 })
    });
    renderDedicatedLpcBatchGallery(data);
  } catch (err) {
    console.warn('Could not refresh LPC batch preview:', err);
  }
}

async function qaDedicatedLpcBatch() {
  const btn = $('#lpcRunQa');
  const datasetDir = btn?.dataset.datasetDir || '';
  if (!datasetDir) {
    toast('Build an LPC batch first.');
    return;
  }
  dedicatedLpcStatus('Running LPC dataset QA...');
  try {
    const data = await api('/api/lpc/dataset-qa', {
      method: 'POST',
      body: JSON.stringify({ dataset_dir: datasetDir, min_layers: 3 })
    });
    dedicatedLpcSetBatchState(data.dataset_dir || datasetDir, !!data.ok);
    await refreshDedicatedLpcBatchPreview(data.dataset_dir || datasetDir);
    const issueText = (data.issues || []).slice(0, 3).map(issue => `${issue.severity}: ${issue.message}`).join(' · ');
    dedicatedLpcStatus(`${data.ok ? 'QA passed' : 'QA needs attention'} · ${data.sample_count || 0} samples · ${data.image_count || 0} images${issueText ? ' · ' + issueText : ''}`);
    toast(data.ok ? 'LPC dataset QA passed.' : 'LPC dataset QA found issues.');
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Dataset QA failed.');
    toast(err.message || 'Dataset QA failed.');
  }
}

async function saveDedicatedLpcPreset() {
  const payload = dedicatedLpcSelectionPayload();
  const name = $('#lpcCharacterName')?.value || 'lpc_character';
  try {
    const data = await api('/api/lpc/presets', {
      method: 'POST',
      body: JSON.stringify({ ...payload, name, label: name })
    });
    await loadDedicatedLpcPresets();
    if ($('#lpcPresetSelect')) $('#lpcPresetSelect').value = data.preset?.id || '';
    dedicatedLpcStatus(`Recipe saved: ${data.preset?.label || name}.`);
    toast('LPC recipe saved.');
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not save LPC recipe.');
    toast(err.message || 'Could not save LPC recipe.');
  }
}

async function deleteDedicatedLpcPreset() {
  const id = $('#lpcPresetSelect')?.value || '';
  if (!id) {
    toast('Choose a saved recipe first.');
    return;
  }
  try {
    await api('/api/lpc/presets/delete', {
      method: 'POST',
      body: JSON.stringify({ id })
    });
    await loadDedicatedLpcPresets();
    dedicatedLpcStatus('Recipe deleted.');
    toast('LPC recipe deleted.');
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not delete LPC recipe.');
    toast(err.message || 'Could not delete LPC recipe.');
  }
}

async function prepareDedicatedLpcLora() {
  const btn = $('#lpcPrepareLora');
  const datasetDir = btn?.dataset.datasetDir || '';
  if (!datasetDir || btn?.dataset.qaOk !== 'true') {
    toast('Run Dataset QA first.');
    return;
  }
  try {
    const prefill = await lpcLoraPrefill(datasetDir);
    const rec = applyLpcLoraPrefill(prefill, datasetDir);
    dedicatedLpcStatus(prefill.summary || 'LPC LoRA defaults prepared.');
    await runAction('lora_training', { ...rec, mode: 'prepare' });
  } catch (err) {
    dedicatedLpcStatus(err.message || 'Could not prepare LPC LoRA.');
    toast(err.message || 'Could not prepare LPC LoRA.');
  }
}

function initDedicatedLpcTab() {
  if (!$('#view-lpc')) return;
  $('#lpcLoadPickers')?.addEventListener('click', () => loadDedicatedLpcPickers().catch(err => {
    dedicatedLpcStatus(err.message || 'Could not load LPC pickers.');
    toast(err.message || 'Could not load LPC pickers.');
  }));
  $('#lpcPresetSelect')?.addEventListener('change', applyDedicatedLpcPreset);
  $('#lpcSavePreset')?.addEventListener('click', saveDedicatedLpcPreset);
  $('#lpcDeletePreset')?.addEventListener('click', deleteDedicatedLpcPreset);
  $('#lpcCheckRules')?.addEventListener('click', () => checkDedicatedLpcRules().catch(err => {
    dedicatedLpcStatus(err.message || 'Could not check LPC rules.');
    toast(err.message || 'Could not check LPC rules.');
  }));
  $('#lpcComposeCharacter')?.addEventListener('click', () => composeDedicatedLpcCharacter());
  $('#lpcBuildBatch')?.addEventListener('click', buildDedicatedLpcBatch);
  $('#lpcRunQa')?.addEventListener('click', qaDedicatedLpcBatch);
  $('#lpcPrepareLora')?.addEventListener('click', prepareDedicatedLpcLora);
  $$('.lpc-mode-tab', $('#view-lpc')).forEach(button => {
    button.addEventListener('click', () => dedicatedLpcSetMode(button.dataset.lpcMode));
  });
  $('#lpcEditorAddLayer')?.addEventListener('click', dedicatedLpcAddEditorLayer);
  $('#lpcEditorClearLayer')?.addEventListener('click', dedicatedLpcClearEditorLayer);
  $('#lpcEditorBake')?.addEventListener('click', dedicatedLpcBakeEditorLayers);
  $('#lpcEditorDownloadFrame')?.addEventListener('click', dedicatedLpcDownloadEditorFrame);
  ['#lpcEditorTool', '#lpcEditorColor', '#lpcEditorSize', '#lpcEditorMirror', '#lpcEditorApplyDirections'].forEach(selector => {
    $(selector)?.addEventListener('input', dedicatedLpcRenderEditor);
    $(selector)?.addEventListener('change', dedicatedLpcRenderEditor);
  });
  $('#lpcEditorCanvas')?.addEventListener('pointerdown', dedicatedLpcBeginEditorStroke);
  $('#lpcEditorCanvas')?.addEventListener('pointermove', dedicatedLpcMoveEditorStroke);
  $('.lpc-stage', $('#view-lpc'))?.addEventListener('pointerdown', dedicatedLpcBeginEditorStroke, true);
  $('.lpc-stage', $('#view-lpc'))?.addEventListener('pointermove', dedicatedLpcMoveEditorStroke, true);
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => {
    $('#lpcEditorCanvas')?.addEventListener(type, dedicatedLpcEndEditorStroke);
    $('.lpc-stage', $('#view-lpc'))?.addEventListener(type, dedicatedLpcEndEditorStroke, true);
  });
  [
    '#lpcGender',
    '#lpcBody',
    '#lpcAction',
    '[data-lpc-query="heads"]',
  ].forEach(selector => $(selector, $('#view-lpc'))?.addEventListener('change', () => {
    refreshDedicatedLpcContext().catch(err => dedicatedLpcStatus(err.message || 'Could not refresh LPC pickers.'));
  }));
  [
    '#lpcDirection',
    '#lpcPalette',
    '#lpcShowBody',
    '#lpcShowAddons',
    '#lpcCastShadow',
  ].forEach(selector => $(selector)?.addEventListener('change', () => scheduleDedicatedLpcPreview()));
  $$('[data-lpc-slot]', $('#view-lpc')).forEach(select => {
    select.addEventListener('change', () => scheduleDedicatedLpcPreview());
  });
  $('#lpcZoom')?.addEventListener('input', event => dedicatedLpcSetZoom(event.currentTarget.value));
  $('#lpcZoomOut')?.addEventListener('click', () => dedicatedLpcSetZoom(Number($('#lpcZoom')?.value || 3) - 0.25));
  $('#lpcZoomIn')?.addEventListener('click', () => dedicatedLpcSetZoom(Number($('#lpcZoom')?.value || 3) + 0.25));
  $('#lpcPlayPause')?.addEventListener('click', () => dedicatedLpcSetPlaying(!dedicatedLpcAnimationPlaying));
  $('#lpcFps')?.addEventListener('input', event => {
    const label = $('#lpcFpsLabel');
    if (label) label.textContent = `${dedicatedLpcFps()} fps`;
    dedicatedLpcRestartAnimationTimer();
  });
  $('#lpcResetView')?.addEventListener('click', () => {
    dedicatedLpcPreviewPan = { x: 0, y: 0 };
    dedicatedLpcSetZoom(3);
  });
  $('#lpcPreviewWindow')?.addEventListener('wheel', event => {
    event.preventDefault();
    dedicatedLpcSetZoom(Number($('#lpcZoom')?.value || 3) + (event.deltaY < 0 ? 0.25 : -0.25));
  }, { passive: false });
  $('#lpcPreviewWindow')?.addEventListener('pointerdown', event => {
    const target = $('#lpcPreviewWindow');
    if (!target) return;
    target.classList.add('dragging');
    target.setPointerCapture?.(event.pointerId);
    dedicatedLpcPreviewDrag = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      panX: dedicatedLpcPreviewPan.x,
      panY: dedicatedLpcPreviewPan.y,
    };
  });
  $('#lpcPreviewWindow')?.addEventListener('pointermove', event => {
    if (!dedicatedLpcPreviewDrag || dedicatedLpcPreviewDrag.pointerId !== event.pointerId) return;
    dedicatedLpcPreviewPan = {
      x: dedicatedLpcPreviewDrag.panX + event.clientX - dedicatedLpcPreviewDrag.x,
      y: dedicatedLpcPreviewDrag.panY + event.clientY - dedicatedLpcPreviewDrag.y,
    };
    dedicatedLpcApplyPreviewTransform();
  });
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => {
    $('#lpcPreviewWindow')?.addEventListener(type, event => {
      if (dedicatedLpcPreviewDrag && event.pointerId && dedicatedLpcPreviewDrag.pointerId !== event.pointerId) return;
      dedicatedLpcPreviewDrag = null;
      $('#lpcPreviewWindow')?.classList.remove('dragging');
    });
  });
  dedicatedLpcSetZoom($('#lpcZoom')?.value || 3);
  dedicatedLpcRenderLayerList();
  dedicatedLpcSetMode('preview');
  loadDedicatedLpcPalettes();
  loadDedicatedLpcPresets();
  loadDedicatedLpcPickers({ silent: true })
    .then(() => {
      if (dedicatedLpcInitialPreviewDone) return null;
      dedicatedLpcInitialPreviewDone = true;
      return composeDedicatedLpcCharacter({ silent: true, reason: 'initial' });
    })
    .catch(() => dedicatedLpcStatus('Ready. Load pickers when the LPC folder is available.'));
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
  if ($('#refreshProviderKeys')) $('#refreshProviderKeys').addEventListener('click', loadProviderKeysPanel);
  if ($('#providerKeyGrid')) {
    loadProviderKeysPanel();
    $('#providerKeyGrid').addEventListener('click', event => {
      const save = event.target.closest('[data-save-provider-key]');
      const remove = event.target.closest('[data-remove-provider-key]');
      if (save) saveProviderKey(save.dataset.saveProviderKey).catch(err => toast(err.message));
      if (remove) removeProviderKey(remove.dataset.removeProviderKey).catch(err => toast(err.message));
    });
  }

  // Generation form
  if ($('#generateForm')) $('#generateForm').addEventListener('submit',e=>{ e.preventDefault(); syncGenerateChoices(); runAction('generate_sprite', formData(e.currentTarget)); showView('logs'); });
  if ($('#generateForm')) {
    loadGenerateActionChoices();
    $('#generateForm').addEventListener('change', event => {
      if (event.target.matches('[data-generate-action], [data-generate-direction], [data-generate-direction-all], [name="default_actions_text"], [name="default_directions_text"]')) {
        syncGenerateChoices();
      }
    });
    $('#generateForm').addEventListener('input', refreshGeneratePromptPreview);
    $('#generateForm').addEventListener('change', refreshGeneratePromptPreview);
    $('#generationReferenceImage')?.addEventListener('input', refreshGenerateReferencePreview);
    $('#generationStyleImage')?.addEventListener('input', refreshGenerateReferencePreview);
    $('#generationReferenceImage')?.addEventListener('change', refreshGenerateReferencePreview);
    $('#generationStyleImage')?.addEventListener('change', refreshGenerateReferencePreview);
    $('#btnAutoFixPrompt')?.addEventListener('click', event => applyGeneratePromptAutofix(event));
    refreshGenerateReferencePreview();
    syncGenerateChoiceChecksFromHidden();
    refreshGeneratePromptPreview();
  }
  if ($('#btnPreviewGenerate')) {
    $('#btnPreviewGenerate').addEventListener('click', () => {
      syncGenerateChoices();
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
  if ($('#scanLpcParts')) $('#scanLpcParts').addEventListener('click', scanLpcParts);
  if ($('#buildLpcPartDataset')) $('#buildLpcPartDataset').addEventListener('click', buildLpcPartDataset);
  if ($('#loadLpcComposerOptions')) $('#loadLpcComposerOptions').addEventListener('click', loadLpcComposerOptions);
  if ($('#composeLpcCharacter')) $('#composeLpcCharacter').addEventListener('click', composeLpcCharacter);
  if ($('#composeLpcBatch')) $('#composeLpcBatch').addEventListener('click', composeLpcBatch);
  if ($('#qaLpcBatch')) $('#qaLpcBatch').addEventListener('click', qaLpcBatch);
  if ($('#useLpcBatchForLora')) $('#useLpcBatchForLora').addEventListener('click', useLpcBatchForLora);
  if ($('#prepareLpcLoraRun')) $('#prepareLpcLoraRun').addEventListener('click', prepareLpcLoraRun);
  if ($('#lpcComposerForm')) loadLpcComposerOptions({ silent: true }).catch(() => {});
  initDedicatedLpcTab();
  if ($('#tileTrainingDatasetForm')) $('#tileTrainingDatasetForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('tile_training_dataset', formData(e.currentTarget)); showView('logs'); });
  if ($('#tilemapGeneratorForm')) $('#tilemapGeneratorForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('tilemap', formData(e.currentTarget)); showView('logs'); });
  $$('[data-lora-mode]').forEach(btn=>btn.addEventListener('click',()=>{
    const form = $('#loraTrainingForm');
    if (!form) return;
    runAction('lora_training', { ...formData(form), mode: btn.dataset.loraMode || 'prepare' });
    showView('logs');
  }));
  if ($('#refreshLoraProgress')) $('#refreshLoraProgress').addEventListener('click', refreshLoraProgress);
  if ($('#registerLoraCheckpoint')) $('#registerLoraCheckpoint').addEventListener('click', registerLoraCheckpoint);
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

function renderLpcPartsResult(data, mode) {
  const target = $('#lpcPartsPreview');
  if (!target) return;
  clearNode(target);
  if (mode === 'dataset') {
    appendText(target, 'b', `${data.sample_count || 0} LPC part samples written`);
    appendText(target, 'small', `Dataset: ${data.output_dir || 'output/training_datasets'} · trigger ${data.trigger || 'lpc_parts'}`);
  } else {
    appendText(target, 'b', `${data.part_count || 0} LPC parts indexed`);
    appendText(target, 'small', `Catalog: ${data.output_dir || 'output/lpc_parts'} · source ${data.spritesheets_dir || data.source_dir || ''}`);
    if (data.readable_part_count || data.unreadable_part_count) appendText(target, 'small', `Preview sample readable ${data.readable_part_count || 0} · unreadable ${data.unreadable_part_count || 0}`);
  }
  const categories = Object.entries(data.category_counts || {}).slice(0, 8).map(([key, count]) => `${key} (${count})`);
  const actions = Object.entries(data.action_counts || {}).slice(0, 8).map(([key, count]) => `${key} (${count})`);
  const bodyTypes = Object.entries(data.body_type_counts || {}).slice(0, 8).map(([key, count]) => `${key} (${count})`);
  if (categories.length) appendText(target, 'small', `Categories: ${categories.join(', ')}`);
  if (actions.length) appendText(target, 'small', `Actions: ${actions.join(', ')}`);
  if (bodyTypes.length) appendText(target, 'small', `Bodies: ${bodyTypes.join(', ')}`);
  (data.samples || []).slice(0, 6).forEach(part => {
    const row = document.createElement('div');
    row.className = 'training-dataset-preview-row lpc-part-preview-row';
    if (part.thumbnail_data_uri) {
      const img = document.createElement('img');
      img.src = part.thumbnail_data_uri;
      img.alt = part.variant || part.category || 'LPC part';
      row.appendChild(img);
    }
    appendText(row, 'b', `${part.category || 'part'} · ${part.variant || 'variant'}`);
    appendText(row, 'span', `${part.action || 'action'}${part.body_type ? ' · ' + part.body_type : ''}${part.layer_phase ? ' · ' + part.layer_phase : ''}`);
    appendText(row, 'small', `${part.relative_path || part.path || ''}`);
    target.appendChild(row);
  });
}

async function scanLpcParts() {
  const form = $('#lpcPartsForm');
  const target = $('#lpcPartsPreview');
  if (!form) return;
  const payload = formData(form);
  if (!payload.source_dir) {
    toast('Choose the Universal LPC folder first.');
    return;
  }
  if (target) target.textContent = 'Scanning LPC paper-doll parts...';
  try {
    const data = await api('/api/lpc/parts/scan', {
      method: 'POST',
      body: JSON.stringify({ ...payload, thumbnail_limit: 24 })
    });
    renderLpcPartsResult(data, 'scan');
    toast('LPC parts catalog ready.');
  } catch (err) {
    if (target) target.textContent = err.message || 'Could not scan LPC parts.';
    toast(err.message || 'Could not scan LPC parts.');
  }
}

async function buildLpcPartDataset() {
  const form = $('#lpcPartsForm');
  const target = $('#lpcPartsPreview');
  if (!form) return;
  const payload = formData(form);
  if (!payload.source_dir) {
    toast('Choose the Universal LPC folder first.');
    return;
  }
  if (target) target.textContent = 'Building LPC part dataset...';
  try {
    const data = await api('/api/lpc/parts/dataset', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    renderLpcPartsResult(data, 'dataset');
    toast('LPC part dataset ready.');
  } catch (err) {
    if (target) target.textContent = err.message || 'Could not build LPC part dataset.';
    toast(err.message || 'Could not build LPC part dataset.');
  }
}

function fillLpcDatalist(id, options) {
  const list = $(id);
  if (!list) return;
  clearNode(list);
  (options || []).forEach(option => {
    const item = document.createElement('option');
    item.value = option.value || option.label || '';
    item.label = option.body_type ? `${option.label} · ${option.body_type}` : (option.label || option.value || '');
    list.appendChild(item);
  });
}

async function loadLpcComposerOptions(opts = {}) {
  const form = $('#lpcComposerForm');
  const target = $('#lpcComposerPreview');
  if (!form) return;
  const payload = formData(form);
  if (!payload.source_dir) return;
  if (!opts.silent && target) target.textContent = 'Loading LPC picker options...';
  const data = await api('/api/lpc/options', {
    method: 'POST',
    body: JSON.stringify({
      source_dir: payload.source_dir,
      categories: ['hair', 'torso', 'legs', 'feet', 'weapons'],
      limit_per_category: 320,
    })
  });
  fillLpcDatalist('#lpcHairOptions', data.options?.hair);
  fillLpcDatalist('#lpcTorsoOptions', data.options?.torso);
  fillLpcDatalist('#lpcLegsOptions', data.options?.legs);
  fillLpcDatalist('#lpcFeetOptions', data.options?.feet);
  fillLpcDatalist('#lpcWeaponsOptions', data.options?.weapons);
  if (!opts.silent && target) {
    clearNode(target);
    appendText(target, 'b', 'LPC pickers loaded');
    appendText(target, 'small', `${data.part_count || 0} indexed parts · ${Object.keys(data.options || {}).length} picker groups`);
  }
  if (!opts.silent) toast('LPC picker options loaded.');
}

function lpcComposerPayload(form) {
  const payload = formData(form);
  const selections = {};
  [
    ['hair', payload.part_hair],
    ['torso', payload.part_torso],
    ['legs', payload.part_legs],
    ['feet', payload.part_feet],
    ['weapons', payload.part_weapons],
  ].forEach(([category, value]) => {
    const text = String(value || '').trim();
    if (text) selections[category] = text;
  });
  String(payload.parts || '').split(';').forEach(item => {
    const text = item.trim();
    if (!text) return;
    const sep = text.includes(':') ? ':' : '=';
    if (!text.includes(sep)) return;
    const [category, ...rest] = text.split(sep);
    const key = String(category || '').trim();
    const value = rest.join(sep).trim();
    if (key && value) selections[key] = value;
  });
  return { ...payload, selections };
}

function renderLpcComposition(data) {
  const target = $('#lpcComposerPreview');
  if (!target) return;
  clearNode(target);
  appendText(target, 'b', `${data.name || 'LPC character'} composed`);
  appendText(target, 'small', `${data.action || 'idle'} · ${data.body_type || 'body'} · ${data.layers?.length || 0} layer${data.layers?.length === 1 ? '' : 's'} · ${data.frame_count || 0} frames`);
  if (data.thumbnail_data_uri) {
    const img = document.createElement('img');
    img.src = data.thumbnail_data_uri;
    img.alt = data.name || 'Composed LPC character';
    img.className = 'lpc-composer-preview-image';
    target.appendChild(img);
  }
  if (data.sheet) {
    const link = document.createElement('a');
    link.className = 'mini link-button';
    link.href = '/file/' + data.sheet;
    link.textContent = 'Open Sheet';
    target.appendChild(link);
  }
  if (data.output_dir) appendText(target, 'small', `Output: ${data.output_dir}`);
  const layers = (data.layers || []).map(layer => `${layer.category}:${layer.variant || layer.relative_path}`).slice(0, 10);
  if (layers.length) appendText(target, 'small', `Layers: ${layers.join(', ')}`);
  const missing = (data.missing || []).map(item => `${item.category}:${item.query}`);
  if (missing.length) appendText(target, 'small', `Missing: ${missing.join(', ')}`);
}

async function composeLpcCharacter() {
  const form = $('#lpcComposerForm');
  const target = $('#lpcComposerPreview');
  if (!form) return;
  const payload = lpcComposerPayload(form);
  if (!payload.source_dir) {
    toast('Choose the Universal LPC folder first.');
    return;
  }
  if (target) target.textContent = 'Composing LPC character...';
  try {
    const data = await api('/api/lpc/compose', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    renderLpcComposition(data);
    toast('LPC character composed.');
  } catch (err) {
    if (target) target.textContent = err.message || 'Could not compose LPC character.';
    toast(err.message || 'Could not compose LPC character.');
  }
}

function renderLpcBatch(data) {
  const target = $('#lpcBatchPreview');
  if (!target) return;
  clearNode(target);
  appendText(target, 'b', `${data.sample_count || 0} composed LPC training sample${data.sample_count === 1 ? '' : 's'}`);
  const actions = (data.actions || [data.action || 'idle']).join(', ');
  const bodies = (data.body_types || [data.body_type || 'body']).join(', ');
  appendText(target, 'small', `${bodies} · ${actions} · ${data.output_dir || ''}`);
  const balance = Object.entries(data.balance || {}).map(([slot, count]) => `${slot} (${count})`);
  if (balance.length) appendText(target, 'small', `Balance: ${balance.join(', ')}`);
  const useBtn = $('#useLpcBatchForLora');
  if (useBtn) {
    useBtn.disabled = true;
    useBtn.dataset.datasetDir = data.output_dir || '';
    useBtn.dataset.qaOk = 'false';
  }
  const prepareBtn = $('#prepareLpcLoraRun');
  if (prepareBtn) {
    prepareBtn.disabled = true;
    prepareBtn.dataset.datasetDir = data.output_dir || '';
    prepareBtn.dataset.qaOk = 'false';
  }
  const qaBtn = $('#qaLpcBatch');
  if (qaBtn) {
    qaBtn.disabled = !data.output_dir;
    qaBtn.dataset.datasetDir = data.output_dir || '';
  }
  (data.samples || []).slice(0, 4).forEach(sample => {
    const row = document.createElement('div');
    row.className = 'training-dataset-preview-row';
    if (sample.thumbnail_data_uri) {
      const img = document.createElement('img');
      img.src = sample.thumbnail_data_uri;
      img.alt = sample.name || 'LPC batch sample';
      row.appendChild(img);
    }
    appendText(row, 'b', sample.name || 'sample');
    appendText(row, 'span', sample.caption || '');
    appendText(row, 'small', sample.output_dir || '');
    target.appendChild(row);
  });
  if ((data.failures || []).length) appendText(target, 'small', `Skipped: ${data.failures.length}`);
}

function renderLpcQa(data) {
  const target = $('#lpcBatchPreview');
  if (!target) return;
  appendText(target, 'b', data.ok ? 'Dataset QA passed' : 'Dataset QA needs attention');
  appendText(target, 'small', `${data.sample_count || 0} samples · ${data.image_count || 0} images · ${data.caption_count || 0} captions · balance delta ${data.balance_delta ?? 'n/a'}`);
  (data.issues || []).forEach(issue => {
    appendText(target, 'small', `${String(issue.severity || 'info').toUpperCase()}: ${issue.message || ''}`);
  });
  if (data.caption_preview && data.caption_preview.length) {
    appendText(target, 'small', `Caption: ${data.caption_preview[0].caption || ''}`);
  }
  const useBtn = $('#useLpcBatchForLora');
  if (useBtn) {
    useBtn.disabled = !data.ok;
    useBtn.dataset.qaOk = data.ok ? 'true' : 'false';
    useBtn.dataset.datasetDir = data.dataset_dir || useBtn.dataset.datasetDir || '';
  }
  const prepareBtn = $('#prepareLpcLoraRun');
  if (prepareBtn) {
    prepareBtn.disabled = !data.ok;
    prepareBtn.dataset.qaOk = data.ok ? 'true' : 'false';
    prepareBtn.dataset.datasetDir = data.dataset_dir || prepareBtn.dataset.datasetDir || '';
  }
}

function lpcBatchButtonState(buttonId) {
  const btn = $(buttonId);
  const datasetDir = btn?.dataset.datasetDir || '';
  if (!datasetDir) {
    toast('Build an LPC batch first.');
    return null;
  }
  if (btn?.dataset.qaOk !== 'true') {
    toast('Run Dataset QA first.');
    return null;
  }
  return { btn, datasetDir };
}

async function lpcLoraPrefill(datasetDir) {
  return api('/api/lpc/lora-prefill', {
    method: 'POST',
    body: JSON.stringify({ dataset_dir: datasetDir })
  });
}

function applyLpcLoraPrefill(prefill, datasetDir) {
  const form = $('#loraTrainingForm');
  const rec = prefill?.recommendation || { dataset_dir: datasetDir, name: 'lpc_composed_lora', trigger: 'lpc_composed' };
  [
    ['dataset_dir', rec.dataset_dir],
    ['name', rec.name],
    ['trigger', rec.trigger],
    ['model_family', rec.model_family],
    ['trainer', rec.trainer],
    ['resolution', rec.resolution],
    ['max_train_steps', rec.max_train_steps],
    ['learning_rate', rec.learning_rate],
    ['network_dim', rec.network_dim],
    ['repeats', rec.repeats],
  ].forEach(([field, value]) => {
    const input = form?.querySelector(`[name="${field}"]`);
    if (input && value !== undefined && value !== null) input.value = String(value);
  });
  const hint = $('#loraGpuDefaultsHint');
  if (hint && prefill) {
    hint.textContent = `${prefill.summary || 'LPC LoRA defaults applied.'}${(prefill.warnings || []).length ? ' Warning: ' + prefill.warnings.join(' ') : ''}`;
  }
  return rec;
}

async function useLpcBatchForLora() {
  const state = lpcBatchButtonState('#useLpcBatchForLora');
  if (!state) return;
  let prefill = null;
  try {
    prefill = await lpcLoraPrefill(state.datasetDir);
  } catch (err) {
    toast(err.message || 'Could not build LPC LoRA defaults.');
  }
  applyLpcLoraPrefill(prefill, state.datasetDir);
  const tab = $('#view-training [data-training-tab="lora"]');
  if (tab) tab.click();
  toast('LPC LoRA settings applied.');
}

async function prepareLpcLoraRun() {
  const state = lpcBatchButtonState('#prepareLpcLoraRun');
  if (!state) return;
  let prefill = null;
  try {
    prefill = await lpcLoraPrefill(state.datasetDir);
  } catch (err) {
    toast(err.message || 'Could not build LPC LoRA defaults.');
    return;
  }
  const rec = applyLpcLoraPrefill(prefill, state.datasetDir);
  await runAction('lora_training', { ...rec, mode: 'prepare' });
}

async function qaLpcBatch() {
  const form = $('#lpcBatchComposerForm');
  const target = $('#lpcBatchPreview');
  const btn = $('#qaLpcBatch');
  const datasetDir = btn?.dataset.datasetDir || '';
  if (!form || !datasetDir) {
    toast('Build an LPC batch first.');
    return;
  }
  const payload = formData(form);
  if (target) appendText(target, 'small', 'Running Dataset QA...');
  try {
    const data = await api('/api/lpc/dataset-qa', {
      method: 'POST',
      body: JSON.stringify({
        dataset_dir: datasetDir,
        min_layers: payload.min_layers || 3,
      })
    });
    renderLpcQa(data);
    toast(data.ok ? 'LPC dataset QA passed.' : 'LPC dataset QA found issues.');
  } catch (err) {
    if (target) appendText(target, 'small', err.message || 'Dataset QA failed.');
    toast(err.message || 'Dataset QA failed.');
  }
}

async function composeLpcBatch() {
  const form = $('#lpcBatchComposerForm');
  const target = $('#lpcBatchPreview');
  if (!form) return;
  const payload = formData(form);
  if (!payload.source_dir) {
    toast('Choose the Universal LPC folder first.');
    return;
  }
  if (target) target.textContent = 'Building LPC composed batch...';
  try {
    const data = await api('/api/lpc/batch-compose', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    renderLpcBatch(data);
    toast('LPC batch dataset ready.');
  } catch (err) {
    if (target) target.textContent = err.message || 'Could not build LPC batch.';
    toast(err.message || 'Could not build LPC batch.');
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

async function registerLoraCheckpoint() {
  const input = $('#loraProgressPath');
  const summary = $('#loraProgressSummary');
  const path = String(input?.value || '').trim();
  if (!path) {
    toast('Enter a training run folder.');
    return;
  }
  if (summary) summary.textContent = 'Registering latest checkpoint...';
  try {
    const data = await api('/api/lora/register-checkpoint', {
      method: 'POST',
      body: JSON.stringify({
        run_path: path,
        make_default: true,
      }),
    });
    if (summary) {
      summary.textContent = `Registered ${data.filename} as ${data.role}${data.default ? ' default' : ''}.`;
    }
    toast('LoRA checkpoint registered.');
    await refreshLoraProgress();
  } catch (err) {
    if (summary) summary.textContent = err.message || 'Could not register LoRA checkpoint.';
    toast(err.message || 'Could not register LoRA checkpoint.');
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
