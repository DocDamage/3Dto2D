function shortcutTargetAllowsTyping(target) {
  if (!target) return false;
  const tag = (target.tagName || '').toLowerCase();
  return target.isContentEditable || ['input', 'textarea', 'select'].includes(tag);
}

function clickIfPresent(selector) {
  const el = $(selector);
  if (!el || el.disabled) return false;
  el.click();
  return true;
}

function activeViewName() {
  const view = $('.view.active');
  return view ? String(view.id || '').replace(/^view-/, '') : '';
}

function submitForm(selector) {
  const form = $(selector);
  if (!form) return false;
  if (typeof form.requestSubmit === 'function') form.requestSubmit();
  else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  return true;
}

function runGenerateShortcut() {
  showView('generate');
  if (!submitForm('#generateForm')) {
    toast('Generate form unavailable.');
  }
}

function runQualityShortcut() {
  if (activeViewName() !== 'quality') showView('quality');
  if (!clickIfPresent('[data-quality="qa"]')) {
    toast('Quality controls unavailable.');
  }
}

function runSaveShortcut() {
  const view = activeViewName();
  if (view === 'quality' && clickIfPresent('#saveSpriteMetadataBtn')) return;
  if (view === 'qa_dashboard' && submitForm('#projectConfigForm')) return;
  if (view === 'generate' && clickIfPresent('#savePresetBtn')) return;
  toast('Nothing to save in this view.');
}

function moveFrame(delta) {
  const scrub = $('#frameScrubber');
  if (!scrub || scrub.disabled) return false;
  const min = Number(scrub.min || 0);
  const max = Number(scrub.max || 0);
  const current = Number(scrub.value || 0);
  const next = Math.max(min, Math.min(max, current + delta));
  if (next === current) return false;
  scrub.value = String(next);
  scrub.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
}

function togglePreviewPlayback() {
  if (activeViewName() !== 'quality') return false;
  return clickIfPresent('#inspectPlayBtn');
}

function handleShortcut(event) {
  if (shortcutTargetAllowsTyping(event.target)) return;
  const key = String(event.key || '').toLowerCase();
  if ((event.ctrlKey || event.metaKey) && key === 'g') {
    event.preventDefault();
    runGenerateShortcut();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 'q') {
    event.preventDefault();
    runQualityShortcut();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 's') {
    event.preventDefault();
    runSaveShortcut();
    return;
  }
  if (key === 'arrowleft' && activeViewName() === 'quality') {
    if (moveFrame(-1)) event.preventDefault();
    return;
  }
  if (key === 'arrowright' && activeViewName() === 'quality') {
    if (moveFrame(1)) event.preventDefault();
    return;
  }
  if (key === ' ' && togglePreviewPlayback()) {
    event.preventDefault();
  }
}

document.addEventListener('keydown', handleShortcut);
