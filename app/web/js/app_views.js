// Interface Density Mode Toggle
function setUiMode(mode) {
  document.body.classList.remove('mode-simple', 'mode-detailed', 'mode-expert');
  document.body.classList.add('mode-' + mode);
  $$('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  localStorage.setItem('uiMode', mode);
}

// Accessibility Preferences Panel
const PREF_ITEMS = [
  { id: 'prefReduceMotion', className: 'pref-reduce-motion' },
  { id: 'prefHighContrast', className: 'pref-high-contrast' },
  { id: 'prefCompact', className: 'pref-compact' },
  { id: 'prefLargeText', className: 'pref-large-text' },
  { id: 'prefAlwaysShowLogs', className: '' },
  { id: 'prefNeverAutoSwitch', className: '' },
  { id: 'prefConfirmLongJobs', className: '' }
];

function initAccessibilityPreferences() {
  PREF_ITEMS.forEach(item => {
    const el = $('#' + item.id);
    if (!el) return;
    const val = localStorage.getItem(item.id) === 'true';
    el.checked = val;
    if (item.className) {
      document.body.classList.toggle(item.className, val);
    }
    el.addEventListener('change', e => {
      const checked = e.target.checked;
      localStorage.setItem(item.id, checked ? 'true' : 'false');
      if (item.className) {
        document.body.classList.toggle(item.className, checked);
      }
      if (item.id === 'prefAlwaysShowLogs') {
        const activeNav = $('.nav.active');
        const activeView = activeNav ? activeNav.dataset.view : 'launchpad';
        showView(activeView);
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // Bind Mode buttons click
  $$('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      if (mode) setUiMode(mode);
    });
  });

  // Step Map Navigation
  $$('.step-map-item').forEach(item => {
    item.addEventListener('click', () => {
      const view = item.dataset.view;
      if (view) {
        showView(view);
      }
    });
  });

  // Restore active view (Continue where I left off) & load state
  const savedView = localStorage.getItem('activeView') || 'guide';
  showView(savedView);
  
  initAccessibilityPreferences();
  const savedMode = localStorage.getItem('uiMode') || 'simple';
  setUiMode(savedMode);
});

// Keyboard / Accessibility Event Listener
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeResultPreview();
    const drawer = $('#notificationDrawer');
    if (drawer) drawer.classList.remove('show');
  }
  if (e.altKey && e.key >= '1' && e.key <= '9') {
    e.preventDefault();
    const tabViews = ['guide', 'dashboard', 'tasks', 'launchpad', 'generate', 'convert', 'quality', 'packs', 'setup'];
    const idx = parseInt(e.key) - 1;
    if (idx < tabViews.length) {
      showView(tabViews[idx]);
      toast(`Switched to ${tabViews[idx].toUpperCase()}`);
    }
  }
  if (e.key === ' ' && $('#view-quality').classList.contains('active')) {
    const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') {
      e.preventDefault();
      if (typeof togglePlayback === 'function') togglePlayback();
    }
  }
  if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && $('#view-quality').classList.contains('active')) {
    const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') {
      e.preventDefault();
      const scrub = $('#frameScrubber');
      const meta = window._currentMeta;
      if (scrub && meta && meta.frame_count) {
        let val = parseInt(scrub.value);
        if (e.key === 'ArrowLeft') {
          val = (val - 1 + meta.frame_count) % meta.frame_count;
        } else {
          val = (val + 1) % meta.frame_count;
        }
        scrub.value = val;
        if (typeof renderInspectorFrame === 'function') renderInspectorFrame(val);
      }
    }
  }
});
