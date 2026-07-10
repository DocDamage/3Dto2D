(function () {
  const state = {
    path: '',
    bundle: null,
    meta: null,
    timeline: [],
    selected: -1,
    selectedIndices: new Set(),
    anchorIndex: -1,
    dragIndex: -1,
  };

  function el(id) {
    return document.getElementById(id);
  }

  function outputs() {
    return typeof currentOutputs !== 'undefined' ? currentOutputs : [];
  }

  function refreshFrameEditorSprites() {
    const select = el('frameEditorSpriteSelect');
    if (!select) return;
    const previous = select.value;
    select.innerHTML = '<option value="">Select a sprite output</option>';
    outputs().forEach((item) => {
      const opt = document.createElement('option');
      opt.value = item.path || '';
      opt.textContent = `${item.name || item.path || 'sprite'} (${item.frame_count || '?'} frames)`;
      select.appendChild(opt);
    });
    if (previous && Array.from(select.options).some((opt) => opt.value === previous)) select.value = previous;
  }

  function setStatus(message) {
    const status = el('frameEditorStatus');
    if (status) status.textContent = message;
  }

  function resetTimeline() {
    const frames = state.bundle?.frames || [];
    state.timeline = frames.map((frame, index) => ({
      source_index: index,
      url: frame.url,
      name: frame.name || `frame_${String(index).padStart(4, '0')}.png`,
      duration_ms: '',
    }));
    state.selected = state.timeline.length ? 0 : -1;
    state.selectedIndices = state.selected >= 0 ? new Set([state.selected]) : new Set();
    state.anchorIndex = state.selected;
    renderTimeline();
    renderSelected();
  }

  function selectTimelineFrame(index, event) {
    if (index < 0 || index >= state.timeline.length) return;
    if (event?.shiftKey && state.anchorIndex >= 0) {
      const start = Math.min(state.anchorIndex, index);
      const end = Math.max(state.anchorIndex, index);
      state.selectedIndices = new Set();
      for (let i = start; i <= end; i += 1) state.selectedIndices.add(i);
    } else if (event?.ctrlKey || event?.metaKey) {
      if (state.selectedIndices.has(index)) state.selectedIndices.delete(index);
      else state.selectedIndices.add(index);
      state.anchorIndex = index;
    } else {
      state.selectedIndices = new Set([index]);
      state.anchorIndex = index;
    }
    if (!state.selectedIndices.size) state.selectedIndices.add(index);
    state.selected = index;
    renderTimeline();
    renderSelected();
  }

  function selectedTimelineIndices() {
    if (state.selectedIndices && state.selectedIndices.size) {
      return Array.from(state.selectedIndices).sort((a, b) => a - b);
    }
    return state.selected >= 0 ? [state.selected] : [];
  }

  function renderTimeline() {
    const zone = el('frameEditorDropZone');
    if (!zone) return;
    zone.innerHTML = '';
    state.timeline.forEach((frame, index) => {
      const tile = document.createElement('button');
      tile.type = 'button';
      tile.className = 'frame-editor-tile' + (state.selectedIndices.has(index) ? ' active' : '');
      tile.draggable = true;
      tile.dataset.index = String(index);
      tile.classList.toggle('retimed', !!frame.duration_ms);
      const image = document.createElement('img');
      image.src = String(frame.url || '');
      image.alt = `Frame ${index + 1}`;
      tile.appendChild(image);
      appendText(tile, 'span', String(index + 1));
      if (frame.duration_ms) appendText(tile, 'small', `${Number(frame.duration_ms)}ms`, 'frame-editor-duration-badge');
      tile.addEventListener('click', (event) => selectTimelineFrame(index, event));
      tile.addEventListener('dragstart', () => {
        state.dragIndex = index;
      });
      tile.addEventListener('dragover', (event) => event.preventDefault());
      tile.addEventListener('drop', (event) => {
        event.preventDefault();
        const from = state.dragIndex;
        const to = index;
        if (from < 0 || from === to) return;
        const [moved] = state.timeline.splice(from, 1);
        state.timeline.splice(to, 0, moved);
        state.selected = to;
        state.dragIndex = -1;
        renderTimeline();
        renderSelected();
      });
      zone.appendChild(tile);
    });
    if (el('frameEditorCount')) el('frameEditorCount').textContent = String(state.timeline.length);
    if (el('frameEditorSelected')) {
      const selected = selectedTimelineIndices();
      el('frameEditorSelected').textContent = selected.length > 1 ? `${selected.length} selected` : (state.selected >= 0 ? String(state.selected + 1) : '-');
    }
    const hint = el('frameEditorDurationHint');
    if (hint) {
      const selected = selectedTimelineIndices();
      hint.textContent = selected.length > 1
        ? `Applies to ${selected.length} selected frames.`
        : 'Applies to the selected frame.';
    }
  }

  function renderSelected() {
    const frame = state.timeline[state.selected];
    const title = el('frameEditorDetailTitle');
    const duration = el('frameEditorDuration');
    if (!frame) {
      if (title) title.textContent = 'No frame selected';
      if (duration) duration.value = '';
      return;
    }
    if (title) title.textContent = `Frame ${state.selected + 1} from source ${frame.source_index + 1}`;
    if (duration) duration.value = frame.duration_ms || '';
    const canvas = el('frameEditorCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = frame.url || '';
  }

  async function loadSprite(path) {
    if (!path) return;
    state.path = path;
    state.bundle = await api('/api/sprite/preview?path=' + encodeURIComponent(path));
    state.meta = await api(state.bundle.json_url || ('/file/' + path + '/sheet.json'));
    if (el('frameEditorFps')) el('frameEditorFps').value = String(state.meta.fps || 12);
    resetTimeline();
    setStatus(`Loaded ${state.timeline.length} frames from ${path}.`);
  }

  function deleteSelected() {
    const selected = selectedTimelineIndices();
    if (!selected.length) return;
    if (state.timeline.length - selected.length < 1) return toast('Cannot delete the last frame.');
    const deleteSet = new Set(selected);
    state.timeline = state.timeline.filter((_frame, index) => !deleteSet.has(index));
    state.selected = Math.min(selected[0], state.timeline.length - 1);
    state.selectedIndices = state.selected >= 0 ? new Set([state.selected]) : new Set();
    state.anchorIndex = state.selected;
    renderTimeline();
    renderSelected();
  }

  function duplicateSelected(count) {
    const selected = selectedTimelineIndices();
    if (!selected.length) return;
    let offset = 0;
    selected.forEach(index => {
      const frame = state.timeline[index + offset];
      for (let i = 0; i < count; i += 1) {
        state.timeline.splice(index + offset + 1 + i, 0, { ...frame });
      }
      offset += count;
    });
    const firstInserted = selected[0] + 1;
    const inserted = [];
    selected.forEach((index, group) => {
      for (let i = 0; i < count; i += 1) inserted.push(index + 1 + group * count + i);
    });
    state.selected = firstInserted;
    state.selectedIndices = new Set(inserted);
    state.anchorIndex = firstInserted;
    renderTimeline();
    renderSelected();
  }

  function moveSelected(delta) {
    const selected = selectedTimelineIndices();
    if (!selected.length || !delta) return;
    const selectedSet = new Set(selected);
    if (delta < 0 && selected[0] === 0) return;
    if (delta > 0 && selected[selected.length - 1] === state.timeline.length - 1) return;

    const frames = state.timeline.slice();
    const order = delta < 0 ? selected : selected.slice().reverse();
    order.forEach(index => {
      const target = index + delta;
      if (target < 0 || target >= frames.length || selectedSet.has(target)) return;
      [frames[index], frames[target]] = [frames[target], frames[index]];
      selectedSet.delete(index);
      selectedSet.add(target);
    });
    state.timeline = frames;
    state.selectedIndices = new Set(Array.from(selectedSet).sort((a, b) => a - b));
    state.selected = delta < 0 ? Math.min(...state.selectedIndices) : Math.max(...state.selectedIndices);
    state.anchorIndex = state.selected;
    renderTimeline();
    renderSelected();
  }

  async function repack() {
    if (!state.path || !state.timeline.length) return toast('Select a sprite and build a timeline first.');
    const payload = {
      path: state.path,
      fps: Number(el('frameEditorFps')?.value || state.meta?.fps || 12),
      frames: state.timeline.map((frame) => ({
        source_index: frame.source_index,
        duration_ms: frame.duration_ms || null,
      })),
    };
    const result = await api('/api/repack-sheet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    toast(`Repacked ${result.frame_count} frames.`);
    await loadSprite(state.path);
    if (typeof refreshAll === 'function') refreshAll();
  }

  function bindFrameEditor() {
    if (!el('frameEditorSpriteSelect') || window.__frameEditorBound) return;
    window.__frameEditorBound = true;
    refreshFrameEditorSprites();
    el('frameEditorSpriteSelect').addEventListener('change', (event) => loadSprite(event.target.value));
    el('frameEditorRefreshBtn').addEventListener('click', async () => {
      if (typeof refreshAll === 'function') await refreshAll();
      refreshFrameEditorSprites();
    });
    el('frameEditorResetBtn').addEventListener('click', resetTimeline);
    el('frameEditorDeleteBtn').addEventListener('click', deleteSelected);
    el('frameEditorDuplicateBtn').addEventListener('click', () => duplicateSelected(1));
    el('frameEditorHoldBtn').addEventListener('click', () => {
      const count = Math.max(1, Number(prompt('Add how many hold frames?', '1') || 1));
      duplicateSelected(count);
    });
    el('frameEditorMoveLeftBtn').addEventListener('click', () => moveSelected(-1));
    el('frameEditorMoveRightBtn').addEventListener('click', () => moveSelected(1));
    el('frameEditorDuration').addEventListener('input', (event) => {
      const selected = selectedTimelineIndices();
      selected.forEach(index => {
        if (state.timeline[index]) state.timeline[index].duration_ms = event.target.value;
      });
      renderTimeline();
    });
    el('frameEditorRepackBtn').addEventListener('click', () => repack().catch((err) => toast('Repack failed: ' + err.message)));
  }

  window.refreshFrameEditorSprites = refreshFrameEditorSprites;
  window.viewComponentsLoaded?.then(bindFrameEditor);
})();
