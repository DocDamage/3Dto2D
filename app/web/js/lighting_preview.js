let lightingSprite = null;
let lightingNormal = null;
let lightingSpecular = null;
let lightingAo = null;

function lightingFileUrl(path, file) {
  const clean = String(path || '').replace(/\\/g, '/').replace(/\/+$/, '');
  return '/file/' + clean + '/' + file;
}

function loadLightingImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not load ' + url));
    img.src = url + '?t=' + Date.now();
  });
}

function lightingControls() {
  return {
    x: Number($('#lightingX')?.value || 0.35),
    y: Number($('#lightingY')?.value || -0.45),
    intensity: Number($('#lightingIntensity')?.value || 1.15),
    ambient: Number($('#lightingAmbient')?.value || 0.35),
    specular: Number($('#lightingSpecular')?.value || 0.35),
    zoom: Number($('#lightingZoom')?.value || 1),
  };
}

function renderLightingPreview() {
  const canvas = $('#lightingCanvas');
  if (!canvas || !lightingSprite || !lightingNormal) return;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const controls = lightingControls();
  const w = lightingSprite.naturalWidth || lightingSprite.width;
  const h = lightingSprite.naturalHeight || lightingSprite.height;
  canvas.width = Math.max(1, Math.round(w * controls.zoom));
  canvas.height = Math.max(1, Math.round(h * controls.zoom));

  const work = document.createElement('canvas');
  work.width = w;
  work.height = h;
  const workCtx = work.getContext('2d', { willReadFrequently: true });
  workCtx.clearRect(0, 0, w, h);
  workCtx.drawImage(lightingSprite, 0, 0, w, h);
  const spriteData = workCtx.getImageData(0, 0, w, h);
  workCtx.clearRect(0, 0, w, h);
  workCtx.drawImage(lightingNormal, 0, 0, w, h);
  const normalData = workCtx.getImageData(0, 0, w, h);
  let specularData = null;
  let aoData = null;
  if (lightingSpecular) {
    workCtx.clearRect(0, 0, w, h);
    workCtx.drawImage(lightingSpecular, 0, 0, w, h);
    specularData = workCtx.getImageData(0, 0, w, h);
  }
  if (lightingAo) {
    workCtx.clearRect(0, 0, w, h);
    workCtx.drawImage(lightingAo, 0, 0, w, h);
    aoData = workCtx.getImageData(0, 0, w, h);
  }
  const out = workCtx.createImageData(w, h);
  const lx = controls.x;
  const ly = controls.y;
  const lz = 0.75;
  const llen = Math.hypot(lx, ly, lz) || 1;
  const light = [lx / llen, ly / llen, lz / llen];

  for (let i = 0; i < spriteData.data.length; i += 4) {
    const a = spriteData.data[i + 3];
    const nx = normalData.data[i] / 127.5 - 1;
    const ny = normalData.data[i + 1] / 127.5 - 1;
    const nz = normalData.data[i + 2] / 127.5 - 1;
    const nlen = Math.hypot(nx, ny, nz) || 1;
    const dot = Math.max(0, (nx / nlen) * light[0] + (ny / nlen) * light[1] + (nz / nlen) * light[2]);
    const specMask = specularData ? specularData.data[i] / 255 : 1;
    const aoMask = aoData ? aoData.data[i] / 255 : 1;
    const shine = Math.pow(dot, 18) * controls.specular * specMask;
    const shade = controls.ambient * aoMask + dot * controls.intensity + shine;
    out.data[i] = Math.min(255, spriteData.data[i] * shade);
    out.data[i + 1] = Math.min(255, spriteData.data[i + 1] * shade);
    out.data[i + 2] = Math.min(255, spriteData.data[i + 2] * shade);
    out.data[i + 3] = a;
  }

  workCtx.putImageData(out, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(work, 0, 0, canvas.width, canvas.height);
}

async function loadLightingPreview() {
  const input = $('#lightingSpriteDir');
  const status = $('#lightingStatus');
  const spriteDir = String(input?.value || selectedSpriteDir || '').trim();
  if (!spriteDir) {
    toast('Choose a sprite folder first.');
    return;
  }
  if (status) status.textContent = 'Loading sprite and normal map...';
  try {
    const spriteUrl = lightingFileUrl(spriteDir, 'sheet.png');
    const normalUrl = lightingFileUrl(spriteDir, 'sheet_normal.png');
    const specularUrl = lightingFileUrl(spriteDir, 'sheet_specular.png');
    const aoUrl = lightingFileUrl(spriteDir, 'sheet_ao.png');
    const loaded = await Promise.all([loadLightingImage(spriteUrl), loadLightingImage(normalUrl)]);
    lightingSprite = loaded[0];
    lightingNormal = loaded[1];
    lightingSpecular = await loadLightingImage(specularUrl).catch(() => null);
    lightingAo = await loadLightingImage(aoUrl).catch(() => null);
    renderLightingPreview();
    if (status) status.textContent = `Drag the canvas to move the light. ${lightingSpecular ? 'Specular map loaded.' : 'Specular map missing; using slider only.'} ${lightingAo ? 'AO map loaded.' : 'AO map missing; ambient is unmasked.'}`;
  } catch (err) {
    if (status) status.textContent = err.message || 'Could not load lighting assets.';
    toast(err.message || 'Could not load lighting assets.');
  }
}

async function exportLightingPreviewGif() {
  const input = $('#lightingSpriteDir');
  const status = $('#lightingStatus');
  const spriteDir = String(input?.value || selectedSpriteDir || '').trim();
  if (!spriteDir) {
    toast('Choose a sprite folder first.');
    return;
  }
  if (status) status.textContent = 'Baking lit preview GIF...';
  try {
    const controls = lightingControls();
    const res = await fetch('/api/sprite/export_lighting_preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: spriteDir,
        light_x: controls.x,
        light_y: controls.y,
        intensity: controls.intensity,
        ambient: controls.ambient,
      }),
    });
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.message || 'Could not export lit preview GIF.');
    const link = data.path ? '/file/' + data.path : '';
    if (status) {
      status.innerHTML = link
        ? 'Lit GIF exported: <a href="' + link + '" target="_blank" rel="noreferrer">' + data.path + '</a>'
        : 'Lit GIF exported.';
    }
    toast('Lit preview GIF exported.');
  } catch (err) {
    if (status) status.textContent = err.message || 'Could not export lit preview GIF.';
    toast(err.message || 'Could not export lit preview GIF.');
  }
}

function installLightingPreview() {
  $('#lightingUseSelected')?.addEventListener('click', () => {
    const input = $('#lightingSpriteDir');
    if (input) input.value = selectedSpriteDir || '';
  });
  $('#lightingLoad')?.addEventListener('click', loadLightingPreview);
  $('#lightingExportGif')?.addEventListener('click', exportLightingPreviewGif);
  $('#lightingExport')?.addEventListener('click', () => {
    const canvas = $('#lightingCanvas');
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = 'lighting_preview.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  });
  ['lightingX', 'lightingY', 'lightingIntensity', 'lightingAmbient', 'lightingSpecular', 'lightingZoom'].forEach(id => {
    $('#' + id)?.addEventListener('input', renderLightingPreview);
  });
  $('#lightingCanvas')?.addEventListener('pointerdown', event => {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    const update = ev => {
      const x = ((ev.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1;
      const y = ((ev.clientY - rect.top) / Math.max(1, rect.height)) * 2 - 1;
      const xInput = $('#lightingX');
      const yInput = $('#lightingY');
      if (xInput) xInput.value = String(Math.max(-1, Math.min(1, x)));
      if (yInput) yInput.value = String(Math.max(-1, Math.min(1, y)));
      renderLightingPreview();
    };
    update(event);
    canvas.setPointerCapture(event.pointerId);
    canvas.onpointermove = update;
    canvas.onpointerup = () => { canvas.onpointermove = null; };
  });
}

installLightingPreview();
