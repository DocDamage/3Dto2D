(function () {
  function fmtSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function tagHtml(tags) {
    return (tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join('');
  }

  function renderMarketplace(entries) {
    const list = $('#marketplaceList');
    if (!list) return;
    if (!entries || entries.length === 0) {
      list.innerHTML = '<div class="empty compact">No shared bundles found yet.</div>';
      return;
    }
    list.innerHTML = entries.map((entry) => {
      const preview = entry.preview_url
        ? `<img src="${escapeHtml(entry.preview_url)}" alt="" loading="lazy" />`
        : '<div class="marketplace-preview-empty">SF</div>';
      const meta = [entry.author, entry.license, fmtSize(entry.size_bytes)].filter(Boolean).join(' · ');
      const sourceClass = entry.source === 'local' ? 'local' : 'index';
      return `
        <article class="marketplace-item">
          <div class="marketplace-preview">${preview}</div>
          <div class="marketplace-body">
            <div class="marketplace-title-row">
              <h4>${escapeHtml(entry.title)}</h4>
              <span class="marketplace-source ${sourceClass}">${escapeHtml(entry.source || 'index')}</span>
            </div>
            <p class="marketplace-meta">${escapeHtml(meta)}</p>
            <p class="marketplace-description">${escapeHtml(entry.description || 'SpriteForge bundle')}</p>
            <div class="marketplace-tags">${tagHtml(entry.tags)}</div>
            <div class="marketplace-actions">
              <a class="mini link-button" href="${escapeHtml(entry.bundle_url)}" download>Download</a>
              ${entry.bundle_path ? `<button class="mini ghost" type="button" data-market-bundle="${escapeHtml(entry.bundle_path)}">Copy path</button>` : ''}
            </div>
          </div>
        </article>
      `;
    }).join('');
  }

  async function loadMarketplace() {
    const list = $('#marketplaceList');
    if (!list) return;
    list.innerHTML = '<div class="empty compact">Loading shared bundles...</div>';
    try {
      const data = await api('/api/marketplace/gallery');
      renderMarketplace(data.entries || []);
    } catch (err) {
      list.innerHTML = `<div class="empty compact">Marketplace unavailable: ${escapeHtml(err.message)}</div>`;
    }
  }

  function bindMarketplace() {
    const refresh = $('#refreshMarketplace');
    if (refresh && !refresh.dataset.bound) {
      refresh.dataset.bound = '1';
      refresh.addEventListener('click', loadMarketplace);
    }
    const list = $('#marketplaceList');
    if (list && !list.dataset.bound) {
      list.dataset.bound = '1';
      list.addEventListener('click', async (event) => {
        const btn = event.target.closest('[data-market-bundle]');
        if (!btn) return;
        const value = btn.dataset.marketBundle || '';
        try {
          await navigator.clipboard.writeText(value);
          toast('Bundle path copied');
        } catch {
          toast(value);
        }
      });
      loadMarketplace();
    }
  }

  window.viewComponentsLoaded.then(bindMarketplace);
  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-view="release"]')) setTimeout(bindMarketplace, 0);
  });
})();
