(function () {
  const state = {
    bundle: null,
    meta: null,
    sheet: null,
    frame: 0,
    playing: false,
    raf: 0,
    lastTime: 0,
    accumulator: 0,
    panX: 0,
    panY: 0,
    dragging: false,
    dragStart: null,
    recording: false,
  };

  function el(id) {
    return document.getElementById(id);
  }

  function playerReady() {
    return el('animationCanvas') && el('animationSpriteSelect');
  }

  function populateSpriteSelect() {
    const select = el('animationSpriteSelect');
    if (!select) return;
    const outputs = typeof currentOutputs !== 'undefined' ? currentOutputs : [];
    const previous = select.value;
    select.innerHTML = '<option value="">Select a sprite output</option>';
    outputs.forEach((item) => {
      const opt = document.createElement('option');
      opt.value = item.path || '';
      opt.textContent = `${item.name || item.path || 'sprite'} (${item.frame_count || '?'} frames)`;
      select.appendChild(opt);
    });
    if (previous && Array.from(select.options).some((opt) => opt.value === previous)) {
      select.value = previous;
    }
  }

  function frameRect(index) {
    const meta = state.meta || {};
    const frame = (meta.frames || [])[index] || {};
    const fw = Number(meta.frame_width || frame.w || 1);
    const fh = Number(meta.frame_height || frame.h || 1);
    const columns = Math.max(1, Number(meta.columns || 1));
    return {
      sx: Number(frame.x ?? ((index % columns) * fw)),
      sy: Number(frame.y ?? (Math.floor(index / columns) * fh)),
      sw: Number(frame.w || fw),
      sh: Number(frame.h || fh),
      duration: Number(frame.duration_ms || (1000 / Math.max(1, Number(meta.fps || 12)))),
      fw,
      fh,
    };
  }

  function drawSheetFrame(ctx, index, alpha, dx, dy) {
    if (!state.sheet || !state.meta) return;
    const rect = frameRect(index);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.drawImage(state.sheet, rect.sx, rect.sy, rect.sw, rect.sh, dx, dy, rect.fw, rect.fh);
    ctx.restore();
  }

  function render() {
    const canvas = el('animationCanvas');
    if (!canvas || !state.meta || !state.sheet) return;
    const rect = frameRect(state.frame);
    canvas.width = rect.fw;
    canvas.height = rect.fh;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const onionCount = Number(el('animationOnionSlider')?.value || 0);
    const frameCount = Number(state.meta.frame_count || 1);
    for (let i = onionCount; i >= 1; i -= 1) {
      drawSheetFrame(ctx, (state.frame - i + frameCount) % frameCount, 0.16, 0, 0);
      drawSheetFrame(ctx, (state.frame + i) % frameCount, 0.12, 0, 0);
    }
    drawSheetFrame(ctx, state.frame, 1, 0, 0);

    const zoom = Number(el('animationZoomSlider')?.value || 4);
    canvas.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${zoom})`;

    const scrub = el('animationFrameScrubber');
    if (scrub) scrub.value = String(state.frame);
    const label = el('animationFrameLabel');
    if (label) label.textContent = `Frame ${state.frame + 1} / ${frameCount}`;
    const duration = el('animationDurationLabel');
    if (duration) duration.textContent = `${Math.round(rect.duration)} ms`;
    document.querySelectorAll('.animation-tick').forEach((tick) => {
      tick.classList.toggle('active', Number(tick.dataset.frame || 0) === state.frame);
    });
  }

  function setFrame(index) {
    const count = Number(state.meta?.frame_count || 1);
    state.frame = Math.max(0, Math.min(count - 1, index));
    render();
  }

  function tick(time) {
    if (!state.playing) return;
    if (!state.lastTime) state.lastTime = time;
    state.accumulator += time - state.lastTime;
    state.lastTime = time;
    const speed = Number(el('animationSpeedSlider')?.value || 1);
    const rect = frameRect(state.frame);
    const frameMs = Math.max(16, rect.duration / Math.max(0.25, speed));
    if (state.accumulator >= frameMs) {
      state.accumulator %= frameMs;
      const count = Number(state.meta?.frame_count || 1);
      const next = state.frame + 1;
      if (next >= count && !el('animationLoopToggle')?.checked) {
        stopPlayback();
      } else {
        setFrame(next % count);
      }
    }
    state.raf = requestAnimationFrame(tick);
  }

  function startPlayback() {
    if (!state.meta || state.playing) return;
    state.playing = true;
    state.lastTime = 0;
    el('animationPlayBtn').textContent = 'Pause';
    state.raf = requestAnimationFrame(tick);
  }

  function stopPlayback() {
    state.playing = false;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    el('animationPlayBtn').textContent = 'Play';
  }

  function setExportStatus(message) {
    const status = el('animationExportStatus');
    if (status) status.textContent = message;
  }

  function backgroundImageUrl(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (/^(https?:|\/file\/|data:image\/)/i.test(text)) return text;
    if (/^[a-z]:[\\/]/i.test(text)) return '';
    return '/file/' + text.replace(/^\.?[\\/]+/, '').replace(/\\/g, '/');
  }

  function applyBackgroundSelection() {
    const wrap = el('animationCanvasWrap');
    if (!wrap) return;
    const mode = el('animationBackgroundSelect')?.value || 'checker';
    const field = el('animationCustomBackgroundField');
    const input = el('animationCustomBackgroundInput');
    wrap.classList.toggle('checker', mode === 'checker');
    wrap.classList.toggle('bg-dark', mode === 'dark');
    wrap.classList.toggle('bg-light', mode === 'light');
    wrap.classList.toggle('bg-magenta', mode === 'magenta');
    wrap.classList.toggle('bg-custom', mode === 'custom');
    if (field) field.classList.toggle('hidden', mode !== 'custom');
    if (mode === 'custom') {
      const url = backgroundImageUrl(input?.value || '');
      wrap.style.backgroundImage = url ? `url("${url}")` : '';
      setExportStatus(url ? 'Custom background preview applied.' : 'Enter a workspace image path for the custom background.');
    } else {
      wrap.style.backgroundImage = '';
    }
  }

  function downloadCanvasPng(canvas) {
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    const frame = String(state.frame + 1).padStart(3, '0');
    a.download = `${state.bundle?.name || 'sprite'}_frame_${frame}.png`;
    a.click();
  }

  function hitFrameLabel(frame, index) {
    if (!frame) return '';
    const marker = frame.hit_frame ?? frame.hit ?? frame.marker ?? frame.event ?? frame.label;
    if (marker === true) return `Hit frame ${index + 1}`;
    return String(marker || '').trim();
  }

  function buildTimeline() {
    const ticks = el('animationTimelineTicks');
    if (!ticks || !state.meta) return;
    ticks.innerHTML = '';
    const count = Number(state.meta.frame_count || 0);
    let markerCount = 0;
    for (let i = 0; i < count; i += 1) {
      const frame = (state.meta.frames || [])[i] || {};
      const marker = hitFrameLabel(frame, i);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'animation-tick';
      if (marker) {
        markerCount += 1;
        btn.classList.add('hit-frame');
        btn.title = marker;
        btn.setAttribute('aria-label', marker);
      }
      btn.dataset.frame = String(i);
      btn.dataset.hitFrame = marker;
      btn.textContent = String(i + 1);
      btn.addEventListener('click', () => setFrame(i));
      ticks.appendChild(btn);
    }
    const legend = el('animationHitFrameLegend');
    if (legend) {
      legend.classList.toggle('hidden', markerCount === 0);
      legend.textContent = markerCount
        ? `${markerCount} hit-frame marker${markerCount === 1 ? '' : 's'} highlighted on the timeline.`
        : 'Hit frames are highlighted on the timeline.';
    }
  }

  async function loadSprite(path) {
    if (!path) return;
    stopPlayback();
    const bundle = await api('/api/sprite/preview?path=' + encodeURIComponent(path));
    const meta = await api(bundle.json_url || ('/file/' + path + '/sheet.json'));
    const img = new Image();
    img.onload = () => {
      state.bundle = bundle;
      state.meta = meta;
      state.sheet = img;
      state.frame = 0;
      state.panX = 0;
      state.panY = 0;

      el('animationMetaFrames').textContent = String(meta.frame_count || '-');
      el('animationMetaFps').textContent = String(meta.fps || '-');
      el('animationMetaSize').textContent = `${meta.frame_width || '-'}x${meta.frame_height || '-'}`;
      const scrub = el('animationFrameScrubber');
      if (scrub) {
        scrub.max = String(Math.max(0, Number(meta.frame_count || 1) - 1));
        scrub.value = '0';
      }
      buildTimeline();
      render();
      setExportStatus('PNG frame copy/download and WebM recording are ready.');
    };
    img.src = bundle.sheet_url + '?t=' + Date.now();
  }

  async function copyCurrentFrame() {
    const canvas = el('animationCanvas');
    if (!canvas || !state.meta) return toast('Load a sprite before exporting a frame.');
    if (!navigator.clipboard || !window.ClipboardItem) {
      downloadCanvasPng(canvas);
      setExportStatus('Clipboard unavailable; downloaded current frame as PNG.');
      return toast('Downloaded current frame as PNG.');
    }
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      try {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        setExportStatus('Current frame copied as PNG.');
        toast('Frame copied as PNG');
      } catch (err) {
        downloadCanvasPng(canvas);
        setExportStatus('Clipboard write failed; downloaded current frame as PNG.');
        toast('Downloaded current frame as PNG.');
      }
    }, 'image/png');
  }

  function recordWebm() {
    const canvas = el('animationCanvas');
    if (!canvas || !state.meta) return toast('Load a sprite before recording WebM.');
    if (state.recording) return toast('Recording is already in progress.');
    if (!canvas.captureStream || !window.MediaRecorder) return toast('WebM recording is not available in this browser.');
    const mimeType = MediaRecorder.isTypeSupported?.('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9'
      : (MediaRecorder.isTypeSupported?.('video/webm;codecs=vp8') ? 'video/webm;codecs=vp8' : 'video/webm');
    const chunks = [];
    const stream = canvas.captureStream(Math.max(1, Number(state.meta?.fps || 12)));
    let recorder = null;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch (err) {
      setExportStatus('WebM recording is not supported by this browser.');
      return toast('WebM recording is not supported by this browser.');
    }
    state.recording = true;
    el('animationExportWebmBtn').disabled = true;
    setExportStatus(`Recording WebM preview (${mimeType})...`);
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${state.bundle?.name || 'sprite'}_preview.webm`;
      a.click();
      URL.revokeObjectURL(a.href);
      state.recording = false;
      el('animationExportWebmBtn').disabled = false;
      setExportStatus('WebM recording downloaded.');
    };
    recorder.start();
    startPlayback();
    setTimeout(() => {
      recorder.stop();
      stopPlayback();
    }, Math.min(8000, Math.max(1000, Number(state.meta?.frame_count || 1) * (1000 / Math.max(1, Number(state.meta?.fps || 12))))));
  }

  function bindPlayer() {
    if (!playerReady() || window.__animationPlayerBound) return;
    window.__animationPlayerBound = true;
    populateSpriteSelect();
    el('animationSpriteSelect').addEventListener('change', (event) => loadSprite(event.target.value));
    el('animationRefreshBtn').addEventListener('click', async () => {
      if (typeof refreshAll === 'function') await refreshAll();
      populateSpriteSelect();
    });
    el('animationPlayBtn').addEventListener('click', () => (state.playing ? stopPlayback() : startPlayback()));
    el('animationPrevBtn').addEventListener('click', () => setFrame(state.frame - 1));
    el('animationNextBtn').addEventListener('click', () => setFrame(state.frame + 1));
    el('animationFrameScrubber').addEventListener('input', (event) => setFrame(Number(event.target.value || 0)));
    el('animationCopyFrameBtn').addEventListener('click', copyCurrentFrame);
    el('animationExportWebmBtn').addEventListener('click', recordWebm);
    ['animationSpeedSlider', 'animationZoomSlider', 'animationOnionSlider'].forEach((id) => {
      el(id).addEventListener('input', () => {
        if (id === 'animationSpeedSlider') el('animationSpeedLabel').textContent = `${el(id).value}x`;
        if (id === 'animationZoomSlider') el('animationZoomLabel').textContent = `${el(id).value}x`;
        if (id === 'animationOnionSlider') el('animationOnionLabel').textContent = el(id).value;
        render();
      });
    });
    el('animationBackgroundSelect').addEventListener('change', applyBackgroundSelection);
    el('animationCustomBackgroundInput')?.addEventListener('input', applyBackgroundSelection);
    const wrap = el('animationCanvasWrap');
    wrap.addEventListener('mousedown', (event) => {
      state.dragging = true;
      state.dragStart = { x: event.clientX, y: event.clientY, panX: state.panX, panY: state.panY };
    });
    window.addEventListener('mouseup', () => { state.dragging = false; });
    window.addEventListener('mousemove', (event) => {
      if (!state.dragging || !state.dragStart) return;
      state.panX = state.dragStart.panX + event.clientX - state.dragStart.x;
      state.panY = state.dragStart.panY + event.clientY - state.dragStart.y;
      render();
    });
  }

  window.refreshAnimationPlayerSprites = populateSpriteSelect;
  window.viewComponentsLoaded?.then(bindPlayer);
})();
