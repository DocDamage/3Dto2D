(function () {
  const el = id => document.getElementById(id);
  const projectQuery = () => {
    const value = el('projectSelect')?.value || '';
    return value ? `?project=${encodeURIComponent(value)}` : '';
  };
  const set = (id, value) => { if (el(id)) el(id).textContent = String(value); };
  const NODE_PORTS={import:['asset'],generate:['asset'],transform:['asset'],background_remove:['asset'],frame_extract:['frames'],style_conform:['asset'],qa:['report'],conditional:['branch'],approval:['asset'],export:['package'],comfyui:['asset']};
  let graphConnectSource='';
  let currentBatch=null;
  let currentWorkflow=null,currentWorkflowRun=null;
  async function refreshProduction() {
    if (!el('productionCompletion')) return;
    if (!projectQuery()) { set('productionCompletionHint', 'Select a project to load production readiness.'); return; }
    try {
      const data = await api('/api/production/dashboard' + projectQuery());
      const d = data.dashboard;
      set('productionCompletion', `${d.completion.percent}%`);
      set('productionCompletionHint', `${d.completion.present}/${d.completion.required} action-direction combinations`);
      set('productionQaErrors', d.qa.errors);
      set('productionQaHint', `${d.qa.warnings} warnings · ${d.assets.unvalidated} unvalidated`);
      set('productionAssets', d.assets.total);
      set('productionAssetsHint', `${d.readiness.problem_count} readiness problems`);
      set('productionExport', d.exports.count ? 'Ready' : 'None');
      set('productionExportHint', d.exports.last_successful || 'No successful export yet.');
      const actions = el('productionActions');
      actions.innerHTML = '';
      if (!d.actions.length) actions.innerHTML = '<div class="empty compact">Project is production-ready.</div>';
      d.actions.forEach(item => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'release-row';
        button.textContent = `${item.label} (${item.count})`;
        button.addEventListener('click', () => typeof showView === 'function' && showView(item.view));
        actions.appendChild(button);
      });
    } catch (error) { set('productionCompletionHint', error.message); }
  }
  async function estimateBatch() {
    try {
      const dimensions = JSON.parse(el('productionBatchDimensions').value);
      const data = await api('/api/batches/estimate', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({dimensions}) });
      const e = data.estimate;
      set('productionBatchEstimate', `${e.cell_count} jobs · ${(e.storage_bytes / 1048576).toFixed(1)} MB · estimated cost $${e.estimated_cost}${e.requires_confirmation ? ' · confirmation required' : ''}`);
    } catch (error) { set('productionBatchEstimate', error.message); }
  }
  async function createBatch() {
    const dimensions = JSON.parse(el('productionBatchDimensions').value);
    const data = await api('/api/batches' + projectQuery(), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:el('productionBatchName').value, dimensions})});
    toast(`Planned ${data.experiment.estimate.cell_count} matrix cells.`); renderBatch(data.experiment); refreshProduction();
  }
  function renderBatch(experiment) {
    currentBatch=experiment;
    const root = el('productionBatchResults'); if (!root) return; root.innerHTML = '';
    (experiment.cells || []).slice(0, 100).forEach(cell => {
      const card=document.createElement('article'); card.className='production-result-cell';
      const title=document.createElement('b'); title.textContent=Object.values(cell.coordinate).join(' · '); card.appendChild(title);
      const meta=document.createElement('small'); meta.textContent=`${cell.status}${cell.rating ? ` · ${cell.rating}★` : ''}`; card.appendChild(meta);
      if(cell.output?.sprite_folder){const image=document.createElement('img');image.loading='lazy';image.alt=title.textContent;image.src=`/file/${cell.output.sprite_folder}/sheet.png`;card.appendChild(image);}
      const action=document.createElement('button');action.type='button';action.className='mini';
      if(cell.status==='queued'||cell.status==='failed'||cell.status==='cancelled'){action.textContent='Start';action.onclick=async()=>{await api(`/api/batches/${experiment.experiment_id}/cells/${cell.cell_id}/submit${projectQuery()}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({generation:{profile:'debug'}})});await syncBatch();};}
      else if(cell.status==='running'){action.textContent='Cancel';action.onclick=async()=>{await api(`/api/batches/${experiment.experiment_id}/cells/${cell.cell_id}/cancel${projectQuery()}`,{method:'POST'});await syncBatch();};}
      else {action.textContent='Promote';action.onclick=async()=>{await api(`/api/batches/${experiment.experiment_id}/cells/${cell.cell_id}/promote${projectQuery()}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:title.textContent})});action.textContent='Promoted';};}
      card.appendChild(action);
      const shortlist=document.createElement('button'); shortlist.type='button'; shortlist.className='mini'; shortlist.textContent='Shortlist';
      shortlist.onclick=async()=>{ await api(`/api/batches/${experiment.experiment_id}/cells/${cell.cell_id}${projectQuery()}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({rating:5,tags:['shortlist'],decision:'shortlisted'})}); shortlist.textContent='Shortlisted'; };
      card.appendChild(shortlist); root.appendChild(card);
    });
  }
  async function syncBatch(){if(!currentBatch)return;await api(`/api/batches/${currentBatch.experiment_id}/synchronize${projectQuery()}`,{method:'POST'});const data=await api(`/api/batches/${currentBatch.experiment_id}${projectQuery()}`);renderBatch(data.experiment);}
  function renderWorkflow() {
    const root=el('productionWorkflowCanvas'); if (!root) return; root.innerHTML='';
    try {
      const workflow=JSON.parse(el('productionWorkflowJson').value); const incoming=new Map();
      (workflow.edges||[]).forEach(edge=>incoming.set(edge.to,edge.from));
      (workflow.nodes||[]).forEach((node,index)=>{
        const card=document.createElement('article');card.className='production-workflow-node';
        card.draggable=true; card.dataset.nodeId=node.id;
        const type=document.createElement('small');type.textContent=node.type;const name=document.createElement('b');name.textContent=node.id;
        card.appendChild(type);card.appendChild(name);
        card.onclick=()=>connectWorkflowNode(node.id);
        card.ondragstart=event=>event.dataTransfer.setData('text/plain',node.id);
        card.ondragover=event=>event.preventDefault();
        card.ondrop=event=>{event.preventDefault();const source=event.dataTransfer.getData('text/plain');if(source&&source!==node.id)connectWorkflowNodes(source,node.id);};
        root.appendChild(card);
      });
      (workflow.edges||[]).forEach(edge=>{const label=document.createElement('span');label.className='production-workflow-edge';label.textContent=`${edge.from}.${edge.output} → ${edge.to}.${edge.input}`;root.appendChild(label);});
    } catch (_) { root.textContent='Fix JSON to preview the graph.'; }
  }
  function workflowDocument(){return JSON.parse(el('productionWorkflowJson').value);}
  function writeWorkflow(workflow){el('productionWorkflowJson').value=JSON.stringify(workflow,null,2);renderWorkflow();}
  function addWorkflowNode(){const workflow=workflowDocument();const type=el('productionNodeType').value;let id=type;let suffix=2;while((workflow.nodes||[]).some(node=>node.id===id))id=`${type}_${suffix++}`;workflow.nodes=workflow.nodes||[];workflow.edges=workflow.edges||[];workflow.nodes.push({id,type,parameters:{}});writeWorkflow(workflow);}
  function connectWorkflowNode(nodeId){if(!graphConnectSource){graphConnectSource=nodeId;set('productionWorkflowStatus',`Selected ${nodeId}; choose a target node.`);return;}connectWorkflowNodes(graphConnectSource,nodeId);graphConnectSource='';}
  function connectWorkflowNodes(sourceId,targetId){const workflow=workflowDocument();const source=workflow.nodes.find(node=>node.id===sourceId);const target=workflow.nodes.find(node=>node.id===targetId);if(!source||!target||source===target)return;const output=(NODE_PORTS[source.type]||['asset'])[0];const inputs={transform:'asset',background_remove:'asset',frame_extract:'asset',style_conform:'asset',qa:'asset',conditional:'report',approval:'asset',export:'asset',comfyui:'asset',generate:'reference'};const input=inputs[target.type];if(!input){set('productionWorkflowStatus',`${target.type} has no compatible input.`);return;}workflow.edges=workflow.edges||[];workflow.edges=workflow.edges.filter(edge=>!(edge.to===targetId&&edge.input===input));workflow.edges.push({from:sourceId,output,to:targetId,input});writeWorkflow(workflow);}
  function animationDocument(){return JSON.parse(el('productionAnimationJson').value);}
  function overlayFrame(workspace){const index=Math.max(0,Math.min((workspace.frames||[]).length-1,Number(el('productionOverlayFrame').value||0)));return workspace.frames[index];}
  function renderOverlay(){const canvas=el('productionOverlayCanvas');if(!canvas)return;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#111827';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.strokeStyle='#26364d';for(let x=0;x<canvas.width;x+=16){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,canvas.height);ctx.stroke();}for(let y=0;y<canvas.height;y+=16){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(canvas.width,y);ctx.stroke();}try{const frame=overlayFrame(animationDocument());if(!frame)return;(frame.hitboxes||[]).forEach((box,index)=>{ctx.strokeStyle=box.kind==='hit'?'#fb7185':'#4ade80';ctx.lineWidth=2;ctx.strokeRect(box.x,box.y,box.width,box.height);ctx.fillStyle=ctx.strokeStyle;ctx.fillText(box.name||`box ${index}`,box.x+3,box.y+12);});Object.entries(frame.anchors||{}).forEach(([name,point])=>{ctx.fillStyle='#38bdf8';ctx.beginPath();ctx.arc(point.x,point.y,6,0,Math.PI*2);ctx.fill();ctx.fillText(name,point.x+9,point.y+4);});}catch(_){} }
  function moveFootAnchor(event){const workspace=animationDocument();const frame=overlayFrame(workspace);if(!frame)return;const rect=event.target.getBoundingClientRect();frame.anchors=frame.anchors||{};frame.anchors.foot={x:Math.round((event.clientX-rect.left)*(event.target.width/rect.width)),y:Math.round((event.clientY-rect.top)*(event.target.height/rect.height))};el('productionAnimationJson').value=JSON.stringify(workspace,null,2);renderOverlay();}
  function addHitbox(){const workspace=animationDocument();const frame=overlayFrame(workspace);if(!frame)return;frame.hitboxes=frame.hitboxes||[];frame.hitboxes.push({name:`hitbox_${frame.hitboxes.length+1}`,kind:'collision',x:32,y:32,width:64,height:64});el('productionAnimationJson').value=JSON.stringify(workspace,null,2);renderOverlay();}
  async function loadAnimationAssets() {
    if (!projectQuery()) return;
    const data=await api('/api/assets'+projectQuery()); const select=el('productionAnimationAsset'); const previous=select.value;
    select.innerHTML='<option value="">Select an asset</option>';
    data.assets.filter(asset=>asset.asset_type==='animation'||asset.asset_type==='sprite').forEach(asset=>{const option=document.createElement('option');option.value=asset.asset_id;option.textContent=`${asset.name} · ${asset.action||asset.asset_type} ${asset.direction||''}`;select.appendChild(option);});
    if(previous) select.value=previous;
  }
  async function loadAnimation() {
    const assetId=el('productionAnimationAsset').value; if(!assetId) throw new Error('Select an animation asset.');
    const data=await api(`/api/animation/${assetId}/workspace${projectQuery()}`);
    if(data.workspace) el('productionAnimationJson').value=JSON.stringify(data.workspace,null,2);
    renderOverlay();
    set('productionAnimationStatus',data.workspace?`Loaded revision ${data.revision_id}.`:'No workspace saved; edit the starter metadata.');
  }
  async function saveAnimation() {
    const assetId=el('productionAnimationAsset').value; if(!assetId) throw new Error('Select an animation asset.');
    const workspace=JSON.parse(el('productionAnimationJson').value);
    const data=await api(`/api/animation/${assetId}/workspace${projectQuery()}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace})});
    set('productionAnimationStatus',`Saved immutable revision ${data.revision.revision_id}.`);
  }
  async function workflow(save) {
    const workflow = JSON.parse(el('productionWorkflowJson').value);
    const path = save ? '/api/workflows' : '/api/workflows/validate';
    const data = await api(path + projectQuery(), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workflow})});
    if(data.workflow)currentWorkflow=data.workflow;
    el('productionWorkflowStatus').textContent = JSON.stringify(data.workflow || data, null, 2);
  }
  async function runWorkflow(){if(!currentWorkflow)await workflow(true);const data=await api(`/api/workflows/${currentWorkflow.workflow_id}/runs${projectQuery()}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{"inputs":{}}'});currentWorkflowRun=data.run;el('productionWorkflowStatus').textContent=JSON.stringify(data.run,null,2);}
  async function syncWorkflow(){if(!currentWorkflowRun)throw new Error('Run a workflow first.');const data=await api(`/api/workflows/runs/${currentWorkflowRun.run_id}/synchronize${projectQuery()}`,{method:'POST'});currentWorkflowRun=data.run.continuation||data.run;el('productionWorkflowStatus').textContent=JSON.stringify(data.run,null,2);}
  async function snapshots() {
    if (!projectQuery()) { el('productionSnapshots').innerHTML='<div class="empty compact">Select a project to manage snapshots.</div>'; return; }
    const data = await api('/api/recovery/snapshots' + projectQuery());
    const root = el('productionSnapshots'); root.innerHTML = '';
    if (!data.snapshots.length) root.innerHTML = '<div class="empty compact">No recovery snapshots yet.</div>';
    data.snapshots.forEach(item => { const row=document.createElement('div'); row.className='release-row'; row.textContent=`${item.created_at || item.path} · ${item.valid ? 'verified' : 'invalid'}`; root.appendChild(row); });
  }
  async function exportPreset(publish){if(!projectQuery())throw new Error('Select a project.');const preset_id=el('productionExportPreset').value;const path=publish?'/api/export-presets/export':'/api/export-presets/preview';const data=await api(path+projectQuery(),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset_id})});el('productionExportStatus').textContent=JSON.stringify(data.preview||data.manifest||data,null,2);if(publish)refreshProduction();}
  function bind() {
    if (!el('productionRefreshBtn') || window.__productionBound) return;
    window.__productionBound = true;
    el('productionRefreshBtn').onclick = refreshProduction;
    el('productionBatchDimensions').addEventListener('input', estimateBatch);
    el('productionWorkflowJson').addEventListener('input', renderWorkflow);
    el('productionAnimationJson').addEventListener('input',renderOverlay);
    el('productionOverlayFrame').addEventListener('input',renderOverlay);
    el('productionOverlayCanvas').addEventListener('pointerdown',moveFootAnchor);
    el('productionAddHitboxBtn').onclick=addHitbox;
    el('productionAddNodeBtn').onclick=()=>{try{addWorkflowNode();}catch(error){set('productionWorkflowStatus',error.message);}};
    el('productionCreateBatchBtn').onclick = () => createBatch().catch(error => toast(error.message));
    el('productionBatchSyncBtn').onclick=()=>syncBatch().catch(error=>toast(error.message));
    el('productionValidateWorkflowBtn').onclick = () => workflow(false).catch(error => set('productionWorkflowStatus', error.message));
    el('productionSaveWorkflowBtn').onclick = () => workflow(true).catch(error => set('productionWorkflowStatus', error.message));
    el('productionRunWorkflowBtn').onclick=()=>runWorkflow().catch(error=>set('productionWorkflowStatus',error.message));
    el('productionSyncWorkflowBtn').onclick=()=>syncWorkflow().catch(error=>set('productionWorkflowStatus',error.message));
    el('productionLoadSnapshotsBtn').onclick = () => snapshots().catch(error => toast(error.message));
    el('productionSnapshotBtn').onclick = async () => { await api('/api/recovery/snapshots' + projectQuery(), {method:'POST'}); await snapshots(); toast('Recovery snapshot created.'); };
    el('productionPreviewExportBtn').onclick=()=>exportPreset(false).catch(error=>set('productionExportStatus',error.message));
    el('productionExportBtn').onclick=()=>exportPreset(true).catch(error=>set('productionExportStatus',error.message));
    el('productionLoadAnimationBtn').onclick=()=>loadAnimation().catch(error=>set('productionAnimationStatus',error.message));
    el('productionSaveAnimationBtn').onclick=()=>saveAnimation().catch(error=>set('productionAnimationStatus',error.message));
    estimateBatch(); renderWorkflow(); renderOverlay();
    if (projectQuery()) { refreshProduction(); snapshots().catch(() => {}); loadAnimationAssets().catch(()=>{}); }
  }
  window.refreshProductionStudio = refreshProduction;
  window.viewComponentsLoaded?.then(bind);
})();
