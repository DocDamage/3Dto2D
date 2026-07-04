(function () {
  const slots = ['A', 'B', 'C', 'D'];
  const state = {
    variants: [],
    frame: 0,
    playing: false,
    raf: 0,
    lastTime: 0,
    accumulator: 0,
    selectedWinner: '',
  };

  function el(id) { return document.getElementById(id); }
  function ready() { return el('compareVariantGrid') && el('compareSpriteA'); }

  function frameRect(meta, index) {
    const frame = (meta.frames || [])[index] || {};
    const fw = Number(meta.frame_width || frame.w || 1);
    const fh = Number(meta.frame_height || frame.h || 1);
    const columns = Math.max(1, Number(meta.columns || 1));
    return {
      sx: Number(frame.x ?? ((index % columns) * fw)),
      sy: Number(frame.y ?? (Math.floor(index / columns) * fh)),
      sw: Number(frame.w || fw),
      sh: Number(frame.h || fh),
      fw,
      fh,
      duration: Number(frame.duration_ms || (1000 / Math.max(1, Number(meta.fps || 12)))),
    };
  }

  function populateSelects() {
    const outputs = typeof currentOutputs !== 'undefined' ? currentOutputs : [];
    slots.forEach(slot => {
      const select = el(`compareSprite${slot}`);
      if (!select) return;
      const previous = select.value;
      select.innerHTML = `<option value="">${slot === 'A' || slot === 'B' ? 'Select sprite' : 'Optional'}</option>`;
      outputs.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.path || '';
        opt.textContent = `${item.name || item.path || 'sprite'} (${item.frame_count || '?'} frames)`;
        select.appendChild(opt);
      });
      if (previous && Array.from(select.options).some(opt => opt.value === previous)) select.value = previous;
    });
  }

  async function loadVariant(path, slot) {
    const bundle = await api('/api/sprite/preview?path=' + encodeURIComponent(path));
    const meta = await api(bundle.json_url || ('/file/' + path + '/sheet.json'));
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
      img.src = bundle.sheet_url + '?t=' + Date.now();
    });
    return { slot, path, bundle, meta, sheet: img };
  }

  async function loadSelected() {
    stopPlayback();
    const selected = slots
      .map(slot => ({ slot, path: el(`compareSprite${slot}`)?.value || '' }))
      .filter(item => item.path);
    if (selected.length < 2) return toast('Select at least two sprite variants to compare.');
    state.variants = await Promise.all(selected.slice(0, 4).map(item => loadVariant(item.path, item.slot)));
    state.frame = 0;
    state.selectedWinner = state.variants[0]?.path || '';
    buildVariantCards();
    updateScrubber();
    render();
  }

  function buildVariantCards() {
    const grid = el('compareVariantGrid');
    if (!grid) return;
    clearNode(grid);
    state.variants.forEach(variant => {
      const card = document.createElement('article');
      card.className = 'compare-variant-card card' + (variant.path === state.selectedWinner ? ' selected' : '');
      card.dataset.path = variant.path;
      const head = document.createElement('div');
      head.className = 'card-head';
      appendText(head, 'h3', `Variant ${variant.slot}`);
      const pick = document.createElement('button');
      pick.type = 'button';
      pick.className = 'mini';
      pick.textContent = 'Pick';
      pick.addEventListener('click', () => selectWinner(variant.path));
      head.appendChild(pick);
      const wrap = document.createElement('div');
      wrap.className = 'compare-canvas-wrap';
      const canvas = document.createElement('canvas');
      canvas.dataset.path = variant.path;
      wrap.appendChild(canvas);
      const meta = document.createElement('div');
      meta.className = 'compare-meta-grid';
      [
        ['Frames', variant.meta.frame_count || '-'],
        ['FPS', variant.meta.fps || '-'],
        ['QA', variant.bundle.qa_report?.score ?? '-'],
      ].forEach(([label, value]) => {
        const cell = document.createElement('div');
        appendText(cell, 'b', String(value));
        appendText(cell, 'span', label);
        meta.appendChild(cell);
      });
      card.append(head, wrap, meta);
      grid.appendChild(card);
    });
    renderMetricsTable();
  }

  function metricValue(value) {
    if (value === null || value === undefined || value === '') return '-';
    const number = Number(value);
    return Number.isFinite(number) ? String(Math.round(number * 100) / 100) : String(value);
  }

  function variantQaMetric(variant, key) {
    const qa = variant.bundle?.qa_report || variant.bundle?.qa || {};
    const metrics = qa.metrics || qa.summary || {};
    return qa[key] ?? metrics[key] ?? metrics[key.replace(/_/g, '-')] ?? '-';
  }

  function renderMetricsTable() {
    const body = el('compareMetricsBody');
    const status = el('compareMetricsStatus');
    if (!body) return;
    body.innerHTML = '';
    if (!state.variants.length) {
      body.innerHTML = '<tr><td colspan="7">No variants loaded.</td></tr>';
      if (status) status.textContent = 'Load variants to compare scores.';
      return;
    }
    state.variants.forEach(variant => {
      const row = document.createElement('tr');
      const isWinner = variant.path === state.selectedWinner;
      const decision = isWinner ? 'selected winner' : 'candidate';
      row.className = isWinner ? 'compare-metrics-winner' : '';
      row.innerHTML = `
        <td>Variant ${escapeHtml(variant.slot)}<small>${escapeHtml(variant.path)}</small></td>
        <td>${metricValue(variant.meta.frame_count)}</td>
        <td>${metricValue(variant.meta.fps)}</td>
        <td>${metricValue(variantQaMetric(variant, 'score'))}</td>
        <td>${metricValue(variantQaMetric(variant, 'loop_rmse'))}</td>
        <td>${metricValue(variantQaMetric(variant, 'foot_drift'))}</td>
        <td>${escapeHtml(decision)}</td>
      `;
      body.appendChild(row);
    });
    if (status) status.textContent = `${state.variants.length} variant${state.variants.length === 1 ? '' : 's'} loaded.`;
  }

  function selectWinner(path) {
    state.selectedWinner = path;
    document.querySelectorAll('.compare-variant-card').forEach(card => {
      card.classList.toggle('selected', card.dataset.path === path);
    });
    renderMetricsTable();
  }

  function drawVariant(variant, canvas) {
    const rect = frameRect(variant.meta, Math.min(state.frame, Number(variant.meta.frame_count || 1) - 1));
    canvas.width = rect.fw;
    canvas.height = rect.fh;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(variant.sheet, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, rect.fw, rect.fh);
  }

  function renderDiff() {
    const canvas = el('compareDiffCanvas');
    if (!canvas || state.variants.length < 2 || !el('compareDiffToggle')?.checked) return;
    const a = state.variants[0];
    const b = state.variants[1];
    const rect = frameRect(a.meta, Math.min(state.frame, Number(a.meta.frame_count || 1) - 1));
    canvas.width = rect.fw;
    canvas.height = rect.fh;
    const offA = document.createElement('canvas');
    const offB = document.createElement('canvas');
    offA.width = offB.width = rect.fw;
    offA.height = offB.height = rect.fh;
    drawVariant(a, offA);
    drawVariant(b, offB);
    const ctx = canvas.getContext('2d');
    const dataA = offA.getContext('2d').getImageData(0, 0, rect.fw, rect.fh);
    const dataB = offB.getContext('2d').getImageData(0, 0, rect.fw, rect.fh);
    const out = ctx.createImageData(rect.fw, rect.fh);
    let changed = 0;
    for (let i = 0; i < dataA.data.length; i += 4) {
      const delta = Math.abs(dataA.data[i] - dataB.data[i]) + Math.abs(dataA.data[i + 1] - dataB.data[i + 1]) + Math.abs(dataA.data[i + 2] - dataB.data[i + 2]) + Math.abs(dataA.data[i + 3] - dataB.data[i + 3]);
      if (delta > 32) changed += 1;
      out.data[i] = Math.min(255, delta);
      out.data[i + 1] = 24;
      out.data[i + 2] = 24;
      out.data[i + 3] = delta > 32 ? 210 : 20;
    }
    ctx.putImageData(out, 0, 0);
    const stats = el('compareDiffStats');
    if (stats) stats.textContent = `${Math.round((changed / Math.max(1, rect.fw * rect.fh)) * 100)}% changed pixels`;
  }

  function render() {
    state.variants.forEach(variant => {
      const canvas = document.querySelector(`canvas[data-path="${CSS.escape(variant.path)}"]`);
      if (canvas) drawVariant(variant, canvas);
    });
    renderDiff();
    const maxFrames = maxFrameCount();
    if (el('compareFrameLabel')) el('compareFrameLabel').textContent = `Frame ${state.frame + 1} / ${maxFrames}`;
    const firstRect = state.variants[0] ? frameRect(state.variants[0].meta, state.frame) : { duration: 0 };
    if (el('compareDurationLabel')) el('compareDurationLabel').textContent = `${Math.round(firstRect.duration)} ms`;
    if (el('compareFrameScrubber')) el('compareFrameScrubber').value = String(state.frame);
  }

  function maxFrameCount() {
    return Math.max(1, ...state.variants.map(v => Number(v.meta.frame_count || 1)));
  }

  function updateScrubber() {
    const scrub = el('compareFrameScrubber');
    if (!scrub) return;
    scrub.max = String(Math.max(0, maxFrameCount() - 1));
    scrub.value = '0';
  }

  function setFrame(index) {
    state.frame = Math.max(0, Math.min(maxFrameCount() - 1, index));
    render();
  }

  function tick(time) {
    if (!state.playing) return;
    if (!state.lastTime) state.lastTime = time;
    state.accumulator += time - state.lastTime;
    state.lastTime = time;
    const firstRect = state.variants[0] ? frameRect(state.variants[0].meta, state.frame) : { duration: 83 };
    const speed = Number(el('compareSpeedSlider')?.value || 1);
    const frameMs = Math.max(16, firstRect.duration / Math.max(0.25, speed));
    if (state.accumulator >= frameMs) {
      state.accumulator %= frameMs;
      setFrame((state.frame + 1) % maxFrameCount());
    }
    state.raf = requestAnimationFrame(tick);
  }

  function startPlayback() {
    if (!state.variants.length || state.playing) return;
    state.playing = true;
    state.lastTime = 0;
    el('comparePlayBtn').textContent = 'Pause';
    state.raf = requestAnimationFrame(tick);
  }

  function stopPlayback() {
    state.playing = false;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    if (el('comparePlayBtn')) el('comparePlayBtn').textContent = 'Play';
  }

  async function pickWinner() {
    if (!state.selectedWinner) return toast('Pick a winning variant first.');
    const variant = state.variants.find(v => v.path === state.selectedWinner);
    const payload = {
      id: variant?.bundle?.experiment?.id || '',
      sprite_folder: state.selectedWinner,
      compared_sprites: state.variants.map(v => v.path),
      note: `Picked Variant ${variant?.slot || '?'} as the compare winner.`,
    };
    const result = await api('/api/experiments/pick-winner', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
    if (!result.ok && variant?.bundle?.experiment?.id) {
      await api('/api/experiments/star', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: variant.bundle.experiment.id, starred: true }) });
    }
    toast(result.message || `Winner picked: ${state.selectedWinner}`);
  }

  function setCompareSelection(paths) {
    populateSelects();
    paths.slice(0, 4).forEach((path, idx) => {
      const select = el(`compareSprite${slots[idx]}`);
      if (select) select.value = path;
    });
    if (paths.length >= 2) loadSelected();
  }

  function bind() {
    if (!ready() || window.__comparePlayerBound) return;
    window.__comparePlayerBound = true;
    populateSelects();
    el('compareRefreshBtn').addEventListener('click', async () => {
      if (typeof refreshAll === 'function') await refreshAll();
      populateSelects();
    });
    el('compareLoadSelectedBtn').addEventListener('click', loadSelected);
    el('comparePlayBtn').addEventListener('click', () => state.playing ? stopPlayback() : startPlayback());
    el('comparePrevBtn').addEventListener('click', () => setFrame(state.frame - 1));
    el('compareNextBtn').addEventListener('click', () => setFrame(state.frame + 1));
    el('compareFrameScrubber').addEventListener('input', event => setFrame(Number(event.target.value || 0)));
    el('compareSpeedSlider').addEventListener('input', event => { el('compareSpeedLabel').textContent = `${event.target.value}x`; });
    el('compareDiffToggle').addEventListener('change', render);
    el('comparePickWinnerBtn').addEventListener('click', pickWinner);
  }

  window.refreshComparePlayerSprites = populateSelects;
  window.setComparePlayerSelection = setCompareSelection;
  window.viewComponentsLoaded?.then(bind);
})();
