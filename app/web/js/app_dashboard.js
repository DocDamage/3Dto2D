// app_dashboard.js — Health bar, task center, failure recovery, project dashboard, cleanup

function formatDuration(start, finish) {
  if (!start) return '—';
  const s = new Date(start), f = finish ? new Date(finish) : new Date();
  const diffMs = f - s; if (diffMs < 0 || isNaN(diffMs)) return '—';
  const diffSecs = Math.floor(diffMs / 1000), mins = Math.floor(diffSecs / 60), secs = diffSecs % 60;
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

function updateHealthBar(s) {
  if (!s) return;
  const dotComfy = $('#health-dot-comfy'), valComfy = $('#health-val-comfy'), btnComfy = $('#healthLaunchComfyBtn');
  if (dotComfy && valComfy) { dotComfy.style.background = s.comfy_running ? 'var(--green)' : 'var(--danger)'; valComfy.textContent = s.comfy_running ? 'online' : 'offline'; if (btnComfy) btnComfy.classList.toggle('hidden', s.comfy_running); }
  const dotModels = $('#health-dot-models'), valModels = $('#health-val-models');
  if (dotModels && valModels) { const present = s.models ? s.models.present : 0; const total = s.models ? s.models.total : 0; dotModels.style.background = (s.models && s.models.ok) ? 'var(--green)' : (present > 0 ? 'var(--yellow)' : 'var(--danger)'); valModels.textContent = `${present}/${total} files`; }
  const dotVram = $('#health-dot-vram'), valVram = $('#health-val-vram');
  if (dotVram && valVram) { if (s.gpu && s.gpu.vram_gb !== undefined) { const free = s.gpu.vram_free_gb || 0; const total = s.gpu.vram_gb || 12; const used = s.gpu.vram_allocated_gb || (total - free); const usedPct = (used / total) * 100; dotVram.style.background = usedPct > 90 ? 'var(--danger)' : (usedPct > 65 ? 'var(--yellow)' : 'var(--green)'); valVram.textContent = `${used.toFixed(1)} GB / ${total.toFixed(0)} GB (${Math.round(usedPct)}%)`; } else { dotVram.style.background = s.gpu && s.gpu.ok ? 'var(--green)' : 'var(--danger)'; valVram.textContent = s.gpu && s.gpu.ok ? (s.gpu.label || 'Supported') : 'N/A'; } }
  const dotDisk = $('#health-dot-disk'), valDisk = $('#health-val-disk');
  if (dotDisk && valDisk) { const freeGb = s.disk ? s.disk.free_gb : 0; dotDisk.style.background = s.disk && s.disk.ok ? 'var(--green)' : 'var(--danger)'; valDisk.textContent = `${freeGb} GB free`; }
  const dotQueue = $('#health-dot-queue'), valQueue = $('#health-val-queue');
  if (dotQueue && valQueue) { const active = s.job && s.job.running; dotQueue.style.background = active ? 'var(--yellow)' : '#888'; const qCount = s.project_workspace ? s.project_workspace.queues : 0; valQueue.textContent = active ? 'busy' : (qCount > 0 ? `${qCount} queued` : 'idle'); }
  const errorDivider = $('#health-divider-error'), errorItem = $('#health-item-error'), errorVal = $('#health-val-error');
  if (errorDivider && errorItem && errorVal) {
    if (s.job && s.job.exit_code !== null && s.job.exit_code !== 0) { errorDivider.classList.remove('hidden'); errorItem.classList.remove('hidden'); errorVal.textContent = s.job.title || 'Failed'; }
    else { errorDivider.classList.add('hidden'); errorItem.classList.add('hidden'); }
  }
}

function renderTaskCenter(s) {
  const activeJob = s.job, running = activeJob && activeJob.running;
  const ar = $('#activeTaskRunningArea'), ai = $('#activeTaskIdleArea'), at = $('#activeTaskTitle'), ast = $('#activeTaskState');
  const pf = $('#activeTaskProgressFill'), pp = $('#activeTaskProgressPct'), tm = $('#activeTaskTimeState'), te = $('#activeTaskTerminal'), ib = $('#activeTaskInspectBtn');
  if (running) { if (ar) ar.classList.remove('hidden'); if (ai) ai.classList.add('hidden'); if (at) at.textContent = activeJob.title || 'Task running'; if (ast) { ast.textContent = 'running'; ast.className = 'badge busy'; }
    const pct = typeof inferredJobProgress === 'function' ? inferredJobProgress(activeJob, true) : (activeJob.progress || 0); if (pf) pf.style.width = `${pct}%`; if (pp) pp.textContent = `${Math.round(pct)}%`;
    const dur = formatDuration(activeJob.started_at, null), st = typeof jobStageText === 'function' ? jobStageText(activeJob, true) : '', dt = typeof jobStageDetail === 'function' ? jobStageDetail(activeJob, true) : '';
    if (tm) tm.textContent = `Running: ${dur} · ${st} · ${dt}`; const logs = (activeJob.logs || []).join('\n'); if (te) { te.textContent = logs; te.scrollTop = te.scrollHeight; } if (ib) ib.classList.add('hidden'); }
  else { if (ast) { ast.textContent = activeJob && activeJob.exit_code !== null ? (activeJob.exit_code === 0 ? 'done' : 'failed') : 'idle'; ast.className = 'badge ' + (activeJob && activeJob.exit_code === 0 ? '' : (activeJob && activeJob.exit_code !== null ? 'danger' : 'muted')); }
    if (activeJob && activeJob.exit_code !== null) { if (ar) ar.classList.remove('hidden'); if (ai) ai.classList.add('hidden'); if (at) at.textContent = activeJob.title || 'Task complete';
      const pct = activeJob.exit_code === 0 ? 100 : (typeof inferredJobProgress === 'function' ? inferredJobProgress(activeJob, false) : 0); if (pf) pf.style.width = `${pct}%`; if (pp) pp.textContent = `${Math.round(pct)}%`;
      const dur = formatDuration(activeJob.started_at, activeJob.finished_at), st = typeof jobStageText === 'function' ? jobStageText(activeJob, false) : '', dt = typeof jobStageDetail === 'function' ? jobStageDetail(activeJob, false) : '';
      if (tm) tm.textContent = `Duration: ${dur} · ${st} · ${dt}`; if (te) te.textContent = (activeJob.logs || []).join('\n');
      const sf = activeJob.metadata ? activeJob.metadata.sprite_folder : null; if (ib && sf) { ib.classList.remove('hidden'); ib.dataset.spriteFolder = sf; } else if (ib) ib.classList.add('hidden'); }
    else { if (ar) ar.classList.add('hidden'); if (ai) ai.classList.remove('hidden'); } }
  checkFailureRecovery(activeJob);
}

async function loadTasksHistory() {
  try { const data = await api('/api/job/history'); const tbody = $('#tasksHistoryBody'); if (!tbody) return; const h = data.history || [];
    if (!h.length) { tableEmpty(tbody, 6, 'No execution history found.'); return; } clearNode(tbody);
    h.forEach(j => { const tr = document.createElement('tr'); const tc = tr.appendChild(document.createElement('td')); tc.style.fontWeight = 'bold'; tc.textContent = j.title || 'Job';
      tr.appendChild(Object.assign(document.createElement('td'), {className: 'nowrap muted-cell', textContent: j.started_at ? new Date(j.started_at).toLocaleString() : '—'}));
      tr.appendChild(Object.assign(document.createElement('td'), {className: 'nowrap', textContent: formatDuration(j.started_at, j.finished_at)}));
      tr.appendChild(Object.assign(document.createElement('td'), {className: 'mono-cell', textContent: j.exit_code !== null ? String(j.exit_code) : '—'}));
      const sc = document.createElement('td'), b = document.createElement('span'); b.className = 'badge';
      b.textContent = j.exit_code === 0 ? 'done' : 'failed'; b.style.background = j.exit_code === 0 ? 'var(--green)' : 'var(--danger)'; sc.appendChild(b); tr.appendChild(sc);
      const ac = document.createElement('td'); ac.className = 'button-row compact-actions';
      const lb = Object.assign(document.createElement('button'), {className: 'mini', textContent: 'View Logs', onclick: async () => { try { const d = await api(`/api/job/detail?id=${j.id}`); const aa = $('#activeTaskRunningArea'), ai2 = $('#activeTaskIdleArea'); if (aa) aa.classList.remove('hidden'); if (ai2) ai2.classList.add('hidden'); if ($('#activeTaskTitle')) $('#activeTaskTitle').textContent = `Historical: ${d.title}`; if ($('#activeTaskState')) { $('#activeTaskState').textContent = d.exit_code === 0 ? 'done' : 'failed'; $('#activeTaskState').className = 'badge ' + (d.exit_code === 0 ? '' : 'danger'); } if ($('#activeTaskProgressFill')) $('#activeTaskProgressFill').style.width = d.exit_code === 0 ? '100%' : '50%'; if ($('#activeTaskProgressPct')) $('#activeTaskProgressPct').textContent = d.exit_code === 0 ? '100%' : 'Failed'; if ($('#activeTaskTimeState')) $('#activeTaskTimeState').textContent = `⏱ Duration: ${formatDuration(d.started_at, d.finished_at)}`; if ($('#activeTaskTerminal')) $('#activeTaskTerminal').textContent = (d.full_logs || []).join('\n'); const sf = d.metadata ? d.metadata.sprite_folder : null; const ib2 = $('#activeTaskInspectBtn'); if (ib2 && sf) { ib2.classList.remove('hidden'); ib2.dataset.spriteFolder = sf; } else if (ib2) ib2.classList.add('hidden'); toast('Loaded historical job log'); } catch (err) { toast('Failed to load logs: ' + err.message); } } }); ac.appendChild(lb);
      const rb = Object.assign(document.createElement('button'), {className: 'mini primary', textContent: 'Retry', onclick: async () => { try { toast('Retrying job...'); const r = await api('/api/job/retry', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: j.id }) }); if (r.ok) { toast('Job retried successfully!'); showView('logs'); await refreshAll(); } else { toast('Retry failed: ' + r.message); } } catch (err) { toast('Retry error: ' + err.message); } } }); ac.appendChild(rb); tr.appendChild(ac); tbody.appendChild(tr); }); } catch (e) { console.error('History load failed:', e); }
}

async function loadQueuedJobs() {
  try { const tbody = $('#queuedTasksBody'), cb = $('#queuedTasksCount'); if (!tbody) return; const d = await api('/api/queues' + projectQuery()); const qs = d.queues || [];
    const rq = qs.find(q => q.progress && q.progress.running); if (!rq) { tableEmpty(tbody, 6, 'No active queue processing.'); if (cb) { cb.textContent = '0 pending'; cb.className = 'badge muted'; } return; }
    const dd = await api('/api/queues/detail?path=' + encodeURIComponent(rq.path)); const jobs = dd.jobs || [], pj = jobs.filter(j => j.status === 'pending' || j.status === 'running');
    if (cb) { cb.textContent = `${pj.length} pending`; cb.className = 'badge busy'; } if (!jobs.length) { tableEmpty(tbody, 6, 'Queue is empty.'); return; } clearNode(tbody);
    jobs.slice(0, 10).forEach(j => { const tr = document.createElement('tr'); appendText(tr, 'td', j.id || '', 'mono-cell'); appendText(tr, 'td', j.action || ''); appendText(tr, 'td', j.direction || '');
      const sc = document.createElement('td'), b = document.createElement('span'); b.className = `queue-status ${typeof queueStatusClass === 'function' ? queueStatusClass(j.status) : ''}`; b.textContent = j.status || 'pending'; sc.appendChild(b); tr.appendChild(sc);
      const pc = document.createElement('td'), jp = j.progress || {}; pc.appendChild(typeof progressElement === 'function' ? progressElement(jp.percent || 0, j.status === 'running' ? 'busy' : j.status === 'done' ? 'done' : '') : document.createTextNode(`${jp.percent || 0}%`)); tr.appendChild(pc);
      const ac = document.createElement('td'); ac.className = 'button-row compact-actions'; if (j.log) { const lb = document.createElement('button'); lb.className = 'mini'; lb.textContent = 'Open Log'; lb.addEventListener('click', () => openPath(j.log)); ac.appendChild(lb); } else ac.textContent = '—'; tr.appendChild(ac); tbody.appendChild(tr); }); } catch (e) { console.error('Queued jobs load failed:', e); }
}

function checkFailureRecovery(job) {
  const ra = $('#activeRecoveryAdvisor'), rm = $('#activeRecoveryMessage'), rc = $('#activeRecoveryActions'); if (!ra || !rm || !rc) return;
  if (!job || job.running || job.exit_code === null || job.exit_code === 0) { ra.classList.add('hidden'); return; }
  const logs = (job.logs || []).join('\n').toLowerCase(); let ro = null;
  if (logs.includes('comfyui') && (logs.includes('offline') || logs.includes('connection') || logs.includes('refused'))) ro = { message: 'ComfyUI appears to be offline.', actionLabel: 'Start ComfyUI', run: async () => { try { await api('/api/launch_comfy', {method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll, 1800); } catch (err) { toast(err.message); } } };
  else if (logs.includes('model') && (logs.includes('missing') || logs.includes('not found') || logs.includes('download'))) ro = { message: 'A model file is missing or failed to download.', actionLabel: 'Repair models', run: () => { showView('setup'); toast('Click "Repair Safe Model Download"'); } };
  else if (logs.includes('video not found') || logs.includes('filenotfounderror')) ro = { message: 'Input video was not found.', actionLabel: 'Open output', run: () => { openPath('output'); } };
  else if (logs.includes('chroma') || logs.includes('green-screen') || logs.includes('keying') || logs.includes('alpha')) ro = { message: 'Chroma keying failed.', actionLabel: 'Reconvert', run: () => { showView('convert'); toast('Adjust green-screen thresholds'); } };
  else if (logs.includes('disk') || logs.includes('space') || logs.includes('nospace') || logs.includes('out of memory')) ro = { message: 'Low disk space or memory.', actionLabel: 'Cleanup', run: () => { showView('cleanup'); if (typeof scanCleanup === 'function') scanCleanup(); } };
  if (ro) { rm.textContent = ro.message; clearNode(rc); const ab = document.createElement('button'); ab.className = 'mini primary'; ab.textContent = ro.actionLabel; ab.addEventListener('click', ro.run); rc.appendChild(ab);
    const sr = document.createElement('button'); sr.className = 'mini'; sr.textContent = 'Retry with safer settings';
    sr.addEventListener('click', async () => { try { const res = await api('/api/job/retry_safe', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: job.id}) }); toast(res.message || 'Safer retry started'); showView('logs'); await refreshAll(); } catch(err) { toast('Safer retry failed: ' + err.message); } }); rc.appendChild(sr); ra.classList.remove('hidden'); }
  else { ra.classList.add('hidden'); }
}

async function renderProjectDashboard(s) {
  const hub = $('#projectDashboardHub'); if (!hub) return; if (!activeProjectPath) { hub.classList.add('hidden'); return; } hub.classList.remove('hidden');
  const drl = $('#dashReferencesList'), dql = $('#dashQueuesList'), drl2 = $('#dashReleasesList');
  try { const rd = await api('/api/references' + projectQuery()); clearNode(drl); const refs = rd.references || [];
    if (!refs.length) appendText(drl, 'div', 'No references uploaded.', 'empty compact');
    else refs.slice(0, 3).forEach(ref => { const it = document.createElement('div'); Object.assign(it.style, {padding:'8px', background:'rgba(255,255,255,0.02)', border:'1px solid var(--line)', borderRadius:'6px', marginBottom:'6px', fontSize:'12px'}); it.innerHTML = `<b style="display:block;">${ref.name}</b><span style="color:var(--muted);font-size:11px;">${ref.modified||''}</span>`; drl.appendChild(it); }); } catch (e) { console.error(e); }
  try { const qd = await api('/api/queues' + projectQuery()); clearNode(dql); const qs = qd.queues || [];
    if (!qs.length) appendText(dql, 'div', 'No persistent queues.', 'empty compact');
    else qs.slice(0, 3).forEach(q => { const it = document.createElement('div'); Object.assign(it.style, {padding:'8px', background:'rgba(255,255,255,0.02)', border:'1px solid var(--line)', borderRadius:'6px', marginBottom:'6px', fontSize:'12px'}); const qp = q.progress || {percent:0}; it.innerHTML = `<b style="display:block;">${q.name}</b><span style="color:var(--muted);font-size:11px;">Progress: ${Math.round(qp.percent)}% (${q.total} jobs)</span>`; dql.appendChild(it); }); } catch (e) { console.error(e); }
  try { const rld = await api('/api/releases' + projectQuery()); clearNode(drl2); const rls = rld.releases || [];
    if (!rls.length) appendText(drl2, 'div', 'No releases built.', 'empty compact');
    else rls.slice(0, 3).forEach(r => { const it = document.createElement('div'); Object.assign(it.style, {padding:'8px', background:'rgba(255,255,255,0.02)', border:'1px solid var(--line)', borderRadius:'6px', marginBottom:'6px', fontSize:'12px'}); it.innerHTML = `<b style="display:block;">${r.name}</b><span style="color:var(--muted);font-size:11px;">${r.sprite_count} sprites · ${r.modified||''}</span>`; drl2.appendChild(it); }); } catch (e) { console.error(e); }
}

let scannedCleanupFiles = [];
async function scanCleanup() { const btn = $('#scanCleanupBtn'); if (btn) { btn.disabled = true; btn.textContent = 'Scanning...'; } try { const res = await api('/api/cleanup/scan'); scannedCleanupFiles = res.files || []; renderCleanupTable(); } catch(e) { toast('Scan failed: ' + e.message); } finally { if (btn) { btn.disabled = false; btn.textContent = 'Scan Workspace'; } } }
function formatBytes(bytes) { if (!bytes) return '0 Bytes'; const k = 1024, sizes = ['Bytes', 'KB', 'MB', 'GB'], i = Math.floor(Math.log(bytes) / Math.log(k)); return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]; }
function formatAge(mtime) { if (!mtime) return '—'; const dm = Date.now() - (mtime * 1000), dh = Math.floor(dm / 3600000); if (dh < 1) return 'Just now'; if (dh < 24) return `${dh} hours old`; return `${Math.floor(dh / 24)} days old`; }
function renderCleanupTable() {
  const tbody = $('#cleanupTableBody'), te = $('#cleanup-total-space'), rse = $('#cleanup-renders-space'), rce = $('#cleanup-renders-count'), fse = $('#cleanup-failed-space'), fce = $('#cleanup-failed-count'), lse = $('#cleanup-logs-space'), lce = $('#cleanup-logs-count'), pb = $('#purgeCleanupSelectedBtn'), sa = $('#cleanupSelectAll');
  if (sa) sa.checked = false; if (pb) pb.disabled = true;
  if (!scannedCleanupFiles.length) { tableEmpty(tbody, 5, 'No cleanup targets found.'); if (te) te.textContent = '0.0 MB'; if (rse) rse.textContent = '0.0 MB'; if (rce) rce.textContent = '0 files'; if (fse) fse.textContent = '0.0 MB'; if (fce) fce.textContent = '0 folders'; if (lse) lse.textContent = '0.0 MB'; if (lce) lce.textContent = '0 files'; return; }
  clearNode(tbody); let tb = 0; const cats = {'ComfyUI Render Outputs': {bytes:0,count:0}, 'Uploaded Reference Videos': {bytes:0,count:0}, 'Failed / Incomplete Outputs': {bytes:0,count:0}, 'Old Task Logs': {bytes:0,count:0}};
  scannedCleanupFiles.forEach(f => { tb += f.size; const c = f.category || 'Other'; if (!cats[c]) cats[c] = {bytes:0,count:0}; cats[c].bytes += f.size; cats[c].count++;
    const tr = document.createElement('tr'), cc = document.createElement('td'), chk = document.createElement('input'); chk.type = 'checkbox'; chk.className = 'cleanup-checkbox'; chk.value = f.id; chk.addEventListener('change', () => { const cnt = $$('.cleanup-checkbox:checked').length; if (pb) { pb.disabled = cnt === 0; pb.textContent = `Delete Selected (${cnt})`; } }); cc.appendChild(chk); tr.appendChild(cc);
    appendText(tr, 'td', f.category || 'Other', 'nowrap muted-cell'); const pc = appendText(tr, 'td', f.path || ''); pc.style.wordBreak = 'break-all'; appendText(tr, 'td', formatBytes(f.size), 'nowrap'); appendText(tr, 'td', formatAge(f.mtime), 'nowrap muted-cell'); tbody.appendChild(tr); });
  if (te) te.textContent = `${(tb / (1024 * 1024)).toFixed(1)} MB`; const renders = cats['ComfyUI Render Outputs'] || {bytes:0,count:0}, failed = cats['Failed / Incomplete Outputs'] || {bytes:0,count:0}, logs = cats['Old Task Logs'] || {bytes:0,count:0};
  if (rse) rse.textContent = `${(renders.bytes / (1024 * 1024)).toFixed(1)} MB`; if (rce) rce.textContent = `${renders.count} files`; if (fse) fse.textContent = `${(failed.bytes / (1024 * 1024)).toFixed(1)} MB`; if (fce) fce.textContent = `${failed.count} folders`; if (lse) lse.textContent = `${(logs.bytes / (1024 * 1024)).toFixed(1)} MB`; if (lce) lce.textContent = `${logs.count} files`;
}
async function purgeSelectedCleanup() { const checked = $$('.cleanup-checkbox:checked').map(chk => chk.value); if (!checked.length) return; if (!confirm(`Delete ${checked.length} selected files?`)) return; try { toast(`Purging ${checked.length} files...`); const res = await api('/api/cleanup/purge', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ids: checked }) }); if (res.ok) { toast(`Deleted ${res.count} items, reclaimed ${res.reclaimed_mb} MB.`); await scanCleanup(); } else toast('Purge failed: ' + res.message); } catch(e) { toast('Purge error: ' + e.message); } }

function initDashboardBindings() {
  if ($('#healthLaunchComfyBtn')) $('#healthLaunchComfyBtn').addEventListener('click', async () => { try { await api('/api/launch_comfy', {method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll, 1800); } catch(err) { toast(err.message); } });
  if ($('#health-item-error')) $('#health-item-error').addEventListener('click', () => showView('tasks'));
  if ($('#activeTaskCancelBtn')) $('#activeTaskCancelBtn').addEventListener('click', () => api('/api/cancel', {method:'POST'}).then(refreshAll));
  if ($('#activeTaskCopyLogsBtn')) $('#activeTaskCopyLogsBtn').addEventListener('click', () => { const t = $('#activeTaskTerminal'); if (t) navigator.clipboard.writeText(t.textContent || '').then(() => toast('Active logs copied')); });
  if ($('#activeTaskInspectBtn')) $('#activeTaskInspectBtn').addEventListener('click', e => { const f = e.currentTarget.dataset.spriteFolder; if (f && typeof openResultPreview === 'function') openResultPreview(f); });
  if ($('#refreshTasksHistoryBtn')) $('#refreshTasksHistoryBtn').addEventListener('click', () => { loadTasksHistory(); loadQueuedJobs(); });
  if ($('#scanCleanupBtn')) $('#scanCleanupBtn').addEventListener('click', scanCleanup);
  if ($('#purgeCleanupSelectedBtn')) $('#purgeCleanupSelectedBtn').addEventListener('click', purgeSelectedCleanup);
  if ($('#cleanupSelectAll')) $('#cleanupSelectAll').addEventListener('change', e => { $$('.cleanup-checkbox').forEach(chk => { chk.checked = e.target.checked; }); const c = $$('.cleanup-checkbox:checked').length, pb = $('#purgeCleanupSelectedBtn'); if (pb) { pb.disabled = c === 0; pb.textContent = `Delete Selected (${c})`; } });
  if ($('#autoCleanBtn')) $('#autoCleanBtn').addEventListener('click', async () => { const ids = scannedCleanupFiles.filter(f => f.category === 'Failed / Incomplete Outputs' || f.category === 'Old Task Logs').map(f => f.id); if (!ids.length) { toast('Nothing to clean.'); return; } if (!confirm(`Purge ${ids.length} failed outputs and old logs?`)) return; try { toast(`Auto-cleaning ${ids.length} items...`); const res = await api('/api/cleanup/purge', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ids }) }); if (res.ok) { toast(`Deleted ${res.count} items, reclaimed ${res.reclaimed_mb} MB.`); await scanCleanup(); } else toast('Clean failed: ' + res.message); } catch(e) { toast('Clean error: ' + e.message); } });
}