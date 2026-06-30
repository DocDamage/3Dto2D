// Job and progress handling with EventSource (SSE) for SpriteForge Studio

let eventSource = null;

function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }
  
  eventSource = new EventSource('/api/status/stream');
  
  eventSource.onmessage = function(event) {
    try {
      const data = JSON.parse(event.data);
      if (data.job) {
        renderJob(data.job);
        setChip('#chip-comfy', data.comfy_running ? 'ok' : 'warn', 'ComfyUI: ' + (data.comfy_running ? 'online' : 'offline'));
        if (data.gpu) {
          setChip('#chip-gpu', data.gpu.ok ? 'ok' : 'warn', data.gpu.ok ? `${data.gpu.label} · ${data.gpu.memory_total || ''}` : 'GPU: check driver');
        }
        
        // Trigger output/dashboard refresh when a running job finishes
        if (window.previousJobRunning && !data.job.running) {
          if (typeof refreshAll === 'function') refreshAll();
        }
        window.previousJobId = data.job.id;
        window.previousJobRunning = !!data.job.running;
      }
    } catch (err) {
      console.error("SSE error:", err);
    }
  };
  
  eventSource.onerror = function(err) {
    console.warn("SSE disconnected. Falling back to default HTTP polling.");
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };
}

function inferredJobProgress(job, running) {
  if (!running) return job.exit_code === 0 ? 100 : 0;
  return job.progress || 10;
}

function renderGlobalProgress(job) {
  const bar = $('#global-progress-bar');
  if (bar) {
    bar.style.width = `${inferredJobProgress(job, job.running)}%`;
  }
}

function setProgressFill(el, pct, status) {
  if (!el) return;
  el.style.width = `${pct}%`;
  el.className = 'progress-fill ' + status;
}

function renderJob(job) {
  const running = !!job.running;
  const progress = inferredJobProgress(job, running);
  
  const jTitle = $('#job-title');
  const lTitle = $('#log-title');
  const jState = $('#job-state');
  const mLog = $('#mini-log');
  const fLog = $('#full-log');
  const progFill = $('#progress-fill');
  
  if (jTitle) jTitle.textContent = job.title || 'Idle';
  if (lTitle) lTitle.textContent = job.title || 'Idle';
  if (jState) {
    jState.textContent = running ? (job.stage_label || 'running') : (job.exit_code === 0 ? 'passed' : (job.exit_code ? 'failed' : 'ready'));
    jState.className = 'badge ' + (running ? 'busy' : '');
  }
  if (progFill) {
    setProgressFill(progFill, progress, running ? 'busy' : job.exit_code === 0 ? 'done' : job.exit_code ? 'failed' : '');
  }
  renderGlobalProgress(job);
  
  const logs = (job.logs || []).join('\n');
  window.lastLogText = logs;
  if (mLog) mLog.textContent = (job.logs || []).slice(-80).join('\n');
  if (fLog) fLog.textContent = logs || 'No command has been run yet.';
  
  if (mLog) mLog.scrollTop = mLog.scrollHeight;
  if (fLog) fLog.scrollTop = fLog.scrollHeight;

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
          currentStep = 'loading model weights';
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
      const eta = job.eta_label || job.metadata?.eta?.label || estTime;
      const elapsed = job.elapsed_seconds ? `Elapsed: ${formatDuration(job.elapsed_seconds)} · ` : '';
      const remaining = job.remaining_seconds !== null && job.remaining_seconds !== undefined ? ` · Remaining: ${formatDuration(job.remaining_seconds)}` : '';
      const progressMode = job.progress_mode === 'comfy_ws' ? 'Exact ComfyUI websocket progress' : 'Estimated progress';
      const detail = job.stage_detail || currentStep;
      timeStateEl.innerHTML = `${elapsed}ETA: ${eta}${remaining}<br>${progressMode}: ${detail}`;
    } else {
      timeStateEl.style.display = 'none';
      timeStateEl.innerHTML = '';
    }
  }
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (mins >= 60) {
    const hours = Math.floor(mins / 60);
    return `${hours}h ${mins % 60}m`;
  }
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

// Connect SSE on load
window.addEventListener('DOMContentLoaded', connectSSE);
