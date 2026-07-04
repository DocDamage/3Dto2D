window._releasePrecheckOk = true;

async function refreshQaDashboard() {
  const tbody = $('#qaDashboardBody');
  if (!tbody) return;
  clearNode(tbody);
  try {
    const res = await api('/api/qa/batch_summary' + projectQuery());
    if (!res.summary || res.summary.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="empty-cell">No sprites found in current project.</td></tr>';
      return;
    }
    res.summary.forEach(s => {
      const tr = document.createElement('tr');
      
      const tdName = document.createElement('td');
      tdName.textContent = s.name;
      tr.appendChild(tdName);
      
      const tdState = document.createElement('td');
      const stateBadge = document.createElement('span');
      stateBadge.className = `qa-gate-badge ${s.has_qa ? (s.passed_gates ? 'pass' : 'fail') : 'warn'}`;
      stateBadge.textContent = s.has_qa ? (s.passed_gates ? 'PASS' : 'FAIL') : 'NO QA';
      tdState.appendChild(stateBadge);
      tr.appendChild(tdState);
      
      const tdSeam = document.createElement('td');
      tdSeam.textContent = s.loop_quality ? s.loop_quality.toFixed(1) : '—';
      tdSeam.style.color = s.gate_details?.loop_quality?.ok ? '#2ecc71' : '#e74c3c';
      if (s.history && s.history.length > 1) {
        const seamHistory = s.history.map(h => h.loop_seam_rmse).filter(x => x !== null && x !== undefined && !isNaN(x));
        if (seamHistory.length > 1) {
          tdSeam.appendChild(makeTinySparkline(seamHistory, '#3498db'));
        }
      }
      tr.appendChild(tdSeam);
      
      const tdDrift = document.createElement('td');
      tdDrift.textContent = s.foot_drift ? s.foot_drift.toFixed(2) + 'px' : '—';
      tdDrift.style.color = s.gate_details?.foot_drift?.ok ? '#2ecc71' : '#e74c3c';
      if (s.history && s.history.length > 1) {
        const driftHistory = s.history.map(h => h.foot_y_stdev_px).filter(x => x !== null && x !== undefined && !isNaN(x));
        if (driftHistory.length > 1) {
          tdDrift.appendChild(makeTinySparkline(driftHistory, '#ffd166'));
        }
      }
      tr.appendChild(tdDrift);
      
      const tdFlicker = document.createElement('td');
      tdFlicker.textContent = s.flicker ? s.flicker.toFixed(2) : '—';
      tdFlicker.style.color = s.gate_details?.flicker?.ok ? '#2ecc71' : '#e74c3c';
      if (s.history && s.history.length > 1) {
        const flickerHistory = s.history.map(h => h.brightness_stdev).filter(x => x !== null && x !== undefined && !isNaN(x));
        if (flickerHistory.length > 1) {
          tdFlicker.appendChild(makeTinySparkline(flickerHistory, '#e74c3c'));
        }
      }
      tr.appendChild(tdFlicker);

      
      const tdCoverage = document.createElement('td');
      tdCoverage.textContent = s.alpha_coverage ? (s.alpha_coverage * 100).toFixed(1) + '%' : '—';
      tr.appendChild(tdCoverage);
      
      const tdNoise = document.createElement('td');
      tdNoise.textContent = s.alpha_cleanliness !== undefined ? (s.alpha_cleanliness * 100).toFixed(2) + '%' : '—';
      tdNoise.style.color = s.gate_details?.alpha_cleanliness?.ok ? '#2ecc71' : '#e74c3c';
      tr.appendChild(tdNoise);
      
      const tdMissing = document.createElement('td');
      tdMissing.textContent = s.missing_frames ? 'YES' : 'NO';
      tdMissing.style.color = s.missing_frames ? '#e74c3c' : '#2ecc71';
      tr.appendChild(tdMissing);
      
      const tdExports = document.createElement('td');
      tdExports.textContent = s.has_exports ? 'YES' : 'NO';
      tdExports.style.color = s.has_exports ? '#2ecc71' : '#f1c40f';
      tr.appendChild(tdExports);
      
      const tdAct = document.createElement('td');
      tdAct.style.whiteSpace = 'nowrap';
      
      const qaBtn = document.createElement('button');
      qaBtn.className = 'mini';
      qaBtn.type = 'button';
      qaBtn.textContent = 'Run QA';
      qaBtn.addEventListener('click', async () => {
        await runAction('qa_report', { sprite_dir: s.path });
        refreshQaDashboard();
      });
      tdAct.appendChild(qaBtn);
      
      const valBtn = document.createElement('button');
      valBtn.className = 'mini primary';
      valBtn.type = 'button';
      valBtn.textContent = 'Validate';
      valBtn.style.marginLeft = '4px';
      valBtn.addEventListener('click', async () => {
        try {
          const valRes = await api(`/api/sprite/validate_engine?path=${encodeURIComponent(s.path)}`);
          if (valRes.ok) {
            alert(`Export is VALID! All ${valRes.results.length} checks passed.`);
          } else {
            const failed = valRes.results.filter(r => !r.ok).map(r => ` - ${r.label}: ${r.detail}`).join('\n');
            alert(`Export has failures!\n\n${failed}`);
          }
        } catch (err) {
          alert('Validation failed: ' + err.message);
        }
      });
      tdAct.appendChild(valBtn);
      
      tr.appendChild(tdAct);
      tbody.appendChild(tr);
    });
  } catch(e) { console.error(e); }
}

async function loadProjectConfig() {
  try {
    const res = await api('/api/project/config');
    const gates = res.quality_gates || {};
    const form = $('#projectConfigForm');
    if (form) {
      form.elements.max_foot_drift.value = gates.max_foot_drift !== undefined ? gates.max_foot_drift : 2.0;
      form.elements.max_flicker.value = gates.max_flicker !== undefined ? gates.max_flicker : 1.0;
      form.elements.loop_seam_threshold.value = gates.loop_seam_threshold !== undefined ? gates.loop_seam_threshold : 15.0;
      form.elements.required_frame_count.value = gates.required_frame_count !== undefined && gates.required_frame_count !== null ? gates.required_frame_count : '';
      form.elements.alpha_cleanliness.value = gates.alpha_cleanliness !== undefined ? gates.alpha_cleanliness : 0.05;
    }
  } catch (err) {
    console.warn(err);
  }
}

async function loadQualityReports() {
  try {
    const data = await api('/api/quality' + projectQuery());
    const list = $('#qualityList');
    if (!list) return;
    if (!data.reports || !data.reports.length) {
      clearNode(list);
      appendText(list, 'div', 'No QA reports found yet.', 'empty compact');
      return;
    }
    clearNode(list);
    data.reports.forEach(q => {
      const item = document.createElement('article');
      item.className = 'release-item';
      appendText(item, 'b', q.name || 'QA report');
      const score = q.score !== null && q.score !== undefined ? ` · score ${Number(q.score).toFixed(1)}` : '';
      const issues = Number(q.issue_count || 0);
      appendText(item, 'small', `${q.kind || 'Report'} · ${issues} issues${score} · ${q.modified || ''}`);
      appendText(item, 'code', q.path || '');

      const actions = document.createElement('div');
      actions.className = 'button-row compact-actions';
      if (q.source_path || q.path) {
        const select = document.createElement('button');
        select.type = 'button';
        select.className = 'mini';
        select.dataset.selectQualityPath = q.source_path || q.path;
        select.textContent = 'Select';
        actions.appendChild(select);
      }
      if (q.html_url) {
        const report = document.createElement('a');
        report.className = 'mini link-button';
        report.href = q.html_url;
        report.textContent = 'Report';
        actions.appendChild(report);
      }
      if (q.report_url) {
        const json = document.createElement('a');
        json.className = 'mini link-button';
        json.href = q.report_url;
        json.textContent = 'JSON';
        actions.appendChild(json);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

let qualityLivePreviewTimer = null;
let qualityLivePreviewLastPath = '';

function qualityPreviewVersionedUrl(url) {
  if (!url) return '';
  return url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
}

function setQualityPreviewEmpty(slot, message) {
  if (!slot) return;
  clearNode(slot);
  slot.classList.add('empty');
  slot.textContent = message;
}

function setQualityPreviewStatus(message) {
  const status = $('#qualityLivePreviewStatus');
  if (status) status.textContent = message;
}

async function refreshQualityLivePreview(path, options = {}) {
  const input = $('#qualitySpriteDir');
  const previewPath = String(path || input?.value || '').trim();
  const videoSlot = $('#qualityLiveVideoSlot');
  const spriteSlot = $('#qualityLiveSpriteSlot');

  if (!videoSlot || !spriteSlot) return;
  if (!previewPath) {
    qualityLivePreviewLastPath = '';
    setQualityPreviewStatus('Enter or select a sprite folder to preview the source video and current sprite immediately.');
    setQualityPreviewEmpty(videoSlot, 'No source video loaded.');
    setQualityPreviewEmpty(spriteSlot, 'No sprite preview loaded.');
    return;
  }

  qualityLivePreviewLastPath = previewPath;
  setQualityPreviewStatus('Loading preview for ' + previewPath + '...');

  try {
    const data = await api('/api/sprite/preview?path=' + encodeURIComponent(previewPath));
    const resolvedPath = data.path || previewPath;

    clearNode(videoSlot);
    clearNode(spriteSlot);
    videoSlot.classList.remove('empty');
    spriteSlot.classList.remove('empty');

    if (data.video_url) {
      const video = document.createElement('video');
      video.controls = true;
      video.loop = true;
      video.muted = true;
      video.playsInline = true;
      video.autoplay = true;
      video.src = qualityPreviewVersionedUrl(data.video_url);
      videoSlot.appendChild(video);
      video.play().catch(() => {});
    } else {
      setQualityPreviewEmpty(videoSlot, 'No source video found for this sprite.');
    }

    const spriteUrl = data.preview_url || data.sheet_url;
    if (spriteUrl) {
      const img = document.createElement('img');
      img.src = qualityPreviewVersionedUrl(spriteUrl);
      img.alt = data.name || 'Sprite preview';
      spriteSlot.appendChild(img);
    } else {
      setQualityPreviewEmpty(spriteSlot, 'Sprite preview will appear when sheet files are written.');
    }

    const frameText = `${data.frame_count || '?'} frames, ${data.fps || '?'} fps, ${data.frame_width || '?'} x ${data.frame_height || '?'}`;
    setQualityPreviewStatus(`${resolvedPath} - ${frameText}`);

    if (input && !input.value.trim() && options.source === 'active') input.value = resolvedPath;
    if (typeof loadSpriteDetails === 'function' && options.inspect !== false) {
      loadSpriteDetails(resolvedPath).catch(err => console.warn(err));
    }
  } catch (err) {
    if (!options.silent) console.warn(err);
    setQualityPreviewStatus('Preview will appear as soon as sprite files are written for ' + previewPath + '.');
    setQualityPreviewEmpty(videoSlot, 'Waiting for source video.');
    setQualityPreviewEmpty(spriteSlot, 'Waiting for sprite sheet or preview GIF.');
  }
}

function scheduleQualityLivePreview(delay = 220) {
  if (qualityLivePreviewTimer) clearTimeout(qualityLivePreviewTimer);
  qualityLivePreviewTimer = setTimeout(() => {
    refreshQualityLivePreview('', { force: true });
  }, delay);
}

function initQualityLivePreview() {
  const input = $('#qualitySpriteDir');
  if (!input || input.dataset.livePreviewBound === '1') return;
  input.dataset.livePreviewBound = '1';
  input.addEventListener('input', () => scheduleQualityLivePreview());
  input.addEventListener('change', () => scheduleQualityLivePreview(0));
  if (input.value.trim()) scheduleQualityLivePreview(0);
}

window.refreshQualityLivePreview = refreshQualityLivePreview;
initQualityLivePreview();

function qualityPanelTitle(targetId) {
  return targetId === 'qualityLivePreview' ? 'Live Preview' : 'Visual Sprite Inspector';
}

function qualityPanelPopoutBody(targetId) {
  if (targetId === 'qualityLivePreview') {
    const video = $('#qualityLiveVideoSlot video');
    const sprite = $('#qualityLiveSpriteSlot img');
    const parts = [];
    if (video && video.src) {
      parts.push(`<figure><figcaption>Source video</figcaption><video src="${video.src}" controls loop muted autoplay playsinline></video></figure>`);
    } else {
      parts.push('<figure><figcaption>Source video</figcaption><div class="empty">No source video loaded.</div></figure>');
    }
    if (sprite && sprite.src) {
      parts.push(`<figure><figcaption>Sprite output</figcaption><img src="${sprite.src}" alt="Sprite preview" /></figure>`);
    } else {
      parts.push('<figure><figcaption>Sprite output</figcaption><div class="empty checker">No sprite preview loaded.</div></figure>');
    }
    return `<div class="popout-grid">${parts.join('')}</div>`;
  }

  const canvas = $('#inspector-canvas');
  const fallbackImg = $('#inspector-img');
  let media = '<div class="empty checker">No inspector frame loaded.</div>';
  if (canvas) {
    try {
      media = `<img class="inspector-frame" src="${canvas.toDataURL('image/png')}" alt="Current inspector frame" />`;
    } catch (err) {
      media = '<div class="empty checker">Unable to export the current inspector frame.</div>';
    }
  } else if (fallbackImg && fallbackImg.src) {
    media = `<img class="inspector-frame" src="${fallbackImg.src}" alt="Current inspector frame" />`;
  }
  const label = $('#frameScrubberLabel')?.textContent || '';
  return `<figure class="single"><figcaption>${label || 'Current frame'}</figcaption>${media}</figure>`;
}

function openQualityPanelPopout(targetId) {
  const title = qualityPanelTitle(targetId);
  const popup = window.open('', '_blank', 'popup=yes,width=980,height=720');
  if (!popup) {
    toast('Popout was blocked by the browser.');
    return;
  }
  popup.document.write(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${title}</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; background: #060914; color: #eef4ff; }
    body { margin: 0; min-height: 100vh; background: #060914; }
    main { box-sizing: border-box; display: grid; gap: 14px; min-height: 100vh; padding: 18px; }
    h1 { font-size: 18px; margin: 0; }
    .popout-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    figure { background: #02040b; border: 1px solid rgba(255,255,255,.12); border-radius: 10px; display: grid; gap: 8px; margin: 0; min-height: 0; padding: 10px; }
    figure.single { min-height: calc(100vh - 92px); }
    figcaption { color: #9fb1cf; font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
    img, video { align-self: center; justify-self: center; max-height: calc(100vh - 140px); max-width: 100%; object-fit: contain; width: 100%; }
    img { image-rendering: pixelated; }
    .empty { align-items: center; color: #9fb1cf; display: flex; justify-content: center; min-height: 260px; text-align: center; }
    .checker { background-color: #080808; background-image: linear-gradient(45deg, #121212 25%, transparent 25%), linear-gradient(-45deg, #121212 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #121212 75%), linear-gradient(-45deg, transparent 75%, #121212 75%); background-position: 0 0, 0 10px, 10px -10px, -10px 0; background-size: 20px 20px; }
    @media(max-width: 760px) { .popout-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body><main><h1>${title}</h1>${qualityPanelPopoutBody(targetId)}</main></body>
</html>`);
  popup.document.close();
}

async function toggleQualityPanelFullscreen(targetId) {
  const target = $('#' + targetId);
  if (!target) return;
  if (target.classList.contains('quality-panel-expanded')) {
    target.classList.remove('quality-panel-expanded');
    return;
  }
  try {
    if (document.fullscreenElement === target) {
      await document.exitFullscreen();
    } else {
      await target.requestFullscreen();
    }
  } catch (err) {
    target.classList.add('quality-panel-expanded');
  }
}

function initQualityPanelActions() {
  $$('[data-quality-panel-action]').forEach(btn => {
    if (btn.dataset.qualityPanelBound === '1') return;
    btn.dataset.qualityPanelBound = '1';
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.qualityPanelTarget || '';
      if (btn.dataset.qualityPanelAction === 'fullscreen') {
        toggleQualityPanelFullscreen(targetId);
      } else if (btn.dataset.qualityPanelAction === 'popout') {
        openQualityPanelPopout(targetId);
      }
    });
  });
}

initQualityPanelActions();

async function runReleasePrecheck() {
  const foldersVal = $('#releaseSprites')?.value || '';
  const sprites = foldersVal.split('\n').map(s => s.trim()).filter(s => s.length > 0);
  const container = $('#releasePrecheckWarnings');
  if (!container) return;
  
  if (sprites.length === 0) {
    container.classList.add('hidden');
    clearNode(container);
    window._releasePrecheckOk = true;
    return;
  }
  
  try {
    const res = await api('/api/release/precheck', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ sprites })
    });
    
    clearNode(container);
    if (!res.ok || (res.errors.length === 0 && res.warnings.length === 0)) {
      container.classList.add('hidden');
      window._releasePrecheckOk = res.ok;
      return;
    }
    
    container.classList.remove('hidden');
    const header = document.createElement('h4');
    header.textContent = 'Quality Gate Precheck Reports:';
    container.appendChild(header);
    
    const list = document.createElement('ul');
    res.errors.forEach(err => {
      const li = appendText(list, 'li', err, 'release-precheck-error');
      li.style.color = '#ff6b6b';
      li.style.fontWeight = 'bold';
    });
    res.warnings.forEach(warn => {
      const li = appendText(list, 'li', warn, 'release-precheck-warning');
      li.style.color = '#ffd166';
    });
    container.appendChild(list);
    
    window._releasePrecheckOk = res.ok;
  } catch(e) {
    console.error('Precheck error:', e);
  }
}

if ($('#projectConfigForm')) {
  $('#projectConfigForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const gates = {
      max_foot_drift: parseFloat(form.elements.max_foot_drift.value),
      max_flicker: parseFloat(form.elements.max_flicker.value),
      loop_seam_threshold: parseFloat(form.elements.loop_seam_threshold.value),
      required_frame_count: form.elements.required_frame_count.value ? parseInt(form.elements.required_frame_count.value) : null,
      alpha_cleanliness: parseFloat(form.elements.alpha_cleanliness.value)
    };
    try {
      await api('/api/project/config', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ quality_gates: gates })
      });
      toast('Quality gates updated successfully!');
      refreshQaDashboard();
    } catch (err) {
      toast('Error updating gates: ' + err.message);
    }
  });
}

function renderQaAdvisor(data) {
  const panel = $('#qaAdvisorPanel');
  if (!panel) return;
  clearNode(panel);
  if (!data || !data.ok) {
    appendText(panel, 'div', data?.message || 'Advisor unavailable.', 'empty compact');
    return;
  }
  const head = document.createElement('div');
  head.className = 'qa-advisor-head';
  appendText(head, 'b', data.score !== null && data.score !== undefined ? `QA score ${data.score}` : 'QA advisor');
  appendText(head, 'span', data.report_found ? 'Based on the latest QA report.' : 'No QA report found; using available metadata only.');
  panel.appendChild(head);
  if (data.learning_summary) {
    const learning = document.createElement('div');
    learning.className = 'qa-advisor-learning';
    const promoted = (data.learning_summary.promoted_codes || []).join(', ') || 'none';
    const deprioritized = (data.learning_summary.deprioritized_codes || []).join(', ') || 'none';
    appendText(learning, 'b', `${data.learning_summary.feedback_count || 0} feedback decision${Number(data.learning_summary.feedback_count || 0) === 1 ? '' : 's'} learned`);
    appendText(learning, 'span', `Promoted: ${promoted} · Deprioritized: ${deprioritized}`);
    panel.appendChild(learning);
  }

  (data.advice || []).forEach(row => {
    const item = document.createElement('article');
    item.className = `qa-advisor-item severity-${row.severity || 'medium'}`;
    appendText(item, 'b', row.title || row.code || 'Advice');
    appendText(item, 'p', row.reason || '');
    appendText(item, 'span', row.action || '');
    if (row.feedback) {
      appendText(item, 'small', `Feedback: ${row.feedback.accepted || 0} accepted · ${row.feedback.rejected || 0} rejected · ${row.feedback.dismissed || 0} dismissed`);
    }
    if (row.repair_plan) {
      appendText(item, 'small', `Plan: ${row.repair_plan.mode || 'manual_review'} · ${row.repair_plan.follow_up || 'Run QA again after repair.'}`);
    }
    if (row.command_hint) appendText(item, 'code', row.command_hint);
    const actions = document.createElement('div');
    actions.className = 'button-row compact-actions';
    if (row.repair_action && (row.repair_action.button_id || row.repair_action.view)) {
      const repair = document.createElement('button');
      repair.className = 'mini primary qa-advisor-repair';
      repair.type = 'button';
      repair.textContent = row.repair_action.label || 'Apply repair';
      repair.addEventListener('click', () => {
        if (row.repair_action.button_id) {
          const target = document.getElementById(row.repair_action.button_id);
          if (target) {
            target.click();
            toast(`Started repair: ${row.repair_action.label || row.code}`);
            return;
          }
        }
        if (row.repair_action.view && typeof showView === 'function') {
          showView(row.repair_action.view);
          toast(`Opened ${row.repair_action.label || row.repair_action.view}.`);
          return;
        }
        toast('Repair action is not available in this view yet.');
      });
      actions.appendChild(repair);
    }
    ['accepted', 'rejected', 'dismissed'].forEach(decision => {
      const btn = document.createElement('button');
      btn.className = 'mini';
      btn.type = 'button';
      btn.textContent = decision;
      btn.addEventListener('click', async () => {
        try {
          await api('/api/qa/advisor/feedback', {
            method: 'POST',
            body: JSON.stringify({ path: $('#qaAdvisorPath')?.value || $('#qaSpriteDir')?.value || '', code: row.code, decision }),
          });
          toast('QA advisor feedback saved.');
        } catch (err) {
          toast(err.message || 'Could not save advisor feedback.');
        }
      });
      actions.appendChild(btn);
    });
    item.appendChild(actions);
    panel.appendChild(item);
  });

  if (data.suggestions && data.suggestions.length) {
    const list = document.createElement('div');
    list.className = 'qa-advisor-suggestions';
    appendText(list, 'b', 'Original QA suggestions');
    data.suggestions.forEach(suggestion => appendText(list, 'span', suggestion));
    panel.appendChild(list);
  }
}

async function loadQaAdvisor() {
  const path = String($('#qualitySpriteDir')?.value || '').trim();
  if (!path) {
    renderQaAdvisor({ ok: false, message: 'Select a sprite folder first.' });
    return;
  }
  try {
    const data = await api('/api/qa/advisor?path=' + encodeURIComponent(path));
    renderQaAdvisor(data);
  } catch (err) {
    renderQaAdvisor({ ok: false, message: err.message || 'Advisor failed.' });
  }
}

$('#qaAdvisorBtn')?.addEventListener('click', loadQaAdvisor);
$('#qaAdvisorRefreshBtn')?.addEventListener('click', loadQaAdvisor);

if ($('#qualityList')) {
  $('#qualityList').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-select-quality-path]');
    if (!btn) return;
    const path = btn.dataset.selectQualityPath;
    selectedSpriteDir = path.replace(/\/qa$|\/quality$/, '');
    $('#qualitySpriteDir').value = selectedSpriteDir;
    if (typeof refreshQualityLivePreview === 'function') await refreshQualityLivePreview(selectedSpriteDir, { force: true });
    if (typeof loadSpriteDetails === 'function') await loadSpriteDetails(selectedSpriteDir);
    await loadQaAdvisor();
  });
}

if ($('#releaseSprites')) {
  $('#releaseSprites').addEventListener('input', runReleasePrecheck);
}

if ($('#releaseForm')) {
  // Override existing submit listener
  const form = $('#releaseForm');
  const newForm = form.cloneNode(true);
  form.replaceWith(newForm);
  
  $('#releaseSprites').addEventListener('input', runReleasePrecheck);
  
  newForm.addEventListener('submit', async e => {
    e.preventDefault();
    const data = formData(e.currentTarget);
    
    const strict = $('#releaseStrictCheckbox')?.checked;
    if (window._releasePrecheckOk === false) {
      if (strict) {
        alert('Release blocked: Some sprites failed the QA quality gates under strict mode. Fix the errors or uncheck "Block release" to force build.');
        return;
      } else {
        if (!confirm('Warning: Selected sprites have QA errors or missing files. Do you want to build the release package anyway?')) {
          return;
        }
      }
    }
    runAction('release_package', data);
    showView('logs');
  });
}
