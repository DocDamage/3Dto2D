let currentPresets = {};

async function loadPresets() {
  try {
    const res = await api('/api/presets');
    currentPresets = res.presets || {};
    const select = $('#presetSelect');
    if (!select) return;
    
    clearNode(select);
    const defOpt = document.createElement('option');
    defOpt.value = '';
    defOpt.textContent = '-- Select Preset --';
    select.appendChild(defOpt);
    
    Object.keys(currentPresets).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    });
  } catch(e) {
    console.error('Failed to load presets:', e);
  }
}

// Preset Advisor quality options
const GOAL_DEFAULTS = {
  'pixel_art': {
    style: 'crisp pixel art, retro 8-bit game sprite style, clean silhouette, locked camera',
    fps: 8,
    cell_size: '256x256',
    negative: 'motion blur, vector, smooth, gradient, 3d render, camera zoom'
  },
  'smooth_2d': {
    style: 'clean vector smooth 2D sprite illustration, crisp edges, locked camera',
    fps: 12,
    cell_size: '512x512',
    negative: 'pixelated, noisy, dithering, photorealistic, camera zoom'
  },
  'side_scroller': {
    style: 'polished 2D side-scroller sprite, professional character design, readable side profile silhouette, locked camera',
    fps: 12,
    cell_size: '512x512',
    negative: 'top-down view, perspective tilt, camera zoom, background details'
  },
  'top_down': {
    style: 'polished top-down RPG sprite, professional character design, readable small-scale silhouette, locked orthographic camera',
    fps: 12,
    cell_size: '512x512',
    negative: 'side-view, platformer view, perspective, rotation, camera zoom'
  },
  'isometric': {
    style: 'polished 2D isometric game sprite, professional character design, crisp silhouette, consistent outfit, isometric angle projection',
    fps: 12,
    cell_size: '512x512',
    negative: 'camera movement, zoom, cuts, rotation, perspective tilt, 3D orthographic view, black borders, childlike drawing, amateur doodle, crude sketch, bad anatomy, muddy colors'
  },
  'local_fast': {
    tier: 'wan21_safe',
    profile: 'sprite_fast',
    fps: 12,
    cell_size: '512x512'
  },
  'local_quality': {
    tier: 'wan22_5b',
    profile: 'wan22_5b_3060_best',
    fps: 12,
    cell_size: '512x512'
  }
};

const TILE_TRAINING_PRESETS = {
  top_down_terrain: {
    trigger: 'sakpix_tiles_terrain',
    cell_size: 'auto',
    max_samples_per_source: '32',
    include_all: false,
    base_caption: 'trained SakPix top-down terrain auto-tile, grass, dirt, stone path, edge and corner pieces',
    manifest: 'Terrain preset: prioritizes floors, paths, cliffs, bridges, and ground sheets for a focused 16-tile auto-tile sheet.'
  },
  dungeon_edges: {
    trigger: 'sakpix_tiles_dungeon',
    cell_size: '128x128',
    max_samples_per_source: '40',
    include_all: false,
    base_caption: 'trained SakPix dungeon tile set, stone floor, wall edge, corner, stair, shadowed top-down RPG tiles',
    manifest: 'Dungeon preset: favors wall, floor, stair, edge, and corner sheets so generated tiles keep collision-friendly borders.'
  },
  town_roofs: {
    trigger: 'sakpix_tiles_town',
    cell_size: 'auto',
    max_samples_per_source: '28',
    include_all: true,
    base_caption: 'trained SakPix town stage tile set, roof, wall, wood, stone path, cozy top-down RPG material tiles',
    manifest: 'Town preset: includes broader structure and roof sheets because town packs often mix terrain, walls, roofs, and props.'
  },
  water_coast: {
    trigger: 'sakpix_tiles_water',
    cell_size: 'auto',
    max_samples_per_source: '36',
    include_all: false,
    base_caption: 'trained SakPix water and coast auto-tile, shoreline edge, corner, bridge, animated-friendly top-down RPG tile',
    manifest: 'Water preset: narrows captions around water, coast, bridge, edge, and corner cells for cleaner shoreline generations.'
  }
};

function setTileTrainingField(form, name, value) {
  const field = form?.querySelector(`[name="${name}"]`);
  if (!field) return;
  if (field.type === 'checkbox') {
    field.checked = Boolean(value);
  } else {
    field.value = value;
  }
  field.dispatchEvent(new Event('input', { bubbles: true }));
  field.dispatchEvent(new Event('change', { bubbles: true }));
}

function applyTileTrainingPreset(presetName) {
  const preset = TILE_TRAINING_PRESETS[presetName];
  const form = $('#tileTrainingDatasetForm');
  if (!preset || !form) return;

  setTileTrainingField(form, 'trigger', preset.trigger);
  setTileTrainingField(form, 'cell_size', preset.cell_size);
  setTileTrainingField(form, 'max_samples_per_source', preset.max_samples_per_source);
  setTileTrainingField(form, 'include_all', preset.include_all);
  setTileTrainingField(form, 'base_caption', preset.base_caption);

  const manifest = $('#tileTrainingPreviewManifest');
  if (manifest) {
    clearNode(manifest);
    const title = document.createElement('b');
    title.textContent = '16-tile auto-tile sheet';
    const body = document.createElement('span');
    body.textContent = preset.manifest;
    manifest.appendChild(title);
    manifest.appendChild(body);
  }

  document.querySelectorAll('[data-tile-preset]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tilePreset === presetName);
  });
  toast(`Tile preset applied: ${presetName.replace(/_/g, ' ')}`);
}

function applyGoalDefaults(goalName) {
  const g = GOAL_DEFAULTS[goalName];
  if (!g) return;
  const form = $('#generateForm');
  if (!form) return;
  if (g.style !== undefined && form.querySelector('[name="style"]')) form.querySelector('[name="style"]').value = g.style;
  if (g.fps !== undefined && form.querySelector('[name="fps"]')) form.querySelector('[name="fps"]').value = g.fps;
  if (g.cell_size !== undefined && form.querySelector('[name="cell_size"]')) form.querySelector('[name="cell_size"]').value = g.cell_size;
  if (g.negative !== undefined && form.querySelector('[name="negative"]')) form.querySelector('[name="negative"]').value = g.negative;
  if (g.tier !== undefined && form.querySelector('[name="tier"]')) form.querySelector('[name="tier"]').value = g.tier;
  if (g.profile !== undefined && form.querySelector('[name="profile"]')) form.querySelector('[name="profile"]').value = g.profile;
  if (goalName === 'isometric') {
    if (form.querySelector('[name="default_actions"]')) form.querySelector('[name="default_actions"]').value = 'idle,walk,attack_light,hurt,death';
    if (form.querySelector('[name="default_directions"]')) form.querySelector('[name="default_directions"]').value = 'iso_front_left,iso_front_right,iso_back_left,iso_back_right';
  }
  if (typeof syncGenerateChoiceChecksFromHidden === 'function') syncGenerateChoiceChecksFromHidden();
  toast(`Applied defaults for: ${goalName.replace('_', ' ').toUpperCase()}`);
}

let activeArchetypeTag = '';
let currentArchetypes = [];
let selectedArchetype = null;

function archetypeInitials(arc) {
  return String(arc.name || 'SF')
    .split(/[\s/]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('') || 'SF';
}

function archetypeGradient(arc) {
  const tags = Array.isArray(arc.tags) ? arc.tags.join('|') : '';
  const seed = `${arc.id || ''}|${arc.name || ''}|${tags}`;
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = ((hash << 5) - hash) + seed.charCodeAt(i);
  const hue = Math.abs(hash) % 360;
  return `linear-gradient(135deg, hsl(${hue} 78% 35% / .95), hsl(${(hue + 52) % 360} 80% 22% / .92))`;
}

function updateSelectedArchetypePanel(arc) {
  selectedArchetype = arc || null;
  const panel = $('#archetypeSelectedPanel');
  const portrait = $('#archetypeSelectedPortrait');
  const name = $('#archetypeSelectedName');
  const description = $('#archetypeSelectedDescription');
  const meta = $('#archetypeSelectedMeta');
  const applyBtn = $('#applySelectedArchetypeBtn');
  if (!panel || !portrait || !name || !description || !meta || !applyBtn) return;

  clearNode(meta);
  if (!arc) {
    portrait.textContent = 'SF';
    portrait.style.background = '';
    name.textContent = 'Choose a visual card';
    description.textContent = 'Pick an archetype to preview the character prompt, style hint, actions, directions, and palette guidance before applying it to Generate.';
    applyBtn.disabled = true;
    return;
  }

  portrait.textContent = archetypeInitials(arc);
  portrait.style.background = archetypeGradient(arc);
  name.textContent = arc.name || 'Untitled archetype';
  description.textContent = arc.description || arc.character || 'No description provided.';
  const chips = [
    ['Actions', (arc.recommended_actions || []).join(', ') || 'custom'],
    ['Directions', (arc.recommended_directions || []).join(', ') || 'custom'],
    ['Palette', arc.palette_hint || 'project palette'],
  ];
  chips.forEach(([label, value]) => {
    const chip = document.createElement('span');
    const labelNode = document.createElement('b');
    labelNode.textContent = label;
    chip.appendChild(labelNode);
    chip.append(` ${value}`);
    meta.appendChild(chip);
  });
  applyBtn.disabled = false;
  populateArchetypeCustomizePanel(arc);
}

function populateArchetypeCustomizePanel(arc) {
  const panel = $('#archetypeCustomizePanel');
  if (!panel) return;
  const character = $('#archetypeCustomizeCharacter');
  const style = $('#archetypeCustomizeStyle');
  const actions = $('#archetypeCustomizeActions');
  const directions = $('#archetypeCustomizeDirections');
  if (!arc) {
    if (character) character.value = '';
    if (style) style.value = '';
    if (actions) actions.value = '';
    if (directions) directions.value = '';
    return;
  }
  if (character) character.value = arc.character || '';
  if (style) style.value = arc.style || '';
  if (actions) actions.value = (arc.recommended_actions || []).join(',');
  if (directions) directions.value = (arc.recommended_directions || []).join(',');
}

function archetypeCustomizeList(value) {
  return String(value || '').split(',').map(item => item.trim()).filter(Boolean);
}

function customizedArchetypePayload(arc) {
  if (!arc) return null;
  const custom = {...arc};
  const character = $('#archetypeCustomizeCharacter');
  const style = $('#archetypeCustomizeStyle');
  const actions = $('#archetypeCustomizeActions');
  const directions = $('#archetypeCustomizeDirections');
  if (character && character.value.trim()) custom.character = character.value.trim();
  if (style && style.value.trim()) custom.style = style.value.trim();
  const customActions = archetypeCustomizeList(actions?.value || '');
  const customDirections = archetypeCustomizeList(directions?.value || '');
  if (customActions.length) custom.recommended_actions = customActions;
  if (customDirections.length) custom.recommended_directions = customDirections;
  custom.customized = true;
  return custom;
}

function setArchetypeProvenance(form, arc) {
  const fields = {
    archetype_id: arc.id || '',
    archetype_name: arc.name || '',
    archetype_tags: Array.isArray(arc.tags) ? arc.tags.join(',') : '',
    archetype_palette_hint: arc.palette_hint || '',
    archetype_customized: arc.customized ? 'true' : 'false'
  };
  Object.entries(fields).forEach(([name, value]) => {
    const field = form.querySelector(`[name="${name}"]`);
    if (field) field.value = value;
  });
}

async function loadArchetypes(search = '', tag = '') {
  try {
    const res = await api(`/api/archetypes?search=${encodeURIComponent(search)}&tag=${encodeURIComponent(tag)}`);
    if (!res.ok) return;
    currentArchetypes = res.archetypes || [];
    
    const grid = $('#archetypesGrid');
    if (!grid) return;
    clearNode(grid);
    
    if (currentArchetypes.length === 0) {
      appendText(grid, 'div', 'No matching archetypes found.', 'result-empty');
      return;
    }
    
    currentArchetypes.forEach(arc => {
      const card = document.createElement('article');
      card.className = 'archetype-card';
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.setAttribute('aria-label', `Preview archetype ${arc.name || 'Untitled archetype'}`);
      card.dataset.archetypeId = arc.id || arc.name || '';
      card.style.setProperty('--archetype-glow', archetypeGradient(arc));

      const portrait = document.createElement('div');
      portrait.className = 'archetype-card-portrait';
      portrait.style.background = archetypeGradient(arc);
      portrait.textContent = archetypeInitials(arc);
      card.appendChild(portrait);
      
      const head = document.createElement('div');
      head.className = 'archetype-card-head';
      const name = document.createElement('h4');
      name.textContent = arc.name;
      head.appendChild(name);
      const family = document.createElement('span');
      family.className = 'archetype-card-family';
      family.textContent = (arc.tags || [])[0] || 'sprite';
      head.appendChild(family);
      card.appendChild(head);
      
      const desc = document.createElement('p');
      desc.textContent = arc.description;
      card.appendChild(desc);
      
      if (arc.tags && arc.tags.length) {
        const tagsWrapper = document.createElement('div');
        tagsWrapper.className = 'archetype-card-tags';
        arc.tags.forEach(t => {
          const tSpan = document.createElement('span');
          tSpan.textContent = t;
          tagsWrapper.appendChild(tSpan);
        });
        card.appendChild(tagsWrapper);
      }
      
      const actionsRow = document.createElement('div');
      actionsRow.className = 'archetype-card-actions';
      const actionCount = document.createElement('span');
      actionCount.append('Actions ');
      appendText(actionCount, 'code', String((arc.recommended_actions || []).length));
      const directionCount = document.createElement('span');
      directionCount.append('Dirs ');
      appendText(directionCount, 'code', String((arc.recommended_directions || []).length || 1));
      const apply = document.createElement('button');
      apply.className = 'mini primary archetype-apply-btn';
      apply.type = 'button';
      apply.textContent = 'Customize';
      apply.addEventListener('click', (event) => {
        event.stopPropagation();
        updateSelectedArchetypePanel(arc);
        document.querySelectorAll('.archetype-card.selected').forEach(el => el.classList.remove('selected'));
        card.classList.add('selected');
        $('#archetypeCustomizeCharacter')?.focus();
      });
      actionsRow.append(actionCount, directionCount, apply);
      card.appendChild(actionsRow);
      
      card.addEventListener('click', () => {
        updateSelectedArchetypePanel(arc);
        document.querySelectorAll('.archetype-card.selected').forEach(el => el.classList.remove('selected'));
        card.classList.add('selected');
      });
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          updateSelectedArchetypePanel(arc);
          document.querySelectorAll('.archetype-card.selected').forEach(el => el.classList.remove('selected'));
          card.classList.add('selected');
        }
      });
      
      grid.appendChild(card);
    });
    updateSelectedArchetypePanel(currentArchetypes[0] || null);
    const firstCard = grid.querySelector('.archetype-card');
    if (firstCard) firstCard.classList.add('selected');
  } catch (e) {
    console.error('Failed to load archetypes:', e);
  }
}

function applyArchetype(arc) {
  const form = $('#generateForm');
  if (!form) return;
  setArchetypeProvenance(form, arc);
  
  if (arc.character !== undefined && form.querySelector('[name="character"]')) {
    form.querySelector('[name="character"]').value = arc.character;
  }
  if (arc.style !== undefined && form.querySelector('[name="style"]')) {
    form.querySelector('[name="style"]').value = arc.style;
  }
  if (arc.negative !== undefined && form.querySelector('[name="negative"]')) {
    form.querySelector('[name="negative"]').value = arc.negative;
  }
  if (arc.recommended_actions && form.querySelector('[name="default_actions"]')) {
    form.querySelector('[name="default_actions"]').value = arc.recommended_actions.join(',');
  }
  if (arc.recommended_directions && form.querySelector('[name="default_directions"]')) {
    form.querySelector('[name="default_directions"]').value = arc.recommended_directions.join(',');
  }
  if (arc.recommended_actions && arc.recommended_actions.length && form.querySelector('[name="sprite_action"]')) {
    form.querySelector('[name="sprite_action"]').value = arc.recommended_actions[0];
  }
  if (arc.recommended_directions && arc.recommended_directions.length && form.querySelector('[name="direction"]')) {
    form.querySelector('[name="direction"]').value = arc.recommended_directions[0];
  }
  if (arc.palette_hint && form.querySelector('[name="pixel_cleanup"]')) {
    form.querySelector('[name="pixel_cleanup"]').checked = true;
  }
  if (typeof syncGenerateChoiceChecksFromHidden === 'function') syncGenerateChoiceChecksFromHidden();
  if (typeof refreshGeneratePromptPreview === 'function') refreshGeneratePromptPreview();
  updateSelectedArchetypePanel(arc);
  
  const modal = $('#recipesModal');
  if (modal) modal.classList.add('hidden');
  
  toast(arc.customized ? `Applied customized archetype: ${arc.name}` : `Applied archetype: ${arc.name}`);
}

function renderArchetypeTags() {
  const tagsContainer = $('#recipeTagsContainer');
  if (!tagsContainer) return;
  clearNode(tagsContainer);
  
  const commonTags = ['all', 'sakpix', 'trained', 'human', 'npc', 'magic', 'melee', 'ranged', 'cyberpunk', 'sci-fi'];
  commonTags.forEach(tag => {
    const pill = document.createElement('div');
    pill.className = 'recipe-tag-pill' + (activeArchetypeTag === tag || (tag === 'all' && !activeArchetypeTag) ? ' active' : '');
    pill.textContent = tag.toUpperCase();
    pill.addEventListener('click', () => {
      activeArchetypeTag = tag === 'all' ? '' : tag;
      document.querySelectorAll('.recipe-tag-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const search = $('#recipeSearchInput')?.value || '';
      loadArchetypes(search, activeArchetypeTag);
    });
    tagsContainer.appendChild(pill);
  });
}

function initPresetBindings() {
  // Populate the preset selector on load
  if ($('#presetSelect')) {
    loadPresets();
    
    $('#presetSelect').addEventListener('change', e => {
      const name = e.target.value;
      if (!name || !currentPresets[name]) return;
      const p = currentPresets[name];
      const form = $('#generateForm');
      
      if (p.character !== undefined) form.querySelector('[name="character"]').value = p.character;
      if (p.style !== undefined) form.querySelector('[name="style"]').value = p.style;
      if (p.tier !== undefined) form.querySelector('[name="tier"]').value = p.tier;
      if (p.profile !== undefined) form.querySelector('[name="profile"]').value = p.profile;
      if (p.fps !== undefined) form.querySelector('[name="fps"]').value = p.fps;
      if (p.cell_size !== undefined) form.querySelector('[name="cell_size"]').value = p.cell_size;
      if (p.negative !== undefined) form.querySelector('[name="negative"]').value = p.negative;
      if (p.reference_image !== undefined && form.querySelector('[name="reference_image"]')) form.querySelector('[name="reference_image"]').value = p.reference_image;
      if (p.style_image !== undefined && form.querySelector('[name="style_image"]')) form.querySelector('[name="style_image"]').value = p.style_image;
      
      if (p.qa_threshold_loop_rmse !== undefined) form.querySelector('[name="qa_threshold_loop_rmse"]').value = p.qa_threshold_loop_rmse;
      if (p.qa_threshold_foot_drift !== undefined) form.querySelector('[name="qa_threshold_foot_drift"]').value = p.qa_threshold_foot_drift;
      if (p.qa_threshold_center_drift !== undefined) form.querySelector('[name="qa_threshold_center_drift"]').value = p.qa_threshold_center_drift;
      if (p.default_actions !== undefined) form.querySelector('[name="default_actions"]').value = p.default_actions;
      if (p.default_directions !== undefined) form.querySelector('[name="default_directions"]').value = p.default_directions;
      if (typeof syncGenerateChoiceChecksFromHidden === 'function') syncGenerateChoiceChecksFromHidden();
      if (typeof refreshGenerateReferencePreview === 'function') refreshGenerateReferencePreview();
      if (typeof refreshGeneratePromptPreview === 'function') refreshGeneratePromptPreview();
      
      $('#presetName').value = name;
      toast(`Preset '${name}' loaded`);
    });
  }

  if ($('#savePresetBtn')) {
    $('#savePresetBtn').addEventListener('click', async () => {
      const name = $('#presetName').value.trim();
      if (!name) { toast('Please enter a preset name'); return; }
      const form = $('#generateForm');
      const data = formData(form);
      
      try {
        const res = await api('/api/presets/save', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ name, ...data })
        });
        if (res.ok) {
          toast(`Preset '${name}' saved`);
          currentPresets = res.presets || {};
          await loadPresets();
          $('#presetSelect').value = name;
        } else {
          toast('Save failed: ' + res.message);
        }
      } catch(e) {
        toast('Save error: ' + e.message);
      }
    });
  }

  if ($('#deletePresetBtn')) {
    $('#deletePresetBtn').addEventListener('click', async () => {
      const name = $('#presetSelect').value;
      if (!name) { toast('Select a preset to delete'); return; }
      if (!confirm(`Delete preset '${name}'?`)) return;
      try {
        const res = await api('/api/presets/delete', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ name })
        });
        if (res.ok) {
          toast(`Preset '${name}' deleted`);
          currentPresets = res.presets || {};
          await loadPresets();
          $('#presetName').value = '';
        } else {
          toast('Delete failed: ' + res.message);
        }
      } catch(e) {
        toast('Delete error: ' + e.message);
      }
    });
  }

  if ($('#getAdvisorBtn')) {
    $('#getAdvisorBtn').addEventListener('click', async () => {
      const quality = $('#advisorQuality').value || 'balanced';
      try {
        const rec = await api(`/api/advisor?quality=${quality}`);
        const form = $('#generateForm');
        if (rec.tier) form.querySelector('[name="tier"]').value = rec.tier;
        if (rec.profile) form.querySelector('[name="profile"]').value = rec.profile;
        
        const box = $('#advisor-result');
        clearNode(box);
        const title = document.createElement('b');
        title.textContent = 'Recommendation: ';
        box.appendChild(title);
        box.append('Tier ');
        appendText(box, 'code', rec.tier || '');
        box.append(', Profile ');
        appendText(box, 'code', rec.profile || '');
        box.append(`, ${rec.frame_count} frames, ${rec.fps} fps, ${rec.cell_size}.`);
        appendText(box, 'small', rec.rationale || '', 'advisor-rationale');
        if (rec.warnings && rec.warnings.length) {
          const warnings = document.createElement('div');
          warnings.className = 'advisor-warnings';
          rec.warnings.forEach(w => appendText(warnings, 'span', w));
          box.appendChild(warnings);
        }
        box.classList.remove('hidden');
        toast('Recommendation applied!');
      } catch(e) { toast('Advisor error: ' + e.message); }
    });
  }

  // Bind character archetypes modal open / close
  const openBtn = $('#openArchetypesBtn');
  const modal = $('#recipesModal');
  const closeBtn = $('#closeRecipesBtn');
  const backdrop = $('#recipesModalBackdrop');
  
  if (openBtn && modal) {
    openBtn.addEventListener('click', () => {
      modal.classList.remove('hidden');
      renderArchetypeTags();
      const search = $('#recipeSearchInput')?.value || '';
      loadArchetypes(search, activeArchetypeTag);
    });
  }
  
  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  }
  if (backdrop && modal) {
    backdrop.addEventListener('click', () => modal.classList.add('hidden'));
  }

  const applySelectedBtn = $('#applySelectedArchetypeBtn');
  if (applySelectedBtn) {
    applySelectedBtn.addEventListener('click', () => {
      if (selectedArchetype) applyArchetype(customizedArchetypePayload(selectedArchetype));
    });
  }
  const resetCustomizeBtn = $('#resetArchetypeCustomizeBtn');
  if (resetCustomizeBtn) {
    resetCustomizeBtn.addEventListener('click', () => populateArchetypeCustomizePanel(selectedArchetype));
  }
  
  // Bind search input filter
  const searchInput = $('#recipeSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      clearTimeout(searchInput._searchTimer);
      searchInput._searchTimer = setTimeout(() => {
        loadArchetypes(searchInput.value, activeArchetypeTag);
      }, 300);
    });
  }

  // Auto-filling and autocomplete presets when typing
  let allArchetypesCache = [];
  async function fetchAllArchetypes() {
    try {
      const res = await api('/api/archetypes');
      if (res.ok) allArchetypesCache = res.archetypes || [];
    } catch (e) {
      console.error('Failed to pre-cache archetypes:', e);
    }
  }
  fetchAllArchetypes();

  const characterTextarea = document.querySelector('#generateForm textarea[name="character"]');
  const suggestionsBox = $('#recipeSuggestions');
  
  if (characterTextarea && suggestionsBox) {
    characterTextarea.addEventListener('input', () => {
      const text = characterTextarea.value.trim().toLowerCase();
      if (text.length < 2) {
        suggestionsBox.classList.add('hidden');
        clearNode(suggestionsBox);
        return;
      }

      // Find matches in cache (match by name or tag)
      const matches = allArchetypesCache.filter(arc => {
        const name = String(arc.name || '').toLowerCase();
        const description = String(arc.description || '').toLowerCase();
        const tags = Array.isArray(arc.tags) ? arc.tags : [];
        return name.includes(text) ||
               tags.some(t => String(t || '').toLowerCase().includes(text)) ||
               description.includes(text);
      }).slice(0, 5); // Limit to top 5 suggestions

      if (matches.length === 0) {
        suggestionsBox.classList.add('hidden');
        clearNode(suggestionsBox);
        return;
      }

      clearNode(suggestionsBox);
      matches.forEach(arc => {
        const item = document.createElement('div');
        item.className = 'recipe-suggestion-item';
        const wrapper = document.createElement('div');
        wrapper.append('Auto-fill: ');
        const name = document.createElement('b');
        name.textContent = arc.name || 'Untitled archetype';
        wrapper.appendChild(name);
        wrapper.append(' ');
        const description = document.createElement('span');
        description.textContent = `(${arc.description || 'No description'})`;
        wrapper.appendChild(description);
        item.appendChild(wrapper);
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          applyArchetype(arc);
          suggestionsBox.classList.add('hidden');
        });
        suggestionsBox.appendChild(item);
      });
      suggestionsBox.classList.remove('hidden');
    });

    // Close suggestions box on clicking outside
    document.addEventListener('click', (e) => {
      if (!characterTextarea.contains(e.target) && !suggestionsBox.contains(e.target)) {
        suggestionsBox.classList.add('hidden');
      }
    });
  }

  if ($('#btnGoalPixelArt')) $('#btnGoalPixelArt').addEventListener('click', () => applyGoalDefaults('pixel_art'));
  if ($('#btnGoalSmooth2D')) $('#btnGoalSmooth2D').addEventListener('click', () => applyGoalDefaults('smooth_2d'));
  if ($('#btnGoalSideScroller')) $('#btnGoalSideScroller').addEventListener('click', () => applyGoalDefaults('side_scroller'));
  if ($('#btnGoalTopDown')) $('#btnGoalTopDown').addEventListener('click', () => applyGoalDefaults('top_down'));
  if ($('#btnGoalIsometric')) $('#btnGoalIsometric').addEventListener('click', () => applyGoalDefaults('isometric'));
  if ($('#btnGoalLocalFast')) $('#btnGoalLocalFast').addEventListener('click', () => applyGoalDefaults('local_fast'));
  if ($('#btnGoalLocalQuality')) $('#btnGoalLocalQuality').addEventListener('click', () => applyGoalDefaults('local_quality'));

  document.querySelectorAll('[data-tile-preset]').forEach(btn => {
    btn.addEventListener('click', () => applyTileTrainingPreset(btn.dataset.tilePreset));
  });
}

if (window.onSpriteForgeReady) {
  window.onSpriteForgeReady(initPresetBindings);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPresetBindings, { once: true });
} else {
  initPresetBindings();
}
