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

function primaryShortcutViews() {
  const views = $$('.rail nav .nav')
    .map(button => button.dataset.view)
    .filter(Boolean);
  return views.length ? views.slice(0, 9) : ['guide', 'dashboard', 'tasks', 'generate', 'convert', 'quality', 'animation_player', 'compare_player', 'lighting_preview'];
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

function runExportShortcut() {
  const view = activeViewName();
  if (view === 'animation_player' && clickIfPresent('#animationExportWebmBtn')) return;
  if (view === 'quality' && clickIfPresent('[data-quality="godot"]')) return;
  if (view === 'release' && submitForm('#releaseForm')) return;
  showView('release');
  toast('Opened Release for export packaging.');
}

function runSaveShortcut() {
  const view = activeViewName();
  if (view === 'quality' && clickIfPresent('#saveSpriteMetadataBtn')) return;
  if (view === 'qa_dashboard' && submitForm('#projectConfigForm')) return;
  if (view === 'generate' && clickIfPresent('#savePresetBtn')) return;
  toast('Nothing to save in this view.');
}

function moveFrame(delta) {
  const scrub = activeViewName() === 'animation_player' ? $('#animationFrameScrubber') : $('#frameScrubber');
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
  if (activeViewName() === 'animation_player') return clickIfPresent('#animationPlayBtn');
  if (activeViewName() !== 'quality') return false;
  return clickIfPresent('#inspectPlayBtn');
}

function toggleShortcutHelp(force) {
  const panel = $('#shortcutCheatSheet');
  if (!panel) return false;
  const shouldShow = force === undefined ? panel.classList.contains('hidden') : Boolean(force);
  panel.classList.toggle('hidden', !shouldShow);
  if (shouldShow) {
    const close = panel.querySelector('[data-shortcut-help-close]');
    if (close) close.focus();
  }
  return true;
}

function handleShortcut(event) {
  const key = String(event.key || '').toLowerCase();

  if (key === 'escape') {
    if (typeof closeResultPreview === 'function') closeResultPreview();
    const drawer = $('#notificationDrawer');
    if (drawer?.getAttribute('aria-hidden') === 'false') {
      if (typeof window.setNotificationDrawer === 'function') window.setNotificationDrawer(false);
      else drawer.classList.remove('show');
    }
    if (typeof CommandPalette !== 'undefined' && typeof CommandPalette.close === 'function') {
      CommandPalette.close();
    }
    toggleShortcutHelp(false);
    // Close help panel on Escape too
    const helpPanel = document.getElementById('viewHelpPanel');
    if (helpPanel && helpPanel.classList.contains('visible')) {
      if (typeof UxEnhancements !== 'undefined') UxEnhancements.toggleHelpPanel();
    }
  }
  // F1 toggles contextual help panel (Improvement 17)
  if (key === 'f1') {
    event.preventDefault();
    if (typeof UxEnhancements !== 'undefined') UxEnhancements.toggleHelpPanel();
    return;
  }
  // Alt+ArrowLeft for back navigation (Improvement 4)
  if (event.altKey && key === 'arrowleft') {
    event.preventDefault();
    if (typeof UxEnhancements !== 'undefined') UxEnhancements.goBack();
    return;
  }
  if (event.altKey && key >= '1' && key <= '9') {
    event.preventDefault();
    const tabViews = primaryShortcutViews();
    const idx = parseInt(key) - 1;
    if (idx < tabViews.length) {
      if (typeof showView === 'function') showView(tabViews[idx]);
      if (typeof toast === 'function') toast(`Switched to ${tabViews[idx].toUpperCase()}`);
    }
    return;
  }

  if (shortcutTargetAllowsTyping(event.target)) return;
  if (key === '?' || (event.shiftKey && key === '/')) {
    event.preventDefault();
    toggleShortcutHelp();
    return;
  }
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
  if ((event.ctrlKey || event.metaKey) && key === 'e') {
    event.preventDefault();
    runExportShortcut();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 's') {
    event.preventDefault();
    runSaveShortcut();
    return;
  }
  if (key === 'arrowleft' && ['quality', 'animation_player'].includes(activeViewName())) {
    if (moveFrame(-1)) event.preventDefault();
    return;
  }
  if (key === 'arrowright' && ['quality', 'animation_player'].includes(activeViewName())) {
    if (moveFrame(1)) event.preventDefault();
    return;
  }
  if (key === ' ' && togglePreviewPlayback()) {
    event.preventDefault();
  }
}

document.addEventListener('keydown', handleShortcut);
document.addEventListener('click', event => {
  if (event.target.closest('[data-shortcut-help-close]')) toggleShortcutHelp(false);
});

window.SpriteForgeShortcuts = {
  activeViewName,
  primaryShortcutViews,
  toggleShortcutHelp,
  runExportShortcut,
  runGenerateShortcut,
  runQualityShortcut,
};
