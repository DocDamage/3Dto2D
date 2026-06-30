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
  toast(`Applied defaults for: ${goalName.replace('_', ' ').toUpperCase()}`);
}

document.addEventListener('DOMContentLoaded', () => {
  if ($('#presetSelect')) {
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
      
      if (p.qa_threshold_loop_rmse !== undefined) form.querySelector('[name="qa_threshold_loop_rmse"]').value = p.qa_threshold_loop_rmse;
      if (p.qa_threshold_foot_drift !== undefined) form.querySelector('[name="qa_threshold_foot_drift"]').value = p.qa_threshold_foot_drift;
      if (p.qa_threshold_center_drift !== undefined) form.querySelector('[name="qa_threshold_center_drift"]').value = p.qa_threshold_center_drift;
      if (p.default_actions !== undefined) form.querySelector('[name="default_actions"]').value = p.default_actions;
      if (p.default_directions !== undefined) form.querySelector('[name="default_directions"]').value = p.default_directions;
      
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

  if ($('#btnGoalPixelArt')) $('#btnGoalPixelArt').addEventListener('click', () => applyGoalDefaults('pixel_art'));
  if ($('#btnGoalSmooth2D')) $('#btnGoalSmooth2D').addEventListener('click', () => applyGoalDefaults('smooth_2d'));
  if ($('#btnGoalSideScroller')) $('#btnGoalSideScroller').addEventListener('click', () => applyGoalDefaults('side_scroller'));
  if ($('#btnGoalTopDown')) $('#btnGoalTopDown').addEventListener('click', () => applyGoalDefaults('top_down'));
  if ($('#btnGoalLocalFast')) $('#btnGoalLocalFast').addEventListener('click', () => applyGoalDefaults('local_fast'));
  if ($('#btnGoalLocalQuality')) $('#btnGoalLocalQuality').addEventListener('click', () => applyGoalDefaults('local_quality'));
});
