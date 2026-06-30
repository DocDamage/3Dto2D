async function loadSeedGallery() {
  const list = $('#seedGalleryList');
  if (!list) return;
  clearNode(list);
  try {
    const data = await api('/api/seeds/gallery' + projectQuery());
    const seeds = data.seeds || [];
    if (!seeds.length) {
      appendText(list, 'div', 'No pinned seeds yet. Generate with fixed seeds to build this gallery.', 'empty compact');
      return;
    }
    seeds.forEach(seed => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'seed-card';
      card.dataset.seed = seed.seed;
      const example = (seed.examples || []).find(x => x.preview_url) || (seed.examples || [])[0] || {};
      if (example.preview_url) {
        const img = document.createElement('img');
        img.src = example.preview_url + '?t=' + Date.now();
        img.alt = `Seed ${seed.seed}`;
        card.appendChild(img);
      }
      const body = document.createElement('span');
      body.className = 'seed-card-body';
      appendText(body, 'b', `Seed ${seed.seed}`);
      const score = seed.best_score === null || seed.best_score === undefined ? 'no QA' : `best ${Number(seed.best_score).toFixed(1)}`;
      appendText(body, 'small', `${seed.uses} use${seed.uses === 1 ? '' : 's'} · ${score}`);
      appendText(body, 'small', [example.action, example.direction, example.profile].filter(Boolean).join(' · ') || 'generation settings');
      card.appendChild(body);
      list.appendChild(card);
    });
  } catch (err) {
    appendText(list, 'div', 'Seed gallery unavailable.', 'empty compact');
    console.warn(err);
  }
}

function installSeedGallery() {
  const form = $('#generateForm');
  if (!form || $('#seedGalleryCard')) return;
  const seedInput = form.querySelector('[name="seed"]');
  const anchor = seedInput ? seedInput.closest('.row') : form.querySelector('.prompt-builder');
  const card = document.createElement('section');
  card.id = 'seedGalleryCard';
  card.className = 'seed-gallery';
  card.innerHTML = `
    <div class="card-head">
      <div><p class="eyebrow">Seed Gallery</p><h3>Reuse proven seeds</h3></div>
      <button class="mini" id="refreshSeedGallery" type="button">Refresh</button>
    </div>
    <div id="seedGalleryList" class="seed-gallery-list"></div>
  `;
  if (anchor) anchor.insertAdjacentElement('afterend', card);
  else form.prepend(card);
  $('#refreshSeedGallery')?.addEventListener('click', loadSeedGallery);
  $('#seedGalleryList')?.addEventListener('click', e => {
    const btn = e.target.closest('.seed-card');
    if (!btn || !seedInput) return;
    seedInput.value = btn.dataset.seed || '';
    toast(`Seed ${seedInput.value} loaded.`);
  });
  loadSeedGallery();
}

installSeedGallery();
