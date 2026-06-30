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

if ($('#qualityList')) {
  $('#qualityList').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-select-quality-path]');
    if (!btn) return;
    const path = btn.dataset.selectQualityPath;
    selectedSpriteDir = path.replace(/\/qa$|\/quality$/, '');
    $('#qualitySpriteDir').value = selectedSpriteDir;
    if (typeof loadSpriteDetails === 'function') await loadSpriteDetails(selectedSpriteDir);
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
