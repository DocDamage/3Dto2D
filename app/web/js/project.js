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
  const data=await api('/api/upload',{method:'POST',body:fd});
  if(!data.ok) throw new Error(data.message||'Upload failed');
  $('#videoPath').value=data.path; toast('Uploaded: '+data.relative);
  if (typeof loadReferences === 'function') await loadReferences();
}
