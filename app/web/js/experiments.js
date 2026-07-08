let currentHistory = [];
let selectedCompareIds = new Set();
let currentExperimentAnalytics = null;
let promptSearchTimer = null;

function metricText(value, suffix = '') {
  if (value === null || value === undefined || value === '') return '-';
  return `${value}${suffix}`;
}

function renderBarList(container, rows, options = {}) {
  if (!container) return;
  clearNode(container);
  if (!rows || !rows.length) {
    appendText(container, 'div', options.empty || 'No analytics yet.', 'empty compact');
    return;
  }
  const valueKey = options.valueKey || 'count';
  const labelKey = options.labelKey || 'label';
  const maxValue = Math.max(1, ...rows.map(row => Number(row[valueKey] || 0)));
  rows.forEach(row => {
    const item = document.createElement('div');
    item.className = 'experiment-bar-row';
    const label = document.createElement('span');
    label.textContent = row[labelKey] || row.name || row.date || 'Unknown';
    const track = document.createElement('div');
    track.className = 'experiment-bar-track';
    const fill = document.createElement('i');
    fill.style.width = `${Math.max(4, (Number(row[valueKey] || 0) / maxValue) * 100)}%`;
    track.appendChild(fill);
    const value = document.createElement('b');
    value.textContent = options.format ? options.format(row) : String(row[valueKey] ?? '-');
    item.append(label, track, value);
    container.appendChild(item);
  });
}

function renderExperimentAnalytics() {
  const data = currentExperimentAnalytics;
  if (!data) return;
  const total = $('#expMetricTotal');
  const scored = $('#expMetricScored');
  const average = $('#expMetricAverage');
  const pass = $('#expMetricPassRate');
  const starred = $('#expMetricStarred');
  if (total) total.textContent = metricText(data.total_runs);
  if (scored) scored.textContent = metricText(data.scored_runs);
  if (average) average.textContent = metricText(data.average_score);
  if (pass) pass.textContent = metricText(data.pass_rate, '%');
  if (starred) starred.textContent = metricText(data.starred_runs);

  const recommendations = $('#expRecommendations');
  if (recommendations) {
    clearNode(recommendations);
    const rows = data.recommendations || [];
    if (!rows.length) {
      appendText(recommendations, 'div', 'Run QA on a few variants to unlock next-run recommendations.', 'empty compact');
    }
    rows.forEach(row => {
      const item = document.createElement('article');
      item.className = 'experiment-recommendation';
      item.dataset.recommendationKind = row.kind || 'insight';
      appendText(item, 'span', row.kind ? row.kind.replace(/_/g, ' ') : 'insight');
      appendText(item, 'b', row.title || 'Try this next');
      appendText(item, 'small', row.detail || '');
      if (row.score !== null && row.score !== undefined) appendText(item, 'em', `${row.score} QA`);
      recommendations.appendChild(item);
    });
  }

  renderBarList($('#expScoreDistribution'), data.score_distribution, {
    labelKey: 'label',
    valueKey: 'count',
    empty: 'No scored runs yet.',
  });
  renderBarList($('#expScoreTrend'), data.score_over_time, {
    labelKey: 'date',
    valueKey: 'average_score',
    empty: 'No trend data yet.',
    format: row => `${row.average_score ?? '-'} (${row.count})`,
  });
  renderBarList($('#expActionScores'), data.score_by_action, {
    labelKey: 'name',
    valueKey: 'average_score',
    empty: 'No action scores yet.',
    format: row => `${row.average_score ?? '-'} / ${row.count}`,
  });

  const settings = $('#expBestSettings');
  if (settings) {
    clearNode(settings);
    const rows = [
      ...(data.best_profiles || []).slice(0, 3).map(row => ({...row, kind: 'Profile'})),
      ...(data.best_seeds || []).slice(0, 3).map(row => ({...row, kind: 'Seed'})),
    ];
    if (!rows.length) appendText(settings, 'div', 'No ranked settings yet.', 'empty compact');
    rows.forEach(row => {
      const item = document.createElement('div');
      item.className = 'experiment-insight';
      appendText(item, 'span', row.kind);
      appendText(item, 'b', row.name);
      appendText(item, 'small', `${row.average_score ?? '-'} avg · ${row.count} run(s)`);
      settings.appendChild(item);
    });
  }

  const bestRuns = $('#expBestRuns');
  if (bestRuns) {
    clearNode(bestRuns);
    const runs = data.best_runs || [];
    if (!runs.length) appendText(bestRuns, 'div', 'Run QA to surface winning prompts here.', 'empty compact');
    runs.forEach(run => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'experiment-best-run';
      item.dataset.runId = run.id || '';
      item.dataset.previewPath = run.sprite_folder || '';
      appendText(item, 'b', `${run.score} QA · ${run.action || 'action'} ${run.direction || ''}`.trim());
      appendText(item, 'span', run.prompt || run.profile || 'No prompt captured.');
      appendText(item, 'small', `${run.profile || 'profile'} · seed ${run.seed ?? '-'}`);
      bestRuns.appendChild(item);
    });
  }

  renderPromptHistory();
}

function renderPromptHistory() {
  const box = $('#experimentPromptHistory');
  if (!box || !currentExperimentAnalytics) return;
  const query = ($('#experimentPromptSearch')?.value || '').trim().toLowerCase();
  clearNode(box);
  const rows = (currentExperimentAnalytics.prompt_history || []).filter(row => {
    if (!query) return true;
    return [row.prompt, row.action, row.direction].some(value => String(value || '').toLowerCase().includes(query));
  }).slice(0, 20);
  if (!rows.length) {
    appendText(box, 'div', 'No matching prompt history.', 'empty compact');
    return;
  }
  rows.forEach(row => {
    const item = document.createElement('article');
    item.className = 'experiment-prompt-row';
    item.dataset.runId = row.id || '';
    appendText(item, 'b', `${row.action || 'run'} ${row.direction || ''}`.trim());
    appendText(item, 'span', row.prompt || '');
    appendText(item, 'small', row.score !== null && row.score !== undefined ? `${row.score} QA` : 'unscored');
    const actions = document.createElement('div');
    actions.className = 'button-row compact-actions';
    const use = document.createElement('button');
    use.type = 'button';
    use.className = 'mini primary';
    use.dataset.promptUse = row.id || '';
    use.textContent = 'Use prompt';
    actions.appendChild(use);
    const pin = document.createElement('button');
    pin.type = 'button';
    pin.className = 'mini';
    pin.dataset.promptPin = row.id || '';
    pin.dataset.starred = row.starred ? 'false' : 'true';
    pin.textContent = row.starred ? 'Unpin' : 'Pin';
    actions.appendChild(pin);
    item.appendChild(actions);
    box.appendChild(item);
  });
}

async function searchPromptHistory() {
  const box = $('#experimentPromptHistory');
  if (!box) return;
  const q = ($('#experimentPromptSearch')?.value || '').trim();
  try {
    const data = await api('/api/experiments/prompts?q=' + encodeURIComponent(q) + '&limit=40' + projectQuery().replace('?', '&'));
    currentExperimentAnalytics = currentExperimentAnalytics || {};
    currentExperimentAnalytics.prompt_history = data.prompts || [];
    renderPromptHistory();
  } catch (e) {
    console.error('Prompt history search failed:', e);
  }
}

function usePromptHistoryRow(row) {
  const form = $('#generateForm');
  if (!form || !row) return;
  const set = (name, value) => {
    const field = form.querySelector(`[name="${name}"]`);
    if (field && value !== undefined && value !== null) field.value = value;
  };
  set('prompt', row.prompt || '');
  set('negative', row.negative || '');
  set('sprite_action', row.action || '');
  set('direction', row.direction || '');
  set('default_actions', row.action || '');
  set('default_directions', row.direction || '');
  set('profile', row.profile || '');
  set('tier', row.tier || '');
  set('seed', row.seed ?? '');
  showView('generate');
  if (typeof syncGenerateChoiceChecksFromHidden === 'function') syncGenerateChoiceChecksFromHidden();
  if (typeof refreshGeneratePromptPreview === 'function') refreshGeneratePromptPreview();
  toast('Loaded prompt history into Generate.');
}

async function loadExperimentAnalytics() {
  try {
    currentExperimentAnalytics = await api('/api/experiments/analytics' + projectQuery());
    renderExperimentAnalytics();
  } catch (e) {
    console.error('Experiment analytics load failed:', e);
  }
}

async function exportWinningPrompts() {
  const target = $('#winningPromptPackResult');
  if (target) target.textContent = 'Building winning prompt pack...';
  try {
    const pack = await api('/api/experiments/winning-prompts?limit=24' + projectQuery().replace('?', '&'));
    if (!target) return;
    clearNode(target);
    appendText(target, 'b', `${pack.entry_count || 0} winning prompt${pack.entry_count === 1 ? '' : 's'} ready`);
    appendText(target, 'small', pack.selection || 'Pinned prompts first, then high QA runs.');
    const textarea = document.createElement('textarea');
    textarea.readOnly = true;
    textarea.rows = 5;
    textarea.value = JSON.stringify(pack, null, 2);
    textarea.className = 'winning-prompt-pack-json';
    target.appendChild(textarea);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'mini primary';
    copy.textContent = 'Copy JSON';
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(textarea.value);
        toast('Winning prompt pack copied.');
      } catch (err) {
        textarea.select();
        toast('Select/copy the prompt pack JSON.');
      }
    });
    target.appendChild(copy);
  } catch (err) {
    if (target) target.textContent = err.message || 'Could not build winning prompt pack.';
    toast(err.message || 'Could not build winning prompt pack.');
  }
}

function statusBadge(rec) {
  const span = document.createElement('span');
  span.className = 'qa-badge';
  if (rec.qa_passed === true) {
    span.classList.add('pass');
    span.textContent = 'QA';
  } else if (rec.qa_passed === false) {
    span.classList.add('fail');
    span.textContent = 'QA';
  } else {
    span.classList.add('muted');
    span.textContent = '—';
  }
  return span;
}

function updateCompareButton() {
  const btn = $('#historyCompareBtn');
  if (btn) {
    btn.textContent = `Compare Selected (${selectedCompareIds.size})`;
    btn.disabled = selectedCompareIds.size !== 2;
  }
}

async function loadHistory() {
  try {
    const data = await api('/api/experiments' + projectQuery());
    currentHistory = data.experiments || [];
    if (!currentHistory.length) {
      try {
        const outputData = await api('/api/outputs' + projectQuery());
        currentHistory = (outputData.outputs || []).map((o, idx) => ({
          id: `output-${idx}-${o.path || o.name || ''}`,
          created_at: o.modified || o.created_at || '',
          project_name: o.project_name || '',
          sprite_action: o.action || o.sprite_action || inferHistoryAction(o),
          direction: o.direction || inferHistoryDirection(o),
          model_tier: o.tier || '',
          profile: o.profile || '',
          qa_score: o.qa_score,
          qa_passed: o.qa_passed,
          sprite_folder: o.path || '',
          notes: 'Recovered from output folder',
        }));
      } catch (fallbackErr) {
        console.warn('Output history fallback failed:', fallbackErr);
      }
    }
    selectedCompareIds.clear();
    updateCompareButton();
    renderHistory();
    await loadExperimentAnalytics();
  } catch(e) { console.error(e); }
}

function inferHistoryAction(row) {
  const text = `${row.name || ''} ${row.path || ''}`.toLowerCase();
  const actions = ['idle', 'walk', 'run', 'jump', 'attack_light', 'attack_heavy', 'cast', 'hurt', 'death', 't_pose', 'a_pose'];
  return actions.find(action => text.includes(action)) || '';
}

function inferHistoryDirection(row) {
  const text = `${row.name || ''} ${row.path || ''}`.toLowerCase();
  const directions = ['front_right', 'front_left', 'back_right', 'back_left', 'front', 'right', 'back', 'left'];
  return directions.find(direction => text.includes(direction)) || '';
}

function renderHistory() {
  const body = $('#historyBody');
  if (!currentHistory || !currentHistory.length) {
    tableEmpty(body, 11, 'No generation history yet.');
    return;
  }
  
  const actionFilter = $('#historyFilterAction')?.value.trim().toLowerCase();
  const dirFilter = $('#historyFilterDirection')?.value.trim().toLowerCase();
  const tierFilter = $('#historyFilterTier')?.value;
  const starredFilter = $('#historyFilterStarred')?.checked;
  
  let filtered = currentHistory.filter(r => {
    if (actionFilter && !String(r.sprite_action || '').toLowerCase().includes(actionFilter)) return false;
    if (dirFilter && !String(r.direction || '').toLowerCase().includes(dirFilter)) return false;
    if (tierFilter && String(r.model_tier || '') !== tierFilter) return false;
    if (starredFilter && !r.starred) return false;
    return true;
  });
  
  const sortBy = $('#historySortBy')?.value || 'time_desc';
  filtered.sort((a, b) => {
    if (sortBy === 'time_desc') {
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    }
    if (sortBy === 'time_asc') {
      return new Date(a.created_at || 0) - new Date(b.created_at || 0);
    }
    if (sortBy === 'qa_desc') {
      const scoreA = a.qa_score !== undefined && a.qa_score !== null ? Number(a.qa_score) : -1;
      const scoreB = b.qa_score !== undefined && b.qa_score !== null ? Number(b.qa_score) : -1;
      return scoreB - scoreA;
    }
    if (sortBy === 'qa_asc') {
      const scoreA = a.qa_score !== undefined && a.qa_score !== null ? Number(a.qa_score) : 999;
      const scoreB = b.qa_score !== undefined && b.qa_score !== null ? Number(b.qa_score) : 999;
      return scoreA - scoreB;
    }
    return 0;
  });
  
  clearNode(body);
  if (!filtered.length) {
    tableEmpty(body, 11, 'No matching history records.');
    return;
  }
  
  filtered.forEach(r => {
    const tr = document.createElement('tr');
    
    // Checkbox column
    const compareCell = document.createElement('td');
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.className = 'compare-checkbox';
    chk.value = r.sprite_folder || '';
    chk.checked = selectedCompareIds.has(r.sprite_folder);
    chk.disabled = !r.sprite_folder;
    chk.addEventListener('change', () => {
      if (chk.checked) {
        if (selectedCompareIds.size >= 2) {
          chk.checked = false;
          toast('You can only select up to 2 runs for comparison.');
          return;
        }
        if (r.sprite_folder) selectedCompareIds.add(r.sprite_folder);
      } else {
        selectedCompareIds.delete(r.sprite_folder);
      }
      updateCompareButton();
    });
    compareCell.appendChild(chk);
    tr.appendChild(compareCell);

    // Keep (Star) column
    const starCell = document.createElement('td');
    const star = document.createElement('button');
    star.type = 'button';
    star.className = 'icon-mini star-toggle' + (r.starred ? ' active' : '');
    star.dataset.runId = r.id || '';
    star.dataset.starred = r.starred ? 'false' : 'true';
    star.title = r.starred ? 'Unstar run' : 'Keep run when clearing history';
    star.textContent = r.starred ? '★' : '☆';
    starCell.appendChild(star);
    tr.appendChild(starCell);

    appendText(tr, 'td', String(r.created_at || '').slice(0, 16), 'nowrap muted-cell');
    appendText(tr, 'td', r.project_name || '—', 'nowrap muted-cell');
    appendText(tr, 'td', r.sprite_action || '—');
    appendText(tr, 'td', r.direction || '—');

    const tier = document.createElement('td');
    appendText(tier, 'code', String(r.model_tier || '').replace('wan21_', '') || '—');
    tr.appendChild(tier);

    const profile = document.createElement('td');
    appendText(profile, 'code', r.profile || '—');
    tr.appendChild(profile);

    const qa = document.createElement('td');
    qa.appendChild(statusBadge(r));
    tr.appendChild(qa);

    const output = document.createElement('td');
    output.className = 'path-cell';
    if (r.sprite_folder) {
      const review = document.createElement('button');
      review.type = 'button';
      review.className = 'mini primary';
      review.dataset.previewPath = r.sprite_folder;
      review.textContent = 'Review';
      output.appendChild(review);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'mini';
      btn.dataset.openPath = r.sprite_folder;
      btn.textContent = 'Open';
      output.appendChild(btn);
      appendText(output, 'span', ' ' + r.sprite_folder, 'subtle-path');
    } else {
      output.textContent = '—';
    }
    
    const memoryBtn = document.createElement('button');
    memoryBtn.type = 'button';
    memoryBtn.className = 'mini';
    memoryBtn.textContent = 'Use Settings';
    memoryBtn.title = 'Load prompts/settings into Generator';
    memoryBtn.style.marginLeft = '4px';
    memoryBtn.addEventListener('click', () => {
      const form = $('#generateForm');
      if (form) {
        if (r.character) form.querySelector('[name="character"]').value = r.character;
        if (r.style) form.querySelector('[name="style"]').value = r.style;
        if (r.negative_prompt) form.querySelector('[name="negative"]').value = r.negative_prompt;
        if (r.seed !== undefined) form.querySelector('[name="seed"]').value = r.seed;
        if (r.model_tier) form.querySelector('[name="tier"]').value = r.model_tier;
        if (r.profile) form.querySelector('[name="profile"]').value = r.profile;
        if (r.fps) form.querySelector('[name="fps"]').value = r.fps;
        if (r.cell_size) form.querySelector('[name="cell_size"]').value = r.cell_size;
        showView('generate');
        toast('Loaded prompts/settings into Generator!');
      }
    });
    output.appendChild(memoryBtn);
    
    tr.appendChild(output);

    appendText(tr, 'td', r.notes || '', 'notes-cell');
    body.appendChild(tr);
  });
}

async function refreshAbRuns() {
  const select = $('#abRunSelect');
  if (!select) return;
  try {
    const res = await api('/api/ab_run/list');
    window._abRuns = res.ab_runs || [];
    
    select.innerHTML = '<option value="">Choose a past run...</option>';
    window._abRuns.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = `${r.name} (${r.created_at})`;
      select.appendChild(opt);
    });
  } catch(e) { console.error(e); }
}

function resolveSpriteDirNameFromCommand(cmd) {
  if (!cmd || !Array.isArray(cmd)) return null;
  const idx = cmd.indexOf('--output');
  if (idx !== -1 && idx + 1 < cmd.length) {
    const val = cmd[idx+1];
    return val.replace(/^output\//, '').replace(/^projects\/[^/]+\/sprites\//, '');
  }
  return null;
}

if ($('#refreshHistory')) $('#refreshHistory').addEventListener('click', loadHistory);
if ($('#refreshExperimentAnalytics')) $('#refreshExperimentAnalytics').addEventListener('click', loadExperimentAnalytics);
if ($('#exportWinningPrompts')) $('#exportWinningPrompts').addEventListener('click', exportWinningPrompts);
if ($('#exportHistory')) $('#exportHistory').addEventListener('click', () => { window.location.href = '/api/experiments/export' + projectQuery(); });
if ($('#clearHistory')) $('#clearHistory').addEventListener('click', async () => {
  if (!confirm('Clear unstarred experiment history? Starred runs will be kept.')) return;
  try {
    const result = await api('/api/experiments/clear' + projectQuery(), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keep_starred:true, active_project:activeProjectPath})});
    toast(`Removed ${result.removed || 0} history records`);
    await loadHistory();
  } catch(e) { toast('History clear failed: ' + e.message); }
});

// Filter events
['historyFilterAction', 'historyFilterDirection'].forEach(id => {
  $(`#${id}`)?.addEventListener('input', renderHistory);
});
['historyFilterTier', 'historySortBy'].forEach(id => {
  $(`#${id}`)?.addEventListener('change', renderHistory);
});
$('#historyFilterStarred')?.addEventListener('change', renderHistory);
$('#experimentPromptSearch')?.addEventListener('input', () => {
  clearTimeout(promptSearchTimer);
  promptSearchTimer = setTimeout(searchPromptHistory, 250);
});

if ($('#expBestRuns')) {
  $('#expBestRuns').addEventListener('click', async (event) => {
    const btn = event.target.closest('[data-preview-path]');
    const path = btn?.dataset.previewPath;
    if (path && typeof openResultPreview === 'function') await openResultPreview(path);
  });
}

if ($('#historyCompareBtn')) {
  $('#historyCompareBtn').addEventListener('click', async () => {
    const selected = Array.from(selectedCompareIds);
    if (selected.length !== 2) {
      toast('Please select exactly 2 runs to compare.');
      return;
    }
    try {
      showView('compare_player');
      if (typeof setComparePlayerSelection === 'function') setComparePlayerSelection(selected);
      toast('Opened synchronized compare player.');
    } catch(e) {
      toast('Compare error: ' + e.message);
    }
  });
}

if ($('#historyBody')) {
  $('#historyBody').addEventListener('click', async (e) => {
    const previewBtn = e.target.closest('[data-preview-path]');
    if (previewBtn) {
      await openResultPreview(previewBtn.dataset.previewPath);
      return;
    }
    const openBtn = e.target.closest('[data-open-path]');
    if (openBtn) {
      await openPath(openBtn.dataset.openPath);
      return;
    }
    const starBtn = e.target.closest('.star-toggle');
    if (starBtn) {
      try {
        const starred = starBtn.dataset.starred === 'true';
        await api('/api/experiments/star', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:starBtn.dataset.runId, starred})});
        await loadHistory();
      } catch(err) { toast('Star update failed: ' + err.message); }
    }
  });
}

if ($('#experimentPromptHistory')) {
  $('#experimentPromptHistory').addEventListener('click', async (event) => {
    const useBtn = event.target.closest('[data-prompt-use]');
    const pinBtn = event.target.closest('[data-prompt-pin]');
    if (useBtn) {
      const row = (currentExperimentAnalytics?.prompt_history || []).find(item => item.id === useBtn.dataset.promptUse);
      usePromptHistoryRow(row);
      return;
    }
    if (pinBtn) {
      try {
        await api('/api/experiments/star', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id: pinBtn.dataset.promptPin, starred: pinBtn.dataset.starred === 'true'})});
        await searchPromptHistory();
      } catch (err) {
        toast('Prompt pin failed: ' + err.message);
      }
    }
  });
}

if ($('#abRunForm')) {
  $('#abRunForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const name = $('#abRunName').value;
    const pName = typeof activeProjectName === 'function' ? activeProjectName() : '';
    
    const variant_a = {
      action: form.elements.a_action.value,
      character: form.elements.a_character.value,
      style: form.elements.a_style.value,
      negative: form.elements.a_negative.value,
      seed: parseInt(form.elements.a_seed.value) || -1,
      project_name: pName
    };
    const variant_b = {
      action: form.elements.b_action.value,
      character: form.elements.b_character.value,
      style: form.elements.b_style.value,
      negative: form.elements.b_negative.value,
      seed: parseInt(form.elements.b_seed.value) || -1,
      project_name: pName
    };
    
    try {
      const res = await api('/api/ab_run/create', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ name, variant_a, variant_b, project_name: pName })
      });
      if (res.ok) {
        toast('A/B Run queue started!');
        showView('logs');
        refreshAbRuns();
      } else if (res.warning === 'low_disk') {
        if (confirm(`${res.message}\n\nProceed anyway?`)) {
          const resForce = await api('/api/ab_run/create', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ name, variant_a, variant_b, project_name: pName, force: true })
          });
          if (resForce.ok) {
            toast('A/B Run queue started (forced)!');
            showView('logs');
            refreshAbRuns();
          } else {
            toast(resForce.message || 'Error starting A/B run');
          }
        }
      } else {
        toast(res.message || 'Error starting A/B run');
      }
    } catch(err) { toast(err.message); }
  });
}

if ($('#abRunSelect')) {
  $('#abRunSelect').addEventListener('change', async () => {
    const abSelect = $('#abRunSelect');
    const runId = abSelect.value;
    if (!runId) {
      $('#abCompareDisplay').classList.add('hidden');
      return;
    }
    const run = window._abRuns.find(r => r.id === runId);
    if (!run) return;
    
    try {
      const qData = await api(`/api/queues/detail?path=${encodeURIComponent(run.queue_path)}`);
      const jobA = qData.jobs[0];
      const jobB = qData.jobs[1];
      
      $('#abCompareDisplay').classList.remove('hidden');
      
      $('#abScoreA').textContent = 'Loading...';
      $('#abSizeA').textContent = '-';
      $('#abDriftA').textContent = '-';
      $('#abFlickerA').textContent = '-';
      $('#abPreviewImgA').removeAttribute('src');
      
      if (jobA.status === 'completed') {
        const spriteDirName = resolveSpriteDirNameFromCommand(jobA.command);
        if (spriteDirName) {
          try {
            const bundle = await api(`/api/sprite/preview?path=${encodeURIComponent(spriteDirName)}`);
            $('#abPreviewImgA').src = '/file/' + bundle.preview_gif;
            if (bundle.qa_report && bundle.qa_report.metrics) {
              const metrics = bundle.qa_report.metrics;
              $('#abScoreA').textContent = bundle.qa_report.score !== undefined ? bundle.qa_report.score : '—';
              $('#abDriftA').textContent = metrics.foot_y_stdev_px !== undefined ? metrics.foot_y_stdev_px.toFixed(2) + 'px' : '—';
              $('#abFlickerA').textContent = metrics.brightness_stdev !== undefined ? metrics.brightness_stdev.toFixed(2) : '—';
            }
            if (bundle.sheet_png_size) {
              $('#abSizeA').textContent = (bundle.sheet_png_size / 1024).toFixed(1) + ' KB';
            }
          } catch(e) { $('#abScoreA').textContent = 'Error loading bundle'; }
        }
      } else {
        $('#abScoreA').textContent = jobA.status.toUpperCase();
      }
      
      $('#abScoreB').textContent = 'Loading...';
      $('#abSizeB').textContent = '-';
      $('#abDriftB').textContent = '-';
      $('#abFlickerB').textContent = '-';
      $('#abPreviewImgB').removeAttribute('src');
      
      if (jobB.status === 'completed') {
        const spriteDirName = resolveSpriteDirNameFromCommand(jobB.command);
        if (spriteDirName) {
          try {
            const bundle = await api(`/api/sprite/preview?path=${encodeURIComponent(spriteDirName)}`);
            $('#abPreviewImgB').src = '/file/' + bundle.preview_gif;
            if (bundle.qa_report && bundle.qa_report.metrics) {
              const metrics = bundle.qa_report.metrics;
              $('#abScoreB').textContent = bundle.qa_report.score !== undefined ? bundle.qa_report.score : '—';
              $('#abDriftB').textContent = metrics.foot_y_stdev_px !== undefined ? metrics.foot_y_stdev_px.toFixed(2) + 'px' : '—';
              $('#abFlickerB').textContent = metrics.brightness_stdev !== undefined ? metrics.brightness_stdev.toFixed(2) : '—';
            }
            if (bundle.sheet_png_size) {
              $('#abSizeB').textContent = (bundle.sheet_png_size / 1024).toFixed(1) + ' KB';
            }
          } catch(e) { $('#abScoreB').textContent = 'Error loading bundle'; }
        }
      } else {
        $('#abScoreB').textContent = jobB.status.toUpperCase();
      }
    } catch(err) { toast('Error loading details: ' + err.message); }
  });
}
