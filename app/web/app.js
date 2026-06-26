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

function toast(msg){ const t=$('#toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'), 3200); }
function formData(form){ const data={}; new FormData(form).forEach((v,k)=>{data[k]=v}); $$('input[type="checkbox"]', form).forEach(i=>data[i.name]=i.checked); return data; }
async function api(path, opts={}){ const r=await fetch(path, opts); const txt=await r.text(); let data={}; try{data=JSON.parse(txt)}catch{data={text:txt}} if(!r.ok) throw new Error(data.message||txt||r.statusText); return data; }
async function runAction(action, extra={}){
  // 1. Confirm before long jobs (Requirement 10)
  if (['generate_sprite', 'convert_video', 'character_pack', 'atlas', 'run_queue'].includes(action)) {
    if (localStorage.getItem('prefConfirmLongJobs') === 'true') {
      if (!confirm(`Confirm: Do you want to start this generation job? It will take several minutes.`)) {
        return;
      }
    }
  }

  // 2. Preflight validation check (Requirement 6)
  if (action === 'generate_sprite') {
    const status = window._latestStatus;
    if (status) {
      if (!status.comfy_running) {
        const displayMsg = 'ComfyUI is offline. SpriteForge cannot generate until it is running.';
        showPreflightErrorBox(displayMsg, 'comfy');
        return;
      }
      if (!status.models.ok) {
        const displayMsg = 'WAN model files are missing. Check WAN Models checkmarks or repair downloads in Setup.';
        showPreflightErrorBox(displayMsg, 'models');
        return;
      }
    }
  }

  try {
    const data=await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,active_project:activeProjectPath,...extra})});
    toast(data.message||'Started');
    await refreshAll();
    
    // 3. Auto-switch to logs view unless disabled (Requirement 10)
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

async function openPath(path){ try{ await api('/api/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})}); }catch(e){ toast(e.message); } }
function setChip(id, state, text){ const el=$(id); el.className='chip '+state; el.textContent=text; }
function showView(name){
  $$('.view').forEach(v=>v.classList.remove('active'));
  $('#view-'+name)?.classList.add('active');
  $$('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===name));
  
  localStorage.setItem('activeView', name);
  
  // Update Step Map (Requirement 2)
  $$('.step-map-item').forEach(item => {
    let active = false;
    const step = item.dataset.step;
    if (step === 'setup') active = ['setup', 'launchpad'].includes(name);
    else if (step === 'describe') active = ['guide', 'generate', 'convert'].includes(name);
    else if (step === 'generate') active = ['queue', 'queues', 'logs'].includes(name);
    else if (step === 'review') active = ['quality'].includes(name);
    else if (step === 'export') active = ['packs', 'release'].includes(name);
    item.classList.toggle('active', active);
  });
}
function relativePath(p){ return p || ''; }
function clearNode(node){ while(node.firstChild) node.removeChild(node.firstChild); }
function appendText(parent, tag, text, className=''){
  const el=document.createElement(tag);
  if(className) el.className=className;
  el.textContent=text;
  parent.appendChild(el);
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
  tbody.appendChild(tr);
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
}
function progressElement(pct, state=''){
  const wrap = document.createElement('div');
  wrap.className = 'task-progressbar compact';
  const fill = document.createElement('i');
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
  $('#globalTaskDetail').textContent = running ? 'Running now' : (job?.finished_at || 'Ready');
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
    modal.classList.remove('hidden');
  } catch(e){
    toast('Preview failed: ' + e.message);
  }
}

function renderProjectSummary(workspace){
  const el = $('#projectSummary');
  if(!el) return;
  if(!workspace || !workspace.active){
    el.textContent = 'Global workspace';
    return;
  }
  el.textContent = `${workspace.active.project_name}: ${workspace.outputs} outputs · ${workspace.references || 0} refs · ${workspace.prompts || 0} prompts · ${workspace.posepacks || 0} posepacks · ${workspace.quality || 0} QA · ${workspace.experiments} runs · ${workspace.queues} queues · ${workspace.releases || 0} releases`;
}

function renderOutputs(outputs){
  currentOutputs = outputs || [];
  $('#stat-outputs').textContent = currentOutputs.length;
  const g=$('#gallery');
  clearNode(g);
  if(!currentOutputs.length){
    appendText(g, 'div', 'No sprite outputs yet. Run the demo or make a sprite.', 'empty');
    renderGuidedGallery(currentOutputs);
    return;
  }
  currentOutputs.slice(0,12).forEach(o => {
    const card = document.createElement('article');
    card.className = 'sprite-card';
    card.dataset.path = o.path || '';
    const imgUrl = o.preview_url || o.sheet_url || '';
    if (imgUrl) {
      const img = document.createElement('img');
      img.src = `${imgUrl}?t=${Date.now()}`;
      img.alt = o.name || '';
      card.appendChild(img);
    } else {
      appendText(card, 'div', 'No preview', 'placeholder');
    }
    const meta = document.createElement('div');
    meta.className = 'meta';
    appendText(meta, 'b', o.name || '');
    appendText(meta, 'small', `${o.frame_count} frames · ${o.fps} fps · ${o.frame_width}×${o.frame_height}`);
    appendText(meta, 'small', o.modified || '');
    const actions = document.createElement('div');
    actions.className = 'button-row compact-actions';
    const review = document.createElement('button');
    review.type = 'button';
    review.className = 'mini primary';
    review.dataset.previewPath = o.path || '';
    review.textContent = 'Review';
    actions.appendChild(review);
    meta.appendChild(actions);
    card.appendChild(meta);
    g.appendChild(card);
  });
  $$('.sprite-card', g).forEach(card=>card.addEventListener('click',(e)=>{
    if (e.target.closest('[data-preview-path]')) return;
    selectedSpriteDir=card.dataset.path;
    $('#qualitySpriteDir').value=selectedSpriteDir;
    if($('#releaseSprites') && !$('#releaseSprites').value.includes(selectedSpriteDir)){
      $('#releaseSprites').value = ($('#releaseSprites').value ? $('#releaseSprites').value+'\n' : '') + selectedSpriteDir;
    }
    showView('quality');
    toast('Selected '+selectedSpriteDir);
    loadSpriteDetails(selectedSpriteDir);
  }));
  $$('[data-preview-path]', g).forEach(btn=>btn.addEventListener('click', e=>{
    e.stopPropagation();
    openResultPreview(e.currentTarget.dataset.previewPath);
  }));
  renderGuidedGallery(currentOutputs);
}

function renderJob(job){
  const running=!!job.running;
  const progress = inferredJobProgress(job, running);
  $('#job-title').textContent=job.title||'Idle'; $('#log-title').textContent=job.title||'Idle';
  $('#job-state').textContent=running?'running':(job.exit_code===0?'done':(job.exit_code?'failed':'ready'));
  $('#job-state').className='badge '+(running?'busy':'');
  setProgressFill($('#progress-fill'), progress, running ? 'busy' : job.exit_code === 0 ? 'done' : job.exit_code ? 'failed' : '');
  renderGlobalProgress(job);
  const logs=(job.logs||[]).join('\n'); lastLogText=logs;
  $('#mini-log').textContent=(job.logs||[]).slice(-80).join('\n');
  $('#full-log').textContent=logs || 'No command has been run yet.';
  $('#mini-log').scrollTop=$('#mini-log').scrollHeight; $('#full-log').scrollTop=$('#full-log').scrollHeight;

  // Expected Time and State (Requirement 8)
  const timeStateEl = $('#job-time-state');
  if (timeStateEl) {
    if (running) {
      const logsLower = logs.toLowerCase();
      let estTime = '1-3 minutes';
      let currentStep = 'processing';
      const title = job.title || '';

      if (title.includes('WAN') || title.includes('generate') || title.includes('Sprite')) {
        estTime = '4-8 minutes';
        if (logsLower.includes('converting video') || logsLower.includes('ffmpeg')) {
          currentStep = 'converting video';
        } else if (logsLower.includes('sampling') || logsLower.includes('denoise') || logsLower.includes('diffusion')) {
          currentStep = 'generating WAN frames';
        } else if (logsLower.includes('loading') || logsLower.includes('weights') || logsLower.includes('model')) {
          currentStep = 'loading model weights (This may look paused during model loading)';
        } else if (logsLower.includes('keying') || logsLower.includes('chroma') || logsLower.includes('alpha') || logsLower.includes('extracting')) {
          currentStep = 'extracting transparent frames';
        } else if (logsLower.includes('stabilizing') || logsLower.includes('align') || logsLower.includes('anchor')) {
          currentStep = 'stabilizing / aligning frame coordinates';
        } else if (logsLower.includes('compiling') || logsLower.includes('atlas') || logsLower.includes('sheet')) {
          currentStep = 'compiling spritesheet';
        } else {
          const lines = job.logs ? job.logs.map(l => l.trim()).filter(l => l.length > 0) : [];
          if (lines.length > 0) {
            const lastLine = lines[lines.length - 1];
            currentStep = lastLine.length > 60 ? lastLine.substring(0, 60) + '...' : lastLine;
          } else {
            currentStep = 'converting video';
          }
        }
      } else if (title.includes('demo') || title.includes('Demo')) {
        estTime = '10-20 seconds';
        currentStep = 'building demo spritesheet';
      } else if (title.includes('pack') || title.includes('Queue') || title.includes('queue')) {
        estTime = 'Several minutes';
        currentStep = 'processing queue job';
      } else if (title.includes('doctor') || title.includes('Doctor')) {
        estTime = '5-15 seconds';
        currentStep = 'diagnosing system';
      }

      timeStateEl.style.display = 'block';
      timeStateEl.innerHTML = `⏱ Estimated time: ${estTime}<br>⚡ Current step: ${currentStep}`;
    } else {
      timeStateEl.style.display = 'none';
      timeStateEl.innerHTML = '';
    }
  }
}

let previousJobId = null;
let previousJobRunning = false;

async function refreshAll(){
  try{
    const s=await api('/api/status' + projectQuery());
    window._latestStatus = s;
    setChip('#chip-comfy', s.comfy_running?'ok':'warn', 'ComfyUI: '+(s.comfy_running?'online':'offline'));
    const modelState=s.models.ok?'ok':'warn';
    const adv = s.models.advanced_total ? ` · 2.2 ${s.models.advanced_present}/${s.models.advanced_total}` : '';
    setChip('#chip-models', modelState, `WAN safe: ${s.models.present}/${s.models.total}${adv}`);
    setChip('#chip-gpu', s.gpu.ok?'ok':'warn', s.gpu.ok?`${s.gpu.label} · ${s.gpu.memory_total||''}`:'GPU: check driver');
    $('#stat-comfy').textContent=s.comfy_running?'Online':'Offline'; $('#stat-comfy-detail').textContent=s.comfy_url;
    $('#stat-models').textContent=`Safe ${s.models.present}/${s.models.total}`; $('#stat-models-detail').textContent=`Wan 2.2 5B: ${s.models.advanced_present}/${s.models.advanced_total}`; $('#stat-disk').textContent=`${s.disk.free_gb} GB`;
    recommendedAction = s.next_step?.action || '';
    if($('#next-step-title')) $('#next-step-title').textContent = s.next_step?.step || 'Ready';
    if($('#next-step-reason')) $('#next-step-reason').textContent = s.next_step?.reason || 'No recommendation available.';
    if($('#guidedNextTitle')) $('#guidedNextTitle').textContent = s.next_step?.step || 'Ready';
    if($('#guidedNextReason')) $('#guidedNextReason').textContent = s.next_step?.reason || 'No recommendation available.';
    renderProjectSummary(s.project_workspace);
    renderOutputs(s.outputs); renderJob(s.job);
    updatePreflightChecklist(s);

    // UX polish updates
    if (typeof updateHealthBar === 'function') updateHealthBar(s);
    if (typeof renderTaskCenter === 'function') renderTaskCenter(s);
    
    // Auto-trigger Result Review Modal on Job Completion
    const activeJob = s.job;
    const activeJobId = activeJob ? activeJob.id : null;
    const activeJobRunning = activeJob ? !!activeJob.running : false;
    
    if (previousJobId && previousJobId === activeJobId && previousJobRunning && !activeJobRunning) {
      const exitCode = activeJob.exit_code;
      const spriteFolder = activeJob.metadata ? activeJob.metadata.sprite_folder : null;
      
      if (exitCode === 0) {
        if (typeof addNotification === 'function') {
          addNotification('Task Completed Successfully', `Task "${activeJob.title}" finished successfully.`, 'success', spriteFolder ? {
            label: 'Inspect Output',
            action: () => openResultPreview(spriteFolder)
          } : null);
        }
        
        if (spriteFolder && typeof openResultPreview === 'function') {
          openResultPreview(spriteFolder);
        }
      } else {
        if (typeof addNotification === 'function') {
          addNotification('Task Failed', `Task "${activeJob.title}" failed with exit code ${exitCode}.`, 'error', {
            label: 'View in Task Center',
            action: () => showView('tasks')
          });
        }
      }
    }
    
    previousJobId = activeJobId;
    previousJobRunning = activeJobRunning;

    // Render project dashboard if selected and active
    if ($('#view-dashboard') && $('#view-dashboard').classList.contains('active') && typeof renderProjectDashboard === 'function') {
      renderProjectDashboard(s);
    }
  }catch(e){ console.error(e); }
}

function updatePreflightChecklist(s) {
  const comfyLi = $('#check-comfy');
  const modelsLi = $('#check-models');
  const diskLi = $('#check-disk');
  const outputLi = $('#check-output');
  const jobLi = $('#check-job');

  const updateItem = (el, ok, text) => {
    if (!el) return;
    el.className = ok ? 'ok' : 'bad';
    const icon = ok ? '✔' : '✘';
    el.innerHTML = `<span class="check-icon">${icon}</span> ${text}`;
  };

  updateItem(comfyLi, s.comfy_running, `ComfyUI online (${s.comfy_running ? 'Connected' : 'Offline'})`);
  updateItem(modelsLi, s.models.ok, `Model files found (${s.models.present}/${s.models.total} present)`);
  updateItem(diskLi, s.disk.ok, `Enough disk space (${s.disk.free_gb} GB free)`);
  updateItem(outputLi, true, `Output folder ready`);
  updateItem(jobLi, !s.job.running, s.job.running ? `Job running: ${s.job.title}` : `No job currently running`);
}

async function loadProjects(){
  try{
    const data = await api('/api/projects');
    const select = $('#projectSelect');
    if(!select) return;
    clearNode(select);
    const none = document.createElement('option');
    none.value = '';
    none.textContent = 'No project';
    select.appendChild(none);
    (data.projects || []).forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.path;
      opt.textContent = p.name;
      select.appendChild(opt);
    });
    activeProjectPath = data.active?.path || '';
    select.value = activeProjectPath;
  }catch(e){ console.error(e); }
}

async function createProject(){
  const input = $('#projectNameInput');
  const name = (input?.value || '').trim();
  if(!name){ toast('Project name required'); return; }
  try{
    const data = await api('/api/projects/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
    activeProjectPath = data.project?.path || '';
    if(input) input.value = '';
    await loadProjects();
    toast('Project active: ' + (data.project?.name || name));
  }catch(e){ toast('Project error: '+e.message); }
}

async function uploadFile(file){
  const fd=new FormData(); fd.append('file', file); fd.append('active_project', activeProjectPath || '');
  toast('Uploading '+file.name+'…');
  const r=await fetch('/api/upload',{method:'POST',body:fd});
  const data=await r.json(); if(!r.ok||!data.ok) throw new Error(data.message||'Upload failed');
  $('#videoPath').value=data.path; toast('Uploaded: '+data.relative);
  await loadReferences();
}

const GUIDE_TEMPLATES = {
  platformer: {
    style: 'clean 2D platformer sprite, readable side-view silhouette, crisp pixel-friendly edges, locked camera',
    actions: ['idle', 'walk', 'run', 'jump', 'attack_light', 'hurt'],
    direction: 'right',
  },
  topdown: {
    style: 'clean top-down RPG sprite, readable small-scale silhouette, consistent outfit, locked orthographic camera',
    actions: ['idle', 'walk', 'attack_light', 'hurt'],
    direction: 'front',
  },
  fighter: {
    style: 'fighting game sprite animation, strong pose clarity, clean silhouette, consistent costume, locked camera',
    actions: ['idle', 'walk', 'attack_light', 'attack_heavy', 'hurt'],
    direction: 'right',
  },
  enemy: {
    style: 'game enemy sprite, bold readable creature silhouette, clean animation poses, locked camera',
    actions: ['idle', 'walk', 'attack_light', 'hurt', 'death'],
    direction: 'right',
  },
  object: {
    style: 'game object sprite animation, centered object, clean outline, locked camera, transparent-ready background',
    actions: ['idle'],
    direction: 'front',
  },
};
let guidedStep = 1;

function setGuideStep(step){
  guidedStep = Math.max(1, Math.min(4, Number(step) || 1));
  $$('.guide-step').forEach(btn => btn.classList.toggle('active', Number(btn.dataset.guideStep) === guidedStep));
  $$('.guide-panel').forEach(panel => panel.classList.toggle('active', Number(panel.dataset.guidePanel) === guidedStep));
  if($('#guidedBack')) $('#guidedBack').disabled = guidedStep === 1;
  if($('#guidedNext')) $('#guidedNext').classList.toggle('hidden', guidedStep === 4);
  if($('#guidedRun')) $('#guidedRun').classList.toggle('ready', guidedStep === 4);
}

function guidedActions(){
  const checked = $$('#guidedActionPick input[type="checkbox"]:checked').map(i => i.value);
  return checked.length ? checked : ['idle'];
}

function applyGuideTemplate(name){
  const template = GUIDE_TEMPLATES[name] || GUIDE_TEMPLATES.platformer;
  const form = $('#guidedForm');
  if(!form) return;
  const direction = form.querySelector('[name="direction"]');
  if(direction) direction.value = template.direction;
  $$('#guidedActionPick input[type="checkbox"]').forEach(input => {
    input.checked = template.actions.includes(input.value);
  });
}

async function guideRecommendation(quality){
  try{
    return await api(`/api/advisor?quality=${encodeURIComponent(quality || 'balanced')}`);
  }catch(e){
    if(quality === 'quality') return {tier:'wan22_5b', profile:'wan22_5b_local'};
    if(quality === 'fast') return {tier:'wan21_safe', profile:'debug'};
    return {tier:'wan21_safe', profile:'auto'};
  }
}

function guideBasePayload(form, rec){
  const data = formData(form);
  const template = GUIDE_TEMPLATES[data.template] || GUIDE_TEMPLATES.platformer;
  const actions = guidedActions();
  return {
    name: data.name || 'hero',
    character: data.character || 'single full body original game hero',
    description: data.character || 'single full body original game hero',
    style: template.style,
    sprite_action: actions[0],
    actions: actions.join(','),
    direction: data.direction || template.direction,
    directions: data.direction || template.direction,
    tier: rec.tier || 'wan21_safe',
    profile: rec.profile || 'auto',
    start_comfy: data.start_comfy !== false,
    quality_check: data.quality_check !== false,
  };
}

async function runGuidedJob(e){
  e.preventDefault();
  const form = e.currentTarget;
  const data = formData(form);
  const rec = await guideRecommendation(data.quality || 'balanced');
  const payload = guideBasePayload(form, rec);
  const goal = data.goal || 'single';
  if(goal === 'single'){
    await runAction('generate_sprite', payload);
    showView('logs');
    return;
  }
  if(goal === 'pack'){
    await runAction('queue_create', payload);
    showView('queues');
    return;
  }
  if(goal === 'convert'){
    const video = String(data.video_path || '').trim();
    if(!video){ toast('Add a video path or use Convert Video to drop a file.'); setGuideStep(3); return; }
    await runAction('convert_video', {
      input: video,
      fps: rec.fps || 12,
      cell_size: rec.cell_size || '512x512',
      key_color: 'auto',
      drop_loop_duplicate: true,
      preview_gif: true,
      report: true,
    });
    showView('logs');
    return;
  }
  if(goal === 'release'){
    const sprites = selectedSpriteDir || currentOutputs.slice(0, 6).map(o => o.path).join('\n');
    if(!sprites){ toast('No finished sprites found yet. Make or convert a sprite first.'); return; }
    await runAction('release_package', {name: `${payload.name}_sprite_pack`, sprites});
    showView('logs');
  }
}

function renderGuidedGallery(outputs){
  const list = $('#guidedGallery');
  if(!list) return;
  clearNode(list);
  if(!outputs || !outputs.length){
    appendText(list, 'div', 'No finished sprites yet.', 'empty compact');
    return;
  }
  outputs.slice(0, 4).forEach(o => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'guided-result';
    btn.dataset.path = o.path || '';
    btn.dataset.previewPath = o.path || '';
    const imgUrl = o.preview_url || o.sheet_url || '';
    if(imgUrl){
      const img = document.createElement('img');
      img.src = `${imgUrl}?t=${Date.now()}`;
      img.alt = o.name || '';
      btn.appendChild(img);
    }
    const text = document.createElement('span');
    appendText(text, 'b', o.name || 'Sprite');
    appendText(text, 'small', `${o.frame_count} frames · ${o.fps} fps`);
    btn.appendChild(text);
    list.appendChild(btn);
  });
}

$$('.nav').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
$$('[data-jump]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.jump)));
$$('[data-run]').forEach(b=>b.addEventListener('click',()=>runAction(b.dataset.run)));
$$('[data-open]').forEach(b=>b.addEventListener('click',()=>openPath(b.dataset.open)));
if($('#guidedForm')) $('#guidedForm').addEventListener('submit', runGuidedJob);
if($('#guidedBack')) $('#guidedBack').addEventListener('click',()=>setGuideStep(guidedStep - 1));
if($('#guidedNext')) $('#guidedNext').addEventListener('click',()=>setGuideStep(guidedStep + 1));
$$('.guide-step').forEach(btn=>btn.addEventListener('click',()=>setGuideStep(btn.dataset.guideStep)));
if($('#guidedForm')) $('#guidedForm').querySelector('[name="template"]').addEventListener('change', e=>applyGuideTemplate(e.currentTarget.value));
if($('#guidedGallery')) $('#guidedGallery').addEventListener('click', e => {
  const item = e.target.closest('[data-path]');
  if(!item) return;
  openResultPreview(item.dataset.previewPath || item.dataset.path || '');
});
$('#refreshOutputs').addEventListener('click', refreshAll);
$('#cancelJob').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
$('#cancelJob2').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
$('#copyLog').addEventListener('click',()=>navigator.clipboard.writeText(lastLogText||'').then(()=>toast('Log copied')));
$('#launchComfy').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });

$('#generateForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('generate_sprite', formData(e.currentTarget)); showView('logs'); });
$('#convertForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('convert_video', formData(e.currentTarget)); showView('logs'); });
$$('[data-quality]').forEach(btn=>btn.addEventListener('click',()=>{
  const data=formData($('#qualityForm')); const mode=btn.dataset.quality;
  if(mode==='validate'){
    runAction('validate_export', {...data, engine: null}); showView('logs'); return;
  }
  const action = mode==='qa'?'qa_report':mode==='fix'?'autofix':mode==='godot'?'export_godot':'export_unity';
  runAction(action, data); showView('logs');
}));
$('#packForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('character_pack', formData(e.currentTarget)); showView('logs'); });
$('#atlasForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('atlas', formData(e.currentTarget)); showView('logs'); });

const dz=$('#dropzone'), vf=$('#videoFile');
['dragenter','dragover'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add('drag')}));
['dragleave','drop'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove('drag')}));
dz.addEventListener('drop',e=>{ const f=e.dataTransfer.files?.[0]; if(f) uploadFile(f).catch(err=>toast(err.message)); });
vf.addEventListener('change',()=>{ const f=vf.files?.[0]; if(f) uploadFile(f).catch(err=>toast(err.message)); });


function runRecommended(){
  if(!recommendedAction){ toast('No recommendation available yet.'); return; }
  if(recommendedAction==='launch_comfy'){ api('/api/launch_comfy',{method:'POST'}).then(()=>toast('ComfyUI launch requested')).then(refreshAll); return; }
  if(recommendedAction==='generate_debug'){
    showView('generate');
    const f=$('#generateForm');
    f.querySelector('[name="profile"]').value='debug';
    f.querySelector('[name="sprite_action"]').value='idle';
    f.querySelector('[name="direction"]').value='front';
    toast('Debug settings loaded. Click Generate WAN → Sprite when ready.');
    return;
  }
  if(recommendedAction==='qa_report'){ showView('quality'); toast('Select a sprite, then run QA.'); return; }
  if(recommendedAction==='release_package'){ showView('release'); toast('Add sprite folders, then build a release ZIP.'); return; }
  runAction(recommendedAction); showView('logs');
}
if($('#runNextAction')) $('#runNextAction').addEventListener('click', runRecommended);
if($('#guidedRecommended')) $('#guidedRecommended').addEventListener('click', runRecommended);
if($('#launchComfy2')) $('#launchComfy2').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });
if($('#releaseForm')) $('#releaseForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('release_package', formData(e.currentTarget)); showView('logs'); });
if($('#queueForm')) $('#queueForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('queue_create', formData(e.currentTarget)); showView('logs'); });
if($('#projectSelect')) $('#projectSelect').addEventListener('change', async e => {
  activeProjectPath = e.currentTarget.value || '';
  try{
    await api('/api/projects/active',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:activeProjectPath})});
    toast(activeProjectPath ? 'Project selected' : 'Global workspace selected');
    await refreshAll();
    if ($('#view-release')?.classList.contains('active')) await loadReleases();
    if ($('#view-history')?.classList.contains('active')) await loadHistory();
    if ($('#view-queues')?.classList.contains('active')) await loadQueues();
    if ($('#view-packs')?.classList.contains('active')) await loadPacks();
    if ($('#view-packs')?.classList.contains('active')) await loadPlanning();
    if ($('#view-quality')?.classList.contains('active')) await loadQualityReports();
    if ($('#view-convert')?.classList.contains('active')) await loadReferences();
  }catch(err){ toast('Project select failed: '+err.message); }
});
if($('#createProjectBtn')) $('#createProjectBtn').addEventListener('click', createProject);
if($('#projectNameInput')) $('#projectNameInput').addEventListener('keydown', e => {
  if(e.key === 'Enter'){ e.preventDefault(); createProject(); }
});

// Step Map Navigation
$$('.step-map-item').forEach(item => {
  item.addEventListener('click', () => {
    const view = item.dataset.view;
    if (view) {
      showView(view);
    }
  });
});

// Interface Density Mode Toggle
function setUiMode(mode) {
  document.body.classList.remove('mode-simple', 'mode-detailed', 'mode-expert');
  document.body.classList.add('mode-' + mode);
  $$('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  localStorage.setItem('uiMode', mode);
}

$$('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const mode = btn.dataset.mode;
    if (mode) setUiMode(mode);
  });
});

// Accessibility Preferences Panel
const PREF_ITEMS = [
  { id: 'prefReduceMotion', className: 'pref-reduce-motion' },
  { id: 'prefHighContrast', className: 'pref-high-contrast' },
  { id: 'prefCompact', className: 'pref-compact' },
  { id: 'prefLargeText', className: 'pref-large-text' },
  { id: 'prefAlwaysShowLogs', className: '' },
  { id: 'prefNeverAutoSwitch', className: '' },
  { id: 'prefConfirmLongJobs', className: '' }
];

function initAccessibilityPreferences() {
  PREF_ITEMS.forEach(item => {
    const el = $('#' + item.id);
    if (!el) return;
    const val = localStorage.getItem(item.id) === 'true';
    el.checked = val;
    if (item.className) {
      document.body.classList.toggle(item.className, val);
    }
    el.addEventListener('change', e => {
      const checked = e.target.checked;
      localStorage.setItem(item.id, checked ? 'true' : 'false');
      if (item.className) {
        document.body.classList.toggle(item.className, checked);
      }
      if (item.id === 'prefAlwaysShowLogs') {
        const activeNav = $('.nav.active');
        const activeView = activeNav ? activeNav.dataset.view : 'launchpad';
        showView(activeView);
      }
    });
  });
}

// Initialise Modes and Preferences
const savedMode = localStorage.getItem('uiMode') || 'simple';
setUiMode(savedMode);
initAccessibilityPreferences();

loadProjects();
loadPresets();
applyGuideTemplate('platformer');
setGuideStep(1);
refreshAll(); setInterval(refreshAll, 3000);

function makeSparkline(values, strokeColor) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 240;
  const height = 30;
  const coords = values.map((val, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - 3 - ((val - min) / range) * (height - 6);
    return `${x},${y}`;
  }).join(' ');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'sparkline');
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', strokeColor);
  line.setAttribute('stroke-width', '1.5');
  line.setAttribute('points', coords);
  svg.appendChild(line);
  return svg;
}

async function loadSpriteDetails(path) {
  if (!path) return;
  try {
    const meta = await api('/file/' + path + '/sheet.json');
    $('#inspect-folder-name').textContent = path;
    $('#inspect-dimensions').textContent = `${meta.frame_width} × ${meta.frame_height}`;
    $('#inspect-frames-count').textContent = meta.frame_count;
    
    const scrub = $('#frameScrubber');
    scrub.min = 0;
    scrub.max = meta.frame_count - 1;
    scrub.value = 0;
    $('#frameScrubberLabel').textContent = `1 / ${meta.frame_count}`;
    
    window._currentMeta = meta;
    window._currentPath = path;
    
    // Fetch QA report if available
    let qa = null;
    try {
      qa = await api('/file/' + path + '/qa_report.json');
    } catch (e) {
      try {
        qa = await api('/file/' + path + '/quality_report.json');
      } catch (err) {}
    }
    window._currentQA = qa;
    
    // Populate QA panel details
    const loopRmse = $('#inspect-loop-rmse');
    const footStdev = $('#inspect-foot-stdev');
    const reportLink = $('#inspect-report-link');
    const driftContainer = $('#driftChartContainer');
    const coverageContainer = $('#coverageChartContainer');
    const issuesContainer = $('#inspect-issues');
    
    if (qa) {
      loopRmse.textContent = qa.metrics?.loop_seam_rmse !== undefined ? Number(qa.metrics.loop_seam_rmse).toFixed(1) : '—';
      footStdev.textContent = qa.metrics?.foot_y_stdev_px !== undefined ? Number(qa.metrics.foot_y_stdev_px).toFixed(2) + 'px' : '—';
      clearNode(reportLink);
      const reportAnchor = document.createElement('a');
      reportAnchor.href = `/file/${encodeURI(path)}/report.html`;
      reportAnchor.target = '_blank';
      reportAnchor.className = 'text-link';
      reportAnchor.textContent = 'Open Report';
      reportLink.appendChild(reportAnchor);
      
      // Draw SVG sparklines
      if (qa.frames) {
        const driftData = qa.frames.map(f => f.foot_y).filter(y => y !== undefined);
        clearNode(driftContainer);
        if (driftData.length > 1) driftContainer.appendChild(makeSparkline(driftData, '#ff4444'));
        else setTextState(driftContainer, 'Insufficient data', 'hint-text');
        
        const covData = qa.frames.map(f => f.alpha_coverage).filter(c => c !== undefined);
        clearNode(coverageContainer);
        if (covData.length > 1) coverageContainer.appendChild(makeSparkline(covData, '#00adb5'));
        else setTextState(coverageContainer, 'Insufficient data', 'hint-text');
      } else {
        driftContainer.textContent = 'No trend data';
        coverageContainer.textContent = 'No trend data';
      }
      
      // Populate dynamic alerts
      clearNode(issuesContainer);
      if (qa.issues && qa.issues.length > 0) {
        qa.issues.forEach(issue => {
          const badge = document.createElement('span');
          badge.className = `chip ${issue.level === 'error' ? 'warn' : 'info'}`;
          badge.classList.add('issue-chip');
          badge.textContent = `${issue.code}: ${issue.message}`;
          issuesContainer.appendChild(badge);
        });
      } else {
        setTextState(issuesContainer, 'Passed QA', 'pass-text');
      }
    } else {
      loopRmse.textContent = '—';
      footStdev.textContent = '—';
      reportLink.textContent = '—';
      setTextState(driftContainer, 'No QA data', 'hint-text');
      setTextState(coverageContainer, 'No QA data', 'hint-text');
      setTextState(issuesContainer, 'Run QA Report to analyze', 'hint-text');
    }
    
    // Check for sibling fixed/original folder for side-by-side comparison
    let siblingPath = '';
    if (path.endsWith('_fixed')) {
      siblingPath = path.slice(0, -6);
    } else {
      siblingPath = path + '_fixed';
    }
    window._siblingPath = siblingPath;
    window._siblingMeta = null;
    window._siblingImg = null;
    
    const siblingToggle = $('#toggleCompareSibling');
    if (siblingToggle) {
      siblingToggle.checked = false;
      siblingToggle.disabled = true;
      siblingToggle.parentElement.classList.add('is-disabled');
    }
    
    try {
      window._siblingMeta = await api('/file/' + siblingPath + '/sheet.json');
      const img = new Image();
      img.src = '/file/' + siblingPath + '/' + (window._siblingMeta.image || 'sheet.png') + '?t=' + Date.now();
      img.onload = () => {
        window._siblingImg = img;
        if (siblingToggle) {
          siblingToggle.disabled = false;
          siblingToggle.parentElement.classList.remove('is-disabled');
        }
      };
    } catch (e) {
      // Sibling not found or not created yet, comparison is not available.
    }
    
    // Populate objective metrics (Requirement 11)
    const framesEl = $('#obj-metric-frames');
    const fpsEl = $('#obj-metric-fps');
    const loopEl = $('#obj-metric-loop');
    const driftEl = $('#obj-metric-drift');
    const exportEl = $('#obj-metric-export');

    if (framesEl) framesEl.textContent = `${meta.frame_count} frames`;
    if (fpsEl) fpsEl.textContent = `${meta.fps || 12} fps`;

    if (qa && qa.metrics) {
      const rmse = qa.metrics.loop_seam_rmse;
      if (rmse !== undefined && rmse !== null) {
        const loopScore = Math.max(0, Math.min(100, Math.round(100 - rmse * 2.5)));
        if (loopEl) loopEl.textContent = loopScore;
      } else {
        if (loopEl) loopEl.textContent = '—';
      }

      const stdev = qa.metrics.foot_y_stdev_px;
      if (stdev !== undefined && stdev !== null) {
        let classification = 'low';
        if (stdev >= 3.0) classification = 'high';
        else if (stdev >= 1.0) classification = 'moderate';
        if (driftEl) driftEl.textContent = classification;
      } else {
        if (driftEl) driftEl.textContent = '—';
      }
    } else {
      if (loopEl) loopEl.textContent = '—';
      if (driftEl) driftEl.textContent = '—';
    }

    const matchedOut = currentOutputs.find(o => o.path === path);
    const ready = matchedOut ? matchedOut.exports_ready : false;
    if (exportEl) {
      exportEl.textContent = ready ? 'ready' : 'pending';
      exportEl.style.color = ready ? '#56c590' : '#dc4d70';
    }

    renderInspectorFrame(0);
  } catch (e) {
    console.error(e);
  }
}

function renderInspectorFrame(index) {
  const meta = window._currentMeta;
  const path = window._currentPath;
  if (!meta || !path) return;
  
  const frame = meta.frames ? meta.frames[index] : null;
  const fw = meta.frame_width;
  const fh = meta.frame_height;
  
  const img = new Image();
  img.src = '/file/' + path + '/' + (meta.image || 'sheet.png') + '?t=' + Date.now();
  img.onload = () => {
    let canvas = $('#inspector-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'inspector-canvas';
      canvas.className = 'inspector-img';
      const placeholder = $('#inspector-img');
      if (placeholder) {
        placeholder.replaceWith(canvas);
      } else {
        $('#inspector-canvas-container').appendChild(canvas);
      }
    }
    
    const compare = $('#toggleCompareSibling') && $('#toggleCompareSibling').checked && window._siblingImg;
    canvas.width = compare ? fw * 2 : fw;
    canvas.height = fh;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, fh);
    
    if (compare) {
      let imgLeft, imgRight, metaLeft, metaRight;
      if (path.endsWith('_fixed')) {
        imgLeft = window._siblingImg;
        metaLeft = window._siblingMeta;
        imgRight = img;
        metaRight = meta;
      } else {
        imgLeft = img;
        metaLeft = meta;
        imgRight = window._siblingImg;
        metaRight = window._siblingMeta;
      }
      
      let sxLeft = (index % metaLeft.columns) * fw;
      let syLeft = Math.floor(index / metaLeft.columns) * fh;
      const frameLeft = metaLeft.frames ? metaLeft.frames[index] : null;
      if (frameLeft) { sxLeft = frameLeft.x; syLeft = frameLeft.y; }
      
      let sxRight = (index % metaRight.columns) * fw;
      let syRight = Math.floor(index / metaRight.columns) * fh;
      const frameRight = metaRight.frames ? metaRight.frames[index] : null;
      if (frameRight) { sxRight = frameRight.x; syRight = frameRight.y; }
      
      ctx.drawImage(imgLeft, sxLeft, syLeft, fw, fh, 0, 0, fw, fh);
      ctx.drawImage(imgRight, sxRight, syRight, fw, fh, fw, 0, fw, fh);
    } else {
      let sx = (index % meta.columns) * fw;
      let sy = Math.floor(index / meta.columns) * fh;
      if (frame) { sx = frame.x; sy = frame.y; }
      ctx.drawImage(img, sx, sy, fw, fh, 0, 0, fw, fh);
    }
    
    if (frame && frame.bad) {
      ctx.fillStyle = 'rgba(255, 0, 0, 0.25)';
      ctx.fillRect(compare ? fw : 0, 0, fw, fh);
      ctx.fillStyle = '#ff4444';
      ctx.font = 'bold 16px sans-serif';
      ctx.fillText('BAD FRAME', (compare ? fw : 0) + 10, 25);
    }

    if (frame) {
      if ($('#pivotXInput')) $('#pivotXInput').value = frame.pivot_x !== undefined ? frame.pivot_x : Math.round(frame.w / 2);
      if ($('#pivotYInput')) $('#pivotYInput').value = frame.pivot_y !== undefined ? frame.pivot_y : frame.h;
    }
    
    $('#frameScrubberLabel').textContent = `${index + 1} / ${meta.frame_count}`;
    updateOverlays(fw, fh, index);
  };
}

function updateOverlays(fw, fh, index) {
  const canvas = $('#inspector-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const compare = $('#toggleCompareSibling') && $('#toggleCompareSibling').checked && window._siblingImg;
  
  const showAnchor = $('#toggleAnchorOverlay').checked;
  const showBBox = $('#toggleBBoxOverlay') && $('#toggleBBoxOverlay').checked;
  
  const drawSideOverlays = (offset, meta, qaData) => {
    // Draw BBox
    if (showBBox && qaData && qaData.frames) {
      const fRecord = qaData.frames[index];
      if (fRecord && fRecord.bbox) {
        const [l, t, r, b] = fRecord.bbox;
        ctx.strokeStyle = 'rgba(0, 255, 128, 0.7)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(offset + l, t, r - l, b - t);
      }
    }
    
    // Draw Anchor Overlay
    if (showAnchor) {
      ctx.strokeStyle = 'rgba(255, 68, 68, 0.8)';
      ctx.lineWidth = 1.5;
      
      // Horizontal baseline at height - 4
      const by = fh - 4;
      ctx.beginPath();
      ctx.moveTo(offset, by);
      ctx.lineTo(offset + fw, by);
      ctx.stroke();
      
      // Vertical center line
      const cx = fw / 2;
      ctx.beginPath();
      ctx.moveTo(offset + cx, 0);
      ctx.lineTo(offset + cx, fh);
      ctx.stroke();
      
      // Small crosshair arc
      ctx.fillStyle = '#00adb5';
      ctx.beginPath();
      ctx.arc(offset + cx, by, 3.5, 0, 2 * Math.PI);
      ctx.fill();
    }
  };
  
  if (compare) {
    const path = window._currentPath;
    let qaLeft = null, qaRight = null;
    if (path.endsWith('_fixed')) {
      qaRight = window._currentQA;
    } else {
      qaLeft = window._currentQA;
    }
    drawSideOverlays(0, window._siblingMeta, qaLeft);
    drawSideOverlays(fw, window._currentMeta, qaRight);
  } else {
    drawSideOverlays(0, window._currentMeta, window._currentQA);
  }
}

if ($('#frameScrubber')) {
  $('#frameScrubber').addEventListener('input', (e) => {
    renderInspectorFrame(parseInt(e.target.value));
  });
}

const toggles = ['#toggleAnchorOverlay', '#toggleBBoxOverlay', '#toggleCompareSibling'];
toggles.forEach(sel => {
  const el = $(sel);
  if (el) {
    el.addEventListener('change', () => {
      const val = $('#frameScrubber').value;
      renderInspectorFrame(parseInt(val));
    });
  }
});

if ($('#toggleCheckerboard')) {
  $('#toggleCheckerboard').addEventListener('change', (e) => {
    const container = $('#inspector-canvas-container');
    if (e.target.checked) {
      container.classList.add('checkerboard');
    } else {
      container.classList.remove('checkerboard');
    }
  });
}

// ============================================================
// Preset Advisor
// ============================================================
if ($('#getAdvisorBtn')) {
  $('#getAdvisorBtn').addEventListener('click', async () => {
    const quality = $('#advisorQuality').value || 'balanced';
    try {
      const rec = await api(`/api/advisor?quality=${quality}`);
      // Auto-fill generate form
      const form = $('#generateForm');
      if (rec.tier) form.querySelector('[name="tier"]').value = rec.tier;
      if (rec.profile) form.querySelector('[name="profile"]').value = rec.profile;
      // Show rationale
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

// ============================================================
// Compare panel (Quality Lab)
// ============================================================
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
      const result = await api('/api/compare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({a, b})
      });
      if (result.ok) {
        window.open(result.report_url, '_blank');
        toast('Compare report opened!');
      } else {
        toast('Compare failed: ' + result.message);
      }
    } catch(e) { toast('Compare error: ' + e.message); }
  });
}
// Auto-fill compareA when a sprite is selected
document.addEventListener('click', e => {
  const card = e.target.closest('.sprite-card');
  if (card && $('#compareA')) $('#compareA').value = card.dataset.path || '';
});

// ============================================================
// Experiment History
// ============================================================
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

let currentHistory = [];
let selectedCompareIds = new Set();

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
    selectedCompareIds.clear();
    updateCompareButton();
    renderHistory();
  } catch(e) { console.error(e); }
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
    tr.appendChild(output);

    appendText(tr, 'td', r.notes || '', 'notes-cell');
    body.appendChild(tr);
  });
}

if ($('#refreshHistory')) $('#refreshHistory').addEventListener('click', loadHistory);
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

if ($('#historyCompareBtn')) {
  $('#historyCompareBtn').addEventListener('click', async () => {
    const selected = Array.from(selectedCompareIds);
    if (selected.length !== 2) {
      toast('Please select exactly 2 runs to compare.');
      return;
    }
    try {
      toast('Comparing runs...');
      const res = await api('/api/compare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({a: selected[0], b: selected[1]})
      });
      if (res.ok) {
        window.open(res.report_url, '_blank');
        toast('Compare report opened!');
      } else {
        toast('Compare failed: ' + res.message);
      }
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

$$('[data-preview-close]').forEach(el => el.addEventListener('click', closeResultPreview));
if ($('#previewOpenFolder')) $('#previewOpenFolder').addEventListener('click', async e => {
  const path = e.currentTarget.dataset.openPath;
  if(path) await openPath(path);
});
if ($('#previewUseForQuality')) $('#previewUseForQuality').addEventListener('click', e => {
  const path = e.currentTarget.dataset.spritePath || '';
  if(!path) return;
  selectedSpriteDir = path;
  if($('#qualitySpriteDir')) $('#qualitySpriteDir').value = path;
  closeResultPreview();
  showView('quality');
  loadSpriteDetails(path);
});
document.addEventListener('keydown', e => {
  if(e.key === 'Escape') closeResultPreview();
});
// Load history when the tab is shown
document.querySelectorAll('.nav').forEach(b => b.addEventListener('click', () => {
  if (b.dataset.view === 'convert') loadReferences();
  if (b.dataset.view === 'history') loadHistory();
  if (b.dataset.view === 'quality') loadQualityReports();
  if (b.dataset.view === 'queues') loadQueues();
  if (b.dataset.view === 'packs') { loadPacks(); loadPlanning(); }
  if (b.dataset.view === 'release') loadReleases();
  if (b.dataset.view === 'tasks') { loadTasksHistory(); loadQueuedJobs(); }
  if (b.dataset.view === 'cleanup') scanCleanup();
}));

// ============================================================
// Reference Files
// ============================================================
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
        select.type = 'button';
        select.className = 'mini';
        select.dataset.referencePath = ref.path;
        select.textContent = 'Use';
        actions.appendChild(select);

        const open = document.createElement('button');
        open.type = 'button';
        open.className = 'mini';
        open.dataset.openPath = ref.path;
        open.textContent = 'Open';
        actions.appendChild(open);
      }
      if (ref.url) {
        const file = document.createElement('a');
        file.className = 'mini link-button';
        file.href = ref.url;
        file.textContent = 'File';
        actions.appendChild(file);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

if ($('#refreshReferences')) $('#refreshReferences').addEventListener('click', loadReferences);
if ($('#referenceList')) {
  $('#referenceList').addEventListener('click', async (e) => {
    const useBtn = e.target.closest('[data-reference-path]');
    if (useBtn) {
      $('#videoPath').value = useBtn.dataset.referencePath;
      toast('Reference selected');
      return;
    }
    const openBtn = e.target.closest('[data-open-path]');
    if (openBtn) await openPath(openBtn.dataset.openPath);
  });
}

// ============================================================
// Quality History
// ============================================================
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

if ($('#refreshQuality')) $('#refreshQuality').addEventListener('click', loadQualityReports);
if ($('#qualityList')) {
  $('#qualityList').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-select-quality-path]');
    if (!btn) return;
    const path = btn.dataset.selectQualityPath;
    selectedSpriteDir = path.replace(/\/qa$|\/quality$/, '');
    $('#qualitySpriteDir').value = selectedSpriteDir;
    await loadSpriteDetails(selectedSpriteDir);
  });
}

// ============================================================
// Pack History
// ============================================================
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
        open.type = 'button';
        open.className = 'mini';
        open.dataset.openPath = p.path;
        open.textContent = 'Open';
        controls.appendChild(open);
      }
      if (p.manifest_url) {
        const manifest = document.createElement('a');
        manifest.className = 'mini link-button';
        manifest.href = p.manifest_url;
        manifest.textContent = 'Manifest';
        controls.appendChild(manifest);
      }
      item.appendChild(controls);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

if ($('#refreshPacks')) $('#refreshPacks').addEventListener('click', loadPacks);
if ($('#packList')) {
  $('#packList').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-open-path]');
    if (btn) await openPath(btn.dataset.openPath);
  });
}

// ============================================================
// Planning Assets
// ============================================================
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
        open.type = 'button';
        open.className = 'mini';
        open.dataset.openPath = asset.path;
        open.textContent = 'Open';
        actions.appendChild(open);
      }
      if (asset.url || asset.manifest_url) {
        const file = document.createElement('a');
        file.className = 'mini link-button';
        file.href = asset.url || asset.manifest_url;
        file.textContent = 'JSON';
        actions.appendChild(file);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

if ($('#refreshPlanning')) $('#refreshPlanning').addEventListener('click', loadPlanning);
if ($('#planningList')) {
  $('#planningList').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-open-path]');
    if (btn) await openPath(btn.dataset.openPath);
  });
}

// ============================================================
// Release History
// ============================================================
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
        open.type = 'button';
        open.className = 'mini';
        open.dataset.openPath = r.path;
        open.textContent = 'Open';
        actions.appendChild(open);
      }
      if (r.zip_path) {
        const zip = document.createElement('a');
        zip.className = 'mini link-button';
        zip.href = r.zip_url;
        zip.textContent = 'ZIP';
        actions.appendChild(zip);
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
  } catch(e) { console.error(e); }
}

if ($('#refreshReleases')) $('#refreshReleases').addEventListener('click', loadReleases);
if ($('#releaseList')) {
  $('#releaseList').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-open-path]');
    if (btn) await openPath(btn.dataset.openPath);
  });
}

// ============================================================
// Queue Monitor
// ============================================================
let _selectedQueuePath = null;
let _queueRefreshTimer = null;

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
  // Refresh the list to update active highlight
  loadQueues();
}

let selectedJobIds = new Set();

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
      
      // Failed Reason Column
      const reasonCell = document.createElement('td');
      reasonCell.className = 'reason-cell';
      reasonCell.textContent = j.failed_reason || '—';
      tr.appendChild(reasonCell);

      // Actions Column
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
        logBtn.dataset.openPath = j.log;
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

// ============================================================
// Preset Builder UI & Logic (Feature 2)
// ============================================================
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

// ============================================================
// Visual Sprite Inspector Edit Tools & Playback Loop (Feature 5)
// ============================================================
let playbackInterval = null;
let isPlaying = false;

function togglePlayback() {
  const btn = $('#inspectPlayBtn');
  if (!btn) return;
  
  if (isPlaying) {
    clearInterval(playbackInterval);
    isPlaying = false;
    btn.textContent = '▶ Play';
  } else {
    const meta = window._currentMeta;
    if (!meta || !meta.frame_count) return;
    
    isPlaying = true;
    btn.textContent = '⏸ Pause';
    
    const fps = parseInt($('#inspectPlayFps').value) || 12;
    const intervalMs = 1000 / fps;
    
    playbackInterval = setInterval(() => {
      const scrub = $('#frameScrubber');
      if (!scrub) return;
      let nextVal = parseInt(scrub.value) + 1;
      if (nextVal >= meta.frame_count) {
        nextVal = 0;
      }
      scrub.value = nextVal;
      renderInspectorFrame(nextVal);
    }, intervalMs);
  }
}

if ($('#inspectPlayBtn')) {
  $('#inspectPlayBtn').addEventListener('click', togglePlayback);
}
if ($('#inspectPlayFps')) {
  $('#inspectPlayFps').addEventListener('change', () => {
    if (isPlaying) {
      togglePlayback();
      togglePlayback();
    }
  });
}

if ($('#inspectMarkBadBtn')) {
  $('#inspectMarkBadBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      frame.bad = !frame.bad;
      toast(frame.bad ? `Frame ${idx + 1} marked as bad` : `Frame ${idx + 1} cleared bad mark`);
      renderInspectorFrame(idx);
    }
  });
}

if ($('#inspectDuplicateBtn')) {
  $('#inspectDuplicateBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      const dup = JSON.parse(JSON.stringify(frame));
      meta.frames.splice(idx + 1, 0, dup);
      meta.frame_count = meta.frames.length;
      meta.frames.forEach((f, i) => f.index = i);
      
      const scrub = $('#frameScrubber');
      scrub.max = meta.frame_count - 1;
      scrub.value = idx + 1;
      
      toast(`Duplicated frame ${idx + 1}`);
      renderInspectorFrame(idx + 1);
    }
  });
}

if ($('#inspectRemoveBtn')) {
  $('#inspectRemoveBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames || meta.frames.length <= 1) {
      toast('Cannot remove the last frame.');
      return;
    }
    const idx = parseInt($('#frameScrubber').value);
    meta.frames.splice(idx, 1);
    meta.frame_count = meta.frames.length;
    meta.frames.forEach((f, i) => f.index = i);
    
    const scrub = $('#frameScrubber');
    scrub.max = meta.frame_count - 1;
    const nextIdx = Math.min(idx, meta.frame_count - 1);
    scrub.value = nextIdx;
    
    toast(`Removed frame ${idx + 1}`);
    renderInspectorFrame(nextIdx);
  });
}

if ($('#inspectTrimBtn')) {
  $('#inspectTrimBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    const path = window._currentPath;
    if (!meta || !path) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (!frame) return;
    
    const img = new Image();
    img.src = '/file/' + path + '/' + (meta.image || 'sheet.png') + '?t=' + Date.now();
    img.onload = () => {
      const osc = document.createElement('canvas');
      osc.width = frame.w;
      osc.height = frame.h;
      const octx = osc.getContext('2d');
      octx.drawImage(img, frame.x, frame.y, frame.w, frame.h, 0, 0, frame.w, frame.h);
      
      const imgData = octx.getImageData(0, 0, frame.w, frame.h);
      const data = imgData.data;
      
      let minX = frame.w, minY = frame.h, maxX = 0, maxY = 0;
      let found = false;
      
      for (let y = 0; y < frame.h; y++) {
        for (let x = 0; x < frame.w; x++) {
          const alpha = data[(y * frame.w + x) * 4 + 3];
          if (alpha > 0) {
            found = true;
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
          }
        }
      }
      
      if (!found) {
        toast('Frame is completely empty.');
        return;
      }
      
      frame.x = frame.x + minX;
      frame.y = frame.y + minY;
      frame.w = maxX - minX + 1;
      frame.h = maxY - minY + 1;
      
      toast(`Trimmed frame ${idx + 1} to size ${frame.w}×${frame.h}`);
      renderInspectorFrame(idx);
    };
  });
}

function nudgeFrame(dx, dy) {
  const meta = window._currentMeta;
  if (!meta || !meta.frames) return;
  const idx = parseInt($('#frameScrubber').value);
  const frame = meta.frames[idx];
  if (frame) {
    frame.x += dx;
    frame.y += dy;
    renderInspectorFrame(idx);
  }
}
if ($('#nudgeUpBtn')) $('#nudgeUpBtn').addEventListener('click', () => nudgeFrame(0, -1));
if ($('#nudgeDownBtn')) $('#nudgeDownBtn').addEventListener('click', () => nudgeFrame(0, 1));
if ($('#nudgeLeftBtn')) $('#nudgeLeftBtn').addEventListener('click', () => nudgeFrame(-1, 0));
if ($('#nudgeRightBtn')) $('#nudgeRightBtn').addEventListener('click', () => nudgeFrame(1, 0));

if ($('#pivotXInput')) {
  $('#pivotXInput').addEventListener('input', e => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      frame.pivot_x = parseFloat(e.target.value) || 0;
    }
  });
}
if ($('#pivotYInput')) {
  $('#pivotYInput').addEventListener('input', e => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      frame.pivot_y = parseFloat(e.target.value) || 0;
    }
  });
}
if ($('#applyPivotAllBtn')) {
  $('#applyPivotAllBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const px = parseFloat($('#pivotXInput').value) || 0;
    const py = parseFloat($('#pivotYInput').value) || 0;
    meta.frames.forEach(f => {
      f.pivot_x = px;
      f.pivot_y = py;
    });
    toast(`Applied pivot (${px}, ${py}) to all frames.`);
  });
}

if ($('#saveSpriteMetadataBtn')) {
  $('#saveSpriteMetadataBtn').addEventListener('click', async () => {
    const meta = window._currentMeta;
    const path = window._currentPath;
    if (!meta || !path) { toast('No active sprite to save'); return; }
    
    try {
      toast('Saving metadata...');
      const res = await api('/api/sprite/save_metadata', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path, metadata: meta })
      });
      if (res.ok) {
        toast('Metadata saved successfully!');
        await loadSpriteDetails(path);
      } else {
        toast('Save failed: ' + res.message);
      }
    } catch(e) {
      toast('Save error: ' + e.message);
    }
  });
}

// ============================================================
// Setup Diagnostic Check Wizard (Feature 8)
// ============================================================
if ($('#runWizardBtn')) {
  $('#runWizardBtn').addEventListener('click', async () => {
    const btn = $('#runWizardBtn');
    const results = $('#wizardResults');
    const summary = $('#wizardSummary');
    btn.disabled = true;
    btn.textContent = '🔍 Scanning environment...';
    results.classList.remove('hidden');
    
    const setWizStep = (id, status, text) => {
      const el = $(id);
      if (!el) return;
      el.className = `wizard-step-item ${status}`;
      el.innerHTML = `<span style="display:inline-block; width:20px; height:20px; border-radius:50%; background:${status === 'ok' ? '#2ec4b6' : '#e71d36'}; color:#fff; text-align:center; font-size:12px; line-height:20px; font-weight:bold;">✓</span> ${text}`;
    };
    
    try {
      const s = await api('/api/status');
      
      const diskOk = s.disk.ok;
      setWizStep('#wiz-step-disk', diskOk ? 'ok' : 'warn', `Disk space: ${s.disk.free_gb} GB free (${diskOk ? 'Healthy' : 'Low, need 25GB'})`);
      
      const gpuOk = s.gpu.ok;
      setWizStep('#wiz-step-gpu', gpuOk ? 'ok' : 'warn', `GPU: ${s.gpu.label} (${s.gpu.vram_gb || '?'} GB VRAM) - ${gpuOk ? 'Supported' : 'Warning: check VRAM/CUDA'}`);
      
      const comfyOk = s.comfy_running;
      setWizStep('#wiz-step-comfy', comfyOk ? 'ok' : 'warn', `ComfyUI: ${comfyOk ? 'Connected' : 'Offline'}`);
      
      const modelsOk = s.models.ok;
      setWizStep('#wiz-step-models', modelsOk ? 'ok' : 'warn', `WAN Models: ${s.models.present}/${s.models.total} safe files present`);
      
      const demoExists = s.outputs.some(o => o.path === 'output/demo_sprite_no_gpu');
      setWizStep('#wiz-step-demo', demoExists ? 'ok' : 'warn', `Demo sprite: ${demoExists ? 'Generated' : 'Not generated yet'}`);
      
      let recs = [];
      if (!diskOk) {
        recs.push("<li><b>Free up disk space</b>: Clear up at least 25 GB on your drive to accommodate ComfyUI and WAN weights.</li>");
      }
      if (!gpuOk) {
        recs.push("<li><b>Verify Nvidia GPU Drivers</b>: Ensure you have CUDA 12+ and Python env set up.</li>");
      }
      if (s.next_step?.action === 'install_all') {
        recs.push("<li><b>Install dependencies & ComfyUI</b>: Click the <i>'Install Everything'</i> button below.</li>");
      } else if (!modelsOk) {
        recs.push("<li><b>Download models</b>: Click the <i>'Repair Safe Model Download'</i> button below to complete the downloads.</li>");
      } else if (!comfyOk) {
        recs.push("<li><b>Launch ComfyUI server</b>: Click the <i>'Launch ComfyUI'</i> button below.</li>");
      } else if (!demoExists) {
        recs.push("<li><b>Run Demo Sprite Job</b>: Run the demo job from the Launchpad step 1 to verify transparent keying and sheet compiling.</li>");
      }
      
      if (recs.length === 0) {
        summary.innerHTML = "<h4>🎉 Setup Verified!</h4><p>Your SpriteForge environment is fully operational. You can start generating sprites with WAN or run production queues.</p>";
      } else {
        summary.innerHTML = `<h4>⚠️ Setup Actions Required</h4><p>Follow these steps to complete your setup:</p><ul>${recs.join('')}</ul>`;
      }
      
    } catch(e) {
      toast('Wizard check failed: ' + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = '✨ Restart First Run Diagnostic';
    }
  });
}

// ============================================================
// Release Builder Precheck & Strict Gate (Feature 9)
// ============================================================
window._releasePrecheckOk = true;

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

if ($('#releaseSprites')) {
  $('#releaseSprites').addEventListener('input', runReleasePrecheck);
}

if ($('#releaseForm')) {
  // Override existing submit listener
  const form = $('#releaseForm');
  
  // Clone form to clear all old listeners
  const newForm = form.cloneNode(true);
  form.replaceWith(newForm);
  
  // Re-bind input listener
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

// ============================================================
// [Polished UX Addition] Persistent Notifications Drawer
// ============================================================
let notifications = [];

function loadNotifications() {
  try {
    notifications = JSON.parse(localStorage.getItem('notifications') || '[]');
  } catch (e) {
    notifications = [];
  }
  renderNotifications();
}

function saveNotifications() {
  localStorage.setItem('notifications', JSON.stringify(notifications));
}

function addNotification(title, message, type = 'info', action = null) {
  const newNotif = {
    id: Date.now() + Math.random().toString(36).substr(2, 9),
    title,
    message,
    type,
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    action
  };
  notifications.unshift(newNotif);
  saveNotifications();
  renderNotifications();
  toast(`🔔 ${title}`);
}

function renderNotifications() {
  const list = $('#notificationList');
  const badge = $('#notificationBadge');
  if (!list) return;

  clearNode(list);
  if (notifications.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-notifications';
    empty.style.color = 'var(--muted)';
    empty.style.textAlign = 'center';
    empty.style.marginTop = '40px';
    empty.textContent = 'No notifications yet.';
    list.appendChild(empty);
    if (badge) {
      badge.textContent = '0';
      badge.style.display = 'none';
    }
    return;
  }

  if (badge) {
    badge.textContent = notifications.length;
    badge.style.display = 'block';
  }

  notifications.forEach(n => {
    const item = document.createElement('div');
    item.className = `notification-item ${n.type}`;
    
    const h4 = document.createElement('h4');
    h4.textContent = n.title;
    item.appendChild(h4);

    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeNotification(n.id);
    });
    item.appendChild(closeBtn);
    
    const p = document.createElement('p');
    p.textContent = n.message;
    item.appendChild(p);

    if (n.action) {
      const actBtn = document.createElement('button');
      actBtn.className = 'action-btn';
      actBtn.textContent = n.action.label;
      actBtn.addEventListener('click', () => {
        if (typeof n.action.action === 'function') {
          n.action.action();
        } else if (n.action.view) {
          showView(n.action.view);
        }
      });
      item.appendChild(actBtn);
    }
    
    const timeSpan = document.createElement('span');
    timeSpan.className = 'time';
    timeSpan.textContent = n.time;
    item.appendChild(timeSpan);
    
    list.appendChild(item);
  });
}

function removeNotification(id) {
  notifications = notifications.filter(n => n.id !== id);
  saveNotifications();
  renderNotifications();
}

function clearAllNotifications() {
  notifications = [];
  saveNotifications();
  renderNotifications();
}

if ($('#notificationTrigger')) {
  $('#notificationTrigger').addEventListener('click', () => {
    const drawer = $('#notificationDrawer');
    if (drawer) drawer.classList.toggle('show');
  });
}
if ($('#closeDrawerBtn')) {
  $('#closeDrawerBtn').addEventListener('click', () => {
    const drawer = $('#notificationDrawer');
    if (drawer) drawer.classList.remove('show');
  });
}
if ($('#clearNotificationsBtn')) {
  $('#clearNotificationsBtn').addEventListener('click', clearAllNotifications);
}

// ============================================================
// [Polished UX Addition] Inline Health Bar Updates
// ============================================================
function updateHealthBar(s) {
  if (!s) return;
  
  // ComfyUI Status
  const dotComfy = $('#health-dot-comfy');
  const valComfy = $('#health-val-comfy');
  const btnComfy = $('#healthLaunchComfyBtn');
  if (dotComfy && valComfy) {
    dotComfy.style.background = s.comfy_running ? 'var(--green)' : 'var(--danger)';
    valComfy.textContent = s.comfy_running ? 'online' : 'offline';
    if (btnComfy) {
      if (s.comfy_running) btnComfy.classList.add('hidden');
      else btnComfy.classList.remove('hidden');
    }
  }

  // Models Status
  const dotModels = $('#health-dot-models');
  const valModels = $('#health-val-models');
  if (dotModels && valModels) {
    const present = s.models ? s.models.present : 0;
    const total = s.models ? s.models.total : 0;
    dotModels.style.background = (s.models && s.models.ok) ? 'var(--green)' : (present > 0 ? 'var(--yellow)' : 'var(--danger)');
    valModels.textContent = `${present}/${total} files`;
  }

  // VRAM Status
  const dotVram = $('#health-dot-vram');
  const valVram = $('#health-val-vram');
  if (dotVram && valVram) {
    if (s.gpu && s.gpu.vram_gb !== undefined) {
      const free = s.gpu.vram_free_gb || 0;
      const total = s.gpu.vram_gb || 12;
      const used = s.gpu.vram_allocated_gb || (total - free);
      const usedPct = (used / total) * 100;
      dotVram.style.background = usedPct > 90 ? 'var(--danger)' : (usedPct > 65 ? 'var(--yellow)' : 'var(--green)');
      valVram.textContent = `${used.toFixed(1)} GB / ${total.toFixed(0)} GB (${Math.round(usedPct)}%)`;
    } else {
      dotVram.style.background = s.gpu && s.gpu.ok ? 'var(--green)' : 'var(--danger)';
      valVram.textContent = s.gpu && s.gpu.ok ? (s.gpu.label || 'Supported') : 'N/A';
    }
  }

  // Disk Status
  const dotDisk = $('#health-dot-disk');
  const valDisk = $('#health-val-disk');
  if (dotDisk && valDisk) {
    const freeGb = s.disk ? s.disk.free_gb : 0;
    const diskOk = s.disk ? s.disk.ok : true;
    dotDisk.style.background = diskOk ? 'var(--green)' : 'var(--danger)';
    valDisk.textContent = `${freeGb} GB free`;
  }

  // Queue Status
  const dotQueue = $('#health-dot-queue');
  const valQueue = $('#health-val-queue');
  if (dotQueue && valQueue) {
    const active = s.job && s.job.running;
    dotQueue.style.background = active ? 'var(--yellow)' : '#888';
    const qCount = s.project_workspace ? s.project_workspace.queues : 0;
    valQueue.textContent = active ? 'busy' : (qCount > 0 ? `${qCount} queued` : 'idle');
  }

  // Last Error Status Strip
  const errorDivider = $('#health-divider-error');
  const errorItem = $('#health-item-error');
  const errorVal = $('#health-val-error');
  if (errorDivider && errorItem && errorVal) {
    if (s.job && s.job.exit_code !== null && s.job.exit_code !== 0) {
      errorDivider.classList.remove('hidden');
      errorItem.classList.remove('hidden');
      errorVal.textContent = s.job.title || 'Failed';
    } else {
      errorDivider.classList.add('hidden');
      errorItem.classList.add('hidden');
    }
  }
}

if ($('#healthLaunchComfyBtn')) {
  $('#healthLaunchComfyBtn').addEventListener('click', async () => {
    try {
      await api('/api/launch_comfy', {method: 'POST'});
      toast('ComfyUI launch requested');
      setTimeout(refreshAll, 1800);
    } catch(err) { toast(err.message); }
  });
}
if ($('#health-item-error')) {
  $('#health-item-error').addEventListener('click', () => {
    showView('tasks');
  });
}

// ============================================================
// [Polished UX Addition] Unified Task Center Rendering
// ============================================================
function formatDuration(start, finish) {
  if (!start) return '—';
  const s = new Date(start);
  const f = finish ? new Date(finish) : new Date();
  const diffMs = f - s;
  if (diffMs < 0 || isNaN(diffMs)) return '—';
  const diffSecs = Math.floor(diffMs / 1000);
  const mins = Math.floor(diffSecs / 60);
  const secs = diffSecs % 60;
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

function renderTaskCenter(s) {
  const activeJob = s.job;
  const running = activeJob && activeJob.running;
  
  const activeRunningArea = $('#activeTaskRunningArea');
  const activeIdleArea = $('#activeTaskIdleArea');
  const activeTitle = $('#activeTaskTitle');
  const activeState = $('#activeTaskState');
  const progressFill = $('#activeTaskProgressFill');
  const progressPct = $('#activeTaskProgressPct');
  const timeState = $('#activeTaskTimeState');
  const terminal = $('#activeTaskTerminal');
  const inspectBtn = $('#activeTaskInspectBtn');
  
  if (running) {
    if (activeRunningArea) activeRunningArea.classList.remove('hidden');
    if (activeIdleArea) activeIdleArea.classList.add('hidden');
    if (activeTitle) activeTitle.textContent = activeJob.title || 'Task running';
    if (activeState) {
      activeState.textContent = 'running';
      activeState.className = 'badge busy';
    }
    
    const pct = inferredJobProgress(activeJob, true);
    if (progressFill) progressFill.style.width = `${pct}%`;
    if (progressPct) progressPct.textContent = `${Math.round(pct)}%`;
    
    const duration = formatDuration(activeJob.started_at, null);
    if (timeState) timeState.textContent = `⏱ Running: ${duration}`;
    
    const logs = (activeJob.logs || []).join('\n');
    if (terminal) {
      terminal.textContent = logs;
      terminal.scrollTop = terminal.scrollHeight;
    }
    if (inspectBtn) inspectBtn.classList.add('hidden');
  } else {
    if (activeState) {
      activeState.textContent = activeJob && activeJob.exit_code !== null ? (activeJob.exit_code === 0 ? 'done' : 'failed') : 'idle';
      activeState.className = 'badge ' + (activeJob && activeJob.exit_code === 0 ? '' : (activeJob && activeJob.exit_code !== null ? 'danger' : 'muted'));
    }
    
    if (activeJob && activeJob.exit_code !== null) {
      if (activeRunningArea) activeRunningArea.classList.remove('hidden');
      if (activeIdleArea) activeIdleArea.classList.add('hidden');
      if (activeTitle) activeTitle.textContent = activeJob.title || 'Task complete';
      
      const pct = activeJob.exit_code === 0 ? 100 : inferredJobProgress(activeJob, false);
      if (progressFill) progressFill.style.width = `${pct}%`;
      if (progressPct) progressPct.textContent = `${Math.round(pct)}%`;
      
      const duration = formatDuration(activeJob.started_at, activeJob.finished_at);
      if (timeState) timeState.textContent = `⏱ Duration: ${duration}`;
      
      const logs = (activeJob.logs || []).join('\n');
      if (terminal) terminal.textContent = logs;
      
      const spriteFolder = activeJob.metadata ? activeJob.metadata.sprite_folder : null;
      if (inspectBtn && spriteFolder) {
        inspectBtn.classList.remove('hidden');
        inspectBtn.dataset.spriteFolder = spriteFolder;
      } else if (inspectBtn) {
        inspectBtn.classList.add('hidden');
      }
    } else {
      if (activeRunningArea) activeRunningArea.classList.add('hidden');
      if (activeIdleArea) activeIdleArea.classList.remove('hidden');
    }
  }
  
  checkFailureRecovery(activeJob);
}

async function loadTasksHistory() {
  try {
    const data = await api('/api/job/history');
    const tbody = $('#tasksHistoryBody');
    if (!tbody) return;
    
    const history = data.history || [];
    if (history.length === 0) {
      tableEmpty(tbody, 6, 'No execution history found.');
      return;
    }
    
    clearNode(tbody);
    history.forEach(j => {
      const tr = document.createElement('tr');
      
      const titleCell = document.createElement('td');
      titleCell.style.fontWeight = 'bold';
      titleCell.textContent = j.title || 'Job';
      tr.appendChild(titleCell);
      
      const startCell = document.createElement('td');
      startCell.className = 'nowrap muted-cell';
      startCell.textContent = j.started_at ? new Date(j.started_at).toLocaleString() : '—';
      tr.appendChild(startCell);
      
      const durCell = document.createElement('td');
      durCell.className = 'nowrap';
      durCell.textContent = formatDuration(j.started_at, j.finished_at);
      tr.appendChild(durCell);
      
      const exitCell = document.createElement('td');
      exitCell.className = 'mono-cell';
      exitCell.textContent = j.exit_code !== null ? j.exit_code : '—';
      tr.appendChild(exitCell);
      
      const statusCell = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = 'badge';
      if (j.exit_code === 0) {
        badge.textContent = 'done';
        badge.style.background = 'var(--green)';
      } else {
        badge.textContent = 'failed';
        badge.style.background = 'var(--danger)';
      }
      statusCell.appendChild(badge);
      tr.appendChild(statusCell);
      
      const actionsCell = document.createElement('td');
      actionsCell.className = 'button-row compact-actions';
      
      const logBtn = document.createElement('button');
      logBtn.className = 'mini';
      logBtn.textContent = 'View Logs';
      logBtn.addEventListener('click', async () => {
        try {
          const detail = await api(`/api/job/detail?id=${j.id}`);
          $('#activeTaskRunningArea').classList.remove('hidden');
          $('#activeTaskIdleArea').classList.add('hidden');
          $('#activeTaskTitle').textContent = `Historical: ${detail.title}`;
          if ($('#activeTaskState')) {
            $('#activeTaskState').textContent = detail.exit_code === 0 ? 'done' : 'failed';
            $('#activeTaskState').className = 'badge ' + (detail.exit_code === 0 ? '' : 'danger');
          }
          if ($('#activeTaskProgressFill')) $('#activeTaskProgressFill').style.width = detail.exit_code === 0 ? '100%' : '50%';
          if ($('#activeTaskProgressPct')) $('#activeTaskProgressPct').textContent = detail.exit_code === 0 ? '100%' : 'Failed';
          if ($('#activeTaskTimeState')) $('#activeTaskTimeState').textContent = `⏱ Duration: ${formatDuration(detail.started_at, detail.finished_at)}`;
          if ($('#activeTaskTerminal')) $('#activeTaskTerminal').textContent = (detail.full_logs || []).join('\n');
          
          const spriteFolder = detail.metadata ? detail.metadata.sprite_folder : null;
          if ($('#activeTaskInspectBtn')) {
            if (spriteFolder) {
              $('#activeTaskInspectBtn').classList.remove('hidden');
              $('#activeTaskInspectBtn').dataset.spriteFolder = spriteFolder;
            } else {
              $('#activeTaskInspectBtn').classList.add('hidden');
            }
          }
          toast('Loaded historical job log');
        } catch (err) { toast('Failed to load logs: ' + err.message); }
      });
      actionsCell.appendChild(logBtn);
      
      const retryBtn = document.createElement('button');
      retryBtn.className = 'mini primary';
      retryBtn.textContent = 'Retry';
      retryBtn.addEventListener('click', async () => {
        try {
          toast('Retrying job...');
          const res = await api('/api/job/retry', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: j.id })
          });
          if (res.ok) {
            toast('Job retried successfully!');
            showView('logs');
            await refreshAll();
          } else { toast('Retry failed: ' + res.message); }
        } catch (err) { toast('Retry error: ' + err.message); }
      });
      actionsCell.appendChild(retryBtn);
      
      tr.appendChild(actionsCell);
      tbody.appendChild(tr);
    });
  } catch(e) { console.error('History load failed:', e); }
}

async function loadQueuedJobs() {
  try {
    const tbody = $('#queuedTasksBody');
    const countBadge = $('#queuedTasksCount');
    if (!tbody) return;
    
    const data = await api('/api/queues' + projectQuery());
    const queues = data.queues || [];
    const runningQ = queues.find(q => q.progress && q.progress.running);
    if (!runningQ) {
      tableEmpty(tbody, 6, 'No active queue processing.');
      if (countBadge) {
        countBadge.textContent = '0 pending';
        countBadge.className = 'badge muted';
      }
      return;
    }
    
    const detail = await api('/api/queues/detail?path=' + encodeURIComponent(runningQ.path));
    const jobs = detail.jobs || [];
    const pendingJobs = jobs.filter(j => j.status === 'pending' || j.status === 'running');
    
    if (countBadge) {
      countBadge.textContent = `${pendingJobs.length} pending`;
      countBadge.className = 'badge busy';
    }
    
    if (jobs.length === 0) {
      tableEmpty(tbody, 6, 'Queue is empty.');
      return;
    }
    
    clearNode(tbody);
    jobs.slice(0, 10).forEach(j => {
      const tr = document.createElement('tr');
      appendText(tr, 'td', j.id || '', 'mono-cell');
      appendText(tr, 'td', j.action || '');
      appendText(tr, 'td', j.direction || '');
      
      const statusCell = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = `queue-status ${queueStatusClass(j.status)}`;
      badge.textContent = j.status || 'pending';
      statusCell.appendChild(badge);
      tr.appendChild(statusCell);
      
      const progressCell = document.createElement('td');
      const jobProgress = j.progress || {};
      progressCell.appendChild(progressElement(jobProgress.percent || 0, j.status === 'running' ? 'busy' : j.status === 'done' ? 'done' : ''));
      tr.appendChild(progressCell);
      
      const actionsCell = document.createElement('td');
      actionsCell.className = 'button-row compact-actions';
      if (j.log) {
        const logBtn = document.createElement('button');
        logBtn.className = 'mini';
        logBtn.textContent = 'Open Log';
        logBtn.addEventListener('click', () => openPath(j.log));
        actionsCell.appendChild(logBtn);
      } else {
        actionsCell.textContent = '—';
      }
      tr.appendChild(actionsCell);
      
      tbody.appendChild(tr);
    });
  } catch (e) { console.error('Queued jobs load failed:', e); }
}

if ($('#activeTaskCancelBtn')) {
  $('#activeTaskCancelBtn').addEventListener('click', () => {
    api('/api/cancel', {method: 'POST'}).then(refreshAll);
  });
}
if ($('#activeTaskCopyLogsBtn')) {
  $('#activeTaskCopyLogsBtn').addEventListener('click', () => {
    const term = $('#activeTaskTerminal');
    if (term) navigator.clipboard.writeText(term.textContent || '').then(() => toast('Active logs copied'));
  });
}
if ($('#activeTaskInspectBtn')) {
  $('#activeTaskInspectBtn').addEventListener('click', e => {
    const folder = e.currentTarget.dataset.spriteFolder;
    if (folder) openResultPreview(folder);
  });
}
if ($('#refreshTasksHistoryBtn')) {
  $('#refreshTasksHistoryBtn').addEventListener('click', () => {
    loadTasksHistory();
    loadQueuedJobs();
  });
}

// ============================================================
// [Polished UX Addition] Cryptic Failure Recovery Advisor
// ============================================================
function checkFailureRecovery(job) {
  const recoveryAdvisor = $('#activeRecoveryAdvisor');
  const recoveryMsg = $('#activeRecoveryMessage');
  const recoveryActions = $('#activeRecoveryActions');
  if (!recoveryAdvisor || !recoveryMsg || !recoveryActions) return;

  if (!job || job.running || job.exit_code === null || job.exit_code === 0) {
    recoveryAdvisor.classList.add('hidden');
    return;
  }

  const logs = (job.logs || []).join('\n').toLowerCase();
  let recoveryOption = null;
  
  if (logs.includes('comfyui') && (logs.includes('offline') || logs.includes('connection') || logs.includes('refused'))) {
    recoveryOption = {
      message: 'ComfyUI appears to be offline. Make sure ComfyUI is running before starting a generation.',
      actionLabel: 'Start ComfyUI',
      run: async () => {
        try {
          await api('/api/launch_comfy', {method: 'POST'});
          toast('ComfyUI launch requested');
          setTimeout(refreshAll, 1800);
        } catch (err) { toast(err.message); }
      }
    };
  } else if (logs.includes('model') && (logs.includes('missing') || logs.includes('not found') || logs.includes('download') || logs.includes('fail'))) {
    recoveryOption = {
      message: 'A model file is missing or failed to download. You can repair the model weights in Setup.',
      actionLabel: 'Repair model download',
      run: () => {
        showView('setup');
        toast('Click "Repair Safe Model Download" to fix models');
      }
    };
  } else if (logs.includes('video not found') || logs.includes('filenotfounderror') || logs.includes('no such file')) {
    recoveryOption = {
      message: 'The requested input video was not found. Open output folder to check results.',
      actionLabel: 'Open output folder',
      run: () => { openPath('output'); }
    };
  } else if (logs.includes('chroma') || logs.includes('green-screen') || logs.includes('keying') || logs.includes('alpha')) {
    recoveryOption = {
      message: 'Chroma keying failed or transparency was poor. Try converting the video again with a stronger chroma key background cleanup.',
      actionLabel: 'Reconvert with stronger cleanup',
      run: () => {
        showView('convert');
        toast('Adjust green-screen thresholds and try again');
      }
    };
  } else if (logs.includes('disk') || logs.includes('space') || logs.includes('nospace') || logs.includes('out of memory')) {
    recoveryOption = {
      message: 'Your system is low on disk space or memory. Try scanning and cleaning old files in the Storage Cleanup Manager.',
      actionLabel: 'Open cleanup targets',
      run: () => {
        showView('cleanup');
        scanCleanup();
      }
    };
  }
  
  if (recoveryOption) {
    recoveryMsg.textContent = recoveryOption.message;
    clearNode(recoveryActions);
    const actionBtn = document.createElement('button');
    actionBtn.className = 'mini primary';
    actionBtn.textContent = recoveryOption.actionLabel;
    actionBtn.addEventListener('click', recoveryOption.run);
    recoveryActions.appendChild(actionBtn);
    recoveryAdvisor.classList.remove('hidden');
  } else {
    recoveryAdvisor.classList.add('hidden');
  }
}

// ============================================================
// [Polished UX Addition] Project Dashboard Consolidation
// ============================================================
async function renderProjectDashboard(s) {
  const hub = $('#projectDashboardHub');
  if (!hub) return;
  
  if (!activeProjectPath) {
    hub.classList.add('hidden');
    return;
  }
  
  hub.classList.remove('hidden');
  
  const dashRefsList = $('#dashReferencesList');
  const dashQueuesList = $('#dashQueuesList');
  const dashReleasesList = $('#dashReleasesList');
  
  // References
  try {
    const refData = await api('/api/references' + projectQuery());
    clearNode(dashRefsList);
    const refs = refData.references || [];
    if (refs.length === 0) {
      appendText(dashRefsList, 'div', 'No references uploaded.', 'empty compact');
    } else {
      refs.slice(0, 3).forEach(ref => {
        const item = document.createElement('div');
        item.style.padding = '8px';
        item.style.background = 'rgba(255,255,255,0.02)';
        item.style.border = '1px solid var(--line)';
        item.style.borderRadius = '6px';
        item.style.marginBottom = '6px';
        item.style.fontSize = '12px';
        item.innerHTML = `<b style="display:block;">${ref.name}</b><span style="color:var(--muted); font-size:11px;">${ref.modified || ''}</span>`;
        dashRefsList.appendChild(item);
      });
    }
  } catch (e) { console.error(e); }

  // Queues
  try {
    const queueData = await api('/api/queues' + projectQuery());
    clearNode(dashQueuesList);
    const queues = queueData.queues || [];
    if (queues.length === 0) {
      appendText(dashQueuesList, 'div', 'No persistent queues.', 'empty compact');
    } else {
      queues.slice(0, 3).forEach(q => {
        const item = document.createElement('div');
        item.style.padding = '8px';
        item.style.background = 'rgba(255,255,255,0.02)';
        item.style.border = '1px solid var(--line)';
        item.style.borderRadius = '6px';
        item.style.marginBottom = '6px';
        item.style.fontSize = '12px';
        const qp = q.progress || { percent: 0 };
        item.innerHTML = `<b style="display:block;">${q.name}</b><span style="color:var(--muted); font-size:11px;">Progress: ${Math.round(qp.percent)}% (${q.total} jobs)</span>`;
        dashQueuesList.appendChild(item);
      });
    }
  } catch (e) { console.error(e); }

  // Releases
  try {
    const releaseData = await api('/api/releases' + projectQuery());
    clearNode(dashReleasesList);
    const releases = releaseData.releases || [];
    if (releases.length === 0) {
      appendText(dashReleasesList, 'div', 'No releases built.', 'empty compact');
    } else {
      releases.slice(0, 3).forEach(r => {
        const item = document.createElement('div');
        item.style.padding = '8px';
        item.style.background = 'rgba(255,255,255,0.02)';
        item.style.border = '1px solid var(--line)';
        item.style.borderRadius = '6px';
        item.style.marginBottom = '6px';
        item.style.fontSize = '12px';
        item.innerHTML = `<b style="display:block;">${r.name}</b><span style="color:var(--muted); font-size:11px;">${r.sprite_count} sprites · ${r.modified || ''}</span>`;
        dashReleasesList.appendChild(item);
      });
    }
  } catch (e) { console.error(e); }
}

// ============================================================
// [Polished UX Addition] One-Click Repairs & Preview Modal Extension
// ============================================================
async function runQuickRepair(type, spritePath) {
  if (!spritePath) {
    toast('No sprite selected for repair');
    return;
  }
  toast(`Running repair: ${type}...`);
  
  const activeProject = activeProjectPath || '';
  if (type === 'qa') {
    await runAction('qa_report', { sprite_dir: spritePath, active_project: activeProject });
    showView('logs');
    closeResultPreview();
    return;
  }
  
  const payload = {
    sprite_dir: spritePath,
    active_project: activeProject,
    stabilize_anchor: type === 'stabilize',
    drop_loop_duplicate: false,
    deflicker: type === 'flicker',
    solidify: type === 'clean' ? 2 : 0,
    blend_loop_frames: type === 'seam' ? 3 : 0,
    sharpen: type === 'sharpen'
  };
  
  await runAction('autofix', payload);
  showView('logs');
  closeResultPreview();
}

if ($('#previewRepairActions')) {
  $('#previewRepairActions').addEventListener('click', e => {
    const btn = e.target.closest('[data-repair]');
    if (!btn) return;
    const type = btn.dataset.repair;
    const spritePath = $('#previewSubtitle').textContent;
    if (type && spritePath) {
      runQuickRepair(type, spritePath);
    }
  });
}

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
      if (!spritePath) {
        toast('Please enter or select a sprite output folder first.');
        return;
      }
      runQuickRepair(b.type, spritePath);
    });
  }
});

// ============================================================
// [Polished UX Addition] Smarter Defaults By Goal
// ============================================================
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
    style: 'clean 2D side-scroller sprite, readable side profile silhouette, locked camera',
    fps: 12,
    cell_size: '512x512',
    negative: 'top-down view, perspective tilt, camera zoom, background details'
  },
  'top_down': {
    style: 'clean top-down RPG sprite, readable small-scale silhouette, locked orthographic camera',
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
    profile: 'quality_local',
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

if ($('#btnGoalPixelArt')) $('#btnGoalPixelArt').addEventListener('click', () => applyGoalDefaults('pixel_art'));
if ($('#btnGoalSmooth2D')) $('#btnGoalSmooth2D').addEventListener('click', () => applyGoalDefaults('smooth_2d'));
if ($('#btnGoalSideScroller')) $('#btnGoalSideScroller').addEventListener('click', () => applyGoalDefaults('side_scroller'));
if ($('#btnGoalTopDown')) $('#btnGoalTopDown').addEventListener('click', () => applyGoalDefaults('top_down'));
if ($('#btnGoalLocalFast')) $('#btnGoalLocalFast').addEventListener('click', () => applyGoalDefaults('local_fast'));
if ($('#btnGoalLocalQuality')) $('#btnGoalLocalQuality').addEventListener('click', () => applyGoalDefaults('local_quality'));

// ============================================================
// [Polished UX Addition] Asset Cleanup Manager
// ============================================================
let scannedCleanupFiles = [];

async function scanCleanup() {
  const btn = $('#scanCleanupBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Scanning...';
  }
  
  try {
    const res = await api('/api/cleanup/scan');
    scannedCleanupFiles = res.files || [];
    renderCleanupTable();
  } catch(e) {
    toast('Scan failed: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Scan Workspace';
    }
  }
}

function renderCleanupTable() {
  const tbody = $('#cleanupTableBody');
  const totalEl = $('#cleanup-total-space');
  const rendersSpaceEl = $('#cleanup-renders-space');
  const rendersCountEl = $('#cleanup-renders-count');
  const failedSpaceEl = $('#cleanup-failed-space');
  const failedCountEl = $('#cleanup-failed-count');
  const logsSpaceEl = $('#cleanup-logs-space');
  const logsCountEl = $('#cleanup-logs-count');
  const purgeBtn = $('#purgeCleanupSelectedBtn');
  const selectAll = $('#cleanupSelectAll');
  
  if (selectAll) selectAll.checked = false;
  if (purgeBtn) purgeBtn.disabled = true;

  if (scannedCleanupFiles.length === 0) {
    tableEmpty(tbody, 5, 'No cleanup targets found. Workspace is healthy!');
    if (totalEl) totalEl.textContent = '0.0 MB';
    if (rendersSpaceEl) rendersSpaceEl.textContent = '0.0 MB';
    if (rendersCountEl) rendersCountEl.textContent = '0 files';
    if (failedSpaceEl) failedSpaceEl.textContent = '0.0 MB';
    if (failedCountEl) failedCountEl.textContent = '0 folders';
    if (logsSpaceEl) logsSpaceEl.textContent = '0.0 MB';
    if (logsCountEl) logsCountEl.textContent = '0 files';
    return;
  }

  clearNode(tbody);
  
  let totalBytes = 0;
  let categories = {
    'ComfyUI Render Outputs': { bytes: 0, count: 0 },
    'Uploaded Reference Videos': { bytes: 0, count: 0 },
    'Failed / Incomplete Outputs': { bytes: 0, count: 0 },
    'Old Task Logs': { bytes: 0, count: 0 }
  };
  
  scannedCleanupFiles.forEach(f => {
    totalBytes += f.size;
    const cat = f.category || 'Other';
    if (!categories[cat]) {
      categories[cat] = { bytes: 0, count: 0 };
    }
    categories[cat].bytes += f.size;
    categories[cat].count += 1;

    const tr = document.createElement('tr');
    
    const chkCell = document.createElement('td');
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.className = 'cleanup-checkbox';
    chk.value = f.id;
    chk.addEventListener('change', () => {
      const checkedCount = $$('.cleanup-checkbox:checked').length;
      if (purgeBtn) {
        purgeBtn.disabled = checkedCount === 0;
        purgeBtn.textContent = `Delete Selected (${checkedCount})`;
      }
    });
    chkCell.appendChild(chk);
    tr.appendChild(chkCell);

    appendText(tr, 'td', f.category || 'Other', 'nowrap muted-cell');
    
    const pathCell = appendText(tr, 'td', f.path || '');
    pathCell.style.wordBreak = 'break-all';
    
    appendText(tr, 'td', formatBytes(f.size), 'nowrap');
    appendText(tr, 'td', formatAge(f.mtime), 'nowrap muted-cell');

    tbody.appendChild(tr);
  });

  if (totalEl) totalEl.textContent = `${(totalBytes / (1024 * 1024)).toFixed(1)} MB`;
  
  const renders = categories['ComfyUI Render Outputs'] || { bytes: 0, count: 0 };
  const failed = categories['Failed / Incomplete Outputs'] || { bytes: 0, count: 0 };
  const logs = categories['Old Task Logs'] || { bytes: 0, count: 0 };
  
  if (rendersSpaceEl) rendersSpaceEl.textContent = `${(renders.bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (rendersCountEl) rendersCountEl.textContent = `${renders.count} files`;
  
  if (failedSpaceEl) failedSpaceEl.textContent = `${(failed.bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (failedCountEl) failedCountEl.textContent = `${failed.count} folders`;
  
  if (logsSpaceEl) logsSpaceEl.textContent = `${(logs.bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (logsCountEl) logsCountEl.textContent = `${logs.count} files`;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatAge(mtime) {
  if (!mtime) return '—';
  const diffMs = Date.now() - (mtime * 1000);
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours} hours old`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} days old`;
}

async function purgeSelectedCleanup() {
  const checked = $$('.cleanup-checkbox:checked').map(chk => chk.value);
  if (checked.length === 0) return;
  
  if (!confirm(`Are you sure you want to permanently delete the ${checked.length} selected files?`)) {
    return;
  }
  
  try {
    toast(`Purging ${checked.length} files...`);
    const res = await api('/api/cleanup/purge', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ids: checked })
    });
    if (res.ok) {
      toast(`Successfully deleted ${res.count} items. Reclaimed ${res.reclaimed_mb} MB.`);
      await scanCleanup();
    } else {
      toast('Purge failed: ' + res.message);
    }
  } catch(e) { toast('Purge error: ' + e.message); }
}

if ($('#scanCleanupBtn')) $('#scanCleanupBtn').addEventListener('click', scanCleanup);
if ($('#purgeCleanupSelectedBtn')) $('#purgeCleanupSelectedBtn').addEventListener('click', purgeSelectedCleanup);

if ($('#cleanupSelectAll')) {
  $('#cleanupSelectAll').addEventListener('change', e => {
    const checked = e.target.checked;
    $$('.cleanup-checkbox').forEach(chk => {
      chk.checked = checked;
    });
    const checkedCount = $$('.cleanup-checkbox:checked').length;
    const purgeBtn = $('#purgeCleanupSelectedBtn');
    if (purgeBtn) {
      purgeBtn.disabled = checkedCount === 0;
      purgeBtn.textContent = `Delete Selected (${checkedCount})`;
    }
  });
}

if ($('#autoCleanBtn')) {
  $('#autoCleanBtn').addEventListener('click', async () => {
    const targetIds = scannedCleanupFiles
      .filter(f => f.category === 'Failed / Incomplete Outputs' || f.category === 'Old Task Logs')
      .map(f => f.id);
      
    if (targetIds.length === 0) {
      toast('No failed outputs or old logs to clean up.');
      return;
    }
    
    if (!confirm(`Safe Auto-Clean: Purge ${targetIds.length} failed outputs and old log files automatically?`)) {
      return;
    }
    
    try {
      toast(`Auto-cleaning ${targetIds.length} items...`);
      const res = await api('/api/cleanup/purge', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ids: targetIds })
      });
      if (res.ok) {
        toast(`Safe clean completed. Deleted ${res.count} items, reclaimed ${res.reclaimed_mb} MB.`);
        await scanCleanup();
      } else {
        toast('Clean failed: ' + res.message);
      }
    } catch(e) { toast('Clean error: ' + e.message); }
  });
}

// ============================================================
// [Polished UX Addition] Keyboard & Accessibility Shortcuts
// ============================================================
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeResultPreview();
    const drawer = $('#notificationDrawer');
    if (drawer) drawer.classList.remove('show');
  }

  if (e.altKey && e.key >= '1' && e.key <= '9') {
    e.preventDefault();
    const tabViews = ['guide', 'dashboard', 'tasks', 'launchpad', 'generate', 'convert', 'quality', 'packs', 'setup'];
    const idx = parseInt(e.key) - 1;
    if (idx < tabViews.length) {
      showView(tabViews[idx]);
      toast(`Switched to ${tabViews[idx].toUpperCase()}`);
    }
  }

  if (e.key === ' ' && $('#view-quality').classList.contains('active')) {
    const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') {
      e.preventDefault();
      togglePlayback();
    }
  }

  if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && $('#view-quality').classList.contains('active')) {
    const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') {
      e.preventDefault();
      const scrub = $('#frameScrubber');
      const meta = window._currentMeta;
      if (scrub && meta && meta.frame_count) {
        let val = parseInt(scrub.value);
        if (e.key === 'ArrowLeft') {
          val = (val - 1 + meta.frame_count) % meta.frame_count;
        } else {
          val = (val + 1) % meta.frame_count;
        }
        scrub.value = val;
        renderInspectorFrame(val);
      }
    }
  }
});

// Restore active view (Continue where I left off) & load state
const savedView = localStorage.getItem('activeView') || 'guide';
showView(savedView);
loadNotifications();
