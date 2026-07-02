let _selectedQueuePath = null;
let _queueRefreshTimer = null;
let selectedJobIds = new Set();

function queueStatusColor(s) {
  if (s === 'done') return '#6f6';
  if (s === 'failed') return '#f66';
  if (s === 'running') return '#fa0';
  return '#888';
}

function queueStatusClass(s) {
  if (s === 'done') return 'status-done';
  if (s === 'failed') return 'status-failed';
  if (s === 'running') return 'status-running';
  return 'status-muted';
}

async function loadQueues() {
  try {
    const data = await api('/api/queues' + projectQuery());
    const list = $('#queueList');
    if (!list) return;
    if (!data.queues || !data.queues.length) {
      clearNode(list);
      appendText(list, 'div', 'No queues found. Create one in Queue Builder.', 'empty compact');
      return;
    }
    clearNode(list);
    data.queues.forEach(q => {
      const c = q.counts || {};
      const active = _selectedQueuePath === q.path;
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'queue-item' + (active ? ' active' : '');
      item.dataset.qpath = q.path || '';
      item.dataset.qname = q.name || q.path || 'Queue';
      appendText(item, 'b', q.name || 'Queue');

      const pills = document.createElement('div');
      pills.className = 'queue-pills';
      Object.entries(c).forEach(([k, v]) => {
        const pill = appendText(pills, 'span', `${k}:${v}`);
        pill.dataset.status = k;
        pill.classList.add(queueStatusClass(k));
      });
      item.appendChild(pills);
      const qp = q.progress || {};
      const qProgress = document.createElement('div');
      qProgress.className = 'queue-progress-line';
      qProgress.appendChild(progressElement(qp.percent || 0, qp.running ? 'busy' : (qp.failed ? 'failed' : qp.percent >= 100 ? 'done' : '')));
      appendText(qProgress, 'span', `${Math.round(clampProgress(qp.percent || 0))}%`);
      item.appendChild(qProgress);
      appendText(item, 'small', String(q.created_at || '').slice(0, 16));
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

async function selectQueue(path, name) {
  _selectedQueuePath = path;
  $('#queueDetailName').textContent = name;
  ['#queueRunBtn','#queueRetryBtn','#queueResetBtn'].forEach(s => $(s).disabled = false);
  await loadQueueDetail(path);
  loadQueues();
}

function updateRunSelectedButton() {
  const btn = $('#queueRunSelectedBtn');
  if (btn) {
    btn.textContent = `▶ Run Selected (${selectedJobIds.size})`;
    btn.disabled = selectedJobIds.size === 0;
  }
}

async function loadQueueDetail(path) {
  if (!path) return;
  try {
    const data = await api('/api/queues/detail?path=' + encodeURIComponent(path));
    const body = $('#queueDetailBody');
    if (!body) return;
    
    const currentJobIds = new Set(data.jobs ? data.jobs.map(j => j.id) : []);
    selectedJobIds = new Set([...selectedJobIds].filter(id => currentJobIds.has(id)));
    updateRunSelectedButton();

    if (!data.jobs || !data.jobs.length) {
      tableEmpty(body, 9, 'No jobs in queue.');
      if ($('#queueEstimates')) $('#queueEstimates').textContent = '';
      return;
    }
    
    const remainingJobs = data.jobs.filter(j => j.status === 'pending' || j.status === 'failed').length;
    const estTimeSec = remainingJobs * 150;
    const estDiskMb = remainingJobs * 50;
    const minutes = Math.floor(estTimeSec / 60);
    const seconds = estTimeSec % 60;
    const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
    
    if ($('#queueEstimates')) {
      const qp = data.progress || {};
      $('#queueEstimates').innerHTML = `Progress: <b>${Math.round(clampProgress(qp.percent || 0))}%</b> · Est. Time: <b>${timeStr}</b> · Est. Disk: <b>${estDiskMb} MB</b> (${remainingJobs} jobs remaining)`;
    }

    clearNode(body);
    data.jobs.forEach(j => {
      const tr = document.createElement('tr');
      tr.dataset.jobId = j.id;

      // Checkbox
      const chkCell = document.createElement('td');
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.className = 'job-checkbox';
      chk.checked = selectedJobIds.has(j.id);
      chk.addEventListener('change', () => {
        if (chk.checked) {
          selectedJobIds.add(j.id);
        } else {
          selectedJobIds.delete(j.id);
        }
        updateRunSelectedButton();
      });
      chkCell.appendChild(chk);
      tr.appendChild(chkCell);

      appendText(tr, 'td', j.id || '', 'mono-cell');
      appendText(tr, 'td', j.action || '');
      appendText(tr, 'td', j.direction || '');
      
      const status = document.createElement('td');
      const statusText = appendText(status, 'span', j.status || '');
      statusText.className = `queue-status ${queueStatusClass(j.status)}`;
      tr.appendChild(status);

      const progressCell = document.createElement('td');
      progressCell.className = 'queue-progress-cell';
      const jobProgress = j.progress || {};
      progressCell.appendChild(progressElement(jobProgress.percent || 0, j.status === 'running' ? 'busy' : j.status === 'done' ? 'done' : j.status === 'failed' ? 'failed' : ''));
      appendText(progressCell, 'span', `${Math.round(clampProgress(jobProgress.percent || 0))}%`, 'muted-cell');
      tr.appendChild(progressCell);
      
      appendText(tr, 'td', j.exit_code !== null && j.exit_code !== undefined ? String(j.exit_code) : '—', 'muted-cell');
      
      const reasonCell = document.createElement('td');
      reasonCell.className = 'reason-cell';
      reasonCell.textContent = j.failed_reason || '—';
      tr.appendChild(reasonCell);

      const actionsCell = document.createElement('td');
      actionsCell.className = 'actions-cell button-row compact-actions';
      
      const upBtn = document.createElement('button');
      upBtn.className = 'mini';
      upBtn.textContent = '▲';
      upBtn.title = 'Move Up';
      upBtn.addEventListener('click', (e) => { e.stopPropagation(); reorderJob(j.id, 'up'); });
      actionsCell.appendChild(upBtn);

      const downBtn = document.createElement('button');
      downBtn.className = 'mini';
      downBtn.textContent = '▼';
      downBtn.title = 'Move Down';
      downBtn.addEventListener('click', (e) => { e.stopPropagation(); reorderJob(j.id, 'down'); });
      actionsCell.appendChild(downBtn);

      const dupBtn = document.createElement('button');
      dupBtn.className = 'mini';
      dupBtn.textContent = '＋';
      dupBtn.title = 'Duplicate Job';
      dupBtn.addEventListener('click', (e) => { e.stopPropagation(); duplicateJob(j.id); });
      actionsCell.appendChild(dupBtn);

      const editBtn = document.createElement('button');
      editBtn.className = 'mini';
      editBtn.textContent = '✎';
      editBtn.title = 'Edit Job Settings';
      editBtn.addEventListener('click', (e) => { e.stopPropagation(); editJob(j); });
      actionsCell.appendChild(editBtn);

      const delBtn = document.createElement('button');
      delBtn.className = 'mini danger';
      delBtn.textContent = '❌';
      delBtn.title = 'Delete Job';
      delBtn.addEventListener('click', (e) => { e.stopPropagation(); deleteJob(j.id); });
      actionsCell.appendChild(delBtn);

      if (j.log) {
        const logBtn = document.createElement('button');
        logBtn.className = 'mini';
        logBtn.textContent = 'Log';
        logBtn.addEventListener('click', (e) => { e.stopPropagation(); openPath(j.log); });
        actionsCell.appendChild(logBtn);
      }

      tr.appendChild(actionsCell);
      body.appendChild(tr);
    });
  } catch(e) { console.error(e); }
}

async function reorderJob(jobId, direction) {
  if (!_selectedQueuePath) return;
  try {
    const res = await api('/api/queues/reorder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ path: _selectedQueuePath, job_id: jobId, direction })
    });
    if (res.ok) {
      toast('Job moved');
      await loadQueueDetail(_selectedQueuePath);
    } else {
      toast('Move failed: ' + res.message);
    }
  } catch(e) { toast('Move error: ' + e.message); }
}

async function duplicateJob(jobId) {
  if (!_selectedQueuePath) return;
  try {
    const res = await api('/api/queues/duplicate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ path: _selectedQueuePath, job_id: jobId })
    });
    if (res.ok) {
      toast('Job duplicated');
      await loadQueueDetail(_selectedQueuePath);
    } else {
      toast('Duplicate failed: ' + res.message);
    }
  } catch(e) { toast('Duplicate error: ' + e.message); }
}

async function deleteJob(jobId) {
  if (!_selectedQueuePath) return;
  if (!confirm(`Delete job '${jobId}'?`)) return;
  try {
    const res = await api('/api/queues/delete_job', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ path: _selectedQueuePath, job_id: jobId })
    });
    if (res.ok) {
      toast('Job deleted');
      await loadQueueDetail(_selectedQueuePath);
    } else {
      toast('Delete failed: ' + res.message);
    }
  } catch(e) { toast('Delete error: ' + e.message); }
}

async function editJob(job) {
  if (!_selectedQueuePath) return;
  const newAction = prompt('Edit Action:', job.action);
  if (newAction === null) return;
  const newDir = prompt('Edit Direction:', job.direction);
  if (newDir === null) return;
  
  const newCmd = [...job.command];
  const actIdx = newCmd.indexOf('--action');
  if (actIdx !== -1 && actIdx < newCmd.length - 1) {
    newCmd[actIdx + 1] = newAction;
  }
  const dirIdx = newCmd.indexOf('--direction');
  if (dirIdx !== -1 && dirIdx < newCmd.length - 1) {
    newCmd[dirIdx + 1] = newDir;
  }
  
  try {
    const res = await api('/api/queues/edit_job', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        path: _selectedQueuePath,
        job_id: job.id,
        action: newAction,
        direction: newDir,
        command: newCmd
      })
    });
    if (res.ok) {
      toast('Job updated and reset to pending');
      await loadQueueDetail(_selectedQueuePath);
    } else {
      toast('Edit failed: ' + res.message);
    }
  } catch(e) { toast('Edit error: ' + e.message); }
}

async function queueAction(endpoint) {
  if (!_selectedQueuePath) return;
  try {
    const r = await api(endpoint, {method:'POST',headers:{'Content-Type': 'application/json'},body:JSON.stringify({path:_selectedQueuePath})});
    toast(r.message || 'Done');
    await refreshAll();
    await loadQueueDetail(_selectedQueuePath);
    await loadQueues();
  } catch(e) { toast('Error: '+e.message); }
}

// Queue Monitor setup
function initQueueMonitorBindings() {
  if ($('#queueRunBtn')) $('#queueRunBtn').addEventListener('click', () => queueAction('/api/queues/run'));
  if ($('#queueRetryBtn')) $('#queueRetryBtn').addEventListener('click', () => queueAction('/api/queues/retry-failed'));
  if ($('#queueResetBtn')) $('#queueResetBtn').addEventListener('click', () => api('/api/cancel', {method:'POST'}).then(refreshAll));
  if ($('#refreshQueues')) $('#refreshQueues').addEventListener('click', loadQueues);
  if ($('#queueList')) {
    $('#queueList').addEventListener('click', async (e) => {
      const item = e.target.closest('[data-qpath]');
      if (item) await selectQueue(item.dataset.qpath, item.dataset.qname || 'Queue');
    });
  }
  if ($('#queueDetailBody')) {
    $('#queueDetailBody').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-open-path]');
      if (btn) await openPath(btn.dataset.openPath);
    });
  }

  if ($('#queueRunSelectedBtn')) {
    $('#queueRunSelectedBtn').addEventListener('click', async () => {
      if (!_selectedQueuePath || selectedJobIds.size === 0) return;
      try {
        const selectedArr = Array.from(selectedJobIds);
        toast(`Running ${selectedArr.length} selected jobs...`);
        const r = await api('/api/queues/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ path: _selectedQueuePath, only_jobs: selectedArr })
        });
        toast(r.message || 'Done');
        await refreshAll();
        await loadQueueDetail(_selectedQueuePath);
      } catch(e) { toast('Run failed: ' + e.message); }
    });
  }

  if ($('#queueSelectAllJobs')) {
    $('#queueSelectAllJobs').addEventListener('change', e => {
      const checked = e.target.checked;
      $$('.job-checkbox').forEach(chk => {
        chk.checked = checked;
        const tr = chk.closest('tr');
        if (tr && tr.dataset.jobId) {
          if (checked) selectedJobIds.add(tr.dataset.jobId);
          else selectedJobIds.delete(tr.dataset.jobId);
        }
      });
      updateRunSelectedButton();
    });
  }

  // Auto-refresh queue detail every 5s when the queues view is visible
  setInterval(() => {
    const v = $('#view-queues');
    if (v && v.classList.contains('active') && _selectedQueuePath) {
      loadQueueDetail(_selectedQueuePath);
    }
  }, 5000);
}

if (window.onSpriteForgeReady) {
  window.onSpriteForgeReady(initQueueMonitorBindings);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initQueueMonitorBindings, { once: true });
} else {
  initQueueMonitorBindings();
}
