let lastAudioCueFrame = null;

function currentAudioCueManifest() {
  return window._currentPreviewBundle?.audio_cues || { cues: [] };
}

function currentAudioCue(frameIndex) {
  return (currentAudioCueManifest().cues || []).find(cue => Number(cue.frame_index) === Number(frameIndex));
}

function renderAudioCueList() {
  const list = $('#audioCueList');
  if (!list) return;
  clearNode(list);
  const cues = currentAudioCueManifest().cues || [];
  if (!cues.length) {
    appendText(list, 'span', 'No cues yet.', 'audio-cue-chip');
    return;
  }
  cues.forEach(cue => {
    const chip = document.createElement('span');
    chip.className = 'audio-cue-chip';
    chip.innerHTML = `<b>${Number(cue.frame_index) + 1}</b>${escapeHtml(cue.label || 'Cue')}`;
    list.appendChild(chip);
  });
}

async function refreshAudioCues() {
  if (!window._currentPath) return;
  const data = await api('/api/sprite/audio_cue?path=' + encodeURIComponent(window._currentPath));
  if (window._currentPreviewBundle) window._currentPreviewBundle.audio_cues = data.audio_cues;
  renderAudioCueList();
}

async function saveAudioCue() {
  const audioPath = ($('#audioCuePath')?.value || '').trim();
  if (!window._currentPath || !audioPath) {
    toast('Select a sprite and audio path first.');
    return;
  }
  const frameIndex = Number($('#frameScrubber')?.value || 0);
  const data = await api('/api/sprite/audio_cue', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      path: window._currentPath,
      frame_index: frameIndex,
      audio_path: audioPath,
      label: $('#audioCueLabel')?.value || '',
    }),
  });
  if (window._currentPreviewBundle) window._currentPreviewBundle.audio_cues = data.audio_cues;
  renderAudioCueList();
  toast('Audio cue saved.');
}

async function removeAudioCue() {
  if (!window._currentPath) return;
  const frameIndex = Number($('#frameScrubber')?.value || 0);
  const data = await api('/api/sprite/audio_cue', {
    method: 'DELETE',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ path: window._currentPath, frame_index: frameIndex }),
  });
  if (window._currentPreviewBundle) window._currentPreviewBundle.audio_cues = data.audio_cues;
  renderAudioCueList();
  toast('Audio cue removed.');
}

async function uploadAudioCueFile() {
  const file = $('#audioCueFile')?.files?.[0];
  if (!file) return;
  try {
    const data = await uploadDroppedFile(file);
    setInputValue($('#audioCuePath'), data.relative || data.path);
    toast('Uploaded: ' + data.name);
  } catch (err) {
    toast(err.message || 'Upload failed');
  }
}

function playAudioCueForFrame(frameIndex) {
  if (lastAudioCueFrame === frameIndex) return;
  const cue = currentAudioCue(frameIndex);
  lastAudioCueFrame = frameIndex;
  if (!cue?.audio_url) return;
  const audio = new Audio(cue.audio_url);
  audio.volume = 0.8;
  audio.play().catch(() => {});
}

function installAudioCuePanel() {
  const anchor = $('#onionSkinControls') || $('#inspectPlayFps')?.closest('.button-row');
  if (!anchor || $('#audioCuePanel')) return;
  const panel = document.createElement('div');
  panel.id = 'audioCuePanel';
  panel.className = 'audio-cue-panel';
  panel.innerHTML = `
    <div class="row">
      <label>Audio path<input id="audioCuePath" placeholder="input/uploaded_videos/footstep.wav" /></label>
      <label class="mini">Upload<input id="audioCueFile" type="file" accept="audio/*" /></label>
    </div>
    <label>Label<input id="audioCueLabel" placeholder="footstep" /></label>
    <div class="button-row compact-actions">
      <button class="mini primary" id="saveAudioCueBtn" type="button">Set Cue</button>
      <button class="mini" id="removeAudioCueBtn" type="button">Clear Frame</button>
    </div>
    <div id="audioCueList" class="audio-cue-list"></div>
  `;
  anchor.insertAdjacentElement('afterend', panel);
  $('#saveAudioCueBtn')?.addEventListener('click', () => saveAudioCue().catch(err => toast(err.message)));
  $('#removeAudioCueBtn')?.addEventListener('click', () => removeAudioCue().catch(err => toast(err.message)));
  $('#audioCueFile')?.addEventListener('change', uploadAudioCueFile);
  renderAudioCueList();
}

function installAudioCueHooks() {
  installAudioCuePanel();
  if (typeof loadSpriteDetails === 'function' && !window._audioCueLoadWrapped) {
    window._audioCueLoadWrapped = true;
    const baseLoad = loadSpriteDetails;
    loadSpriteDetails = async function audioCueLoad(path) {
      await baseLoad(path);
      await refreshAudioCues().catch(() => {});
      installAudioCuePanel();
    };
  }
}

installAudioCueHooks();
