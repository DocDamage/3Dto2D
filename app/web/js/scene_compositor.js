function sceneCompositorRecentRows() {
  return (window.currentOutputs || []).slice(0, 3).map((item, index) => {
    const x = 220 + index * 90;
    const y = 180;
    return `${item.name || 'Layer ' + (index + 1)}|${item.path}|${x}|${y}|1`;
  }).join('\n');
}

function parseSceneLayers(text) {
  return String(text || '').split(/\r?\n/).map((line) => {
    const parts = line.split('|').map((part) => part.trim());
    return {
      name: parts[0],
      sprite_path: parts[1],
      x: parseFloat(parts[2] || '320'),
      y: parseFloat(parts[3] || '180'),
      scale: parseFloat(parts[4] || '1'),
      opacity: parseFloat(parts[5] || '1'),
      z: parseInt(parts[6] || '0', 10),
    };
  }).filter((layer) => layer.name && layer.sprite_path);
}

function drawSceneFrame(ctx, layer, image, tick) {
  const frame = Math.floor((tick / Math.max(1, 60 / layer.fps))) % Math.max(1, layer.frame_count);
  const sx = (frame % layer.columns) * layer.frame_width;
  const sy = Math.floor(frame / layer.columns) * layer.frame_height;
  const w = layer.frame_width * layer.scale;
  const h = layer.frame_height * layer.scale;
  ctx.globalAlpha = layer.opacity;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(image, sx, sy, layer.frame_width, layer.frame_height, layer.x - w / 2, layer.y - h, w, h);
  ctx.globalAlpha = 1;
}

async function previewSceneCompositor() {
  const payload = {
    name: $('#sceneCompositorName')?.value || 'scene',
    width: parseInt($('#sceneCompositorWidth')?.value || '640', 10),
    height: parseInt($('#sceneCompositorHeight')?.value || '360', 10),
    fps: parseInt($('#sceneCompositorFps')?.value || '12', 10),
    grid_size: parseInt($('#sceneCompositorGrid')?.value || '16', 10),
    snap_to_grid: $('#sceneCompositorSnap')?.checked || false,
    write_exports: $('#sceneCompositorExport')?.checked || false,
    background_color: $('#sceneCompositorBackground')?.value || '#1B1F2A',
    background_type: $('#sceneCompositorBackgroundImage')?.value ? 'image' : 'color',
    background_image: $('#sceneCompositorBackgroundImage')?.value || '',
    layers: parseSceneLayers($('#sceneCompositorLayers')?.value || ''),
  };
  const status = $('#sceneCompositorStatus');
  if (status) status.textContent = 'Building scene preview...';
  try {
    const data = await api('/api/scene_compositor/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    renderSceneCompositor(data);
    if (status) status.textContent = `${data.layers.length} layer scene ready.`;
  } catch (err) {
    if (status) status.textContent = err.message || 'Scene preview failed.';
  }
}

function renderSceneCompositor(data) {
  const canvas = $('#sceneCompositorCanvas');
  if (!canvas) return;
  canvas.width = data.scene.width;
  canvas.height = data.scene.height;
  const ctx = canvas.getContext('2d');
  const bg = data.scene.background || {};
  const images = [];
  let backgroundImage = null;
  let backgroundLoaded = !bg.image;
  if (bg.image) {
    backgroundImage = new Image();
    backgroundImage.onload = () => { backgroundLoaded = true; };
    backgroundImage.onerror = () => { backgroundLoaded = true; backgroundImage = null; };
    backgroundImage.src = '/file/' + String(bg.image).replace(/^\/?file\//, '').replace(/\\/g, '/') + '?t=' + Date.now();
  }
  let loaded = 0;
  data.layers.forEach((layer, index) => {
    const img = new Image();
    img.onload = () => { loaded += 1; };
    img.src = layer.sheet_url + '?t=' + Date.now();
    images[index] = img;
  });
  let tick = 0;
  if (window._sceneCompositorTimer) clearInterval(window._sceneCompositorTimer);
  window._sceneCompositorTimer = setInterval(() => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = bg.color || 'rgba(0,0,0,0.18)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (backgroundLoaded && backgroundImage) {
      ctx.drawImage(backgroundImage, 0, 0, canvas.width, canvas.height);
    }
    if (loaded < images.length) return;
    data.layers.forEach((layer, index) => drawSceneFrame(ctx, layer, images[index], tick));
    tick += 1;
  }, 1000 / Math.max(1, data.scene.fps));
}

function installSceneCompositorPanel() {
  const stateCard = $('#stateMachineCard');
  const atlasForm = $('#atlasForm');
  if ((!stateCard && !atlasForm) || $('#sceneCompositorCard')) return;
  const card = document.createElement('section');
  card.id = 'sceneCompositorCard';
  card.className = 'card form scene-compositor-card';
  card.innerHTML = `
    <div class="card-head">
      <h3>Scene Compositor</h3>
      <button class="mini" id="fillSceneLayers" type="button">Use recent</button>
    </div>
    <div class="row compact-fields">
      <label>Name<input id="sceneCompositorName" value="scene_preview" /></label>
      <label>W<input id="sceneCompositorWidth" type="number" value="640" /></label>
      <label>H<input id="sceneCompositorHeight" type="number" value="360" /></label>
      <label>FPS<input id="sceneCompositorFps" type="number" value="12" /></label>
      <label>Grid<input id="sceneCompositorGrid" type="number" value="16" /></label>
      <label>BG<input id="sceneCompositorBackground" value="#1B1F2A" /></label>
    </div>
    <label>Background image<input id="sceneCompositorBackgroundImage" placeholder="output/backgrounds/arena.png" /></label>
    <div class="switches">
      <label class="switch"><input type="checkbox" id="sceneCompositorSnap" checked /><span></span>Snap to grid</label>
      <label class="switch"><input type="checkbox" id="sceneCompositorExport" /><span></span>Write Godot scene</label>
    </div>
    <label>Layers<textarea id="sceneCompositorLayers" rows="5" placeholder="Hero|output\\hero_idle_sprite|240|220|2|1|1&#10;Slime|output\\slime_walk_sprite|360|220|1.5|1|2"></textarea></label>
    <button class="primary" id="previewSceneCompositorBtn" type="button">Preview Scene</button>
    <canvas id="sceneCompositorCanvas" class="scene-compositor-canvas" width="640" height="360"></canvas>
    <div id="sceneCompositorStatus" class="scene-compositor-status">No scene preview yet.</div>
  `;
  (stateCard || atlasForm).insertAdjacentElement('afterend', card);
  $('#previewSceneCompositorBtn')?.addEventListener('click', previewSceneCompositor);
  $('#fillSceneLayers')?.addEventListener('click', () => {
    const rows = sceneCompositorRecentRows();
    if (rows) $('#sceneCompositorLayers').value = rows;
  });
}

window.viewComponentsLoaded.then(installSceneCompositorPanel);
