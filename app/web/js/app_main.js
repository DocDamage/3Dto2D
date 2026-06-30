// app_main.js — Thin glue: refreshAll + DOM init orchestration
// All function implementations are in: app_forms.js, app_listings.js, app_dashboard.js

let previousJobId = null;
let previousJobRunning = false;

async function refreshAll() {
  try {
    const s = await api('/api/status' + projectQuery());
    window._latestStatus = s;
    setChip('#chip-comfy', s.comfy_running ? 'ok' : 'warn', 'ComfyUI: ' + (s.comfy_running ? 'online' : 'offline'));
    const modelState = s.models.ok ? 'ok' : 'warn';
    const adv = s.models.advanced_total ? ` · 2.2 ${s.models.advanced_present}/${s.models.advanced_total}` : '';
    setChip('#chip-models', modelState, `WAN safe: ${s.models.present}/${s.models.total}${adv}`);
    setChip('#chip-gpu', s.gpu.ok ? 'ok' : 'warn', s.gpu.ok ? `${s.gpu.label} · ${s.gpu.memory_total||''}` : 'GPU: check driver');
    $('#stat-comfy').textContent = s.comfy_running ? 'Online' : 'Offline';
    $('#stat-comfy-detail').textContent = s.comfy_url;
    $('#stat-models').textContent = `Safe ${s.models.present}/${s.models.total}`;
    $('#stat-models-detail').textContent = `Wan 2.2 5B: ${s.models.advanced_present}/${s.models.advanced_total}`;
    $('#stat-disk').textContent = `${s.disk.free_gb} GB`;
    recommendedAction = s.next_step?.action || '';
    if ($('#next-step-title')) $('#next-step-title').textContent = s.next_step?.step || 'Ready';
    if ($('#next-step-reason')) $('#next-step-reason').textContent = s.next_step?.reason || 'No recommendation available.';
    if ($('#guidedNextTitle')) $('#guidedNextTitle').textContent = s.next_step?.step || 'Ready';
    if ($('#guidedNextReason')) $('#guidedNextReason').textContent = s.next_step?.reason || 'No recommendation available.';

    if (typeof renderProjectSummary === 'function') renderProjectSummary(s.project_workspace);
    if (typeof renderOutputs === 'function') renderOutputs(s.outputs);
    renderJob(s.job);
    updatePreflightChecklist(s);
    if (typeof updateHealthBar === 'function') updateHealthBar(s);
    if (typeof updateHealthProgress === 'function') updateHealthProgress(s);
    renderTaskCenter(s);

    const currentView = localStorage.getItem('activeView') || 'guide';
    if (currentView === 'library' && typeof refreshLibrary === 'function') refreshLibrary();
    if (currentView === 'qa_dashboard' && typeof refreshQaDashboard === 'function') refreshQaDashboard();
    if (currentView === 'ab_runs' && typeof refreshAbRuns === 'function') refreshAbRuns();

    const activeJob = s.job;
    const activeJobId = activeJob ? activeJob.id : null;
    const activeJobRunning = activeJob ? !!activeJob.running : false;
    if (previousJobId && previousJobId === activeJobId && previousJobRunning && !activeJobRunning) {
      const exitCode = activeJob.exit_code;
      const spriteFolder = activeJob.metadata ? activeJob.metadata.sprite_folder : null;
      if (exitCode === 0) {
        const duration = formatDuration(activeJob.started_at, activeJob.finished_at);
        const message = `${activeJob.title || 'Task'} passed in ${duration}. ${activeJob.stage_detail || ''}`.trim();
        addNotification('Task Passed', message, 'success', spriteFolder ? { label: 'Inspect Output', spriteFolder } : null);
        if (spriteFolder) openResultPreview(spriteFolder);
      } else {
        const logs = (activeJob.logs || []).slice(-8).join(' ');
        const detail = activeJob.stage_detail || `Exit code ${exitCode}.`;
        const hint = logs.match(/ERROR:?\s*([^[]+)/i);
        addNotification('Task Failed', `${activeJob.title || 'Task'} failed. ${detail}${hint ? ' ' + hint[1].trim() : ''}`, 'error', { label: 'View in Task Center', view: 'tasks' });
      }
    }
    previousJobId = activeJobId;
    previousJobRunning = activeJobRunning;

    if ($('#view-dashboard') && $('#view-dashboard').classList.contains('active')) {
      renderProjectDashboard(s);
    }
    if (window.UxEnhancements && typeof window.UxEnhancements.refreshFromStatus === 'function') {
      window.UxEnhancements.refreshFromStatus(s);
    }
  } catch (e) { console.error(e); }
}

let pollIntervalId = null;
function updatePollingInterval() {
  if (pollIntervalId) {
    clearInterval(pollIntervalId);
  }
  const interval = window._sseActive ? 15000 : 3000;
  pollIntervalId = setInterval(refreshAll, interval);
}

// Init all bindings on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  loadProjects();
  if (typeof initFormBindings === 'function') initFormBindings();
  if (typeof initListingsBindings === 'function') initListingsBindings();
  if (typeof initDashboardBindings === 'function') initDashboardBindings();
  refreshAll();
  updatePollingInterval();
});
