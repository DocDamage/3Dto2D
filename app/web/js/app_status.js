// Status-related UI handlers for SpriteForge Studio

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

function updateHealthBar(s) {
  const total = 5;
  let passed = 0;
  if (s.comfy_running) passed++;
  if (s.models.ok) passed++;
  if (s.gpu.ok) passed++;
  if (s.disk.ok) passed++;
  if (!s.job.running) passed++;
  
  const pct = (passed / total) * 100;
  const bar = $('#dashboard-health-fill');
  if (bar) {
    bar.style.width = `${pct}%`;
    if (pct < 50) bar.style.backgroundColor = '#ec5f5f';
    else if (pct < 100) bar.style.backgroundColor = '#ecb15f';
    else bar.style.backgroundColor = '#6eec5f';
  }
}
