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
async function runAction(action, extra={}){ try{ const data=await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,active_project:activeProjectPath,...extra})}); toast(data.message||'Started'); await refreshAll(); }catch(e){ toast('Error: '+e.message); } }
async function openPath(path){ try{ await api('/api/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})}); }catch(e){ toast(e.message); } }
function setChip(id, state, text){ const el=$(id); el.className='chip '+state; el.textContent=text; }
function showView(name){ $$('.view').forEach(v=>v.classList.remove('active')); $('#view-'+name)?.classList.add('active'); $$('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===name)); }
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

function renderOutputs(outputs){
  currentOutputs = outputs || [];
  $('#stat-outputs').textContent = currentOutputs.length;
  const g=$('#gallery');
  clearNode(g);
  if(!currentOutputs.length){
    appendText(g, 'div', 'No sprite outputs yet. Run the demo or make a sprite.', 'empty');
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
    card.appendChild(meta);
    g.appendChild(card);
  });
  $$('.sprite-card', g).forEach(card=>card.addEventListener('click',()=>{
    selectedSpriteDir=card.dataset.path;
    $('#qualitySpriteDir').value=selectedSpriteDir;
    if($('#releaseSprites') && !$('#releaseSprites').value.includes(selectedSpriteDir)){
      $('#releaseSprites').value = ($('#releaseSprites').value ? $('#releaseSprites').value+'\n' : '') + selectedSpriteDir;
    }
    showView('quality');
    toast('Selected '+selectedSpriteDir);
    loadSpriteDetails(selectedSpriteDir);
  }));
}

function renderJob(job){
  const running=!!job.running;
  $('#job-title').textContent=job.title||'Idle'; $('#log-title').textContent=job.title||'Idle';
  $('#job-state').textContent=running?'running':(job.exit_code===0?'done':(job.exit_code?'failed':'ready'));
  $('#job-state').className='badge '+(running?'busy':'');
  $('#progress-fill').className=running?'busy':'';  $('#progress-fill').style.width=running?`${job.progress || 10}%`:(job.exit_code===0?'100%':'0');
  const logs=(job.logs||[]).join('\n'); lastLogText=logs;
  $('#mini-log').textContent=(job.logs||[]).slice(-80).join('\n');
  $('#full-log').textContent=logs || 'No command has been run yet.';
  $('#mini-log').scrollTop=$('#mini-log').scrollHeight; $('#full-log').scrollTop=$('#full-log').scrollHeight;
}

async function refreshAll(){
  try{
    const s=await api('/api/status');
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
    renderOutputs(s.outputs); renderJob(s.job);
  }catch(e){ console.error(e); }
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
  const fd=new FormData(); fd.append('file', file);
  toast('Uploading '+file.name+'…');
  const r=await fetch('/api/upload',{method:'POST',body:fd});
  const data=await r.json(); if(!r.ok||!data.ok) throw new Error(data.message||'Upload failed');
  $('#videoPath').value=data.path; toast('Uploaded: '+data.relative);
}

$$('.nav').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
$$('[data-jump]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.jump)));
$$('[data-run]').forEach(b=>b.addEventListener('click',()=>runAction(b.dataset.run)));
$$('[data-open]').forEach(b=>b.addEventListener('click',()=>openPath(b.dataset.open)));
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
if($('#launchComfy2')) $('#launchComfy2').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });
if($('#releaseForm')) $('#releaseForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('release_package', formData(e.currentTarget)); showView('logs'); });
if($('#queueForm')) $('#queueForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('queue_create', formData(e.currentTarget)); showView('logs'); });
if($('#projectSelect')) $('#projectSelect').addEventListener('change', async e => {
  activeProjectPath = e.currentTarget.value || '';
  if(!activeProjectPath) return;
  try{
    await api('/api/projects/active',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:activeProjectPath})});
    toast('Project selected');
  }catch(err){ toast('Project select failed: '+err.message); }
});
if($('#createProjectBtn')) $('#createProjectBtn').addEventListener('click', createProject);
if($('#projectNameInput')) $('#projectNameInput').addEventListener('keydown', e => {
  if(e.key === 'Enter'){ e.preventDefault(); createProject(); }
});

loadProjects();
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

async function loadHistory() {
  try {
    const data = await api('/api/experiments');
    const body = $('#historyBody');
    if (!data.experiments || !data.experiments.length) {
      tableEmpty(body, 10, 'No generation history yet.');
      return;
    }
    clearNode(body);
    data.experiments.forEach(r => {
      const tr = document.createElement('tr');

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
  } catch(e) { console.error(e); }
}

if ($('#refreshHistory')) $('#refreshHistory').addEventListener('click', loadHistory);
if ($('#exportHistory')) $('#exportHistory').addEventListener('click', () => { window.location.href = '/api/experiments/export'; });
if ($('#clearHistory')) $('#clearHistory').addEventListener('click', async () => {
  if (!confirm('Clear unstarred experiment history? Starred runs will be kept.')) return;
  try {
    const result = await api('/api/experiments/clear', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keep_starred:true})});
    toast(`Removed ${result.removed || 0} history records`);
    await loadHistory();
  } catch(e) { toast('History clear failed: ' + e.message); }
});
if ($('#historyBody')) {
  $('#historyBody').addEventListener('click', async (e) => {
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
// Load history when the tab is shown
document.querySelectorAll('.nav').forEach(b => b.addEventListener('click', () => {
  if (b.dataset.view === 'history') loadHistory();
  if (b.dataset.view === 'queues') loadQueues();
}));

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
    const data = await api('/api/queues');
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

async function loadQueueDetail(path) {
  if (!path) return;
  try {
    const data = await api('/api/queues/detail?path=' + encodeURIComponent(path));
    const body = $('#queueDetailBody');
    if (!data.jobs || !data.jobs.length) {
      tableEmpty(body, 6, 'No jobs in queue.');
      return;
    }
    clearNode(body);
    data.jobs.forEach(j => {
      const tr = document.createElement('tr');
      appendText(tr, 'td', j.id || '', 'mono-cell');
      appendText(tr, 'td', j.action || '');
      appendText(tr, 'td', j.direction || '');
      const status = document.createElement('td');
      const statusText = appendText(status, 'span', j.status || '');
      statusText.className = `queue-status ${queueStatusClass(j.status)}`;
      tr.appendChild(status);
      appendText(tr, 'td', j.exit_code !== null && j.exit_code !== undefined ? String(j.exit_code) : '—', 'muted-cell');
      const output = document.createElement('td');
      if (j.log) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mini';
        btn.dataset.openPath = j.log;
        btn.textContent = 'Log';
        output.appendChild(btn);
      }
      tr.appendChild(output);
      body.appendChild(tr);
    });
  } catch(e) { console.error(e); }
}

async function queueAction(endpoint) {
  if (!_selectedQueuePath) return;
  try {
    const r = await api(endpoint, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:_selectedQueuePath})});
    toast(r.message || 'Done');
    await refreshAll();
    await loadQueueDetail(_selectedQueuePath);
    await loadQueues();
  } catch(e) { toast('Error: '+e.message); }
}

if ($('#queueRunBtn')) $('#queueRunBtn').addEventListener('click', () => queueAction('/api/queues/run'));
if ($('#queueRetryBtn')) $('#queueRetryBtn').addEventListener('click', () => queueAction('/api/queues/retry-failed'));
if ($('#queueResetBtn')) $('#queueResetBtn').addEventListener('click', () => queueAction('/api/queues/reset'));
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

// Auto-refresh queue detail every 5s when the queues view is visible
setInterval(() => {
  const v = $('#view-queues');
  if (v && v.classList.contains('active') && _selectedQueuePath) {
    loadQueueDetail(_selectedQueuePath);
  }
}, 5000);
