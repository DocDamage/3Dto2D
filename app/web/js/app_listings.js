// app_listings.js — Reference, pack, planning, release, and quality listing renders
// Extracted from app_main.js

// Reference Files
async function loadReferences() {
  try {
    const data = await api('/api/references' + projectQuery());
    const list = $('#referenceList');
    if (!list) return;
    if (!data.references || !data.references.length) {
      clearNode(list);
      appendText(list, 'div', 'No references uploaded yet.', 'empty compact');
      return;
    }
    clearNode(list);
    data.references.forEach(ref => {
      const item = document.createElement('article');
      item.className = 'release-item';
      appendText(item, 'b', ref.name || 'Reference');
      const sizeKb = ref.size ? `${Math.max(1, Math.round(ref.size / 1024))} KB` : 'unknown size';
      appendText(item, 'small', `${ref.kind || 'file'} · ${sizeKb} · ${ref.modified || ''}`);
      appendText(item, 'code', ref.path || '');
      const actions = document.createElement('div');
      actions.className = 'button-row compact-actions';
      if (ref.path) {
        const select = document.createElement('button');
        select.type = 'button'; select.className = 'mini';
        select.dataset.referencePath = ref.path; select.textContent = 'Use';
        actions.appendChild(select);
        const open = document.createElement('button');
        open.type = 'button'; open.className = 'mini';
        open.dataset.openPath = ref.path; open.textContent = 'Open';
        actions.appendChild(open);
      }
      if (ref.url) {
        const file = document.createElement('a');
        file.className = 'mini link-button'; file.href = ref.url; file.textContent = 'File';
        actions.appendChild(file);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

// Pack History
async function loadPacks() {
  try {
    const data = await api('/api/packs' + projectQuery());
    const list = $('#packList');
    if (!list) return;
    if (!data.packs || !data.packs.length) {
      clearNode(list);
      appendText(list, 'div', 'No packs found yet.', 'empty compact');
      return;
    }
    clearNode(list);
    data.packs.forEach(p => {
      const item = document.createElement('article');
      item.className = 'release-item';
      appendText(item, 'b', p.name || 'Pack');
      const actions = Array.isArray(p.actions) ? p.actions.length : 0;
      const directions = Array.isArray(p.directions) ? p.directions.length : 0;
      appendText(item, 'small', `${p.entries || 0} entries · ${actions} actions · ${directions} directions · ${p.modified || String(p.created_at || '').slice(0, 16)}`);
      appendText(item, 'code', p.path || '');
      const controls = document.createElement('div');
      controls.className = 'button-row compact-actions';
      if (p.path) {
        const open = document.createElement('button');
        open.type = 'button'; open.className = 'mini';
        open.dataset.openPath = p.path; open.textContent = 'Open';
        controls.appendChild(open);
      }
      if (p.manifest_url) {
        const manifest = document.createElement('a');
        manifest.className = 'mini link-button'; manifest.href = p.manifest_url; manifest.textContent = 'Manifest';
        controls.appendChild(manifest);
      }
      item.appendChild(controls);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

// Planning Assets
async function loadPlanning() {
  try {
    const data = await api('/api/planning' + projectQuery());
    const list = $('#planningList');
    if (!list) return;
    const prompts = data.prompts || [];
    const posepacks = data.posepacks || [];
    if (!prompts.length && !posepacks.length) {
      clearNode(list);
      appendText(list, 'div', 'No project prompts or posepacks found yet.', 'empty compact');
      return;
    }
    clearNode(list);
    const rows = [
      ...prompts.map(p => ({...p, kind: 'Prompt'})),
      ...posepacks.map(p => ({...p, kind: 'Posepack'})),
    ];
    rows.forEach(asset => {
      const item = document.createElement('article');
      item.className = 'release-item';
      appendText(item, 'b', asset.name || asset.kind);
      const parts = [asset.kind];
      if (asset.action) parts.push(asset.action);
      if (asset.direction) parts.push(asset.direction);
      if (asset.frames !== undefined) parts.push(`${asset.frames} frames`);
      if (asset.modified) parts.push(asset.modified);
      appendText(item, 'small', parts.join(' · '));
      appendText(item, 'code', asset.path || asset.manifest_path || '');
      const actions = document.createElement('div');
      actions.className = 'button-row compact-actions';
      if (asset.path) {
        const open = document.createElement('button');
        open.type = 'button'; open.className = 'mini';
        open.dataset.openPath = asset.path; open.textContent = 'Open';
        actions.appendChild(open);
      }
      if (asset.url || asset.manifest_url) {
        const file = document.createElement('a');
        file.className = 'mini link-button'; file.href = asset.url || asset.manifest_url; file.textContent = 'JSON';
        actions.appendChild(file);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

// Release History
async function loadReleases() {
  try {
    const data = await api('/api/releases' + projectQuery());
    const list = $('#releaseList');
    if (!list) return;
    if (!data.releases || !data.releases.length) {
      clearNode(list);
      appendText(list, 'div', 'No releases found yet.', 'empty compact');
      return;
    }
    clearNode(list);
    data.releases.forEach(r => {
      const item = document.createElement('article');
      item.className = 'release-item';
      appendText(item, 'b', r.name || 'Release');
      appendText(item, 'small', `${r.sprite_count || 0} sprites · ${r.modified || String(r.created_at || '').slice(0, 16)}`);
      appendText(item, 'code', r.path || '');
      const actions = document.createElement('div');
      actions.className = 'button-row compact-actions';
      if (r.path) {
        const open = document.createElement('button');
        open.type = 'button'; open.className = 'mini';
        open.dataset.openPath = r.path; open.textContent = 'Open';
        actions.appendChild(open);
      }
      if (r.zip_path) {
        const zip = document.createElement('a');
        zip.className = 'mini link-button'; zip.href = r.zip_url; zip.textContent = 'ZIP';
        actions.appendChild(zip);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

// Model/Profile Explainer
async function updateModelProfileExplainer() {
  const form = $('#generateForm');
  if (!form) return;
  const tier = form.querySelector('[name="tier"]')?.value || '';
  const profile = form.querySelector('[name="profile"]')?.value || '';
  try {
    const info = await api(`/api/model/explain?tier=${encodeURIComponent(tier)}&profile=${encodeURIComponent(profile)}`);
    if ($('#modelProfileExplainerTitle')) $('#modelProfileExplainerTitle').textContent = info.label || 'Model/profile';
    if ($('#modelProfileExplainerBody')) $('#modelProfileExplainerBody').textContent = `${info.why_selected || ''} ${info.tradeoffs || ''}`.trim();
  } catch(e) {
    if ($('#modelProfileExplainerBody')) $('#modelProfileExplainerBody').textContent = 'Could not load model explanation.';
  }
}

// Quality Modal & Lab Repairs
async function runQuickRepair(type, spritePath) {
  if (!spritePath) { toast('No sprite selected for repair'); return; }
  toast(`Running repair: ${type}...`);
  const activeProject = activeProjectPath || '';
  if (type === 'qa') {
    await runAction('qa_report', { sprite_dir: spritePath, active_project: activeProject });
    showView('logs');
    if (typeof closeResultPreview === 'function') closeResultPreview();
    return;
  }
  const payload = {
    sprite_dir: spritePath, active_project: activeProject,
    stabilize_anchor: type === 'stabilize', drop_loop_duplicate: false,
    deflicker: type === 'flicker', solidify: type === 'clean' ? 2 : 0,
    blend_loop_frames: type === 'seam' ? 3 : 0, sharpen: type === 'sharpen'
  };
  await runAction('autofix', payload);
  showView('logs');
  if (typeof closeResultPreview === 'function') closeResultPreview();
}

async function reviewExperiment(decision, id) {
  if (!id) { toast('This result is not linked to a recorded generation run.'); return; }
  try {
    await api('/api/experiments/review', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, decision}) });
    toast(decision === 'star' ? 'Result starred' : decision === 'reject' ? 'Result rejected' : 'Review saved');
    await refreshAll();
  } catch(e) { toast('Review failed: ' + e.message); }
}

function initListingsBindings() {
  if ($('#refreshReferences')) $('#refreshReferences').addEventListener('click', loadReferences);
  if ($('#referenceList')) {
    $('#referenceList').addEventListener('click', async (e) => {
      const useBtn = e.target.closest('[data-reference-path]');
      if (useBtn) {
        const refPath = useBtn.dataset.referencePath;
        const generateRef = $('#generationReferenceImage');
        if (generateRef) generateRef.value = refPath;
        if ($('#videoPath')) $('#videoPath').value = refPath;
        toast('Reference selected');
        return;
      }
      const openBtn = e.target.closest('[data-open-path]');
      if (openBtn) await openPath(openBtn.dataset.openPath);
    });
  }

  if ($('#refreshPacks')) $('#refreshPacks').addEventListener('click', loadPacks);
  if ($('#packList')) {
    $('#packList').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-open-path]');
      if (btn) await openPath(btn.dataset.openPath);
    });
  }

  if ($('#refreshPlanning')) $('#refreshPlanning').addEventListener('click', loadPlanning);
  if ($('#planningList')) {
    $('#planningList').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-open-path]');
      if (btn) await openPath(btn.dataset.openPath);
    });
  }

  if ($('#refreshReleases')) $('#refreshReleases').addEventListener('click', loadReleases);
  if ($('#releaseList')) {
    $('#releaseList').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-open-path]');
      if (btn) await openPath(btn.dataset.openPath);
    });
  }

  // Compare panel
  if ($('#compareBtn')) {
    $('#compareBtn').addEventListener('click', () => {
      const section = $('#compare-section');
      const vis = section.classList.contains('hidden');
      section.classList.toggle('hidden', !vis);
      if (vis && selectedSpriteDir) $('#compareA').value = selectedSpriteDir;
    });
  }
  if ($('#runCompareBtn')) {
    $('#runCompareBtn').addEventListener('click', async () => {
      const a = $('#compareA').value.trim();
      const b = $('#compareB').value.trim();
      if (!a || !b) { toast('Both A and B paths required'); return; }
      try {
        toast('Running compare…');
        const result = await api('/api/compare', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({a, b}) });
        if (result.ok) { window.open(result.report_url, '_blank'); toast('Compare report opened!'); }
        else { toast('Compare failed: ' + result.message); }
      } catch(e) { toast('Compare error: ' + e.message); }
    });
  }
  document.addEventListener('click', e => {
    const card = e.target.closest('.sprite-card');
    if (card && $('#compareA')) $('#compareA').value = card.dataset.path || '';
  });

  // Preview repair actions
  if ($('#previewRepairActions')) {
    $('#previewRepairActions').addEventListener('click', e => {
      const btn = e.target.closest('[data-repair]');
      if (!btn) return;
      const type = btn.dataset.repair;
      const spritePath = $('#previewSubtitle')?.textContent;
      if (type && spritePath) runQuickRepair(type, spritePath);
    });
  }

  // Model profile explainer listeners
  if ($('#generateForm')) {
    ['tier', 'profile'].forEach(name => {
      const el = $('#generateForm').querySelector(`[name="${name}"]`);
      if (el) el.addEventListener('change', updateModelProfileExplainer);
    });
  }

  // Review experiment buttons
  if ($('#previewStarResult')) $('#previewStarResult').addEventListener('click', e => reviewExperiment('star', e.currentTarget.dataset.experimentId));
  if ($('#previewRejectResult')) $('#previewRejectResult').addEventListener('click', e => reviewExperiment('reject', e.currentTarget.dataset.experimentId));
  if ($('#previewRerunSimilar')) {
    $('#previewRerunSimilar').addEventListener('click', async e => {
      const id = e.currentTarget.dataset.experimentId;
      if (!id) { toast('This result is not linked to a recorded generation run.'); return; }
      try {
        const res = await api('/api/experiments/rerun_similar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) });
        toast(res.message || 'Similar run started');
        if (typeof closeResultPreview === 'function') closeResultPreview();
        showView('logs');
        await refreshAll();
      } catch(err) { toast('Rerun failed: ' + err.message); }
    });
  }

  // Repair buttons
  const repairButtons = [
    { id: '#labRepairCleanBtn', type: 'clean' },
    { id: '#labRepairStabilizeBtn', type: 'stabilize' },
    { id: '#labRepairSeamBtn', type: 'seam' },
    { id: '#labRepairFlickerBtn', type: 'flicker' },
    { id: '#labRepairSharpenBtn', type: 'sharpen' },
    { id: '#labRepairPreviewBtn', type: 'preview' }
  ];
  repairButtons.forEach(b => {
    const el = $(b.id);
    if (el) {
      el.addEventListener('click', () => {
        const spritePath = $('#qualitySpriteDir').value.trim();
        if (!spritePath) { toast('Please enter or select a sprite output folder first.'); return; }
        runQuickRepair(b.type, spritePath);
      });
    }
  });
}