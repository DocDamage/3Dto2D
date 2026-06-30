let spritePreviewAnimation = null;
let spritePreviewLastTime = 0;
let spritePreviewAccumulator = 0;

function spritePreviewControls() {
  if ($('#onionSkinControls') || !$('#inspectPlayFps')) return;
  const box = document.createElement('div');
  box.id = 'onionSkinControls';
  box.className = 'onion-skin-controls';
  box.innerHTML = `
    <label class="switch"><input type="checkbox" id="toggleOnionPrev" checked /><span></span>Previous</label>
    <label class="switch"><input type="checkbox" id="toggleOnionNext" /><span></span>Next</label>
    <label class="onion-opacity">Opacity
      <input type="range" id="onionOpacity" min="0" max="0.8" step="0.05" value="0.28" />
    </label>
  `;
  const playRow = $('#inspectPlayFps').closest('.button-row');
  if (playRow) playRow.insertAdjacentElement('afterend', box);
  ['#toggleOnionPrev', '#toggleOnionNext', '#onionOpacity'].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener('input', spritePreviewRenderCurrentFrame);
  });
}

async function spritePreviewLoadBundle(path) {
  try {
    window._currentPreviewBundle = await api('/api/sprite/preview?path=' + encodeURIComponent(path));
  } catch (err) {
    window._currentPreviewBundle = null;
    console.warn(err);
  }
}

function spritePreviewFrameUrl(index) {
  const bundle = window._currentPreviewBundle;
  const frame = bundle?.frames?.[index];
  return frame?.url || '';
}

function spritePreviewSheetCrop(meta, index) {
  const frame = meta.frames ? meta.frames[index] : null;
  const fw = Number(meta.frame_width || frame?.w || 0);
  const fh = Number(meta.frame_height || frame?.h || 0);
  const columns = Math.max(1, Number(meta.columns || 1));
  return {
    sx: frame ? Number(frame.x || 0) : (index % columns) * fw,
    sy: frame ? Number(frame.y || 0) : Math.floor(index / columns) * fh,
    sw: Number(frame?.w || fw),
    sh: Number(frame?.h || fh),
    fw,
    fh,
  };
}

function spritePreviewDrawSheetFrame(ctx, img, meta, index, dx, opacity) {
  const crop = spritePreviewSheetCrop(meta, index);
  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.drawImage(img, crop.sx, crop.sy, crop.sw, crop.sh, dx, 0, crop.fw, crop.fh);
  ctx.restore();
}

function spritePreviewDrawUrlFrame(ctx, url, dx, fw, fh, opacity, onDone) {
  const img = new Image();
  img.onload = () => {
    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.drawImage(img, dx, 0, fw, fh);
    ctx.restore();
    if (onDone) onDone();
  };
  img.src = url + '?t=' + Date.now();
}

function spritePreviewDrawOnion(ctx, meta, sheetImg, index, offset, opacity) {
  const count = Number(meta.frame_count || 0);
  if (count < 2) return;
  const target = (index + offset + count) % count;
  spritePreviewDrawSheetFrame(ctx, sheetImg, meta, target, 0, opacity);
}

function spritePreviewRenderFrame(index) {
  const meta = window._currentMeta;
  const path = window._currentPath;
  if (!meta || !path) return;

  const fw = Number(meta.frame_width || 0);
  const fh = Number(meta.frame_height || 0);
  const currentUrl = spritePreviewFrameUrl(index);
  const sheet = new Image();
  sheet.onload = () => {
    let canvas = $('#inspector-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'inspector-canvas';
      canvas.className = 'inspector-img';
      const placeholder = $('#inspector-img');
      if (placeholder) placeholder.replaceWith(canvas);
      else $('#inspector-canvas-container')?.appendChild(canvas);
    }

    const compare = $('#toggleCompareSibling') && $('#toggleCompareSibling').checked && window._siblingImg;
    if (compare && typeof window._baseRenderInspectorFrame === 'function') {
      window._baseRenderInspectorFrame(index);
      return;
    }

    canvas.width = fw;
    canvas.height = fh;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, fw, fh);

    const onionOpacity = Number($('#onionOpacity')?.value || 0.28);
    if ($('#toggleOnionPrev')?.checked) spritePreviewDrawOnion(ctx, meta, sheet, index, -1, onionOpacity);
    if ($('#toggleOnionNext')?.checked) spritePreviewDrawOnion(ctx, meta, sheet, index, 1, onionOpacity);

    const drawCurrent = () => {
      const frame = meta.frames ? meta.frames[index] : null;
      if (frame && frame.bad) {
        ctx.fillStyle = 'rgba(255, 0, 0, 0.25)';
        ctx.fillRect(0, 0, fw, fh);
        ctx.fillStyle = '#ff4444';
        ctx.font = 'bold 16px sans-serif';
        ctx.fillText('BAD FRAME', 10, 25);
      }
      if (frame) {
        if ($('#pivotXInput')) $('#pivotXInput').value = frame.pivot_x !== undefined ? frame.pivot_x : Math.round(frame.w / 2);
        if ($('#pivotYInput')) $('#pivotYInput').value = frame.pivot_y !== undefined ? frame.pivot_y : frame.h;
      }
      if ($('#frameScrubberLabel')) $('#frameScrubberLabel').textContent = `${index + 1} / ${meta.frame_count}`;
      if (typeof playAudioCueForFrame === 'function' && spritePreviewAnimation) playAudioCueForFrame(index);
      if (typeof updateOverlays === 'function') updateOverlays(fw, fh, index);
      if (typeof updateCompareOverlay === 'function') updateCompareOverlay();
    };

    if (currentUrl) spritePreviewDrawUrlFrame(ctx, currentUrl, 0, fw, fh, 1, drawCurrent);
    else {
      spritePreviewDrawSheetFrame(ctx, sheet, meta, index, 0, 1);
      drawCurrent();
    }
  };
  sheet.src = '/file/' + path + '/' + (meta.image || 'sheet.png') + '?t=' + Date.now();
}

function spritePreviewRenderCurrentFrame() {
  const scrub = $('#frameScrubber');
  if (scrub) spritePreviewRenderFrame(Number(scrub.value || 0));
}

function spritePreviewStopPlayback() {
  if (spritePreviewAnimation) cancelAnimationFrame(spritePreviewAnimation);
  spritePreviewAnimation = null;
  spritePreviewLastTime = 0;
  spritePreviewAccumulator = 0;
  if ($('#inspectPlayBtn')) $('#inspectPlayBtn').textContent = '▶ Play';
}

function spritePreviewStartPlayback() {
  const meta = window._currentMeta;
  const scrub = $('#frameScrubber');
  if (!meta || !scrub || !Number(meta.frame_count)) return;
  $('#inspectPlayBtn').textContent = '⏸ Pause';
  const tick = time => {
    if (!spritePreviewLastTime) spritePreviewLastTime = time;
    const fps = Math.max(1, Number($('#inspectPlayFps')?.value || meta.fps || 12));
    spritePreviewAccumulator += time - spritePreviewLastTime;
    spritePreviewLastTime = time;
    const frameMs = 1000 / fps;
    while (spritePreviewAccumulator >= frameMs) {
      scrub.value = (Number(scrub.value || 0) + 1) % Number(meta.frame_count);
      spritePreviewAccumulator -= frameMs;
      spritePreviewRenderFrame(Number(scrub.value));
    }
    spritePreviewAnimation = requestAnimationFrame(tick);
  };
  spritePreviewAnimation = requestAnimationFrame(tick);
}

function spritePreviewTogglePlayback() {
  if (spritePreviewAnimation) spritePreviewStopPlayback();
  else spritePreviewStartPlayback();
}

function spritePreviewInstall() {
  spritePreviewControls();
  if (typeof loadSpriteDetails === 'function' && !window._baseLoadSpriteDetails) {
    window._baseLoadSpriteDetails = loadSpriteDetails;
    loadSpriteDetails = async function wrappedLoadSpriteDetails(path) {
      await window._baseLoadSpriteDetails(path);
      await spritePreviewLoadBundle(path);
      spritePreviewRenderCurrentFrame();
    };
  }
  if (typeof renderInspectorFrame === 'function' && !window._baseRenderInspectorFrame) {
    window._baseRenderInspectorFrame = renderInspectorFrame;
    renderInspectorFrame = spritePreviewRenderFrame;
  }
  togglePlayback = spritePreviewTogglePlayback;
}

spritePreviewInstall();
