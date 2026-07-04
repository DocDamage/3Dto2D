async function uploadDroppedFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('active_project', activeProjectPath || '');
  const data = await api('/api/upload', { method: 'POST', body: fd });
  if (!data.ok) throw new Error(data.message || 'Upload failed');
  return data;
}

function setInputValue(input, value) {
  if (!input) return;
  input.value = value;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  if ((input.id === 'generationReferenceImage' || input.id === 'generationStyleImage') && typeof refreshGenerateReferencePreview === 'function') {
    refreshGenerateReferencePreview();
  }
  if (input.id === 'existingSpriteSource') {
    const generateRef = $('#generationReferenceImage');
    if (generateRef && !generateRef.value && typeof refreshGenerateReferencePreview === 'function') {
      generateRef.value = value;
      refreshGenerateReferencePreview();
    }
  }
}

function droppedText(event) {
  return (event.dataTransfer?.getData('text/plain') || '').trim();
}

function bindDropTarget(target, onDrop) {
  if (!target) return;
  ['dragenter', 'dragover'].forEach(name => {
    target.addEventListener(name, event => {
      event.preventDefault();
      target.classList.add('drag-active');
    });
  });
  ['dragleave', 'drop'].forEach(name => {
    target.addEventListener(name, event => {
      event.preventDefault();
      target.classList.remove('drag-active');
    });
  });
  target.addEventListener('drop', event => onDrop(event).catch(err => toast(err.message)));
}

function makeDropCard(id, label, input, accept) {
  const card = document.createElement('div');
  card.className = 'drop-target-card';
  card.id = id;
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.setAttribute('aria-label', `${label}: choose or drop an image`);
  card.innerHTML = `
    <input type="file" accept="${accept}" />
    <span>${label}</span>
    <button class="mini drop-target-button" type="button">Choose image</button>
    <small>or drag and drop here. Preview updates after upload.</small>
  `;
  const fileInput = card.querySelector('input');
  const button = card.querySelector('button');
  button.addEventListener('click', () => fileInput.click());
  card.addEventListener('click', event => {
    if (event.target === card || event.target.tagName === 'SPAN' || event.target.tagName === 'SMALL') {
      fileInput.click();
    }
  });
  card.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener('change', async () => {
    try {
      const file = fileInput.files?.[0];
      if (!file) return;
      const data = await uploadDroppedFile(file);
      setInputValue(input, data.relative || data.path);
      toast('Uploaded: ' + data.name);
    } catch (err) {
      toast(err.message || 'Upload failed');
    }
  });
  bindDropTarget(card, async event => {
    const file = event.dataTransfer?.files?.[0];
    const text = droppedText(event);
    if (file) {
      const data = await uploadDroppedFile(file);
      setInputValue(input, data.relative || data.path);
      toast('Uploaded: ' + data.name);
    } else if (text) {
      setInputValue(input, text);
      toast('Path loaded.');
    }
  });
  return card;
}

function installGenerateDrops() {
  const refInput = $('#generationReferenceImage');
  const styleInput = $('#generationStyleImage');
  if (!refInput || !styleInput || $('#generateDropTargets')) return;
  const row = document.createElement('div');
  row.id = 'generateDropTargets';
  row.className = 'drop-target-row';
  row.appendChild(makeDropCard('referenceDropTarget', 'Reference image', refInput, 'image/*'));
  row.appendChild(makeDropCard('styleDropTarget', 'Style image', styleInput, 'image/*'));
  styleInput.closest('label')?.insertAdjacentElement('afterend', row);
}

function installWizardDrops() {
  const refInput = $('#wizReferenceImage');
  const styleInput = $('#wizStyleImage');
  if (!refInput || !styleInput || $('#wizardDropTargets')) return;
  const row = document.createElement('div');
  row.id = 'wizardDropTargets';
  row.className = 'drop-target-row wizard-drop-target-row';
  row.appendChild(makeDropCard('wizardReferenceDropTarget', 'Character reference image', refInput, 'image/*'));
  row.appendChild(makeDropCard('wizardStyleDropTarget', 'Style reference image', styleInput, 'image/*'));
  styleInput.closest('label')?.insertAdjacentElement('afterend', row);
}

function installExistingSpriteDrop() {
  const sourceInput = $('#existingSpriteSource');
  if (!sourceInput || $('#existingSpriteDropTarget')) return;
  const card = makeDropCard('existingSpriteDropTarget', 'Source sprite image', sourceInput, 'image/*');
  sourceInput.closest('label')?.insertAdjacentElement('afterend', card);
}

function installQualityDrops() {
  const input = $('#qualitySpriteDir');
  if (!input || $('#qualityDropTarget')) return;
  const card = makeDropCard('qualityDropTarget', 'Sprite folder or reference', input, 'image/*,video/*');
  input.closest('label')?.insertAdjacentElement('afterend', card);
}

function installDragDropEverywhere() {
  installGenerateDrops();
  installWizardDrops();
  installExistingSpriteDrop();
  installQualityDrops();
}

window.installDragDropEverywhere = installDragDropEverywhere;
window.installWizardDrops = installWizardDrops;
installDragDropEverywhere();
