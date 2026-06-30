function paletteCandidatePaths() {
  const paths = [];
  if (window.selectedSpriteDir) paths.push(window.selectedSpriteDir);
  (window.currentOutputs || []).forEach(item => {
    if (item && item.path) paths.push(item.path);
  });
  return Array.from(new Set(paths)).slice(0, 8);
}

function renderPaletteReport(report) {
  const target = $('#paletteHarmonizerResult');
  if (!target) return;
  clearNode(target);
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
    toast('Palette harmonization complete.');
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
  card.className = 'palette-harmonizer';
  card.innerHTML = `
    <div class="card-head">
      <div><p class="eyebrow">Batch Palette</p><h3>Harmonize sprite sheets</h3></div>
      <button class="mini primary" id="runPaletteHarmonizer" type="button">Run</button>
    </div>
    <label>Sprite folders
      <textarea id="paletteHarmonizerPaths" rows="4" placeholder="output\\hero_idle&#10;output\\hero_walk"></textarea>
    </label>
    <div class="row">
      <label>Shared colors<input id="paletteHarmonizerColors" class="short-number" type="number" min="2" max="256" value="32" /></label>
      <button class="mini" id="fillPaletteHarmonizerPaths" type="button">Use recent</button>
    </div>
    <div id="paletteHarmonizerResult" class="palette-harmonizer-result empty compact">No palette report yet.</div>
  `;
  form.insertAdjacentElement('afterend', card);
  $('#runPaletteHarmonizer')?.addEventListener('click', runPaletteHarmonizer);
  $('#fillPaletteHarmonizerPaths')?.addEventListener('click', () => {
    const paths = paletteCandidatePaths();
    const pathsInput = $('#paletteHarmonizerPaths');
    if (pathsInput) pathsInput.value = paths.join('\n');
  });
}

installPaletteHarmonizer();
