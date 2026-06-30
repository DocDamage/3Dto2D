// app_forms.js — Form submit wiring, runAction triggers, and recommended action
// Extracted from app_main.js

let recommendedAction = '';

function runRecommended(){
  if(!recommendedAction){ toast('No recommendation available yet.'); return; }
  if(recommendedAction==='launch_comfy'){ api('/api/launch_comfy',{method:'POST'}).then(()=>toast('ComfyUI launch requested')).then(refreshAll); return; }
  if(recommendedAction==='generate_debug'){
    showView('generate');
    const f=$('#generateForm');
    if(f.querySelector('[name="profile"]')) f.querySelector('[name="profile"]').value='debug';
    if(f.querySelector('[name="sprite_action"]')) f.querySelector('[name="sprite_action"]').value='idle';
    if(f.querySelector('[name="direction"]')) f.querySelector('[name="direction"]').value='front';
    toast('Debug settings loaded. Click Generate WAN → Sprite when ready.');
    return;
  }
  if(recommendedAction==='qa_report'){ showView('quality'); toast('Select a sprite, then run QA.'); return; }
  if(recommendedAction==='release_package'){ showView('release'); toast('Add sprite folders, then build a release ZIP.'); return; }
  runAction(recommendedAction); showView('logs');
}

function initFormBindings() {
  // Nav, jump, run, open binders
  $$('.nav').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
  $$('[data-jump]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.jump)));
  $$('[data-run]').forEach(b=>b.addEventListener('click',()=>runAction(b.dataset.run)));
  $$('[data-open]').forEach(b=>b.addEventListener('click',()=>openPath(b.dataset.open)));

  if ($('#refreshOutputs')) $('#refreshOutputs').addEventListener('click', refreshAll);
  if ($('#cancelJob')) $('#cancelJob').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
  if ($('#cancelJob2')) $('#cancelJob2').addEventListener('click',()=>api('/api/cancel',{method:'POST'}).then(refreshAll));
  if ($('#copyLog')) $('#copyLog').addEventListener('click',()=>navigator.clipboard.writeText(lastLogText||'').then(()=>toast('Log copied')));
  if ($('#launchComfy')) $('#launchComfy').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });

  // Generation form
  if ($('#generateForm')) $('#generateForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('generate_sprite', formData(e.currentTarget)); showView('logs'); });
  if ($('#btnPreviewGenerate')) {
    $('#btnPreviewGenerate').addEventListener('click', () => {
      const data = formData($('#generateForm'));
      runAction('generate_sprite', { ...data, preview: true });
      showView('logs');
    });
  }
  if ($('#convertForm')) $('#convertForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('convert_video', formData(e.currentTarget)); showView('logs'); });

  // Quality actions
  $$('[data-quality]').forEach(btn=>btn.addEventListener('click',()=>{
    const data=formData($('#qualityForm')); const mode=btn.dataset.quality;
    if(mode==='validate'){
      runAction('validate_export', {...data, engine: null}); showView('logs'); return;
    }
    const action = mode==='qa'?'qa_report':mode==='fix'?'autofix':mode==='godot'?'export_godot':mode==='unity'?'export_unity':'export_unreal';
    runAction(action, data); showView('logs');
  }));
  if ($('#packForm')) $('#packForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('character_pack', formData(e.currentTarget)); showView('logs'); });
  if ($('#atlasForm')) $('#atlasForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('atlas', formData(e.currentTarget)); showView('logs'); });

  // Release and queue forms
  if ($('#releaseForm')) $('#releaseForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('release_package', formData(e.currentTarget)); showView('logs'); });
  if ($('#queueForm')) $('#queueForm').addEventListener('submit',e=>{ e.preventDefault(); runAction('queue_create', formData(e.currentTarget)); showView('logs'); });

  // Dropzone
  const dz=$('#dropzone'), vf=$('#videoFile');
  if (dz && vf) {
    ['dragenter','dragover'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add('drag')}));
    ['dragleave','drop'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove('drag')}));
    dz.addEventListener('drop',e=>{ const f=e.dataTransfer.files?.[0]; if(f) uploadFile(f).catch(err=>toast(err.message)); });
    vf.addEventListener('change',()=>{ const f=vf.files?.[0]; if(f) uploadFile(f).catch(err=>toast(err.message)); });
  }

  // Run next action / guided
  if($('#runNextAction')) $('#runNextAction').addEventListener('click', runRecommended);
  if($('#guidedRecommended')) $('#guidedRecommended').addEventListener('click', runRecommended);
  if($('#launchComfy2')) $('#launchComfy2').addEventListener('click',async()=>{ try{await api('/api/launch_comfy',{method:'POST'}); toast('ComfyUI launch requested'); setTimeout(refreshAll,1800);}catch(e){toast(e.message)} });

  // Project select
  if($('#projectSelect')) $('#projectSelect').addEventListener('change', async e => {
    activeProjectPath = e.currentTarget.value || '';
    try{
      await api('/api/projects/active',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:activeProjectPath})});
      toast(activeProjectPath ? 'Project selected' : 'Global workspace selected');
      await refreshAll();
      if ($('#view-release')?.classList.contains('active') && typeof loadReleases === 'function') await loadReleases();
      if ($('#view-history')?.classList.contains('active') && typeof loadHistory === 'function') await loadHistory();
      if ($('#view-queues')?.classList.contains('active') && typeof loadQueues === 'function') await loadQueues();
      if ($('#view-packs')?.classList.contains('active')) {
        if (typeof loadPacks === 'function') await loadPacks();
        if (typeof loadPlanning === 'function') await loadPlanning();
      }
      if ($('#view-quality')?.classList.contains('active') && typeof loadQualityReports === 'function') await loadQualityReports();
      if ($('#view-convert')?.classList.contains('active') && typeof loadReferences === 'function') await loadReferences();
    }catch(err){ toast('Project select failed: '+err.message); }
  });
  if($('#createProjectBtn')) $('#createProjectBtn').addEventListener('click', createProject);
  if($('#projectNameInput')) $('#projectNameInput').addEventListener('keydown', e => {
    if(e.key === 'Enter'){ e.preventDefault(); createProject(); }
  });
}