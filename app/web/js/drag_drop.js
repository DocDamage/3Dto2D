async function uploadDroppedFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('active_project', activeProjectPath || '');
  const response = await fetch('/api/upload', { method: 'POST', body: fd });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.message || 'Upload failed');
  return data;
}

function setInputValue(input, value) {
  if (!input) return;
  input.value = value;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
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
  const card = document.createElement('label');
  card.className = 'drop-target-card';
  card.id = id;
  card.innerHTML = `<input type="file" accept="${accept}" /><span>${label}</span>`;
  const fileInput = card.querySelector('input');
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

function installQualityDrops() {
  const input = $('#qualitySpriteDir');
  if (!input || $('#qualityDropTarget')) return;
  const card = makeDropCard('qualityDropTarget', 'Sprite folder or reference', input, 'image/*,video/*');
  input.closest('label')?.insertAdjacentElement('afterend', card);
}

function installDragDropEverywhere() {
  installGenerateDrops();
  installQualityDrops();
}

installDragDropEverywhere();
