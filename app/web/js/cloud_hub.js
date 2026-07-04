function cloudHubTags(value) {
  return String(value || '').split(',').map(item => item.trim()).filter(Boolean);
}

function cloudHubStatusText(node) {
  const status = node.last_status || {};
  if (!status.checked_at) return 'unchecked';
  return status.ok ? `online ${status.latency_ms || 0}ms` : 'offline';
}

function renderCloudHub(data) {
  const selected = $('#cloudHubSelected');
  if (selected) {
    const node = data.selected;
    selected.textContent = node
      ? `Selected: ${node.label} (${node.url})`
      : 'No enabled cloud node selected yet.';
  }

  const target = $('#cloudHubNodes');
  if (!target) return;
  clearNode(target);
  const nodes = data.nodes || [];
  if (!nodes.length) {
    target.textContent = 'No configured nodes.';
    return;
  }
  nodes.forEach(node => {
    const row = document.createElement('article');
    row.className = 'cloud-hub-node';
    const status = node.last_status || {};
    const pillClass = status.checked_at ? (status.ok ? 'ok' : 'warn') : '';
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(node.label)}</strong>
        <span>${escapeHtml(node.url)}</span>
        <small>${escapeHtml(node.id)} · priority ${Number(node.priority || 100)} · ${escapeHtml(node.status || 'ready')} · ${Number(node.active_jobs || 0)}/${Number(node.max_jobs || 1)} jobs · ${escapeHtml((node.capabilities || []).join(', '))}</small>
      </div>
      <div class="button-row compact-actions">
        <span class="cloud-hub-pill ${pillClass}">${escapeHtml(cloudHubStatusText(node))}</span>
        <button class="mini ghost" type="button" data-cloud-state="${escapeHtml(node.id)}" data-cloud-status="ready" data-cloud-enabled="true">Resume</button>
        <button class="mini ghost" type="button" data-cloud-state="${escapeHtml(node.id)}" data-cloud-status="draining" data-cloud-enabled="true">Drain</button>
        <button class="mini ghost" type="button" data-cloud-state="${escapeHtml(node.id)}" data-cloud-status="offline" data-cloud-enabled="false">Offline</button>
        <button class="mini" type="button" data-cloud-edit="${escapeHtml(node.id)}">Edit</button>
        <button class="mini danger" type="button" data-cloud-delete="${escapeHtml(node.id)}">Delete</button>
      </div>
    `;
    target.appendChild(row);
  });
}

async function refreshCloudHub(check=false) {
  const query = check ? '?check=1' : '';
  const data = await api('/api/cloud/nodes' + query);
  window.cloudHubNodes = data.nodes || [];
  renderCloudHub(data);
}

function renderCloudHubSkeleton(target, label) {
  if (!target) return;
  target.innerHTML = `
    <div class="skeleton-stack" aria-label="${escapeHtml(label || 'Loading')}">
      <div class="skeleton-card"></div>
      <div class="skeleton-line medium"></div>
      <div class="skeleton-line short"></div>
    </div>
  `;
}

function renderCloudImageProviders(data) {
  const target = $('#cloudImageProviders');
  if (!target) return;
  clearNode(target);
  const providers = Object.values(data.providers || {});
  if (!providers.length) {
    target.textContent = 'No provider status available.';
    return;
  }
  providers.forEach(provider => {
    const row = document.createElement('div');
    row.className = 'cloud-hub-provider';
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(provider.provider)}</strong>
        <small>${escapeHtml(provider.configured_env_name || provider.env_names.join(', '))}</small>
      </div>
      <span class="cloud-hub-pill ${provider.configured ? 'ok' : 'warn'}">${provider.configured ? 'configured' : 'missing key'}</span>
    `;
    target.appendChild(row);
  });
}

async function refreshCloudImageProviders() {
  renderCloudHubSkeleton($('#cloudImageProviders'), 'Loading cloud image providers');
  const data = await api('/api/cloud/image-providers');
  renderCloudImageProviders(data);
}

function renderCloudImagePlan(plan) {
  const target = $('#cloudImagePlanResult');
  if (!target) return;
  clearNode(target);
  const summary = document.createElement('div');
  summary.className = 'cloud-hub-provider';
  summary.innerHTML = `
    <div>
      <strong>${escapeHtml(plan.provider)} · ${escapeHtml(plan.model)}</strong>
      <small>${Number(plan.frame_count || 0)} frame(s), ${escapeHtml(plan.generation_size)} to ${escapeHtml(plan.cell_size)} · ${escapeHtml(plan.configured_env_name || 'key missing')}</small>
    </div>
    <span class="cloud-hub-pill ${plan.provider_configured ? 'ok' : 'warn'}">${plan.provider_configured ? 'ready' : 'missing key'}</span>
  `;
  target.appendChild(summary);
  (plan.processing_steps || []).forEach(step => {
    const item = document.createElement('div');
    item.className = 'compact';
    item.textContent = `${step.name}: ${step.detail}`;
    target.appendChild(item);
  });
  (plan.hardened_prompts || []).slice(0, 3).forEach((prompt, index) => {
    appendText(target, 'code', `Prompt ${index + 1}: ${prompt}`);
  });
}

async function previewCloudImagePlan() {
  renderCloudHubSkeleton($('#cloudImagePlanResult'), 'Planning cloud image sprite');
  const body = {
    prompt: $('#cloudImagePlanPrompt')?.value || '',
    provider: $('#cloudImagePlanProvider')?.value || 'openai',
    frames: Number($('#cloudImagePlanFrames')?.value || 1),
    size: $('#cloudImagePlanSize')?.value || '1024x1024',
    cell_size: $('#cloudImagePlanCellSize')?.value || '64x64',
  };
  const data = await api('/api/cloud/image-generation-plan', { method: 'POST', body: JSON.stringify(body) });
  renderCloudImagePlan(data);
}

function cloudQueueJobsFromText(value) {
  return String(value || '').split('\n').map((line, index) => line.trim() ? ({
    id: `queued-${index + 1}`,
    label: line.trim(),
    prompt: line.trim(),
    capability: 'remote_generate',
    priority: 100 + index,
  }) : null).filter(Boolean);
}

function renderCloudQueuePlan(plan) {
  const target = $('#cloudQueuePlanResult');
  if (!target) return;
  clearNode(target);
  const summary = document.createElement('div');
  summary.className = 'cloud-hub-provider';
  summary.innerHTML = `
    <div>
      <strong>${Number(plan.assignment_count || 0)}/${Number(plan.job_count || 0)} assigned</strong>
      <small>${escapeHtml(plan.message || 'Queue plan ready.')} · dry run ${plan.dry_run ? 'on' : 'off'}</small>
    </div>
    <span class="cloud-hub-pill ${plan.unassigned?.length ? 'warn' : 'ok'}">${plan.non_destructive ? 'safe plan' : 'active'}</span>
  `;
  target.appendChild(summary);
  (plan.assignments || []).forEach(row => {
    const item = document.createElement('div');
    item.className = 'cloud-hub-provider';
    item.innerHTML = `
      <div>
        <strong>${escapeHtml(row.job?.label || row.job?.id || 'queued job')}</strong>
        <small>${escapeHtml(row.node_label || row.node_id)} · queue ${Number(row.queue_position || 0)} · slot ${Number(row.slot_index || 0)} · ${escapeHtml(row.reason || '')}</small>
        <code>${escapeHtml(row.dispatch?.command_hint || row.dispatch?.dispatch_url || '')}</code>
      </div>
      <span class="cloud-hub-pill ok">assigned</span>
    `;
    target.appendChild(item);
  });
  (plan.unassigned || []).forEach(row => {
    const item = document.createElement('div');
    item.className = 'cloud-hub-provider';
    item.innerHTML = `
      <div>
        <strong>${escapeHtml(row.job?.label || row.job?.id || 'queued job')}</strong>
        <small>${escapeHtml((row.reasons || []).join(', '))}</small>
      </div>
      <span class="cloud-hub-pill warn">waiting</span>
    `;
    target.appendChild(item);
  });
}

async function previewCloudQueuePlan() {
  renderCloudHubSkeleton($('#cloudQueuePlanResult'), 'Planning remote queue distribution');
  const jobs = cloudQueueJobsFromText($('#cloudQueueJobs')?.value || '');
  const data = await api('/api/cloud/queue-plan', { method: 'POST', body: JSON.stringify({ jobs }) });
  renderCloudQueuePlan(data);
}

function fillCloudHubForm(node) {
  $('#cloudHubNodeId').value = node.id || '';
  $('#cloudHubNodeLabel').value = node.label || '';
  $('#cloudHubNodeUrl').value = node.url || '';
  $('#cloudHubNodePriority').value = node.priority || 100;
  $('#cloudHubNodeMaxJobs').value = node.max_jobs || 1;
  $('#cloudHubNodeStatus').value = node.status || 'ready';
  $('#cloudHubNodeCapabilities').value = (node.capabilities || ['comfyui', 'remote_generate']).join(', ');
  $('#cloudHubNodeEnabled').checked = node.enabled !== false;
}

async function saveCloudHubNode() {
  const body = {
    id: $('#cloudHubNodeId')?.value || '',
    label: $('#cloudHubNodeLabel')?.value || '',
    url: $('#cloudHubNodeUrl')?.value || '',
    priority: Number($('#cloudHubNodePriority')?.value || 100),
    max_jobs: Number($('#cloudHubNodeMaxJobs')?.value || 1),
    status: $('#cloudHubNodeStatus')?.value || 'ready',
    capabilities: cloudHubTags($('#cloudHubNodeCapabilities')?.value || 'comfyui, remote_generate'),
    enabled: $('#cloudHubNodeEnabled')?.checked !== false,
  };
  await api('/api/cloud/nodes', { method: 'POST', body: JSON.stringify(body) });
  toast('Cloud node saved.');
  await refreshCloudHub(false);
}

async function deleteCloudHubNode(id) {
  await api('/api/cloud/nodes/' + encodeURIComponent(id), { method: 'DELETE' });
  toast('Cloud node removed.');
  await refreshCloudHub(false);
}

async function updateCloudHubNodeState(id, status, enabled) {
  const node = (window.cloudHubNodes || []).find(item => item.id === id);
  if (!node) return toast('Cloud node not found.');
  const body = {
    ...node,
    status: status || node.status || 'ready',
    enabled: enabled !== false,
  };
  await api('/api/cloud/nodes', { method: 'POST', body: JSON.stringify(body) });
  toast(`Cloud node ${body.label || body.id} set to ${body.enabled ? body.status : 'offline'}.`);
  await refreshCloudHub(false);
}

function installCloudHub() {
  if (!$('#view-cloud_hub')) return;
  $('#cloudHubRefresh')?.addEventListener('click', () => refreshCloudHub(false).catch(err => toast(err.message)));
  $('#cloudHubCheck')?.addEventListener('click', () => refreshCloudHub(true).catch(err => toast(err.message)));
  $('#cloudImageProviderRefresh')?.addEventListener('click', () => refreshCloudImageProviders().catch(err => toast(err.message)));
  $('#cloudImagePlanPreview')?.addEventListener('click', () => previewCloudImagePlan().catch(err => toast(err.message)));
  $('#cloudQueuePlanPreview')?.addEventListener('click', () => previewCloudQueuePlan().catch(err => toast(err.message)));
  $('#cloudHubSave')?.addEventListener('click', () => saveCloudHubNode().catch(err => toast(err.message)));
  $('#cloudHubNodes')?.addEventListener('click', event => {
    const editId = event.target?.dataset?.cloudEdit;
    const deleteId = event.target?.dataset?.cloudDelete;
    const stateId = event.target?.dataset?.cloudState;
    if (editId) {
      const node = (window.cloudHubNodes || []).find(item => item.id === editId);
      if (node) fillCloudHubForm(node);
    }
    if (stateId) {
      const enabled = event.target?.dataset?.cloudEnabled !== 'false';
      updateCloudHubNodeState(stateId, event.target?.dataset?.cloudStatus || 'ready', enabled).catch(err => toast(err.message));
    }
    if (deleteId) deleteCloudHubNode(deleteId).catch(err => toast(err.message));
  });
  refreshCloudHub(false).catch(() => {});
  refreshCloudImageProviders().catch(() => {});
}

window.viewComponentsLoaded?.then(installCloudHub);
