let frameEdits = [];
let playbackInterval = null;
let isPlaying = false;

async function updateCompareOverlay() {
  const enabled = $('#inspectCompareEnable') && $('#inspectCompareEnable').checked;
  const compareImg = $('#inspector-img-compare');
  if (!compareImg) return;
  if (!enabled) {
    compareImg.classList.add('hidden');
    const canvas = $('#inspector-canvas');
    if (canvas) canvas.classList.remove('sidebyside-left');
    return;
  }
  const versionId = $('#inspectCompareVersion').value;
  if (!versionId || !selectedSpriteDir) {
    compareImg.src = '';
    return;
  }
  const frameIdx = parseInt($('#frameScrubber').value) || 0;
  const padIdx = String(frameIdx).padStart(4, '0');
  const mode = $('#inspectCompareMode').value;
  
  compareImg.src = `/file/${selectedSpriteDir}/.versions/${versionId}/frames_processed/frame_${padIdx}.png?t=` + Date.now();
  compareImg.classList.remove('hidden');
  
  if (mode === 'sidebyside') {
    compareImg.style.opacity = 1;
    compareImg.classList.add('sidebyside-right');
    const canvas = $('#inspector-canvas');
    if (canvas) canvas.classList.add('sidebyside-left');
  } else {
    compareImg.style.opacity = $('#inspectCompareOpacity').value;
    compareImg.classList.remove('sidebyside-right');
    const canvas = $('#inspector-canvas');
    if (canvas) canvas.classList.remove('sidebyside-left');
  }
}

async function loadSpriteVersions(spritePath) {
  try {
    const res = await api(`/api/sprite/version/list?path=${encodeURIComponent(spritePath)}`);
    const activeSel = $('#inspectActiveVersion');
    const compareSel = $('#inspectCompareVersion');
    if (!activeSel || !compareSel) return;
    
    activeSel.innerHTML = '<option value="current">Current Working Copy</option>';
    compareSel.innerHTML = '<option value="">Choose snapshot...</option>';
    
    (res.versions || []).forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = `${v.label} (${v.created_at})`;
      activeSel.appendChild(opt.cloneNode(true));
      compareSel.appendChild(opt);
    });
    
    activeSel.value = res.active_version || 'current';
    if ($('#inspectRollbackBtn')) {
      $('#inspectRollbackBtn').disabled = activeSel.value === 'current';
    }
  } catch (err) {
    console.warn(err);
  }
}

function togglePlayback() {
  const btn = $('#inspectPlayBtn');
  if (!btn) return;
  
  if (isPlaying) {
    clearInterval(playbackInterval);
    isPlaying = false;
    btn.textContent = '▶ Play';
  } else {
    const meta = window._currentMeta;
    if (!meta || !meta.frame_count) return;
    
    isPlaying = true;
    btn.textContent = '⏸ Pause';
    
    const fps = parseInt($('#inspectPlayFps').value) || 12;
    const intervalMs = 1000 / fps;
    
    playbackInterval = setInterval(() => {
      const scrub = $('#frameScrubber');
      if (!scrub) return;
      let nextVal = parseInt(scrub.value) + 1;
      if (nextVal >= meta.frame_count) {
        nextVal = 0;
      }
      scrub.value = nextVal;
      if (typeof renderInspectorFrame === 'function') renderInspectorFrame(nextVal);
    }, intervalMs);
  }
}

function nudgeFrame(dx, dy) {
  const meta = window._currentMeta;
  if (!meta || !meta.frames) return;
  saveUndoState();
  const idx = parseInt($('#frameScrubber').value);
  const frame = meta.frames[idx];
  if (frame) {
    frame.x += dx;
    frame.y += dy;
    if (typeof renderInspectorFrame === 'function') renderInspectorFrame(idx);
  }
}

if ($('#inspectPlayBtn')) {
  $('#inspectPlayBtn').addEventListener('click', togglePlayback);
}
if ($('#inspectPlayFps')) {
  $('#inspectPlayFps').addEventListener('change', () => {
    if (isPlaying) {
      togglePlayback();
      togglePlayback();
    }
  });
}

if ($('#inspectMarkBadBtn')) {
  $('#inspectMarkBadBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    saveUndoState();
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      frame.bad = !frame.bad;
      toast(frame.bad ? `Frame ${idx + 1} marked as bad` : `Frame ${idx + 1} cleared bad mark`);
      if (typeof renderInspectorFrame === 'function') renderInspectorFrame(idx);
    }
  });
}

if ($('#inspectDuplicateBtn')) {
  $('#inspectDuplicateBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    saveUndoState();
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      const dup = JSON.parse(JSON.stringify(frame));
      meta.frames.splice(idx + 1, 0, dup);
      meta.frame_count = meta.frames.length;
      meta.frames.forEach((f, i) => f.index = i);
      
      const scrub = $('#frameScrubber');
      scrub.max = meta.frame_count - 1;
      scrub.value = idx + 1;
      
      toast(`Duplicated frame ${idx + 1}`);
      if (typeof renderInspectorFrame === 'function') renderInspectorFrame(idx + 1);
    }
  });
}

if ($('#inspectRemoveBtn')) {
  $('#inspectRemoveBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames || meta.frames.length <= 1) {
      toast('Cannot remove the last frame.');
      return;
    }
    saveUndoState();
    const idx = parseInt($('#frameScrubber').value);
    meta.frames.splice(idx, 1);
    meta.frame_count = meta.frames.length;
    meta.frames.forEach((f, i) => f.index = i);
    
    const scrub = $('#frameScrubber');
    scrub.max = meta.frame_count - 1;
    const nextIdx = Math.min(idx, meta.frame_count - 1);
    scrub.value = nextIdx;
    
    toast(`Removed frame ${idx + 1}`);
    if (typeof renderInspectorFrame === 'function') renderInspectorFrame(nextIdx);
  });
}

if ($('#inspectTrimBtn')) {
  $('#inspectTrimBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    const path = window._currentPath;
    if (!meta || !path) return;
    saveUndoState();
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (!frame) return;
    
    const img = new Image();
    img.src = '/file/' + path + '/' + (meta.image || 'sheet.png') + '?t=' + Date.now();
    img.onload = () => {
      const osc = document.createElement('canvas');
      osc.width = frame.w;
      osc.height = frame.h;
      const octx = osc.getContext('2d');
      octx.drawImage(img, frame.x, frame.y, frame.w, frame.h, 0, 0, frame.w, frame.h);
      
      const imgData = octx.getImageData(0, 0, frame.w, frame.h);
      const data = imgData.data;
      
      let minX = frame.w, minY = frame.h, maxX = 0, maxY = 0;
      let found = false;
      
      for (let y = 0; y < frame.h; y++) {
        for (let x = 0; x < frame.w; x++) {
          const alpha = data[(y * frame.w + x) * 4 + 3];
          if (alpha > 0) {
            found = true;
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
          }
        }
      }
      
      if (!found) {
        toast('Frame is completely empty.');
        return;
      }
      
      frame.x = frame.x + minX;
      frame.y = frame.y + minY;
      frame.w = maxX - minX + 1;
      frame.h = maxY - minY + 1;
      
      toast(`Trimmed frame ${idx + 1} to size ${frame.w}×${frame.h}`);
      if (typeof renderInspectorFrame === 'function') renderInspectorFrame(idx);
    };
  });
}

if ($('#nudgeUpBtn')) $('#nudgeUpBtn').addEventListener('click', () => nudgeFrame(0, -1));
if ($('#nudgeDownBtn')) $('#nudgeDownBtn').addEventListener('click', () => nudgeFrame(0, 1));
if ($('#nudgeLeftBtn')) $('#nudgeLeftBtn').addEventListener('click', () => nudgeFrame(-1, 0));
if ($('#nudgeRightBtn')) $('#nudgeRightBtn').addEventListener('click', () => nudgeFrame(1, 0));

if ($('#pivotXInput')) {
  $('#pivotXInput').addEventListener('focus', () => saveUndoState());
  $('#pivotXInput').addEventListener('input', e => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      frame.pivot_x = parseFloat(e.target.value) || 0;
    }
  });
}
if ($('#pivotYInput')) {
  $('#pivotYInput').addEventListener('focus', () => saveUndoState());
  $('#pivotYInput').addEventListener('input', e => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    const idx = parseInt($('#frameScrubber').value);
    const frame = meta.frames[idx];
    if (frame) {
      frame.pivot_y = parseFloat(e.target.value) || 0;
    }
  });
}
if ($('#applyPivotAllBtn')) {
  $('#applyPivotAllBtn').addEventListener('click', () => {
    const meta = window._currentMeta;
    if (!meta || !meta.frames) return;
    saveUndoState();
    const px = parseFloat($('#pivotXInput').value) || 0;
    const py = parseFloat($('#pivotYInput').value) || 0;
    meta.frames.forEach(f => {
      f.pivot_x = px;
      f.pivot_y = py;
    });
    toast(`Applied pivot (${px}, ${py}) to all frames.`);
  });
}

if ($('#saveSpriteMetadataBtn')) {
  $('#saveSpriteMetadataBtn').addEventListener('click', async () => {
    const meta = window._currentMeta;
    const path = window._currentPath;
    if (!meta || !path) { toast('No active sprite to save'); return; }
    
    try {
      toast('Saving metadata...');
      const res = await api('/api/sprite/save_metadata', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path, metadata: meta })
      });
      if (res.ok) {
        toast('Metadata saved successfully!');
        if (typeof loadSpriteDetails === 'function') await loadSpriteDetails(path);
      } else {
        toast('Save failed: ' + res.message);
      }
    } catch(e) {
      toast('Save error: ' + e.message);
    }
  });
}

if ($('#inspectSaveSnapshotBtn')) {
  $('#inspectSaveSnapshotBtn').addEventListener('click', async () => {
    if (!selectedSpriteDir) {
      toast('Select a sprite first.');
      return;
    }
    const label = prompt('Enter a label for this version snapshot (e.g. original, autofix, QA pass):');
    if (label === null) return;
    try {
      const res = await api('/api/sprite/version/save', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ path: selectedSpriteDir, label })
      });
      if (res.ok) {
        toast('Snapshot saved successfully!');
        loadSpriteVersions(selectedSpriteDir);
      }
    } catch (err) {
      toast('Error saving snapshot: ' + err.message);
    }
  });
}

if ($('#inspectRollbackBtn')) {
  $('#inspectRollbackBtn').addEventListener('click', async () => {
    const activeSel = $('#inspectActiveVersion');
    const versionId = activeSel.value;
    if (versionId === 'current' || !selectedSpriteDir) return;
    if (!confirm('Are you sure you want to rollback to this version? All unsaved edits since this snapshot will be lost.')) {
      return;
    }
    try {
      const res = await api('/api/sprite/version/rollback', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ path: selectedSpriteDir, version_id: versionId })
      });
      if (res.ok) {
        toast('Rollback completed!');
        if (typeof loadSpriteDetails === 'function') loadSpriteDetails(selectedSpriteDir);
      }
    } catch (err) {
      toast('Error rolling back: ' + err.message);
    }
  });
}

if ($('#inspectActiveVersion')) {
  $('#inspectActiveVersion').addEventListener('change', () => {
    const activeSel = $('#inspectActiveVersion');
    if ($('#inspectRollbackBtn')) {
      $('#inspectRollbackBtn').disabled = activeSel.value === 'current';
    }
  });
}

if ($('#inspectCompareEnable')) {
  $('#inspectCompareEnable').addEventListener('change', (e) => {
    const enabled = e.target.checked;
    $('#inspectCompareVersion').disabled = !enabled;
    $('#inspectCompareBlendControls').classList.toggle('hidden', !enabled);
    const compareImg = $('#inspector-img-compare');
    if (compareImg) compareImg.classList.toggle('hidden', !enabled);
    updateCompareOverlay();
  });
}

if ($('#inspectCompareVersion')) $('#inspectCompareVersion').addEventListener('change', updateCompareOverlay);
if ($('#inspectCompareMode')) $('#inspectCompareMode').addEventListener('change', updateCompareOverlay);
if ($('#inspectCompareOpacity')) {
  $('#inspectCompareOpacity').addEventListener('input', (e) => {
    const compareImg = $('#inspector-img-compare');
    if (compareImg) compareImg.style.opacity = e.target.value;
  });
}

if ($('#inspectDeleteFrameBtn')) {
  $('#inspectDeleteFrameBtn').addEventListener('click', () => {
    const frameIdx = parseInt($('#frameScrubber').value) || 0;
    frameEdits.push({ type: 'delete', indices: [frameIdx] });
    toast(`Frame ${frameIdx} marked for deletion.`);
  });
}

if ($('#inspectHoldFrameBtn')) {
  $('#inspectHoldFrameBtn').addEventListener('click', () => {
    const frameIdx = parseInt($('#frameScrubber').value) || 0;
    const count = parseInt(prompt('Hold for how many additional frames?', '1')) || 1;
    frameEdits.push({ type: 'hold', index: frameIdx, count });
    toast(`Frame ${frameIdx} set to hold for ${count} frames.`);
  });
}

if ($('#inspectTrimStartBtn')) {
  $('#inspectTrimStartBtn').addEventListener('click', () => {
    const frameIdx = parseInt($('#frameScrubber').value) || 0;
    frameEdits.push({ type: 'trim', start: frameIdx });
    toast(`Trim start set at frame ${frameIdx}.`);
  });
}

if ($('#inspectTrimEndBtn')) {
  $('#inspectTrimEndBtn').addEventListener('click', () => {
    const frameIdx = parseInt($('#frameScrubber').value) || 0;
    frameEdits.push({ type: 'trim', end: frameIdx + 1 });
    toast(`Trim end set at frame ${frameIdx}.`);
  });
}

if ($('#inspectReorderFrameBtn')) {
  $('#inspectReorderFrameBtn').addEventListener('click', () => {
    const orderStr = prompt('Enter new order mapping as comma-separated indices (e.g. 0,1,3,2,4):');
    if (!orderStr) return;
    const mapping = orderStr.split(',').map(x => parseInt(x.trim())).filter(x => !isNaN(x));
    frameEdits.push({ type: 'reorder', mapping });
    toast('Custom reorder applied.');
  });
}

if ($('#inspectSavePackBtn')) {
  $('#inspectSavePackBtn').addEventListener('click', async () => {
    if (!selectedSpriteDir) return;
    if (frameEdits.length === 0) {
      toast('No edits to pack.');
      return;
    }
    const newFps = parseInt($('#inspectPlayFps').value) || 12;
    try {
      const res = await api('/api/sprite/edit_frames', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          path: selectedSpriteDir,
          actions: frameEdits,
          fps: newFps
        })
      });
      if (res.ok) {
        toast('Repacking job started. Check Log console.');
        frameEdits = [];
        showView('logs');
      } else {
        toast('Repacking failed: ' + res.message);
      }
    } catch (err) {
      toast('Repacking error: ' + err.message);
    }
  });
}

// Undo/Redo Stack Implementation
let undoStack = [];
let redoStack = [];

function saveUndoState() {
  if (window._currentMeta) {
    undoStack.push(JSON.stringify(window._currentMeta));
    redoStack = []; // Clear redo on new action
    updateUndoRedoButtons();
  }
}

function undo() {
  if (undoStack.length > 0) {
    redoStack.push(JSON.stringify(window._currentMeta));
    const state = JSON.parse(undoStack.pop());
    window._currentMeta = state;
    restoreEditorState();
    updateUndoRedoButtons();
    toast("Undo performed");
  }
}

function redo() {
  if (redoStack.length > 0) {
    undoStack.push(JSON.stringify(window._currentMeta));
    const state = JSON.parse(redoStack.pop());
    window._currentMeta = state;
    restoreEditorState();
    updateUndoRedoButtons();
    toast("Redo performed");
  }
}

function restoreEditorState() {
  const meta = window._currentMeta;
  const scrub = $('#frameScrubber');
  if (scrub && meta) {
    scrub.max = meta.frame_count - 1;
    const val = Math.min(parseInt(scrub.value) || 0, meta.frame_count - 1);
    scrub.value = val;
    if (typeof renderInspectorFrame === 'function') renderInspectorFrame(val);
  }
}

function updateUndoRedoButtons() {
  const undoBtn = $('#inspectUndoBtn');
  const redoBtn = $('#inspectRedoBtn');
  if (undoBtn) undoBtn.disabled = undoStack.length === 0;
  if (redoBtn) redoBtn.disabled = redoStack.length === 0;
}

// Wire up Undo/Redo Buttons
if ($('#inspectUndoBtn')) $('#inspectUndoBtn').addEventListener('click', undo);
if ($('#inspectRedoBtn')) $('#inspectRedoBtn').addEventListener('click', redo);

// Add Ctrl+Z and Ctrl+Y keydown listeners
document.addEventListener('keydown', e => {
  if (e.ctrlKey && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    undo();
  }
  if (e.ctrlKey && e.key.toLowerCase() === 'y') {
    e.preventDefault();
    redo();
  }
});
