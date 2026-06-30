(function () {
  const MAX_HISTORY = 40;
  let undoStack = [];
  let redoStack = [];

  function cloneMeta() {
    return window._currentMeta ? JSON.stringify(window._currentMeta) : '';
  }

  function restoreEditorState() {
    const meta = window._currentMeta;
    const scrub = $('#frameScrubber');
    if (!scrub || !meta) return;
    scrub.max = Math.max(0, (meta.frame_count || 1) - 1);
    const val = Math.min(parseInt(scrub.value, 10) || 0, parseInt(scrub.max, 10) || 0);
    scrub.value = val;
    if (typeof renderInspectorFrame === 'function') renderInspectorFrame(val);
  }

  function updateButtons() {
    const undoBtn = $('#inspectUndoBtn');
    const redoBtn = $('#inspectRedoBtn');
    if (undoBtn) undoBtn.disabled = undoStack.length === 0;
    if (redoBtn) redoBtn.disabled = redoStack.length === 0;
  }

  function save() {
    const state = cloneMeta();
    if (!state) return;
    if (undoStack[undoStack.length - 1] === state) return;
    undoStack.push(state);
    if (undoStack.length > MAX_HISTORY) undoStack.shift();
    redoStack = [];
    updateButtons();
  }

  function undo() {
    if (!undoStack.length || !window._currentMeta) return;
    redoStack.push(cloneMeta());
    window._currentMeta = JSON.parse(undoStack.pop());
    restoreEditorState();
    updateButtons();
    toast('Undo performed');
  }

  function redo() {
    if (!redoStack.length || !window._currentMeta) return;
    undoStack.push(cloneMeta());
    if (undoStack.length > MAX_HISTORY) undoStack.shift();
    window._currentMeta = JSON.parse(redoStack.pop());
    restoreEditorState();
    updateButtons();
    toast('Redo performed');
  }

  function reset() {
    undoStack = [];
    redoStack = [];
    updateButtons();
  }

  function bind() {
    const undoBtn = $('#inspectUndoBtn');
    const redoBtn = $('#inspectRedoBtn');
    if (undoBtn && !undoBtn.dataset.historyBound) {
      undoBtn.dataset.historyBound = '1';
      undoBtn.addEventListener('click', undo);
    }
    if (redoBtn && !redoBtn.dataset.historyBound) {
      redoBtn.dataset.historyBound = '1';
      redoBtn.addEventListener('click', redo);
    }
    updateButtons();
  }

  function wrapSpriteLoad() {
    if (window._editorHistoryLoadWrapped || typeof loadSpriteDetails !== 'function') return;
    window._editorHistoryLoadWrapped = true;
    const baseLoadSpriteDetails = loadSpriteDetails;
    loadSpriteDetails = async function editorHistoryLoad(path) {
      const result = await baseLoadSpriteDetails(path);
      reset();
      return result;
    };
  }

  document.addEventListener('keydown', (event) => {
    const key = event.key.toLowerCase();
    const modifier = event.ctrlKey || event.metaKey;
    if (!modifier || event.shiftKey) return;
    if (key === 'z') {
      event.preventDefault();
      undo();
    } else if (key === 'y') {
      event.preventDefault();
      redo();
    }
  });

  window.SpriteForgeEditorHistory = {
    save,
    undo,
    redo,
    reset,
    bind,
    updateButtons,
    maxHistory: MAX_HISTORY,
  };

  wrapSpriteLoad();
  window.viewComponentsLoaded.then(() => {
    bind();
    wrapSpriteLoad();
  });
})();
