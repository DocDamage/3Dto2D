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
    window.marketplaceEntries = entries || [];
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
              <button class="mini ghost" type="button" data-market-import="${escapeHtml(entry.id)}">Import</button>
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

  async function importMarketplaceEntry(id) {
    const entry = (window.marketplaceEntries || []).find((item) => item.id === id);
    if (!entry) return toast('Marketplace entry not found');
    const data = await api('/api/marketplace/import', { method: 'POST', body: JSON.stringify({ entry }) });
    toast(data.message || (data.ok ? 'Bundle imported' : 'Bundle could not be imported'));
  }

  async function buildMarketplaceShareManifest() {
    const bundlePaths = (window.marketplaceEntries || [])
      .filter((entry) => entry.bundle_path)
      .map((entry) => entry.bundle_path);
    const data = await api('/api/marketplace/share-manifest', {
      method: 'POST',
      body: JSON.stringify({ bundle_paths: bundlePaths, author: 'Local workspace' }),
    });
    const target = $('#marketplaceShareResult');
    if (target) {
      target.classList.remove('hidden');
      target.value = JSON.stringify(data, null, 2);
      target.select();
    }
    toast(`Share manifest prepared for ${Number(data.entry_count || 0)} bundle(s)`);
  }

  async function loadPluginSdkStarter() {
    const id = ($('#pluginSdkId')?.value || 'my_plugin').trim() || 'my_plugin';
    const summary = $('#pluginSdkSummary');
    const scaffold = $('#pluginSdkScaffold');
    if (summary) summary.textContent = 'Loading plugin SDK starter...';
    const data = await api('/api/plugins/sdk?id=' + encodeURIComponent(id));
    const contract = data.contract || {};
    const starter = data.scaffold || {};
    const hooks = (contract.known_hooks || []).join(', ') || 'none';
    if (summary) {
      summary.innerHTML = `
        <b>SDK ${escapeHtml(contract.sdk_version || 'unknown')}</b>
        <small>Known hooks: ${escapeHtml(hooks)}</small>
        <small>Compatibility: ${escapeHtml(contract.compatibility_rule || 'Match the host SDK major version.')}</small>
      `;
    }
    if (scaffold) {
      scaffold.classList.remove('hidden');
      scaffold.value = JSON.stringify({
        manifest: starter.manifest || {},
        files: starter.files || {},
      }, null, 2);
      scaffold.select();
    }
    toast('Plugin SDK starter loaded.');
  }

  function bindMarketplace() {
    const refresh = $('#refreshMarketplace');
    if (refresh && !refresh.dataset.bound) {
      refresh.dataset.bound = '1';
      refresh.addEventListener('click', loadMarketplace);
    }
    const share = $('#marketplaceShareManifest');
    if (share && !share.dataset.bound) {
      share.dataset.bound = '1';
      share.addEventListener('click', () => buildMarketplaceShareManifest().catch((err) => toast(err.message)));
    }
    const list = $('#marketplaceList');
    if (list && !list.dataset.bound) {
      list.dataset.bound = '1';
      list.addEventListener('click', async (event) => {
        const importBtn = event.target.closest('[data-market-import]');
        if (importBtn) {
          await importMarketplaceEntry(importBtn.dataset.marketImport || '');
          return;
        }
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
    const sdk = $('#loadPluginSdkStarter');
    if (sdk && !sdk.dataset.bound) {
      sdk.dataset.bound = '1';
      sdk.addEventListener('click', () => loadPluginSdkStarter().catch((err) => toast(err.message)));
    }
  }

  window.viewComponentsLoaded.then(bindMarketplace);
  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-view="release"]')) setTimeout(bindMarketplace, 0);
  });
})();
