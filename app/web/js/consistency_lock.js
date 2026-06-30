(function () {
  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function activeProjectPath() {
    const select = $('#projectSelect');
    return select ? select.value : '';
  }

  function ensurePanel() {
    const referenceInput = $('#generationReferenceImage');
    if (!referenceInput || $('#consistencyLockPanel')) return;
    const panel = document.createElement('section');
    panel.className = 'consistency-lock-panel';
    panel.id = 'consistencyLockPanel';
    panel.innerHTML = `
      <h4>Character consistency lock</h4>
      <div class="row">
        <label>Mode
          <select id="consistencyLockMode">
            <option value="ip_adapter">IP-Adapter</option>
            <option value="controlnet">ControlNet</option>
            <option value="reference_only">Reference only</option>
          </select>
        </label>
        <label>Strength
          <input id="consistencyLockStrength" type="number" min="0" max="1" step="0.05" value="0.75" />
        </label>
      </div>
      <div class="button-row form-actions-tight">
        <button class="ghost" id="consistencyLockApply" type="button">Save lock</button>
      </div>
      <span class="consistency-lock-status" id="consistencyLockStatus">Uses the reference image field above for all generated actions.</span>
    `;
    referenceInput.closest('label').insertAdjacentElement('afterend', panel);
    $('#consistencyLockApply', panel).addEventListener('click', saveLock);
  }

  async function saveLock() {
    const referenceInput = $('#generationReferenceImage');
    const status = $('#consistencyLockStatus');
    const characterInput = document.querySelector('input[name="character"]');
    const payload = {
      name: characterInput ? characterInput.value : 'character_lock',
      reference_image: referenceInput ? referenceInput.value : '',
      mode: $('#consistencyLockMode')?.value || 'ip_adapter',
      strength: $('#consistencyLockStrength')?.value || '0.75',
      active_project: activeProjectPath()
    };
    if (status) status.textContent = 'Saving consistency lock...';
    try {
      const data = await api('/api/consistency_lock/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!data.ok) throw new Error(data.message || 'Unable to save consistency lock.');
      if (referenceInput) referenceInput.value = data.reference_image || data.lock.reference_image;
      if (status) status.textContent = 'Locked: reference image will be reused across generated actions.';
    } catch (err) {
      if (status) status.textContent = err.message || String(err);
    }
  }

  window.viewComponentsLoaded?.then(ensurePanel);
})();
