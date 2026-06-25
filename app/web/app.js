const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => Array.from(root.querySelectorAll(s));
let currentOutputs = [];
let selectedSpriteDir = '';
let lastLogText = '';
let recommendedAction = '';

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
async function runAction(action, extra={}){ try{ const data=await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...extra})}); toast(data.message||'Started'); await refreshAll(); }catch(e){ toast('Error: '+e.message); } }
async function openPath(path){ try{ await api('/api/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})}); }catch(e){ toast(e.message); } }
function setChip(id, state, text){ const el=$(id); el.className='chip '+state; el.textContent=text; }
function showView(name){ $$('.view').forEach(v=>v.classList.remove('active')); $('#view-'+name)?.classList.add('active'); $$('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===name)); }
function relativePath(p){ return p || ''; }

function renderOutputs(outputs){
  currentOutputs = outputs || [];
  $('#stat-outputs').textContent = currentOutputs.length;
  const g=$('#gallery');
  if(!currentOutputs.length){ g.innerHTML='<div class="empty">No sprite outputs yet. Run the demo or make a sprite.</div>'; return; }
  g.innerHTML=currentOutputs.slice(0,12).map(o=>`<article class="sprite-card" data-path="${escapeHtml(o.path)}">
    ${o.preview_url?`<img src="${escapeHtml(o.preview_url)}?t=${Date.now()}" alt="${escapeHtml(o.name)}">`:(o.sheet_url?`<img src="${escapeHtml(o.sheet_url)}?t=${Date.now()}" alt="${escapeHtml(o.name)}">`:'<div class="placeholder">No preview</div>')}
    <div class="meta"><b>${escapeHtml(o.name)}</b><small>${escapeHtml(o.frame_count)} frames · ${escapeHtml(o.fps)} fps · ${escapeHtml(o.frame_width)}×${escapeHtml(o.frame_height)}</small><small>${escapeHtml(o.modified)}</small></div>
  </article>`).join('');
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
  return `<svg width="${width}" height="${height}" style="background: rgba(255,255,255,0.03); border-radius: 4px; border: 1px solid rgba(255,255,255,0.08);">
    <polyline fill="none" stroke="${strokeColor}" stroke-width="1.5" points="${coords}" />
  </svg>`;
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
      reportLink.innerHTML = `<a href="/file/${escapeHtml(path)}/report.html" target="_blank" style="color: #00adb5; text-decoration: underline;">Open Report</a>`;
      
      // Draw SVG sparklines
      if (qa.frames) {
        const driftData = qa.frames.map(f => f.foot_y).filter(y => y !== undefined);
        driftContainer.innerHTML = driftData.length > 1 ? makeSparkline(driftData, '#ff4444') : '<span style="font-size: 11px; color: #a9b7d0;">Insufficient data</span>';
        
        const covData = qa.frames.map(f => f.alpha_coverage).filter(c => c !== undefined);
        coverageContainer.innerHTML = covData.length > 1 ? makeSparkline(covData, '#00adb5') : '<span style="font-size: 11px; color: #a9b7d0;">Insufficient data</span>';
      } else {
        driftContainer.textContent = 'No trend data';
        coverageContainer.textContent = 'No trend data';
      }
      
      // Populate dynamic alerts
      issuesContainer.innerHTML = '';
      if (qa.issues && qa.issues.length > 0) {
        qa.issues.forEach(issue => {
          const badge = document.createElement('span');
          badge.className = `chip ${issue.level === 'error' ? 'warn' : 'info'}`;
          badge.style.fontSize = '9px';
          badge.style.padding = '2px 5px';
          badge.style.borderRadius = '4px';
          badge.style.margin = '2px';
          badge.style.display = 'inline-block';
          badge.textContent = `${issue.code}: ${issue.message}`;
          issuesContainer.appendChild(badge);
        });
      } else {
        issuesContainer.innerHTML = '<span style="color: #6affb8; font-size: 11px;">✓ Passed QA</span>';
      }
    } else {
      loopRmse.textContent = '—';
      footStdev.textContent = '—';
      reportLink.textContent = '—';
      driftContainer.innerHTML = '<span style="font-size: 11px; color: #a9b7d0;">No QA data</span>';
      coverageContainer.innerHTML = '<span style="font-size: 11px; color: #a9b7d0;">No QA data</span>';
      issuesContainer.innerHTML = '<span style="color: #a9b7d0; font-size: 11px;">Run QA Report to analyze</span>';
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
      siblingToggle.parentElement.style.opacity = '0.5';
    }
    
    try {
      window._siblingMeta = await api('/file/' + siblingPath + '/sheet.json');
      const img = new Image();
      img.src = '/file/' + siblingPath + '/' + (window._siblingMeta.image || 'sheet.png') + '?t=' + Date.now();
      img.onload = () => {
        window._siblingImg = img;
        if (siblingToggle) {
          siblingToggle.disabled = false;
          siblingToggle.parentElement.style.opacity = '1.0';
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
      canvas.style.maxHeight = '90%';
      canvas.style.maxWidth = '90%';
      canvas.style.objectFit = 'contain';
      canvas.style.imageRendering = 'pixelated';
      canvas.style.position = 'relative';
      canvas.style.zIndex = '10';
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
      container.style.backgroundImage = 'linear-gradient(45deg, #181818 25%, transparent 25%), linear-gradient(-45deg, #181818 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #181818 75%), linear-gradient(-45deg, transparent 75%, #181818 75%)';
      container.style.backgroundColor = '#0d0d0d';
    } else {
      container.style.backgroundImage = 'none';
      container.style.backgroundColor = '#000';
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
      let html = `<b>Recommendation:</b> Tier <code>${rec.tier}</code>, Profile <code>${rec.profile}</code>, ${rec.frame_count} frames, ${rec.fps} fps, ${rec.cell_size}.<br><small style="color:#aaa">${rec.rationale}</small>`;
      if (rec.warnings && rec.warnings.length) {
        html += '<br>' + rec.warnings.map(w => `<span style="color:#f0a040">⚠ ${w}</span>`).join('<br>');
      }
      box.innerHTML = html;
      box.style.display = 'block';
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
    const vis = section.style.display === 'none';
    section.style.display = vis ? 'block' : 'none';
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
  if (rec.qa_passed === true) return '<span style="color:#6f6;font-size:.8em">✔ QA</span>';
  if (rec.qa_passed === false) return '<span style="color:#f66;font-size:.8em">✘ QA</span>';
  return '<span style="color:#888;font-size:.8em">—</span>';
}

async function loadHistory() {
  try {
    const data = await api('/api/experiments');
    const body = $('#historyBody');
    if (!data.experiments || !data.experiments.length) {
      body.innerHTML = '<tr><td colspan="8" style="padding:24px;text-align:center;color:#555">No generation history yet.</td></tr>';
      return;
    }
    body.innerHTML = data.experiments.map(r => `
      <tr style="border-bottom:1px solid #1e1e2e">
        <td style="padding:6px 10px;color:#888;font-size:.78em;white-space:nowrap">${escapeHtml(r.created_at||'').slice(0,16)}</td>
        <td style="padding:6px 10px">${escapeHtml(r.sprite_action||'—')}</td>
        <td style="padding:6px 10px">${escapeHtml(r.direction||'—')}</td>
        <td style="padding:6px 10px;font-size:.8em"><code>${escapeHtml((r.model_tier||'').replace('wan21_',''))}</code></td>
        <td style="padding:6px 10px;font-size:.8em"><code>${escapeHtml(r.profile||'—')}</code></td>
        <td style="padding:6px 10px">${statusBadge(r)}</td>
        <td style="padding:6px 10px;font-size:.78em;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${r.sprite_folder ? `<button class="mini" onclick="openPath('${escapeHtml(r.sprite_folder)}')">Open</button> <span style="color:#666">${escapeHtml(r.sprite_folder)}</span>` : '—'}
        </td>
        <td style="padding:6px 10px;font-size:.8em;color:#aaa">${escapeHtml(r.notes||'')}</td>
      </tr>`).join('');
  } catch(e) { console.error(e); }
}

if ($('#refreshHistory')) $('#refreshHistory').addEventListener('click', loadHistory);
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

async function loadQueues() {
  try {
    const data = await api('/api/queues');
    const list = $('#queueList');
    if (!data.queues || !data.queues.length) {
      list.innerHTML = '<div style="color:#555;font-size:.85rem">No queues found. Create one in Queue Builder.</div>';
      return;
    }
    list.innerHTML = data.queues.map(q => {
      const c = q.counts || {};
      const pills = Object.entries(c).map(([k,v]) =>
        `<span style="background:#1e1e2e;color:${queueStatusColor(k)};font-size:.7em;padding:1px 6px;border-radius:10px;margin:1px">${k}:${v}</span>`
      ).join('');
      const active = _selectedQueuePath === q.path;
      return `<div class="card" style="padding:10px;cursor:pointer;border:1px solid ${active?'#5070d0':'transparent'}" data-qpath="${escapeHtml(q.path)}" onclick="selectQueue('${escapeHtml(q.path)}','${escapeHtml(q.name)}')">
        <b style="font-size:.85rem">${escapeHtml(q.name)}</b>
        <div style="margin-top:4px">${pills}</div>
        <small style="color:#555">${escapeHtml(q.created_at||'').slice(0,16)}</small>
      </div>`;
    }).join('');
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
      body.innerHTML = '<tr><td colspan="6" style="padding:16px;color:#555">No jobs in queue.</td></tr>';
      return;
    }
    body.innerHTML = data.jobs.map(j => {
      const sc = queueStatusColor(j.status);
      const logBtn = j.log ? `<button class="mini" onclick="openPath('${escapeHtml(j.log)}')">Log</button>` : '';
      return `<tr style="border-bottom:1px solid #1a1a2e">
        <td style="padding:5px 10px;font-family:monospace;font-size:.78em">${escapeHtml(j.id)}</td>
        <td style="padding:5px 10px">${escapeHtml(j.action||'')}</td>
        <td style="padding:5px 10px">${escapeHtml(j.direction||'')}</td>
        <td style="padding:5px 10px"><span style="color:${sc};font-weight:600">${escapeHtml(j.status||'')}</span></td>
        <td style="padding:5px 10px;color:#888">${j.exit_code !== null && j.exit_code !== undefined ? j.exit_code : '—'}</td>
        <td style="padding:5px 10px">${logBtn}</td>
      </tr>`;
    }).join('');
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

// Auto-refresh queue detail every 5s when the queues view is visible
setInterval(() => {
  const v = $('#view-queues');
  if (v && v.classList.contains('active') && _selectedQueuePath) {
    loadQueueDetail(_selectedQueuePath);
  }
}, 5000);

