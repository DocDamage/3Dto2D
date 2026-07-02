const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => Array.from(root.querySelectorAll(s));
let currentOutputs = [];
let selectedSpriteDir = '';
let lastLogText = '';
let recommendedAction = '';
let activeProjectPath = '';

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function toast(msg){
  const t=$('#toast');
  if (!t) return;
  t.textContent=msg;
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 3200);
}

function formData(form){
  const data={};
  new FormData(form).forEach((v,k)=>{data[k]=v});
  $$('input[type="checkbox"]', form).forEach(i=>data[i.name]=i.checked);
  return data;
}

const apiControllers = {};
let sessionTokenPromise = null;

async function getSessionToken() {
  if (!sessionTokenPromise) {
    sessionTokenPromise = fetch('/api/auth/token')
      .then(r => r.json())
      .then(data => {
        if (!data || !data.ok || !data.token) {
          throw new Error('Unable to initialize API session token');
        }
        return data.token;
      });
  }
  return sessionTokenPromise;
}

async function api(path, opts={}){
  const key = path.split('?')[0];
  if (apiControllers[key]) {
    try { apiControllers[key].abort(); } catch(e) {}
  }
  const controller = new AbortController();
  apiControllers[key] = controller;
  try {
    const method = String(opts.method || 'GET').toUpperCase();
    const headers = new Headers(opts.headers || {});
    if (method !== 'GET' && method !== 'HEAD' && !headers.has('X-SF-Token')) {
      headers.set('X-SF-Token', await getSessionToken());
    }
    if (typeof opts.body === 'string' && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const r=await fetch(path, { ...opts, headers, signal: controller.signal });
    const txt=await r.text();
    let data={};
    try{data=JSON.parse(txt)}catch{data={text:txt}}
    if(!r.ok) throw new Error(data.message||txt||r.statusText);
    return data;
  } catch(err) {
    if (err.name === 'AbortError') {
      return new Promise(() => {});
    }
    throw err;
  } finally {
    if (apiControllers[key] === controller) {
      delete apiControllers[key];
    }
  }
}


async function runAction(action, extra={}){
  // 1. Confirm before long jobs
  if (['generate_sprite', 'convert_video', 'character_pack', 'atlas', 'run_queue'].includes(action)) {
    if (localStorage.getItem('prefConfirmLongJobs') === 'true') {
      if (!confirm(`Confirm: Do you want to start this generation job? It will take several minutes.`)) {
        return;
      }
    }
  }

  // 2. Preflight validation check
  if (action === 'generate_sprite') {
    const params = new URLSearchParams({action, ...extra});
    try {
      const preflight = await api('/api/preflight/generation?' + params.toString());
      if (preflight.status !== 'pass') {
        const displayMsg = preflight.reasons.join(' ');
        showPreflightErrorBox(displayMsg, displayMsg.toLowerCase().includes('model') ? 'models' : 'comfy');
        if (!confirm(`Preflight ${preflight.status.toUpperCase()}:\n\n${preflight.reasons.join('\n')}\n\nStart anyway?`)) return;
      }
    } catch(e) {
      toast('Preflight check failed: ' + e.message);
      return;
    }
  }

  try {
    const data=await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,active_project:activeProjectPath,...extra})});
    if (data.warning === 'low_disk') {
      if (confirm(`${data.message}\n\nRunning this task might consume critical disk space. Proceed anyway?`)) {
        const forceData=await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,active_project:activeProjectPath,force:true,...extra})});
        toast(forceData.message||'Started (forced)');
        await refreshAll();
        if (localStorage.getItem('prefNeverAutoSwitch') !== 'true') {
          showView('logs');
        }
      }
      return;
    }
    toast(data.message||'Started');
    await refreshAll();

    // 3. Auto-switch to logs view unless disabled
    if (['generate_sprite', 'convert_video', 'character_pack', 'atlas', 'run_queue'].includes(action)) {
      if (localStorage.getItem('prefNeverAutoSwitch') !== 'true') {
        showView('logs');
      }
    }
  } catch(e) {
    let displayMsg = 'Error: ' + e.message;
    if (e.message && (e.message.includes('ComfyUI') || e.message.includes('offline')) || (action === 'generate_sprite' && window._latestStatus && !window._latestStatus.comfy_running)) {
      displayMsg = 'ComfyUI is offline. SpriteForge cannot generate until it is running.';
      showPreflightErrorBox(displayMsg, 'comfy');
    } else {
      toast(displayMsg);
      if (typeof addNotification === 'function') {
        addNotification('Task Did Not Start', displayMsg, 'error', { label: 'Open Logs', view: 'logs' });
      }
    }
  }
}

function showPreflightErrorBox(msg, type) {
  const box = $('#generateErrorBox');
  const msgEl = $('#generateErrorMsg');
  const actionsEl = $('#generateErrorActions');
  const debugEl = $('#generateErrorDebug');
  if (!box || !msgEl) return;

  box.classList.remove('hidden');
  msgEl.textContent = msg;
  clearNode(actionsEl);

  if (type === 'comfy') {
    const startBtn = document.createElement('button');
    startBtn.type = 'button';
    startBtn.className = 'mini primary';
    startBtn.textContent = 'Start ComfyUI';
    startBtn.addEventListener('click', async () => {
      try {
        await api('/api/launch_comfy', {method: 'POST'});
        toast('ComfyUI launch requested');
        box.classList.add('hidden');
        setTimeout(refreshAll, 1800);
      } catch (err) {
        toast(err.message);
      }
    });
    actionsEl.appendChild(startBtn);
  }

  if (debugEl) {
    debugEl.textContent = `Action: generate\nTimestamp: ${new Date().toISOString()}\nError Details: ${msg}\nStatus State: ${JSON.stringify(window._latestStatus || {}, null, 2)}`;
  }
}

async function openPath(path){
  try{
    await api('/api/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});
  }catch(e){
    toast(e.message);
  }
}

function setChip(id, state, text){
  const el=$(id);
  if (el) {
    el.className='chip '+state;
    el.textContent=text;
  }
}

window.SUBVIEW_PARENTS = {
  tasks: 'tasks-parent',
  launchpad: 'tasks-parent',
  queue: 'tasks-parent',
  queues: 'tasks-parent',
  
  quality: 'quality-parent',
  ab_runs: 'quality-parent',
  library: 'quality-parent',
  qa_dashboard: 'quality-parent'
};

window.NAV_VIEW_MAP = {
  'quality-parent': 'quality',
  'tasks-parent': 'tasks'
};

function showView(name){
  if (name === 'tasks-parent') name = 'tasks';
  if (name === 'quality-parent') name = 'quality';

  const parentName = window.SUBVIEW_PARENTS[name] || name;
  
  // Deactivate all top-level views except the active parent/view
  $$('.shell > .view').forEach(v => {
    const isCurrent = v.id === 'view-' + parentName;
    v.classList.toggle('active', isCurrent);
    if (isCurrent) {
      v.classList.remove('view-enter');
      void v.offsetWidth;
      v.classList.add('view-enter');
    }
  });

  // If it's a subview, activate the subview pane and tab button
  if (window.SUBVIEW_PARENTS[name]) {
    const parentEl = $('#view-' + parentName);
    if (parentEl) {
      parentEl.querySelectorAll('.view-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.subview === name);
      });
      parentEl.querySelectorAll('.subview-pane').forEach(pane => {
        const isCurrent = pane.id === 'view-' + name;
        pane.classList.toggle('active', isCurrent);
        if (isCurrent) {
          pane.classList.remove('view-enter');
          void pane.offsetWidth;
          pane.classList.add('view-enter');
        }
      });
    }
  }

  // Highlight active navigation menu button in sidebar
  const activeNavView = window.NAV_VIEW_MAP[parentName] || parentName;
  $$('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===activeNavView));

  // Sync hash (avoid infinite loop — only set if different)
  const hashView = location.hash.replace('#', '') || 'guide';
  if (hashView !== name) {
    history.pushState(null, '', '#' + name);
  }

  // Store for API polling context
  localStorage.setItem('activeView', name);

  if (name === 'library' && typeof refreshLibrary === 'function') refreshLibrary();
  if (name === 'qa_dashboard') {
    if (typeof loadProjectConfig === 'function') loadProjectConfig();
    if (typeof refreshQaDashboard === 'function') refreshQaDashboard();
  }
  if (name === 'ab_runs' && typeof refreshAbRuns === 'function') refreshAbRuns();
}

// Hash routing — browser back/forward navigates between tabs
window.addEventListener('hashchange', () => {
  const hash = location.hash.replace('#', '') || 'guide';
  const currentView = localStorage.getItem('activeView') || 'guide';
  if (hash !== currentView) {
    showView(hash);
  }
});

// Delegated click listener for tab switches inside parents
document.addEventListener('click', e => {
  const tabBtn = e.target.closest('.view-tab-btn');
  if (tabBtn) {
    const subview = tabBtn.dataset.subview;
    if (subview) showView(subview);
  }
});

function relativePath(p){ return p || ''; }

function clearNode(node){
  if (node) {
    while(node.firstChild) node.removeChild(node.firstChild);
  }
}

function appendText(parent, tag, text, className=''){
  const el=document.createElement(tag);
  if(className) el.className=className;
  el.textContent=text;
  if (parent) parent.appendChild(el);
  return el;
}

function tableEmpty(tbody, colspan, text){
  clearNode(tbody);
  const tr=document.createElement('tr');
  const td=document.createElement('td');
  td.colSpan=colspan;
  td.className='empty-cell';
  td.textContent=text;
  tr.appendChild(td);
  if (tbody) tbody.appendChild(tr);
}

function setTextState(node, text, className=''){
  clearNode(node);
  appendText(node, 'span', text, className);
}

function clampProgress(value){
  const n = Number(value);
  if(!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

function setProgressFill(fill, pct, state=''){
  if(!fill) return;
  const value = clampProgress(pct);
  fill.style.width = `${value}%`;
  fill.className = state || '';
  fill.dataset.percent = String(Math.round(value));
  fill.setAttribute('aria-valuenow', String(Math.round(value)));
}

function progressElement(pct, state=''){
  const wrap = document.createElement('div');
  wrap.className = 'task-progressbar compact';
  const fill = document.createElement('i');
  wrap.setAttribute('role', 'progressbar');
  wrap.setAttribute('aria-valuemin', '0');
  wrap.setAttribute('aria-valuemax', '100');
  setProgressFill(fill, pct, state);
  wrap.appendChild(fill);
  return wrap;
}

function inferredJobProgress(job, running){
  const raw = clampProgress(job?.progress);
  if(!running) return job?.exit_code === 0 ? 100 : raw;
  if(raw > 0) return raw;
  const title = String(job?.title || '').toLowerCase();
  const logs = (job?.logs || []).join('\n').toLowerCase();
  if(logs.includes('sheet:') || logs.includes('metadata:') || logs.includes('preview:')) return 95;
  if(logs.includes('converting video') || logs.includes('extract') || logs.includes('opencv')) return 72;
  if(logs.includes('history outputs') || logs.includes('chosen_output') || logs.includes('generated sprite output')) return 82;
  if(logs.includes('waiting for exact') || logs.includes('prompt history')) return 38;
  if(logs.includes('loading') || logs.includes('model') || logs.includes('weights')) return 18;
  if(title.includes('queue')) return 20;
  if(title.includes('install')) return 12;
  return 10;
}

function jobStageText(job, running){
  if(!job) return 'Ready';
  if(job.stage_label) {
    const suffix = job.progress_mode === 'reported' ? 'reported' : 'estimated';
    return running ? `${job.stage_label} · ${suffix}` : job.stage_label;
  }
  if(running) return 'Running';
  if(job.exit_code === 0) return 'Passed';
  if(job.exit_code !== null && job.exit_code !== undefined) return 'Failed';
  return 'Ready';
}

function jobStageDetail(job, running){
  if(!job) return 'No task running';
  if(job.stage_detail) return job.stage_detail;
  if(running) return 'Running now';
  return job.finished_at || 'Ready';
}

function renderGlobalProgress(job){
  const box = $('#globalTaskProgress');
  if(!box) return;
  const running = !!job?.running;
  const done = !running && job?.exit_code === 0;
  const failed = !running && job?.exit_code;
  const pct = inferredJobProgress(job || {}, running);
  box.classList.toggle('idle', !running && !done && !failed);
  box.classList.toggle('failed', !!failed);
  box.classList.toggle('done', !!done);
  $('#globalTaskTitle').textContent = running ? (job.title || 'Task running') : (done ? 'Last task complete' : failed ? 'Last task failed' : 'No task running');
  const eta = job?.metadata?.eta?.label ? ` · ETA ${job.metadata.eta.label}` : '';
  const mode = job?.progress_mode === 'comfy_ws' ? ' · exact ComfyUI progress' : '';
  $('#globalTaskDetail').textContent = running ? jobStageText(job, true) + ' — ' + jobStageDetail(job, true) + eta + mode : (done || failed ? jobStageDetail(job, false) : 'Ready');
  $('#globalProgressPct').textContent = `${Math.round(clampProgress(pct))}%`;
  setProgressFill($('#globalProgressFill'), pct, running ? 'busy' : done ? 'done' : failed ? 'failed' : '');
}

function projectQuery(){
  return activeProjectPath ? `?project=${encodeURIComponent(activeProjectPath)}` : '';
}

function mediaEmpty(text){
  const div = document.createElement('div');
  div.className = 'result-empty';
  div.textContent = text;
  return div;
}

function setPreviewLink(id, url){
  const el = $(id);
  if(!el) return;
  if(url){
    el.href = url;
    el.classList.remove('hidden');
  } else {
    el.href = '#';
    el.classList.add('hidden');
  }
}

function closeResultPreview(){
  const modal = $('#previewModal');
  if(!modal) return;
  modal.classList.add('hidden');
  const videoSlot = $('#previewVideoSlot');
  const spriteSlot = $('#previewSpriteSlot');
  if(videoSlot) clearNode(videoSlot);
  if(spriteSlot) clearNode(spriteSlot);
}

async function openResultPreview(spritePath){
  if(!spritePath){ toast('No sprite output selected.'); return; }
  try{
    const data = await api('/api/sprite/preview?path=' + encodeURIComponent(spritePath));
    const modal = $('#previewModal');
    const videoSlot = $('#previewVideoSlot');
    const spriteSlot = $('#previewSpriteSlot');
    if(!modal || !videoSlot || !spriteSlot) return;
    clearNode(videoSlot);
    clearNode(spriteSlot);

    $('#previewTitle').textContent = data.name || 'Review result';
    $('#previewSubtitle').textContent = data.path || '';
    $('#previewVideoMeta').textContent = data.video_path ? data.video_path.split('/').pop() : 'No source video found';
    $('#previewSpriteMeta').textContent = `${data.frame_count || '?'} frames · ${data.fps || '?'} fps · ${data.frame_width || '?'}×${data.frame_height || '?'}`;

    if(data.video_url){
      const video = document.createElement('video');
      video.controls = true;
      video.loop = true;
      video.muted = true;
      video.playsInline = true;
      video.src = data.video_url + '?t=' + Date.now();
      videoSlot.appendChild(video);
    } else {
      videoSlot.appendChild(mediaEmpty('Source video was not found for this older output.'));
    }

    const spriteUrl = data.preview_url || data.sheet_url;
    if(spriteUrl){
      const img = document.createElement('img');
      img.src = spriteUrl + '?t=' + Date.now();
      img.alt = data.name || 'Sprite preview';
      spriteSlot.appendChild(img);
    } else {
      spriteSlot.appendChild(mediaEmpty('No sprite preview image found.'));
    }

    $('#previewOpenFolder').dataset.openPath = data.path || spritePath;
    $('#previewUseForQuality').dataset.spritePath = data.path || spritePath;
    setPreviewLink('#previewOpenSheet', data.sheet_url || data.preview_url || '');
    setPreviewLink('#previewOpenReport', data.report_url || data.qa_url || '');
    setPreviewLink('#previewOpenContactSheet', data.contact_sheet_url || '');

    const qaGate = data.qa_gate || {};
    const qaBadge = $('#previewQaStatusBadge');
    if (qaBadge) {
      qaBadge.textContent = (qaGate.status || 'warning').toUpperCase();
      qaBadge.className = 'badge ' + (qaGate.status === 'pass' ? 'ok' : qaGate.status === 'fail' ? 'bad' : 'warn');
    }
    const loopVal = data.qa_report?.metrics?.loop_seam_rmse;
    const driftVal = data.qa_report?.metrics?.foot_y_stdev_px || data.qa_report?.metrics?.center_x_stdev_px;
    if ($('#previewLoopRmseVal')) $('#previewLoopRmseVal').textContent = loopVal == null ? '—' : Number(loopVal).toFixed(2);
    if ($('#previewFootDriftVal')) $('#previewFootDriftVal').textContent = driftVal == null ? '—' : Number(driftVal).toFixed(2);
    const issues = $('#previewQaIssues');
    if (issues) {
      clearNode(issues);
      (qaGate.reasons || []).forEach(reason => appendText(issues, 'div', reason));
    }
    const starBtn = $('#previewStarResult');
    const rejectBtn = $('#previewRejectResult');
    const rerunBtn = $('#previewRerunSimilar');
    const experimentId = data.experiment?.id || '';
    [starBtn, rejectBtn, rerunBtn].forEach(btn => { if (btn) btn.disabled = !experimentId; });
    if (starBtn) starBtn.dataset.experimentId = experimentId;
    if (rejectBtn) rejectBtn.dataset.experimentId = experimentId;
    if (rerunBtn) rerunBtn.dataset.experimentId = experimentId;
    modal.classList.remove('hidden');
  } catch(e){
    toast('Preview failed: ' + e.message);
  }
}

function makeSparkline(values, strokeColor, options = {}) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = options.width || 240;
  const height = options.height || 30;
  const strokeWidth = options.strokeWidth || '1.5';
  const padding = options.padding || 3;
  const contentHeight = height - padding * 2;

  const coords = values.map((val, i) => {
    const x = values.length > 1 ? (i / (values.length - 1)) * width : 0;
    const y = height - padding - ((val - min) / range) * contentHeight;
    return `${x},${y}`;
  }).join(' ');

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  if (options.className) svg.setAttribute('class', options.className);
  if (options.style) {
    Object.entries(options.style).forEach(([k, v]) => {
      svg.style[k] = v;
    });
  }
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));

  const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', strokeColor);
  line.setAttribute('stroke-width', String(strokeWidth));
  line.setAttribute('points', coords);
  svg.appendChild(line);
  return svg;
}

function makeTinySparkline(values, strokeColor) {
  return makeSparkline(values, strokeColor, {
    width: 80,
    height: 18,
    strokeWidth: '1.2',
    padding: 2,
    style: { verticalAlign: 'middle', marginLeft: '6px' }
  });
}

function makeMultiLineChart(points) {
  const width = 240;
  const height = 40;

  const drifts = points.map(p => p.drift);
  const seams = points.map(p => p.seam);

  const maxDrift = Math.max(...drifts, 1);
  const maxSeam = Math.max(...seams, 1);

  const driftCoords = points.map((p, i) => {
    const x = points.length > 1 ? (i / (points.length - 1)) * width : 0;
    const y = height - 3 - (p.drift / maxDrift) * (height - 6);
    return `${x},${y}`;
  }).join(' ');

  const seamCoords = points.map((p, i) => {
    const x = points.length > 1 ? (i / (points.length - 1)) * width : 0;
    const y = height - 3 - (p.seam / maxSeam) * (height - 6);
    return `${x},${y}`;
  }).join(' ');

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));

  const driftLine = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  driftLine.setAttribute('fill', 'none');
  driftLine.setAttribute('stroke', '#ffd166');
  driftLine.setAttribute('stroke-width', '1.5');
  driftLine.setAttribute('points', driftCoords);
  svg.appendChild(driftLine);

  const seamLine = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  seamLine.setAttribute('fill', 'none');
  seamLine.setAttribute('stroke', '#3498db');
  seamLine.setAttribute('stroke-width', '1.5');
  seamLine.setAttribute('points', seamCoords);
  svg.appendChild(seamLine);

  return svg;
}
