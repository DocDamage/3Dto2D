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

function initAppViews() {
  // Bind Mode buttons click
  $$('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      if (mode) setUiMode(mode);
    });
  });

  // Navigate to hash-routed view, or fall back to 'guide'
  const hashView = location.hash.replace('#', '') || 'guide';
  showView(hashView);

  initAccessibilityPreferences();
  const savedMode = localStorage.getItem('uiMode') || 'simple';
  setUiMode(savedMode);
}

if (window.onSpriteForgeReady) {
  window.onSpriteForgeReady(initAppViews);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAppViews, { once: true });
} else {
  initAppViews();
}
