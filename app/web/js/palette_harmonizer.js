function paletteCandidatePaths() {
  const paths = [];
  if (window.selectedSpriteDir) paths.push(window.selectedSpriteDir);
  (window.currentOutputs || []).forEach(item => {
    if (item && item.path) paths.push(item.path);
  });
  return Array.from(new Set(paths)).slice(0, 8);
}

function normalizePaletteEditorColors(value) {
  const colors = Array.isArray(value) ? value : String(value || '').split(/[\s,]+/);
  const seen = new Set();
  return colors.map(color => String(color || '').trim())
    .map(color => color && !color.startsWith('#') ? '#' + color : color)
    .filter(color => /^#[0-9a-fA-F]{6}$/.test(color))
    .map(color => color.toUpperCase())
    .filter(color => {
      if (seen.has(color)) return false;
      seen.add(color);
      return true;
    });
}

function paletteRgbToHex(r, g, b) {
  return '#' + [r, g, b].map(value => {
    const clamped = Math.max(0, Math.min(255, Number(value) || 0));
    return clamped.toString(16).padStart(2, '0');
  }).join('').toUpperCase();
}

function paletteHexToRgb(color) {
  const hex = String(color || '').replace('#', '');
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return null;
  return [
    parseInt(hex.slice(0, 2), 16),
    parseInt(hex.slice(2, 4), 16),
    parseInt(hex.slice(4, 6), 16),
  ];
}

function paletteHslToHex(h, s, l) {
  const hue = (((Number(h) || 0) % 360) + 360) % 360;
  const sat = Math.max(0, Math.min(100, Number(s) || 0)) / 100;
  const light = Math.max(0, Math.min(100, Number(l) || 0)) / 100;
  const chroma = (1 - Math.abs(2 * light - 1)) * sat;
  const x = chroma * (1 - Math.abs((hue / 60) % 2 - 1));
  const match = light - chroma / 2;
  let r = 0;
  let g = 0;
  let b = 0;
  if (hue < 60) [r, g, b] = [chroma, x, 0];
  else if (hue < 120) [r, g, b] = [x, chroma, 0];
  else if (hue < 180) [r, g, b] = [0, chroma, x];
  else if (hue < 240) [r, g, b] = [0, x, chroma];
  else if (hue < 300) [r, g, b] = [x, 0, chroma];
  else [r, g, b] = [chroma, 0, x];
  return paletteRgbToHex(Math.round((r + match) * 255), Math.round((g + match) * 255), Math.round((b + match) * 255));
}

function nearestPaletteRgb(r, g, b, palette) {
  let best = palette[0];
  let bestDistance = Number.POSITIVE_INFINITY;
  palette.forEach(color => {
    const dr = r - color[0];
    const dg = g - color[1];
    const db = b - color[2];
    const distance = dr * dr + dg * dg + db * db;
    if (distance < bestDistance) {
      bestDistance = distance;
      best = color;
    }
  });
  return best;
}

function palettePreviewImageUrl(spritePath) {
  const clean = String(spritePath || '').replace(/\\/g, '/').replace(/\/+$/, '');
  return clean ? '/file/' + clean + '/sheet.png' : '';
}

function loadPalettePreviewImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Could not load palette preview image.'));
    image.src = url + '?t=' + Date.now();
  });
}

async function refreshPaletteQuantizedPreview() {
  const canvas = $('#paletteEditorPreviewCanvas');
  const status = $('#paletteEditorPreviewStatus');
  if (!canvas) return;
  const colors = getPaletteEditorColors();
  const palette = colors.map(paletteHexToRgb).filter(Boolean);
  if (!palette.length) {
    if (status) status.textContent = 'Add palette colors to preview quantization.';
    return;
  }
  const explicit = ($('#paletteHarmonizerPaths')?.value || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const spritePath = explicit[0] || paletteCandidatePaths()[0];
  const url = palettePreviewImageUrl(spritePath);
  if (!url) {
    if (status) status.textContent = 'Select or load a sprite folder to preview.';
    return;
  }
  if (status) status.textContent = 'Building palette preview...';
  try {
    const image = await loadPalettePreviewImage(url);
    const maxSide = 192;
    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth || image.width, image.naturalHeight || image.height, 1));
    const sourceWidth = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
    const sourceHeight = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
    canvas.width = sourceWidth * 2;
    canvas.height = sourceHeight;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, sourceWidth, sourceHeight);
    const data = ctx.getImageData(0, 0, sourceWidth, sourceHeight);
    for (let i = 0; i < data.data.length; i += 4) {
      if (data.data[i + 3] < 8) continue;
      const nearest = nearestPaletteRgb(data.data[i], data.data[i + 1], data.data[i + 2], palette);
      data.data[i] = nearest[0];
      data.data[i + 1] = nearest[1];
      data.data[i + 2] = nearest[2];
    }
    ctx.putImageData(data, sourceWidth, 0);
    ctx.strokeStyle = 'rgba(255,255,255,.22)';
    ctx.beginPath();
    ctx.moveTo(sourceWidth + 0.5, 0);
    ctx.lineTo(sourceWidth + 0.5, sourceHeight);
    ctx.stroke();
    if (status) status.textContent = `Previewing ${colors.length} colors on ${spritePath || 'selected sprite'} (source left, snapped right).`;
  } catch (err) {
    if (status) status.textContent = err.message || 'Could not build palette preview.';
  }
}

function parseImportedPaletteText(text) {
  const raw = String(text || '');
  const colors = [];
  try {
    const parsed = JSON.parse(raw);
    const lospecColors = Array.isArray(parsed?.colors)
      ? parsed.colors
      : Array.isArray(parsed?.palette?.colors)
        ? parsed.palette.colors
        : [];
    lospecColors.forEach(color => colors.push(typeof color === 'string' ? color : color?.hex || color?.color || ''));
  } catch (err) {
    // Plain text, GPL, and hex-list palettes are expected to land here.
  }
  const hexMatches = raw.match(/#[0-9a-fA-F]{6}\b|(?:^|[\s,;])([0-9a-fA-F]{6})(?=$|[\s,;])/gm) || [];
  hexMatches.forEach(match => {
    const cleaned = match.trim().replace(/^[,;\s]+/, '');
    colors.push(cleaned.startsWith('#') ? cleaned : '#' + cleaned);
  });
  raw.split(/\r?\n/).forEach(line => {
    const cleaned = line.trim();
    if (!cleaned || cleaned.startsWith('#') || /^GIMP Palette/i.test(cleaned) || /^Name:/i.test(cleaned) || /^Columns:/i.test(cleaned)) return;
    const rgb = cleaned.match(/^(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})(?:\s+.*)?$/);
    if (rgb) colors.push(paletteRgbToHex(rgb[1], rgb[2], rgb[3]));
  });
  return normalizePaletteEditorColors(colors);
}

function paletteAseUtf16(view, offset, chars) {
  let text = '';
  for (let i = 0; i < chars; i += 1) {
    const code = view.getUint16(offset + i * 2, false);
    if (code) text += String.fromCharCode(code);
  }
  return text;
}

function paletteAseAscii(view, offset, chars) {
  let text = '';
  for (let i = 0; i < chars; i += 1) {
    text += String.fromCharCode(view.getUint8(offset + i));
  }
  return text;
}

function paletteAseRgbToHex(model, components) {
  const clamp = value => Math.max(0, Math.min(255, Math.round(value)));
  if (model === 'RGB ') {
    return paletteRgbToHex(clamp(components[0] * 255), clamp(components[1] * 255), clamp(components[2] * 255));
  }
  if (model === 'Gray') {
    const gray = clamp(components[0] * 255);
    return paletteRgbToHex(gray, gray, gray);
  }
  if (model === 'CMYK') {
    const c = components[0];
    const m = components[1];
    const y = components[2];
    const k = components[3];
    return paletteRgbToHex(clamp(255 * (1 - c) * (1 - k)), clamp(255 * (1 - m) * (1 - k)), clamp(255 * (1 - y) * (1 - k)));
  }
  return '';
}

function parseAsePalette(buffer) {
  const view = new DataView(buffer);
  if (buffer.byteLength < 12 || paletteAseAscii(view, 0, 4) !== 'ASEF') return [];
  const colors = [];
  const blockCount = view.getUint32(8, false);
  let offset = 12;
  for (let block = 0; block < blockCount && offset + 6 <= buffer.byteLength; block += 1) {
    const blockType = view.getUint16(offset, false);
    const blockLength = view.getUint32(offset + 2, false);
    const blockStart = offset + 6;
    const blockEnd = Math.min(blockStart + blockLength, buffer.byteLength);
    if (blockType === 0x0001 && blockStart + 8 <= blockEnd) {
      const nameLength = view.getUint16(blockStart, false);
      const colorOffset = blockStart + 2 + nameLength * 2;
      if (colorOffset + 20 <= blockEnd) {
        const model = paletteAseAscii(view, colorOffset, 4);
        const componentCount = model === 'CMYK' ? 4 : 3;
        const components = [];
        for (let i = 0; i < componentCount && colorOffset + 4 + i * 4 + 4 <= blockEnd; i += 1) {
          components.push(view.getFloat32(colorOffset + 4 + i * 4, false));
        }
        colors.push(paletteAseRgbToHex(model, components));
      }
    }
    offset = blockEnd;
  }
  return normalizePaletteEditorColors(colors);
}

function setPaletteEditorColors(colors) {
  const normalized = normalizePaletteEditorColors(colors);
  const text = $('#paletteEditorColorsText');
  if (text) text.value = normalized.join(', ');
  renderPaletteEditorSwatches(normalized);
  refreshPaletteQuantizedPreview();
  return normalized;
}

function getPaletteEditorColors() {
  return normalizePaletteEditorColors($('#paletteEditorColorsText')?.value || '');
}

async function importPaletteEditorFile(file) {
  if (!file) return [];
  const isAse = /\.ase$/i.test(file.name || '');
  const parsed = isAse ? parseAsePalette(await file.arrayBuffer()) : parseImportedPaletteText(await file.text());
  const colors = setPaletteEditorColors(parsed);
  const status = $('#paletteEditorImportStatus');
  if (status) status.textContent = colors.length
    ? `Imported ${colors.length} colors from ${file.name}.`
    : `No importable colors found in ${file.name}.`;
  return colors;
}

function renderPaletteEditorSwatches(colors) {
  const target = $('#paletteEditorSwatches');
  if (!target) return;
  clearNode(target);
  colors.forEach((color, index) => {
    const input = document.createElement('input');
    input.type = 'color';
    input.value = color;
    input.title = `Palette color ${index + 1}: ${color}`;
    input.addEventListener('input', () => {
      const updated = getPaletteEditorColors();
      updated[index] = input.value.toUpperCase();
      setPaletteEditorColors(updated);
    });
    target.appendChild(input);
  });
}

function updatePaletteHslWheel(event) {
  const wheel = $('#paletteHslWheel');
  if (!wheel) return;
  const rect = wheel.getBoundingClientRect();
  const center = rect.width / 2;
  const x = event.clientX - rect.left - center;
  const y = event.clientY - rect.top - center;
  const radius = Math.min(1, Math.hypot(x, y) / Math.max(1, center));
  const hue = Math.round((Math.atan2(y, x) * 180 / Math.PI + 360) % 360);
  const saturation = Math.round(radius * 100);
  wheel.dataset.hue = String(hue);
  wheel.dataset.saturation = String(saturation);
  const handle = $('#paletteHslHandle');
  if (handle) {
    handle.style.left = `${50 + Math.cos(hue * Math.PI / 180) * radius * 50}%`;
    handle.style.top = `${50 + Math.sin(hue * Math.PI / 180) * radius * 50}%`;
  }
  refreshPaletteHslPreview();
}

function refreshPaletteHslPreview() {
  const wheel = $('#paletteHslWheel');
  const lightness = Number($('#paletteHslLightness')?.value || 52);
  const hex = paletteHslToHex(Number(wheel?.dataset.hue || 210), Number(wheel?.dataset.saturation || 72), lightness);
  const preview = $('#paletteHslPreview');
  const value = $('#paletteHslValue');
  if (preview) preview.style.background = hex;
  if (value) value.textContent = hex;
  return hex;
}

function addPaletteHslColor() {
  const hex = refreshPaletteHslPreview();
  const colors = getPaletteEditorColors();
  colors.push(hex);
  setPaletteEditorColors(colors);
  toast(`Added ${hex} to palette.`);
}

function installPaletteHslWheel() {
  const wheel = $('#paletteHslWheel');
  if (!wheel) return;
  let dragging = false;
  const stop = () => { dragging = false; };
  wheel.addEventListener('pointerdown', event => {
    dragging = true;
    wheel.setPointerCapture?.(event.pointerId);
    updatePaletteHslWheel(event);
  });
  wheel.addEventListener('pointermove', event => {
    if (dragging) updatePaletteHslWheel(event);
  });
  wheel.addEventListener('pointerup', stop);
  wheel.addEventListener('pointercancel', stop);
  $('#paletteHslLightness')?.addEventListener('input', refreshPaletteHslPreview);
  $('#paletteHslAddColor')?.addEventListener('click', addPaletteHslColor);
  refreshPaletteHslPreview();
}

function renderPaletteReport(report) {
  const target = $('#paletteHarmonizerResult');
  if (!target) return;
  clearNode(target);
  setPaletteEditorColors(report.palette || []);
  const palette = document.createElement('div');
  palette.className = 'palette-harmonizer-swatches';
  (report.palette || []).forEach(color => {
    const swatch = document.createElement('span');
    swatch.style.background = color;
    swatch.title = color;
    palette.appendChild(swatch);
  });
  target.appendChild(palette);

  const list = document.createElement('div');
  list.className = 'palette-harmonizer-list';
  (report.sprites || []).forEach(sprite => {
    const row = document.createElement('div');
    row.className = 'palette-harmonizer-row';
    const name = (sprite.path || '').split(/[\\/]/).filter(Boolean).pop() || 'sprite';
    appendText(row, 'b', name);
    appendText(row, 'small', `${sprite.distinct_colors} colors · avg drift ${sprite.average_palette_drift}`);
    if (sprite.harmonized_sheet_url) {
      const link = document.createElement('a');
      link.href = sprite.harmonized_sheet_url + '?t=' + Date.now();
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = 'Open harmonized sheet';
      row.appendChild(link);
    }
    list.appendChild(row);
  });
  target.appendChild(list);
}

async function maybeSaveProjectPaletteLock(report) {
  const checkbox = $('#paletteHarmonizerLockProject');
  const colors = getPaletteEditorColors();
  if (!checkbox?.checked || !colors.length) return;
  await api('/api/project/config', {
    method: 'POST',
    body: JSON.stringify({
      palette_lock: {
        enabled: true,
        colors,
        colors_limit: Number(report?.colors || colors.length || 32),
        palette_file: report.palette_file || '',
        source: 'palette_editor',
      },
    }),
  });
}

async function runPaletteHarmonizer() {
  const pathsInput = $('#paletteHarmonizerPaths');
  const colorsInput = $('#paletteHarmonizerColors');
  const result = $('#paletteHarmonizerResult');
  const explicit = (pathsInput?.value || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const sprites = explicit.length ? explicit : paletteCandidatePaths();
  if (sprites.length < 2) {
    toast('Choose at least two sprite folders.');
    return;
  }
  if (result) result.textContent = 'Harmonizing palettes...';
  try {
    const report = await api('/api/sprites/palette_harmonize', {
      method: 'POST',
      body: JSON.stringify({
        sprites,
        colors: Number(colorsInput?.value || 32),
        write_images: true,
      }),
    });
    renderPaletteReport(report);
    await maybeSaveProjectPaletteLock(report);
    toast($('#paletteHarmonizerLockProject')?.checked ? 'Palette harmonized and locked to project.' : 'Palette harmonization complete.');
  } catch (err) {
    if (result) result.textContent = 'Palette harmonization failed.';
    toast(err.message || 'Palette harmonization failed.');
  }
}

function installPaletteHarmonizer() {
  const form = $('#qualityForm');
  if (!form || $('#paletteHarmonizerCard')) return;
  const card = document.createElement('section');
  card.id = 'paletteHarmonizerCard';
  card.className = 'card quality-control-panel palette-harmonizer';
  card.innerHTML = `
    <details class="quality-accordion">
      <summary>Palette harmonizer</summary>
      <div class="quality-accordion-body palette-harmonizer-body">
        <label>Sprite folders
          <textarea id="paletteHarmonizerPaths" rows="3" placeholder="output\\hero_idle&#10;output\\hero_walk"></textarea>
        </label>
        <div class="row compact-fields">
          <label>Shared colors<input id="paletteHarmonizerColors" class="short-number" type="number" min="2" max="256" value="32" /></label>
          <button class="mini" id="fillPaletteHarmonizerPaths" type="button">Use recent</button>
        </div>
        <div class="palette-editor-panel">
          <div class="row compact-fields">
            <label>Editable palette
              <textarea id="paletteEditorColorsText" rows="2" placeholder="#112233, #445566"></textarea>
            </label>
            <button class="mini" id="applyPaletteEditorText" type="button">Apply colors</button>
          </div>
          <div class="row compact-fields">
            <label>Import palette file
              <input id="paletteEditorImportFile" type="file" accept=".gpl,.txt,.hex,.pal,.json,.ase,application/json" />
            </label>
            <button class="mini" id="importPaletteEditorText" type="button">Import file</button>
          </div>
          <div id="paletteEditorSwatches" class="palette-editor-swatches" aria-label="Editable palette swatches"></div>
          <div class="palette-hsl-picker" aria-label="HSL color wheel palette picker">
            <div id="paletteHslWheel" class="palette-hsl-wheel" data-hue="210" data-saturation="72" role="slider" aria-label="Drag to choose hue and saturation">
              <span id="paletteHslHandle" class="palette-hsl-handle"></span>
            </div>
            <div class="palette-hsl-controls">
              <label>Lightness<input id="paletteHslLightness" type="range" min="12" max="88" value="52" /></label>
              <span id="paletteHslPreview" class="palette-hsl-preview"></span>
              <code id="paletteHslValue">#000000</code>
              <button class="mini" id="paletteHslAddColor" type="button">Add wheel color</button>
            </div>
          </div>
          <small id="paletteEditorImportStatus" class="muted">Supports hex lists, GIMP GPL RGB rows, Lospec JSON, and Adobe ASE swatches.</small>
          <small class="muted">Edit swatches before locking to project; generation can reuse the saved palette lock.</small>
          <div class="palette-editor-preview">
            <canvas id="paletteEditorPreviewCanvas" width="384" height="192" aria-label="Palette quantized sprite preview"></canvas>
            <small id="paletteEditorPreviewStatus" class="muted">Add colors and select a sprite folder to preview palette quantization.</small>
          </div>
        </div>
        <label class="switch palette-lock-switch"><input type="checkbox" id="paletteHarmonizerLockProject" /><span></span>Lock this palette to the active project</label>
        <button class="mini primary quality-full-action" id="runPaletteHarmonizer" type="button">Run palette harmonizer</button>
        <div id="paletteHarmonizerResult" class="palette-harmonizer-result empty compact">No palette report yet.</div>
      </div>
    </details>
  `;
  form.insertAdjacentElement('afterend', card);
  $('#runPaletteHarmonizer')?.addEventListener('click', runPaletteHarmonizer);
  $('#fillPaletteHarmonizerPaths')?.addEventListener('click', () => {
    const paths = paletteCandidatePaths();
    const pathsInput = $('#paletteHarmonizerPaths');
    if (pathsInput) pathsInput.value = paths.join('\n');
    refreshPaletteQuantizedPreview();
  });
  $('#applyPaletteEditorText')?.addEventListener('click', () => {
    const colors = setPaletteEditorColors(getPaletteEditorColors());
    toast(colors.length ? 'Palette editor updated.' : 'No valid hex colors found.');
  });
  $('#paletteEditorColorsText')?.addEventListener('change', () => {
    setPaletteEditorColors(getPaletteEditorColors());
  });
  $('#paletteHarmonizerPaths')?.addEventListener('change', refreshPaletteQuantizedPreview);
  $('#importPaletteEditorText')?.addEventListener('click', async () => {
    const file = $('#paletteEditorImportFile')?.files?.[0];
    if (!file) {
      toast('Choose a palette file first.');
      return;
    }
    const colors = await importPaletteEditorFile(file);
    toast(colors.length ? `Imported ${colors.length} palette colors.` : 'No importable colors found.');
  });
  installPaletteHslWheel();
}

installPaletteHarmonizer();
