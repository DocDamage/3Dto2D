// ================================================================
// UX Enhancements Module — 20 Improvements
// Covers: Breadcrumbs, Back Button, Grouped Nav, Persistent Banners,
// Time Estimates, Structured Errors, Operation Locking, Field Hints,
// Smart Defaults, Validation, Help Panel, View Summaries, Undo,
// Saved Layouts, Quick Actions Footer, Step Map Progress
// ================================================================

(function () {
  'use strict';

  // ------------------------------------------------------------------
  // 1. Breadcrumb Trail
  // ------------------------------------------------------------------
  const VIEW_LABELS = {
    guide: 'Guide', dashboard: 'Dashboard', tasks: 'Task Center',
    launchpad: 'Launchpad', generate: 'Generate Sprite', convert: 'Convert Video',
    quality: 'Quality Lab', ab_runs: 'A/B Runs', library: 'Pose Library',
    qa_dashboard: 'QA Dashboard', packs: 'Packs & Atlas', queue: 'Queue Builder',
    queues: 'Queue Monitor', history: 'History', release: 'Release',
    cleanup: 'Cleanup Manager', setup: 'Setup', logs: 'Logs'
  };

  const VIEW_GROUPS = {
    guide: 'Create', generate: 'Create', convert: 'Create', queue: 'Create',
    quality: 'Review', ab_runs: 'Review', qa_dashboard: 'Review', library: 'Review',
    dashboard: 'Manage', tasks: 'Manage', launchpad: 'Manage', packs: 'Manage',
    queues: 'Manage', history: 'Manage', release: 'Manage', cleanup: 'Manage',
    setup: 'System', logs: 'System'
  };

  function updateBreadcrumb(viewName) {
    const bar = document.getElementById('breadcrumbBar');
    if (!bar) return;
    while (bar.firstChild) bar.removeChild(bar.firstChild);

    const group = VIEW_GROUPS[viewName] || 'App';
    const label = VIEW_LABELS[viewName] || viewName;

    // Home segment
    const home = document.createElement('button');
    home.className = 'bc-segment';
    home.textContent = 'SpriteForge';
    home.addEventListener('click', () => { if (typeof showView === 'function') showView('guide'); });
    bar.appendChild(home);

    const sep1 = document.createElement('span');
    sep1.className = 'bc-sep';
    sep1.textContent = '/';
    bar.appendChild(sep1);

    // Group segment
    const groupBtn = document.createElement('button');
    groupBtn.className = 'bc-segment';
    groupBtn.textContent = group;
    bar.appendChild(groupBtn);

    const sep2 = document.createElement('span');
    sep2.className = 'bc-sep';
    sep2.textContent = '/';
    bar.appendChild(sep2);

    // Current view
    const current = document.createElement('span');
    current.className = 'bc-segment bc-current';
    current.textContent = label;
    bar.appendChild(current);
  }

  // ------------------------------------------------------------------
  // 2. Grouped Navigation
  // ------------------------------------------------------------------
  const NAV_GROUPS = [
    { name: 'Create', views: ['guide', 'generate', 'convert', 'queue'] },
    { name: 'Review', views: ['quality', 'ab_runs', 'qa_dashboard', 'library'] },
    { name: 'Manage', views: ['dashboard', 'tasks', 'launchpad', 'packs', 'queues', 'history', 'release', 'cleanup'] },
    { name: 'System', views: ['setup', 'logs'] }
  ];

  function buildGroupedNav() {
    const railNav = document.querySelector('.rail nav');
    if (!railNav) return;

    // Gather existing nav buttons by data-view
    const existingBtns = {};
    railNav.querySelectorAll('.nav[data-view]').forEach(btn => {
      existingBtns[btn.dataset.view] = btn;
    });

    // Clear nav
    while (railNav.firstChild) railNav.removeChild(railNav.firstChild);

    NAV_GROUPS.forEach(group => {
      const wrapper = document.createElement('div');
      wrapper.className = 'nav-group';
      wrapper.dataset.navGroup = group.name;

      const heading = document.createElement('button');
      heading.className = 'nav-group-heading';
      heading.type = 'button';
      heading.innerHTML = `<span class="ng-arrow">&#9660;</span> ${group.name}`;
      heading.addEventListener('click', () => {
        wrapper.classList.toggle('collapsed');
        // Save collapse state
        const collapsed = JSON.parse(localStorage.getItem('navGroupCollapsed') || '{}');
        collapsed[group.name] = wrapper.classList.contains('collapsed');
        localStorage.setItem('navGroupCollapsed', JSON.stringify(collapsed));
      });
      wrapper.appendChild(heading);

      const items = document.createElement('div');
      items.className = 'nav-group-items';
      group.views.forEach(viewName => {
        const btn = existingBtns[viewName];
        if (btn) items.appendChild(btn);
      });
      wrapper.appendChild(items);

      railNav.appendChild(wrapper);
    });

    // Restore collapse states
    const collapsed = JSON.parse(localStorage.getItem('navGroupCollapsed') || '{}');
    Object.entries(collapsed).forEach(([name, isCollapsed]) => {
      if (isCollapsed) {
        const el = railNav.querySelector(`[data-nav-group="${name}"]`);
        if (el) el.classList.add('collapsed');
      }
    });
  }

  function updateNavGroupActiveState(viewName) {
    document.querySelectorAll('.nav-group').forEach(g => {
      const hasActive = g.querySelector(`.nav[data-view="${viewName}"]`);
      g.classList.toggle('has-active', !!hasActive);
    });
  }

  // ------------------------------------------------------------------
  // 4. Back Button — View History Stack
  // ------------------------------------------------------------------
  const viewHistory = [];
  const MAX_HISTORY = 15;

  function pushViewHistory(viewName) {
    if (viewHistory.length === 0 || viewHistory[viewHistory.length - 1] !== viewName) {
      viewHistory.push(viewName);
      if (viewHistory.length > MAX_HISTORY) viewHistory.shift();
    }
    updateBackButton();
  }

  function goBack() {
    if (viewHistory.length < 2) return;
    viewHistory.pop(); // remove current
    const prev = viewHistory[viewHistory.length - 1];
    if (typeof showView === 'function') {
      _skipHistoryPush = true;
      showView(prev);
      _skipHistoryPush = false;
    }
  }

  let _skipHistoryPush = false;

  function updateBackButton() {
    const btn = document.getElementById('viewBackBtn');
    if (btn) btn.disabled = viewHistory.length < 2;
  }

  // ------------------------------------------------------------------
  // 5. Persistent Action Banners
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
      // Undo banner (improvement 19)
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

      // Auto-dismiss after duration if specified
      if (options.autoDismiss) {
        setTimeout(() => { if (banner.parentNode) banner.remove(); }, options.autoDismiss);
      }
    }

    container.appendChild(banner);
    return id;
  }

  // Expose globally
  window.showBanner = showBanner;

  // ------------------------------------------------------------------
  // 6. Time Estimates on Progress
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

    // Track start time
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
  // 7. Structured Error Display
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
  // 8. Operation State Locking
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
  // 9. Inline Field Descriptions
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
        // Don't add twice
        if (field.parentElement && field.parentElement.querySelector('.field-hint')) return;
        const span = document.createElement('span');
        span.className = 'field-hint';
        span.textContent = hint;
        field.parentElement.appendChild(span);
      });
    });
  }

  // ------------------------------------------------------------------
  // 10. Smart Default "Why?" Explanations
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

    // Insert after the field label text, before the input
    const labelText = label.childNodes[0];
    if (labelText && labelText.nodeType === 3) {
      label.insertBefore(btn, labelText.nextSibling);
    } else {
      label.appendChild(btn);
    }
    label.appendChild(tooltip);
  }

  // ------------------------------------------------------------------
  // 11. Real-Time Form Validation
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
          // Remove previous error
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
          // Debounced validation on input
          clearTimeout(field._valTimer);
          field._valTimer = setTimeout(validate, 400);
        });
      });
    });
  }

  // ------------------------------------------------------------------
  // 12. Keyboard-First Form Navigation
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
  // 14. Simplified Health Bar
  // ------------------------------------------------------------------
  function simplifyHealthBar(statusData) {
    if (!statusData) return;

    const indicators = {
      'health-dot-comfy': statusData.comfy_running ? 'good' : 'broken',
      'health-dot-models': statusData.models?.ok ? 'good' : 'degraded',
      'health-dot-vram': 'good', // default
      'health-dot-disk': 'good',
      'health-dot-queue': 'good'
    };

    // VRAM check
    if (statusData.gpu && !statusData.gpu.ok) indicators['health-dot-vram'] = 'broken';

    // Disk check
    if (statusData.disk) {
      const freeGb = parseFloat(statusData.disk.free_gb);
      if (freeGb < 5) indicators['health-dot-disk'] = 'broken';
      else if (freeGb < 20) indicators['health-dot-disk'] = 'degraded';
    }

    // Queue check
    if (statusData.job && statusData.job.running) indicators['health-dot-queue'] = 'degraded';

    Object.entries(indicators).forEach(([id, state]) => {
      const dot = document.getElementById(id);
      if (dot) {
        // Clear any inline styles set by updateHealthBar so CSS classes win
        dot.style.background = '';
        dot.style.backgroundColor = '';
        dot.className = 'status-indicator health-' + state;
      }
    });

    // Remove pulsing animation from error item
    const errorItem = document.getElementById('health-item-error');
    if (errorItem) errorItem.style.animation = 'none';
  }

  // ------------------------------------------------------------------
  // 3. Step Map — Functional Progress Tracking
  // ------------------------------------------------------------------
  function updateStepMapProgress(statusData) {
    if (!statusData) return;

    const hasSetup = statusData.comfy_running && statusData.models?.ok;
    const hasGenerated = statusData.outputs && statusData.outputs.length > 0;
    const hasJob = statusData.job && (statusData.job.running || statusData.job.exit_code !== undefined);
    const currentView = localStorage.getItem('activeView') || 'guide';

    const steps = {
      setup: hasSetup ? 'completed' : 'current',
      describe: hasSetup ? (hasGenerated ? 'completed' : 'current') : 'future',
      generate: hasGenerated ? 'completed' : (hasJob ? 'current' : 'future'),
      review: hasGenerated ? 'current' : 'future',
      export: 'future'
    };

    // Override: mark current view's step as current
    const viewStepMap = {
      setup: 'setup', launchpad: 'setup',
      guide: 'describe', generate: 'describe', convert: 'describe',
      queue: 'generate', queues: 'generate', logs: 'generate',
      quality: 'review', ab_runs: 'review', qa_dashboard: 'review',
      packs: 'export', release: 'export'
    };
    const activeStep = viewStepMap[currentView];
    if (activeStep) steps[activeStep] = 'current';

    // Mark everything before current as completed
    const order = ['setup', 'describe', 'generate', 'review', 'export'];
    let foundCurrent = false;
    for (let i = order.length - 1; i >= 0; i--) {
      if (steps[order[i]] === 'current') { foundCurrent = true; continue; }
      if (foundCurrent) steps[order[i]] = 'completed';
    }
    // Mark everything after current as future
    foundCurrent = false;
    for (let i = 0; i < order.length; i++) {
      if (steps[order[i]] === 'current') { foundCurrent = true; continue; }
      if (foundCurrent) steps[order[i]] = 'future';
    }

    document.querySelectorAll('.step-map-item').forEach(item => {
      const step = item.dataset.step;
      if (!step || !steps[step]) return;
      item.classList.remove('step-completed', 'step-current', 'step-future', 'active');
      item.classList.add('step-' + steps[step]);
    });
  }

  // ------------------------------------------------------------------
  // 16. Quick-Actions Footer
  // ------------------------------------------------------------------
  const QUICK_ACTIONS = {
    guide: [
      { label: 'Start Generating', action: () => showView('generate'), primary: true }
    ],
    generate: [
      { label: 'Run Generation', action: () => { const f = document.getElementById('generateForm'); if (f && f.requestSubmit) f.requestSubmit(); }, primary: true },
      { label: 'Load Preset', action: () => { const s = document.getElementById('presetSelect'); if (s) s.focus(); } }
    ],
    quality: [
      { label: 'Run QA Audit', action: () => { const btn = document.querySelector('[data-quality="qa"]'); if (btn) btn.click(); }, primary: true },
      { label: 'View Dashboard', action: () => showView('qa_dashboard') }
    ],
    release: [
      { label: 'Export Pack', action: () => { const btn = document.querySelector('#releaseExportBtn'); if (btn) btn.click(); }, primary: true }
    ],
    setup: [
      { label: 'Check Status', action: () => { if (typeof refreshAll === 'function') refreshAll(); }, primary: true }
    ],
    queues: [
      { label: 'View Logs', action: () => showView('logs') }
    ],
    dashboard: [
      { label: 'New Sprite', action: () => showView('generate'), primary: true }
    ]
  };

  function updateQuickActionsFooter(viewName) {
    const footer = document.getElementById('quickActionsFooter');
    if (!footer) return;

    const actions = QUICK_ACTIONS[viewName];
    // Clear existing buttons (keep the label)
    const existingBtns = footer.querySelectorAll('.mini, .primary');
    existingBtns.forEach(b => b.remove());

    if (!actions || actions.length === 0) {
      footer.style.display = 'none';
      return;
    }

    footer.style.display = 'flex';
    actions.forEach(a => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = a.primary ? 'primary' : 'mini';
      btn.textContent = a.label;
      btn.addEventListener('click', a.action);
      footer.appendChild(btn);
    });
  }

  // ------------------------------------------------------------------
  // 17. Contextual Help Panel
  // ------------------------------------------------------------------
  const VIEW_HELP = {
    guide: {
      title: 'Guide — Quick Reference',
      tips: [
        'Choose a character template to auto-fill sprite settings.',
        'The 4-step wizard walks through character, action, quality, and output.',
        'Click "Run" on Step 4 to start generating your first sprite.',
        'Templates set optimized defaults for each game genre.'
      ],
      next: 'After completing the guide, your sprite will appear in the Quality Lab.'
    },
    generate: {
      title: 'Generate Sprite — Quick Reference',
      tips: [
        'Character description drives the AI generation. Be specific.',
        'Action = the animation (idle, walk, run). Direction = camera angle.',
        'Model tier controls quality vs speed. Higher tiers need more VRAM.',
        'Use presets to save and reuse your favorite configurations.',
        'Leave "prompt override" empty to use the smart prompt builder.'
      ],
      next: 'After generation, the result opens automatically for review.'
    },
    quality: {
      title: 'Quality Lab — Quick Reference',
      tips: [
        'Loop RMSE: Measures frame-to-frame seamlessness. Lower is better.',
        'Foot Drift: Measures vertical foot movement. Lower = more stable.',
        'Use the frame scrubber (or arrow keys) to inspect individual frames.',
        'One-click repair buttons fix common issues like background noise.',
        'Space bar toggles animation playback.'
      ],
      next: 'When satisfied, export from the Release view or add to a pack.'
    },
    dashboard: {
      title: 'Dashboard — Quick Reference',
      tips: [
        'Shows overall project health, recent outputs, and system status.',
        'Cards summarize queue status, model availability, and disk space.',
        'Click any output card to open it in the Quality Lab.'
      ],
      next: 'Use the Guide or Generate view to create new sprites.'
    },
    setup: {
      title: 'Setup — Quick Reference',
      tips: [
        'Verify ComfyUI is running and models are downloaded.',
        'Green indicators = ready. Amber = needs attention. Red = broken.',
        'The preflight check runs automatically before each generation.',
        'Configure output paths and quality thresholds here.'
      ],
      next: 'Once everything is green, head to Generate to create sprites.'
    },
    release: {
      title: 'Release — Quick Reference',
      tips: [
        'Package approved sprites into engine-ready sprite sheets.',
        'Export includes metadata JSON and resolution variants.',
        'Only sprites that pass QA gates are included by default.'
      ],
      next: 'Exported packs are saved to your project output directory.'
    },
    tasks: {
      title: 'Task Center — Quick Reference',
      tips: [
        'Shows all running and completed tasks in one place.',
        'Failed tasks include error details and recovery suggestions.',
        'Click any task to view its full log output.'
      ],
      next: 'Review task outputs in the Quality Lab.'
    },
    logs: {
      title: 'Logs — Quick Reference',
      tips: [
        'Live output from the current running process.',
        'Scroll to bottom for the latest output.',
        'Errors are highlighted in red.'
      ],
      next: 'When the task completes, review results in Quality Lab.'
    }
  };

  function updateHelpPanel(viewName) {
    const panel = document.getElementById('viewHelpPanel');
    if (!panel) return;

    const help = VIEW_HELP[viewName];
    while (panel.firstChild) panel.removeChild(panel.firstChild);

    if (!help) {
      const h4 = document.createElement('h4');
      h4.textContent = (VIEW_LABELS[viewName] || viewName) + ' — Quick Reference';
      panel.appendChild(h4);
      const p = document.createElement('p');
      p.style.color = 'var(--muted)';
      p.style.fontSize = '12px';
      p.textContent = 'No specific help available for this view.';
      panel.appendChild(p);
      return;
    }

    const h4 = document.createElement('h4');
    h4.textContent = help.title;
    panel.appendChild(h4);

    const ul = document.createElement('ul');
    help.tips.forEach(tip => {
      const li = document.createElement('li');
      li.textContent = tip;
      ul.appendChild(li);
    });
    panel.appendChild(ul);

    if (help.next) {
      const nextDiv = document.createElement('div');
      nextDiv.className = 'help-next';
      nextDiv.innerHTML = '<strong>Next step:</strong> ' + escapeHtml(help.next);
      panel.appendChild(nextDiv);
    }
  }

  function toggleHelpPanel() {
    const panel = document.getElementById('viewHelpPanel');
    const toggle = document.getElementById('helpPanelToggle');
    if (!panel) return;
    const isOpen = panel.classList.toggle('visible');
    document.body.classList.toggle('help-panel-open', isOpen);
    if (toggle) toggle.classList.toggle('active', isOpen);

    // Remember state
    const currentView = localStorage.getItem('activeView') || 'guide';
    const states = JSON.parse(localStorage.getItem('helpPanelStates') || '{}');
    states[currentView] = isOpen;
    localStorage.setItem('helpPanelStates', JSON.stringify(states));
  }

  function restoreHelpPanelState(viewName) {
    const states = JSON.parse(localStorage.getItem('helpPanelStates') || '{}');
    const panel = document.getElementById('viewHelpPanel');
    const toggle = document.getElementById('helpPanelToggle');
    const isOpen = !!states[viewName];
    if (panel) panel.classList.toggle('visible', isOpen);
    if (toggle) toggle.classList.toggle('active', isOpen);
    document.body.classList.toggle('help-panel-open', isOpen);
  }

  // ------------------------------------------------------------------
  // 18. View Summary Line
  // ------------------------------------------------------------------
  const VIEW_SUMMARIES = {
    guide: () => 'Step-by-step wizard to create your first sprite.',
    dashboard: (s) => s && s.outputs ? `${s.outputs.length} sprite outputs in workspace.` : 'Loading project overview...',
    generate: () => 'Configure and launch a new sprite generation.',
    quality: () => {
      const scrub = document.getElementById('frameScrubber');
      if (scrub && scrub.max > 0) return `Inspecting sprite — ${Number(scrub.max) + 1} frames loaded.`;
      return 'No sprite selected. Choose one from Dashboard or History.';
    },
    setup: (s) => {
      if (!s) return 'Checking system status...';
      const issues = [];
      if (!s.comfy_running) issues.push('ComfyUI offline');
      if (!s.models?.ok) issues.push('models incomplete');
      if (issues.length) return 'Needs attention: ' + issues.join(', ') + '.';
      return 'All systems ready.';
    },
    logs: (s) => s?.job?.running ? `Running: ${s.job.title || 'task'}` : 'No task currently running.',
    tasks: (s) => s?.job ? `Last task: ${s.job.title || 'unknown'} — ${s.job.running ? 'running' : (s.job.exit_code === 0 ? 'passed' : 'failed')}.` : 'No tasks recorded.',
    release: () => 'Package and export approved sprites for your game engine.',
    queues: (s) => s?.job?.running ? 'Queue is processing.' : 'Queue is idle.',
    history: () => 'Browse all past generation results.',
    cleanup: () => 'Remove unused outputs to free disk space.',
    convert: () => 'Convert video files into sprite animations.',
    launchpad: () => 'Quick-start hub for common sprite generation tasks.',
    packs: () => 'Build sprite packs, atlases, and export bundles.',
    queue: () => 'Create batched sprite generation jobs.',
    ab_runs: () => 'Compare A/B generation runs side by side.',
    qa_dashboard: () => 'Overview of QA metrics across all sprites.',
    library: () => 'Browse and manage pose and reference images.'
  };

  function updateViewSummary(viewName, statusData) {
    const el = document.getElementById('viewSummaryLine');
    if (!el) return;
    const fn = VIEW_SUMMARIES[viewName];
    el.textContent = fn ? fn(statusData) : '';
  }

  // ------------------------------------------------------------------
  // 19. Undo System
  // ------------------------------------------------------------------
  window.undoableAction = function(message, doFn, undoFn, timeout) {
    showBanner(message, 'info', {
      undoFn: undoFn,
      undoTimeout: timeout || 10
    });
    if (typeof doFn === 'function') doFn();
  };

  // ------------------------------------------------------------------
  // 11b. Form-Ready State Detection
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

  // Hook validation to also update form-ready state
  const _realInitFormValidation = initFormValidation;
  initFormValidation = function () {
    _realInitFormValidation();
    // Also observe overall form validity
    const form = document.getElementById('generateForm');
    if (form) {
      const checkForm = () => {
        setTimeout(updateFormReadyState, 50);
      };
      form.addEventListener('input', checkForm);
      form.addEventListener('change', checkForm);
      // Initial check
      setTimeout(updateFormReadyState, 200);
    }
  };

  // ------------------------------------------------------------------
  // 20. Saved View Layouts Per Mode
  // ------------------------------------------------------------------
  function saveLayoutState(viewName, mode) {
    const key = `layout_${mode}_${viewName}`;
    const scrollPos = document.querySelector('.shell')?.scrollTop || window.scrollY;
    localStorage.setItem(key, JSON.stringify({ scroll: scrollPos }));
  }

  function restoreLayoutState(viewName) {
    const mode = localStorage.getItem('uiMode') || 'simple';
    const key = `layout_${mode}_${viewName}`;
    const saved = JSON.parse(localStorage.getItem(key) || 'null');
    if (saved && saved.scroll) {
      requestAnimationFrame(() => {
        const shell = document.querySelector('.shell');
        if (shell) shell.scrollTop = saved.scroll;
        else window.scrollTo(0, saved.scroll);
      });
    }
  }

  // ------------------------------------------------------------------
  // Hook into showView
  // ------------------------------------------------------------------
  const _origShowView = window.showView;
  window.showView = function (name) {
    // Save current layout before switching
    const prevView = localStorage.getItem('activeView') || 'guide';
    const mode = localStorage.getItem('uiMode') || 'simple';
    saveLayoutState(prevView, mode);

    // Call original
    _origShowView(name);

    // UX enhancements
    if (!_skipHistoryPush) pushViewHistory(name);
    updateBreadcrumb(name);
    updateNavGroupActiveState(name);
    updateQuickActionsFooter(name);
    updateHelpPanel(name);
    restoreHelpPanelState(name);
    updateViewSummary(name, window._latestStatus);
    updateStepMapProgress(window._latestStatus);
    restoreLayoutState(name);
  };

  // ------------------------------------------------------------------
  // Hook into refreshAll results
  // ------------------------------------------------------------------
  function refreshUxFromStatus(statusData) {
    const currentView = localStorage.getItem('activeView') || 'guide';
    updateViewSummary(currentView, statusData);
    updateStepMapProgress(statusData);
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

    // Operation locking (improvement 8)
    if (job && job.running) {
      lockOperationButtons(job.title ? job.title.substring(0, 20) + '...' : 'Running...');
    } else {
      unlockOperationButtons();
    }
  };

  // ------------------------------------------------------------------
  // Deferred Form Enhancer — runs after async view components load
  // ------------------------------------------------------------------
  let _formEnhancementsRun = false;
  function runFormEnhancements() {
    if (_formEnhancementsRun) return;
    _formEnhancementsRun = true;
    addFieldHints();
    initFormValidation();
    setFormTabOrder();

    // Observe for future DOM changes (e.g., views loading later)
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
  // Init on DOMContentLoaded
  // ------------------------------------------------------------------
  // ------------------------------------------------------------------
  // 14b. Health Bar Detail Panel Click Handler
  // ------------------------------------------------------------------
  function initHealthDetailPanels() {
    const healthBar = document.getElementById('healthBar');
    const detailPanel = document.getElementById('healthDetailPanel');
    if (!healthBar) return;

    // Create detail panel if it doesn't exist
    let panel = detailPanel;
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'healthDetailPanel';
      panel.className = 'health-detail-panel';
      healthBar.parentElement.insertBefore(panel, healthBar.nextSibling);
    }

    // Click any health item to toggle detail
    healthBar.querySelectorAll('.health-item').forEach(item => {
      if (item.dataset.healthDetailWired) return;
      item.dataset.healthDetailWired = '1';
      item.style.cursor = 'pointer';
      item.addEventListener('click', () => {
        const isOpen = panel.classList.contains('visible');
        // Populate detail
        const statusData = window._latestStatus;
        if (!isOpen && statusData) {
          let detailText = '';
          if (item.querySelector('#health-dot-comfy')) {
            detailText = statusData.comfy_running
              ? 'ComfyUI is online and accepting requests. No action needed.'
              : 'ComfyUI is offline. Click "Start ComfyUI" button or run it manually. SpriteForge cannot generate sprites without ComfyUI.';
          } else if (item.querySelector('#health-dot-models')) {
            const present = statusData.models?.present || 0;
            const total = statusData.models?.total || 0;
            detailText = `${present}/${total} model files found. Models are required for WAN generation. Missing models can be downloaded via Setup > Repair.`;
          } else if (item.querySelector('#health-dot-vram')) {
            const gpu = statusData.gpu || {};
            detailText = `GPU: ${gpu.label || 'Unknown'}, ${gpu.memory_total || '?'} total. SpriteForge auto-selects the best profile based on your hardware.`;
          } else if (item.querySelector('#health-dot-disk')) {
            const freeGb = statusData.disk?.free_gb || 0;
            detailText = `${freeGb} GB free. At least 5 GB is recommended for smooth operation. Use Cleanup Manager to reclaim space.`;
          } else if (item.querySelector('#health-dot-queue')) {
            const job = statusData.job;
            detailText = job?.running
              ? `Job running: ${job.title || 'task'}. Started ${job.started_at || 'unknown'}. Check logs for progress.`
              : 'No jobs running. Queue is idle.';
          } else if (item.querySelector('#health-dot-error') || item.querySelector('#health-val-error')) {
            const job = statusData.job;
            detailText = job?.exit_code
              ? `Last job "${job.title}" failed with exit code ${job.exit_code}. Click to view in Task Center for recovery options.`
              : 'No recent errors.';
          }
          panel.textContent = detailText || 'No details available.';
        }
        panel.classList.toggle('visible');
      });
    });
  }

  function initUxEnhancements() {
    buildGroupedNav();

    // Run form enhancements after async view components are loaded
    if (window.viewComponentsLoaded) {
      window.viewComponentsLoaded.then(runFormEnhancements);
    } else {
      // Fallback: run after a delay
      setTimeout(runFormEnhancements, 200);
    }

    // Health bar detail panels
    initHealthDetailPanels();

    // Back button
    const backBtn = document.getElementById('viewBackBtn');
    if (backBtn) backBtn.addEventListener('click', goBack);

    // Help panel toggle
    const helpToggle = document.getElementById('helpPanelToggle');
    if (helpToggle) helpToggle.addEventListener('click', toggleHelpPanel);

    // Initialize current view state
    const currentView = localStorage.getItem('activeView') || 'guide';
    pushViewHistory(currentView);
    updateBreadcrumb(currentView);
    updateNavGroupActiveState(currentView);
    updateQuickActionsFooter(currentView);
    updateHelpPanel(currentView);
    restoreHelpPanelState(currentView);
    updateViewSummary(currentView, window._latestStatus);

    // Add smart default hints when status is available (may be delayed)
    if (window._latestStatus) addSmartDefaultHints(window._latestStatus);

    // Re-run hints after each refresh when refreshAll already exists. app_main.js
    // also calls UxEnhancements.refreshFromStatus because it loads after this file.
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

    const origHandler = rejectBtn.onclick;
    rejectBtn.addEventListener('click', function (e) {
      const spritePath = rejectBtn.dataset.spriteFolder || selectedSpriteDir;
      if (!spritePath || typeof undoableAction !== 'function') return;
      const expt = rejectBtn.dataset.experimentId;
      window.undoableAction(
        'Sprite result rejected — recoverable for 10s.',
        async () => {
          // The doFn is empty because the reject already happened via the original handler
        },
        async () => {
          // Undo: restore by clearing the rejection
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

  // Hook structured errors into showPreflightErrorBox (the real error display path)
  const _origShowPreflightErrorBox = window.showPreflightErrorBox;
  if (typeof _origShowPreflightErrorBox === 'function') {
    window.showPreflightErrorBox = function (msg, type) {
      // Call original first
      _origShowPreflightErrorBox(msg, type);

      // Also show structured error card
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

  // Also hook runAction catch for non-preflight errors (toast-displayed errors)
  const _origRunAction = window.runAction;
  if (typeof _origRunAction === 'function') {
    window.runAction = async function (action, extra) {
      try {
        return await _origRunAction(action, extra);
      } catch (e) {
        // showPreflightErrorBox already handles preflight-type errors inside runAction;
        // this catch fires for truly unhandled errors
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

  // Hook undo prompt for reject button whenever preview opens
  const _origOpenResultPreview = window.openResultPreview;
  if (typeof _origOpenResultPreview === 'function') {
    window.openResultPreview = async function (spritePath) {
      await _origOpenResultPreview(spritePath);
      selectedSpriteDir = spritePath;
      setTimeout(hookUndoIntoReject, 100);
    };
  }

  // Expose for cross-module use
  window.updateStepMapProgress = updateStepMapProgress;
  window.simplifyHealthBar = simplifyHealthBar;
  window.updateViewSummary = updateViewSummary;
  window.showBanner = showBanner;
  window.showStructuredError = showStructuredError;
  window.lockOperationButtons = lockOperationButtons;
  window.unlockOperationButtons = unlockOperationButtons;
  window.undoableAction = window.undoableAction; // preserve
  window.UxEnhancements = {
    toggleHelpPanel: toggleHelpPanel,
    goBack: goBack,
    refreshFromStatus: refreshUxFromStatus
  };

})();
