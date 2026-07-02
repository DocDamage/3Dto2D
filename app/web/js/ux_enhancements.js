// ================================================================
// UX Enhancements Module — Streamlined
// Covers: Grouped Nav, Persistent Banners, Time Estimates,
// Structured Errors, Operation Locking, Field Hints, Smart Defaults,
// Validation, Undo, Saved Layouts
// ================================================================

(function () {
  'use strict';

  const VIEW_LABELS = {
    guide: 'Guide', dashboard: 'Dashboard', tasks: 'Task Center',
    launchpad: 'Launchpad', generate: 'Generate Sprite', convert: 'Convert Video',
    quality: 'Quality Lab', ab_runs: 'A/B Runs', library: 'Pose Library',
    qa_dashboard: 'QA Dashboard', packs: 'Packs & Atlas', queue: 'Queue Builder',
    queues: 'Queue Monitor', history: 'History', release: 'Release',
    cleanup: 'Cleanup Manager', setup: 'Setup', logs: 'Logs'
  };

  // ------------------------------------------------------------------
  // 1. Grouped Navigation
  // ------------------------------------------------------------------
  const NAV_ICONS = {
    guide: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`,
    generate: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="m19 2 4 4L7 22H3v-4z"/><path d="M14 7l4 4"/></svg>`,
    convert: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M23 7a2 2 0 0 0-2.45-1.45L16 7V5a2 2 0 0 0-2-2H2a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2l4.55 1.45A2 2 0 0 0 23 17z"/></svg>`,
    queue: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`,
    quality: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    ab_runs: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22V2"/><path d="m21 3-7.5 7.5"/><path d="m3 3 7.5 7.5"/></svg>`,
    qa_dashboard: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    library: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
    dashboard: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>`,
    tasks: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
    launchpad: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M4.5 16.5c-1.5 1.26-2 3.42-2 3.42s2.16-.5 3.42-2c1.24-1.46 1.77-3.9 1.77-3.9s-2.44.53-3.9 1.77z"/><path d="M12 12c-2-2-5.5-2.5-5.5-2.5s.5 3.5 2.5 5.5c2 2 5.5 2.5 5.5 2.5s-.5-3.5-2.5-5.5z"/><path d="M19 5c-3 0-8.5 4.5-8.5 4.5s4 4 8.5 8.5c0 0 4.5-5.5 4.5-8.5 0-3-1.5-4.5-4.5-4.5z"/></svg>`,
    packs: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><polygon points="12 22.08 12 12 3 6.92 3 17.08 12 22.08"/><polygon points="12 12 21 6.92 21 17.08 12 22.08"/><polygon points="12 2 21 6.92 12 11.85 3 6.92 12 2"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
    queues: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
    history: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    release: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 13 7 8"/><line x1="12" y1="13" x2="12" y2="3"/></svg>`,
    cleanup: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`,
    setup: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2 2v.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
    logs: `<svg class="nav-icon icon-svg" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`
  };

  const NAV_GROUPS = [
    { name: 'Create', views: ['guide', 'generate', 'convert'] },
    { name: 'Review', views: ['quality'] },
    { name: 'Manage', views: ['dashboard', 'tasks', 'packs', 'history', 'release', 'cleanup'] },
    { name: 'System', views: ['setup', 'logs'] }
  ];

  function buildGroupedNav() {
    const railNav = document.querySelector('.rail nav');
    if (!railNav) return;

    const existingBtns = {};
    railNav.querySelectorAll('.nav[data-view]').forEach(btn => {
      existingBtns[btn.dataset.view] = btn;
    });

    while (railNav.firstChild) railNav.removeChild(railNav.firstChild);

    // Prepend prominent Create New Sprite button
    const createBtn = document.createElement('button');
    createBtn.className = 'nav-create-sprite-btn';
    createBtn.type = 'button';
    createBtn.innerHTML = `<svg class="icon-svg" viewBox="0 0 24 24" style="width:14px;height:14px;"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> <span class="nav-label">New Sprite</span>`;
    createBtn.addEventListener('click', () => {
      if (typeof openWizard === 'function') openWizard();
    });
    railNav.appendChild(createBtn);

    NAV_GROUPS.forEach(group => {
      const wrapper = document.createElement('div');
      wrapper.className = 'nav-group';
      wrapper.dataset.navGroup = group.name;

      const heading = document.createElement('div');
      heading.className = 'nav-group-heading';
      heading.textContent = group.name;
      wrapper.appendChild(heading);

      const items = document.createElement('div');
      items.className = 'nav-group-items';
      group.views.forEach(viewName => {
        const btn = existingBtns[viewName];
        if (btn) {
          if (!btn.querySelector('.nav-label')) {
            const label = btn.textContent;
            btn.innerHTML = `${NAV_ICONS[viewName] || ''} <span class="nav-label">${label}</span>`;
            btn.title = label;
          }
          items.appendChild(btn);
        }
      });
      wrapper.appendChild(items);
      railNav.appendChild(wrapper);
    });
  }

  function updateNavGroupActiveState(viewName) {
    const parentName = (window.SUBVIEW_PARENTS && window.SUBVIEW_PARENTS[viewName]) || viewName;
    const activeNavView = (window.NAV_VIEW_MAP && window.NAV_VIEW_MAP[parentName]) || parentName;
    document.querySelectorAll('.nav-group').forEach(g => {
      const hasActive = g.querySelector(`.nav[data-view="${activeNavView}"]`);
      g.classList.toggle('has-active', !!hasActive);
    });
  }

  // ------------------------------------------------------------------
  // 2. Persistent Action Banners
  // ------------------------------------------------------------------
  let bannerIdCounter = 0;

  function showBanner(message, type, options) {
    type = type || 'info';
    options = options || {};
    const container = document.getElementById('bannerContainer');
    if (!container) return null;

    const id = 'banner-' + (++bannerIdCounter);
    const banner = document.createElement('div');
    banner.className = 'action-banner ' + type;
    banner.id = id;

    const msg = document.createElement('span');
    msg.className = 'banner-msg';
    msg.textContent = message;
    banner.appendChild(msg);

    if (options.undoFn) {
      banner.classList.add('undo-banner');
      const countdown = document.createElement('span');
      countdown.className = 'undo-countdown';
      let remaining = options.undoTimeout || 10;
      countdown.textContent = remaining + 's';
      banner.appendChild(countdown);

      const undoBtn = document.createElement('button');
      undoBtn.className = 'undo-btn';
      undoBtn.textContent = 'Undo';
      undoBtn.type = 'button';
      banner.appendChild(undoBtn);

      const interval = setInterval(() => {
        remaining--;
        countdown.textContent = remaining + 's';
        if (remaining <= 0) {
          clearInterval(interval);
          banner.remove();
          if (options.onExpire) options.onExpire();
        }
      }, 1000);

      undoBtn.addEventListener('click', () => {
        clearInterval(interval);
        banner.remove();
        if (typeof options.undoFn === 'function') options.undoFn();
        if (typeof toast === 'function') toast('Action undone.');
      });
    } else {
      const dismiss = document.createElement('button');
      dismiss.className = 'banner-dismiss';
      dismiss.textContent = 'Dismiss';
      dismiss.type = 'button';
      dismiss.addEventListener('click', () => banner.remove());
      banner.appendChild(dismiss);

      if (options.autoDismiss) {
        setTimeout(() => { if (banner.parentNode) banner.remove(); }, options.autoDismiss);
      }
    }

    container.appendChild(banner);
    return id;
  }

  window.showBanner = showBanner;

  // ------------------------------------------------------------------
  // 3. Time Estimates on Progress
  // ------------------------------------------------------------------
  let jobStartTimestamp = null;

  function updateTimeEstimates(job) {
    const infoEl = document.getElementById('progressTimeInfo');
    if (!infoEl) return;

    if (!job || !job.running) {
      infoEl.style.display = 'none';
      jobStartTimestamp = null;
      return;
    }

    if (!jobStartTimestamp) {
      jobStartTimestamp = job.started_at ? new Date(job.started_at).getTime() : Date.now();
    }

    const elapsed = Date.now() - jobStartTimestamp;
    const progress = typeof inferredJobProgress === 'function' ? inferredJobProgress(job, true) : 0;

    infoEl.style.display = 'flex';

    const elapsedStr = formatElapsed(elapsed);
    const elapsedEl = infoEl.querySelector('.pti-elapsed');
    if (elapsedEl) elapsedEl.textContent = elapsedStr + ' elapsed';

    const remainEl = infoEl.querySelector('.pti-remaining');
    if (remainEl) {
      if (progress > 5) {
        const totalEstimate = elapsed / (progress / 100);
        const remaining = Math.max(0, totalEstimate - elapsed);
        remainEl.textContent = '~' + formatElapsed(remaining) + ' remaining';
      } else {
        remainEl.textContent = 'estimating...';
      }
    }
  }

  function formatElapsed(ms) {
    const totalSec = Math.floor(ms / 1000);
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    return min + ':' + String(sec).padStart(2, '0');
  }

  // ------------------------------------------------------------------
  // 4. Structured Error Display
  // ------------------------------------------------------------------
  function showStructuredError(what, why, steps) {
    const container = document.getElementById('bannerContainer');
    if (!container) return;

    const card = document.createElement('div');
    card.className = 'structured-error';

    const whatEl = document.createElement('div');
    whatEl.className = 'se-what';
    whatEl.textContent = what;
    card.appendChild(whatEl);

    if (why) {
      const whyEl = document.createElement('div');
      whyEl.className = 'se-why';
      whyEl.textContent = why;
      card.appendChild(whyEl);
    }

    if (steps && steps.length > 0) {
      const ol = document.createElement('ol');
      ol.className = 'se-steps';
      steps.forEach(step => {
        const li = document.createElement('li');
        li.textContent = step;
        ol.appendChild(li);
      });
      card.appendChild(ol);
    }

    const dismiss = document.createElement('button');
    dismiss.className = 'banner-dismiss';
    dismiss.textContent = 'Dismiss';
    dismiss.type = 'button';
    dismiss.style.marginTop = '8px';
    dismiss.addEventListener('click', () => card.remove());
    card.appendChild(dismiss);

    container.appendChild(card);
  }

  window.showStructuredError = showStructuredError;

  // ------------------------------------------------------------------
  // 5. Operation State Locking
  // ------------------------------------------------------------------
  const LOCKABLE_SELECTORS = [
    '#generateForm button[type="submit"]', '.primary.big',
    '#guidedRun', '#convertForm button[type="submit"]'
  ];

  function lockOperationButtons(label) {
    LOCKABLE_SELECTORS.forEach(sel => {
      document.querySelectorAll(sel).forEach(btn => {
        btn.classList.add('op-locked');
        btn.dataset.lockLabel = label || 'Running...';
        btn.dataset.originalText = btn.textContent;
      });
    });
  }

  function unlockOperationButtons() {
    document.querySelectorAll('.op-locked').forEach(btn => {
      btn.classList.remove('op-locked');
      if (btn.dataset.originalText) {
        btn.textContent = btn.dataset.originalText;
      }
      delete btn.dataset.lockLabel;
      delete btn.dataset.originalText;
    });
  }

  window.lockOperationButtons = lockOperationButtons;
  window.unlockOperationButtons = unlockOperationButtons;

  // ------------------------------------------------------------------
  // 6. Inline Field Descriptions
  // ------------------------------------------------------------------
  const FIELD_HINTS = {
    'character': 'Describe one character in full detail. Include body type, outfit, and pose references.',
    'sprite_action': 'The animation the character performs. Choose the primary action for this sprite.',
    'direction': 'Camera angle for the sprite. "right" is standard for platformers.',
    'tier': 'Hardware preset. Higher tiers produce better results but require more VRAM.',
    'profile': 'Fine-tuned settings for your GPU. "auto" detects the best match.',
    'seed': 'Fixed seed for reproducible results. Use -1 for a random seed each time.',
    'fps': 'Frames per second for the animation. 12 is standard for pixel-art sprites.',
    'cell_size': 'Pixel dimensions of each frame in the final sprite sheet.',
    'style': 'Visual style prompt injected into every generation. Affects look and feel.',
    'reference_image': 'Path to a character concept image to guide generation.',
    'resolutions': 'Export multiple scaled versions. Example: 0.5x,1x,2x for three sizes.',
    'style_image': 'IP-Adapter style reference. Generation will mimic this image\'s visual style.',
    'prompt': 'Full override of the automatic prompt. Leave empty to use the smart builder.',
    'negative': 'Terms to avoid in generation. Helps prevent common artifacts.',
    'qa_threshold_loop_rmse': 'Maximum difference between first and last frame for seamless looping.',
    'qa_threshold_foot_drift': 'Maximum vertical foot movement (pixels) before flagging drift.',
    'qa_threshold_center_drift': 'Maximum horizontal center movement (pixels) before flagging drift.'
  };

  function addFieldHints() {
    Object.entries(FIELD_HINTS).forEach(([name, hint]) => {
      const fields = document.querySelectorAll(`[name="${name}"]`);
      fields.forEach(field => {
        if (field.parentElement && field.parentElement.querySelector('.field-hint')) return;
        const span = document.createElement('span');
        span.className = 'field-hint';
        span.textContent = hint;
        field.parentElement.appendChild(span);
      });
    });
  }

  // ------------------------------------------------------------------
  // 7. Smart Default "Why?" Explanations
  // ------------------------------------------------------------------
  function addSmartDefaultHints(statusData) {
    if (!statusData) return;
    const tierField = document.querySelector('[name="tier"]');
    const profileField = document.querySelector('[name="profile"]');

    if (tierField && !tierField.parentElement.querySelector('.why-default')) {
      const gpuLabel = statusData.gpu?.label || 'your GPU';
      const vram = statusData.gpu?.memory_total || 'unknown';
      addWhyButton(tierField, `Auto-selected based on ${gpuLabel} (${vram} VRAM).`);
    }
    if (profileField && !profileField.parentElement.querySelector('.why-default')) {
      addWhyButton(profileField, 'Best profile match for your detected hardware configuration.');
    }
  }

  function addWhyButton(field, explanation) {
    const label = field.closest('label');
    if (!label) return;
    label.style.position = 'relative';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'why-default';
    btn.textContent = '?';

    const tooltip = document.createElement('div');
    tooltip.className = 'why-tooltip';
    tooltip.textContent = explanation;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      tooltip.classList.toggle('visible');
    });
    document.addEventListener('click', () => tooltip.classList.remove('visible'));

    const labelText = label.childNodes[0];
    if (labelText && labelText.nodeType === 3) {
      label.insertBefore(btn, labelText.nextSibling);
    } else {
      label.appendChild(btn);
    }
    label.appendChild(tooltip);
  }

  // ------------------------------------------------------------------
  // 8. Real-Time Form Validation
  // ------------------------------------------------------------------
  const VALIDATION_RULES = {
    'character': { required: true, minLength: 5, message: 'Character description needs at least 5 characters.' },
    'fps': { pattern: /^[0-9]+$/, message: 'FPS must be a whole number.' },
    'seed': { pattern: /^-?[0-9]*$/, message: 'Seed must be a number (or -1 for random).' },
    'qa_threshold_loop_rmse': { pattern: /^[0-9]*\.?[0-9]*$/, message: 'Must be a decimal number.' },
    'qa_threshold_foot_drift': { pattern: /^[0-9]*\.?[0-9]*$/, message: 'Must be a decimal number.' },
    'qa_threshold_center_drift': { pattern: /^[0-9]*\.?[0-9]*$/, message: 'Must be a decimal number.' }
  };

  function initFormValidation() {
    Object.entries(VALIDATION_RULES).forEach(([name, rule]) => {
      const fields = document.querySelectorAll(`[name="${name}"]`);
      fields.forEach(field => {
        const validate = () => {
          const val = field.value.trim();
          const existing = field.parentElement.querySelector('.field-error-msg');
          if (existing) existing.remove();
          field.classList.remove('field-invalid', 'field-valid');

          if (rule.required && !val) {
            field.classList.add('field-invalid');
            const err = document.createElement('span');
            err.className = 'field-error-msg';
            err.textContent = rule.message || 'This field is required.';
            field.parentElement.appendChild(err);
            return false;
          }
          if (val && rule.minLength && val.length < rule.minLength) {
            field.classList.add('field-invalid');
            const err = document.createElement('span');
            err.className = 'field-error-msg';
            err.textContent = rule.message;
            field.parentElement.appendChild(err);
            return false;
          }
          if (val && rule.pattern && !rule.pattern.test(val)) {
            field.classList.add('field-invalid');
            const err = document.createElement('span');
            err.className = 'field-error-msg';
            err.textContent = rule.message;
            field.parentElement.appendChild(err);
            return false;
          }
          if (val) field.classList.add('field-valid');
          return true;
        };

        field.addEventListener('blur', validate);
        field.addEventListener('input', () => {
          clearTimeout(field._valTimer);
          field._valTimer = setTimeout(validate, 400);
        });
      });
    });
  }

  // ------------------------------------------------------------------
  // 9. Keyboard-First Form Navigation
  // ------------------------------------------------------------------
  function setFormTabOrder() {
    const form = document.getElementById('generateForm');
    if (!form) return;
    const fields = form.querySelectorAll('input, select, textarea, button[type="submit"], button.primary.big');
    fields.forEach((field, idx) => {
      field.tabIndex = idx + 1;
    });
  }

  // ------------------------------------------------------------------
  // 10. Simplified Health Bar
  // ------------------------------------------------------------------
  function simplifyHealthBar(statusData) {
    if (!statusData) return;

    const indicators = {
      'health-dot-comfy': statusData.comfy_running ? 'good' : 'broken',
      'health-dot-models': statusData.models?.ok ? 'good' : 'degraded',
      'health-dot-vram': 'good',
      'health-dot-disk': 'good',
      'health-dot-queue': 'good'
    };

    if (statusData.gpu && !statusData.gpu.ok) indicators['health-dot-vram'] = 'broken';
    if (statusData.disk) {
      const freeGb = parseFloat(statusData.disk.free_gb);
      if (freeGb < 5) indicators['health-dot-disk'] = 'broken';
      else if (freeGb < 20) indicators['health-dot-disk'] = 'degraded';
    }
    if (statusData.job && statusData.job.running) indicators['health-dot-queue'] = 'degraded';

    Object.entries(indicators).forEach(([id, state]) => {
      const dot = document.getElementById(id);
      if (dot) {
        dot.style.background = '';
        dot.style.backgroundColor = '';
        dot.className = 'status-indicator health-' + state;
      }
    });
  }

  // ------------------------------------------------------------------
  // 11. Form-Ready State Detection
  // ------------------------------------------------------------------
  function updateFormReadyState() {
    const form = document.getElementById('generateForm');
    if (!form) return;
    const errors = form.querySelectorAll('.field-error-msg');
    const required = form.querySelectorAll('[name="character"]');
    let allValid = errors.length === 0;
    required.forEach(f => { if (!f.value.trim()) allValid = false; });
    form.classList.toggle('form-ready', allValid);
  }

  const _realInitFormValidation = initFormValidation;
  initFormValidation = function () {
    _realInitFormValidation();
    const form = document.getElementById('generateForm');
    if (form) {
      const checkForm = () => {
        setTimeout(updateFormReadyState, 50);
      };
      form.addEventListener('input', checkForm);
      form.addEventListener('change', checkForm);
      setTimeout(updateFormReadyState, 200);
    }
  };

  // ------------------------------------------------------------------
  // 12. Undo System
  // ------------------------------------------------------------------
  window.undoableAction = function(message, doFn, undoFn, timeout) {
    showBanner(message, 'info', {
      undoFn: undoFn,
      undoTimeout: timeout || 10
    });
    if (typeof doFn === 'function') doFn();
  };

  // ------------------------------------------------------------------
  // Hook into showView — lightweight
  // ------------------------------------------------------------------
  const _origShowView = window.showView;
  window.showView = function (name) {
    _origShowView(name);

    // Track recent views for command palette ranking
    try {
      let recent = JSON.parse(localStorage.getItem('recentViews') || '[]');
      recent = recent.filter(v => v !== name);
      recent.unshift(name);
      recent = recent.slice(0, 5);
      localStorage.setItem('recentViews', JSON.stringify(recent));
    } catch (e) {
      console.error('Error updating recent views:', e);
    }

    updateNavGroupActiveState(name);
  };

  // ------------------------------------------------------------------
  // Hook into refreshAll results
  // ------------------------------------------------------------------
  function refreshUxFromStatus(statusData) {
    simplifyHealthBar(statusData);
    addSmartDefaultHints(statusData);
    addFieldHints();
    setFormTabOrder();
    updateFormReadyState();
  }

  const _origRenderGlobalProgress = window.renderGlobalProgress;
  window.renderGlobalProgress = function (job) {
    if (typeof _origRenderGlobalProgress === 'function') _origRenderGlobalProgress(job);
    updateTimeEstimates(job);

    if (job && job.running) {
      lockOperationButtons(job.title ? job.title.substring(0, 20) + '...' : 'Running...');
    } else {
      unlockOperationButtons();
    }
  };

  // ------------------------------------------------------------------
  // Deferred Form Enhancer
  // ------------------------------------------------------------------
  let _formEnhancementsRun = false;
  function runFormEnhancements() {
    if (_formEnhancementsRun) return;
    _formEnhancementsRun = true;
    addFieldHints();
    initFormValidation();
    setFormTabOrder();

    const observer = new MutationObserver(() => {
      addFieldHints();
      setFormTabOrder();
    });
    observer.observe(document.querySelector('.shell') || document.body, {
      childList: true,
      subtree: true
    });
    window._formObserver = observer;
  }

  // ------------------------------------------------------------------
  // Init
  // ------------------------------------------------------------------
  function initUxEnhancements() {
    buildGroupedNav();

    // Sidebar collapse/expand with localStorage persistence
    const rail = document.querySelector('.rail');
    const collapseToggle = document.getElementById('railCollapseToggle');
    if (rail && collapseToggle) {
      const isCollapsed = localStorage.getItem('railCollapsed') === 'true';
      if (isCollapsed) {
        rail.classList.add('collapsed');
        document.body.classList.add('rail-collapsed');
      }
      collapseToggle.addEventListener('click', () => {
        const collapsedNow = rail.classList.toggle('collapsed');
        document.body.classList.toggle('rail-collapsed', collapsedNow);
        localStorage.setItem('railCollapsed', collapsedNow);
      });
    }

    if (window.viewComponentsLoaded) {
      window.viewComponentsLoaded.then(runFormEnhancements);
    } else {
      setTimeout(runFormEnhancements, 200);
    }

    const currentView = location.hash.replace('#', '') || 'guide';
    updateNavGroupActiveState(currentView);

    if (window._latestStatus) addSmartDefaultHints(window._latestStatus);

    const _origRefreshAll = window.refreshAll;
    if (typeof _origRefreshAll === 'function') {
      window.refreshAll = async function () {
        await _origRefreshAll();
        refreshUxFromStatus(window._latestStatus);
      };
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUxEnhancements);
  } else {
    setTimeout(initUxEnhancements, 0);
  }

  // ------------------------------------------------------------------
  // Integration Hooks
  // ------------------------------------------------------------------
  function hookUndoIntoReject() {
    const rejectBtn = document.getElementById('previewRejectResult');
    if (!rejectBtn || rejectBtn.dataset.undoHooked) return;
    rejectBtn.dataset.undoHooked = '1';

    rejectBtn.addEventListener('click', function (e) {
      const spritePath = rejectBtn.dataset.spriteFolder || selectedSpriteDir;
      if (!spritePath || typeof undoableAction !== 'function') return;
      const expt = rejectBtn.dataset.experimentId;
      window.undoableAction(
        'Sprite result rejected \u2014 recoverable for 10s.',
        async () => {},
        async () => {
          try {
            if (expt && typeof api === 'function') {
              await api('/api/experiments/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: expt }) });
            }
            if (typeof refreshAll === 'function') refreshAll();
          } catch (err) {
            if (typeof toast === 'function') toast('Undo failed: ' + err.message);
          }
        },
        10
      );
    }, { once: false });
  }

  const _origShowPreflightErrorBox = window.showPreflightErrorBox;
  if (typeof _origShowPreflightErrorBox === 'function') {
    window.showPreflightErrorBox = function (msg, type) {
      _origShowPreflightErrorBox(msg, type);

      let what = 'The operation could not be completed.';
      let why = msg || '';
      let steps = ['Check the logs view for more details.', 'Try the action again from the appropriate view.', 'If the issue persists, check disk space and ComfyUI status.'];
      if ((msg || '').toLowerCase().includes('comfyui') || (msg || '').toLowerCase().includes('offline') || type === 'comfy') {
        what = 'ComfyUI is not reachable.';
        why = 'SpriteForge needs ComfyUI running to generate sprites.';
        steps = ['Click "Start ComfyUI" in the Setup view or health bar.', 'Wait 30-60 seconds for ComfyUI to fully start.', 'Refresh the status, then try generating again.'];
      } else if ((msg || '').toLowerCase().includes('model') || (msg || '').toLowerCase().includes('download') || (msg || '').toLowerCase().includes('missing') || type === 'models') {
        what = 'A required model file is missing.';
        why = 'The WAN model checkpoint was not found or failed to download.';
        steps = ['Go to Setup view and click "Repair Safe Model Download".', 'Check your internet connection and disk space.', 'Wait for the download to complete, then retry.'];
      } else if ((msg || '').toLowerCase().includes('disk') || (msg || '').toLowerCase().includes('space') || (msg || '').toLowerCase().includes('memory')) {
        what = 'Insufficient disk space or memory.';
        why = 'SpriteForge needs free disk space to write outputs and temporary files.';
        steps = ['Go to Cleanup Manager and remove unused outputs.', 'Free at least 5 GB of disk space.', 'Try again with a smaller resolution or tier.'];
      }
      if (typeof showStructuredError === 'function') {
        showStructuredError(what, why, steps);
      }
    };
  }

  const _origRunAction = window.runAction;
  if (typeof _origRunAction === 'function') {
    window.runAction = async function (action, extra) {
      try {
        return await _origRunAction(action, extra);
      } catch (e) {
        const msg = e.message || '';
        if (typeof showStructuredError === 'function') {
          showStructuredError(
            'Operation failed unexpectedly.',
            msg,
            ['Check the logs view for detailed output.', 'Verify your system status in Setup.', 'Contact support with the error message above.']
          );
        }
        throw e;
      }
    };
  }

  const _origOpenResultPreview = window.openResultPreview;
  if (typeof _origOpenResultPreview === 'function') {
    window.openResultPreview = async function (spritePath) {
      await _origOpenResultPreview(spritePath);
      selectedSpriteDir = spritePath;
      setTimeout(hookUndoIntoReject, 100);
    };
  }

  // Expose for cross-module use — stub removed functions for backward compatibility
  window.updateStepMapProgress = function() {};
  window.simplifyHealthBar = simplifyHealthBar;
  window.updateViewSummary = function() {};
  window.showBanner = showBanner;
  window.showStructuredError = showStructuredError;
  window.lockOperationButtons = lockOperationButtons;
  window.unlockOperationButtons = unlockOperationButtons;
  window.undoableAction = window.undoableAction;
  window.UxEnhancements = {
    refreshFromStatus: refreshUxFromStatus
  };

})();
