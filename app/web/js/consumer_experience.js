(function () {
  'use strict';

  const CONSUMER_PRIMARY_VIEWS = Object.freeze([
    'guide', 'dashboard', 'generate', 'aaa_studio', 'quality', 'release'
  ]);

  const CONSUMER_VIEW_LABELS = Object.freeze({
    guide: 'Home',
    dashboard: 'Projects',
    generate: 'Create',
    aaa_studio: 'Studio',
    quality: 'Review',
    release: 'Export',
    tasks: 'Activity',
    setup: 'Settings',
    production: 'Automation'
  });

  const CONSUMER_VIEW_TITLES = Object.freeze({
    guide: ['Home', 'Make something wonderful.'],
    dashboard: ['Projects', 'Your characters and projects.'],
    generate: ['Create', 'Bring a new character to life.'],
    aaa_studio: ['Studio', 'Draw, animate, and refine.'],
    quality: ['Review', 'Make every movement feel right.'],
    release: ['Export', 'Send your sprites to your game.'],
    tasks: ['Activity', 'See what SpriteForge is working on.'],
    setup: ['Settings', 'Keep SpriteForge ready to create.'],
    production: ['Professional tools', 'Automate your production workflow.']
  });

  let initialized = false;

  function activeTopLevelView() {
    return document.querySelector('.shell > .view.active');
  }

  function friendlyViewName(name) {
    const parent = window.SUBVIEW_PARENTS?.[name] || name;
    if (parent === 'quality-parent') return 'quality';
    if (parent === 'tasks-parent') return 'tasks';
    return parent;
  }

  function updateViewAccessibility(name) {
    const normalized = friendlyViewName(name);
    document.querySelectorAll('.rail .nav[data-view]').forEach(button => {
      const current = button.dataset.view === normalized;
      if (current) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });

    document.querySelectorAll('.shell > .view').forEach(view => {
      const active = view.classList.contains('active');
      view.hidden = !active;
      view.setAttribute('aria-hidden', active ? 'false' : 'true');
      if ('inert' in view) view.inert = !active;
    });

    document.querySelectorAll('.subview-pane').forEach(view => {
      const active = view.classList.contains('active');
      view.setAttribute('aria-hidden', active ? 'false' : 'true');
      if ('inert' in view) view.inert = !active;
    });

    const title = CONSUMER_VIEW_TITLES[normalized] || [CONSUMER_VIEW_LABELS[normalized] || 'SpriteForge', 'Create with confidence.'];
    const eyebrow = document.getElementById('currentViewEyebrow');
    const heading = document.getElementById('currentViewTitle');
    if (eyebrow) eyebrow.textContent = title[0];
    if (heading) heading.textContent = title[1];
  }

  function decorateNavigation() {
    const nav = document.getElementById('primaryNavigation');
    if (!nav) return;
    nav.setAttribute('aria-label', 'Primary navigation');

    nav.querySelectorAll('.nav-group-heading').forEach(heading => {
      heading.setAttribute('role', 'heading');
      heading.setAttribute('aria-level', '2');
    });

    nav.querySelectorAll('.nav[data-view]').forEach(button => {
      const view = button.dataset.view;
      const primary = CONSUMER_PRIMARY_VIEWS.includes(view);
      button.classList.toggle('consumer-primary', primary);
      if (primary) button.classList.remove('mode-detail', 'mode-expert');
      const label = button.querySelector('.nav-label');
      const friendly = CONSUMER_VIEW_LABELS[view];
      if (label && friendly) label.textContent = friendly;
      if (friendly) {
        button.title = friendly;
        button.setAttribute('aria-label', friendly);
      }
    });

    let primaryGroup = nav.querySelector('.consumer-primary-group');
    if (!primaryGroup) {
      primaryGroup = document.createElement('div');
      primaryGroup.className = 'nav-group consumer-primary-group';
      primaryGroup.dataset.navGroup = 'Essentials';
      const heading = document.createElement('div');
      heading.className = 'nav-group-heading';
      heading.textContent = 'Essentials';
      heading.setAttribute('role', 'heading');
      heading.setAttribute('aria-level', '2');
      const items = document.createElement('div');
      items.className = 'nav-group-items consumer-primary-items';
      primaryGroup.append(heading, items);
      const create = nav.querySelector('.nav-create-sprite-btn');
      if (create) create.after(primaryGroup);
      else nav.prepend(primaryGroup);
    }
    const primaryItems = primaryGroup.querySelector('.consumer-primary-items');
    CONSUMER_PRIMARY_VIEWS.forEach(view => {
      const button = nav.querySelector(`.nav[data-view="${view}"]`);
      if (button && primaryItems) primaryItems.appendChild(button);
    });

    const createButton = nav.querySelector('.nav-create-sprite-btn');
    if (createButton) {
      const label = createButton.querySelector('.nav-label');
      if (label) label.textContent = 'New character';
      createButton.setAttribute('aria-label', 'New character');
    }
  }

  function toggleDisclosure(toggle, panel, open) {
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    panel.hidden = !open;
  }

  function initHealthSummary() {
    const toggle = document.getElementById('healthSummaryToggle');
    const panel = document.getElementById('healthSummaryPanel');
    if (!toggle || !panel || toggle.dataset.bound) return;
    toggle.dataset.bound = '1';
    toggle.addEventListener('click', event => {
      event.stopPropagation();
      toggleDisclosure(toggle, panel, panel.hidden);
    });
    document.addEventListener('click', event => {
      if (!panel.hidden && !panel.contains(event.target) && event.target !== toggle) {
        toggleDisclosure(toggle, panel, false);
      }
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !panel.hidden) {
        toggleDisclosure(toggle, panel, false);
        toggle.focus();
      }
    });
  }

  function refreshHealthSummary(status) {
    if (!status) return;
    const control = document.querySelector('.readiness-control');
    const summary = document.getElementById('healthSummaryText');
    const gpu = document.getElementById('chip-gpu');
    const engine = document.getElementById('chip-comfy');
    const models = document.getElementById('chip-models');
    const storage = document.getElementById('chip-storage');
    const graphicsReady = !!status.gpu?.ok;
    const engineReady = !!status.comfy_running;
    const modelsReady = !!status.models?.ok;
    const storageReady = typeof status.disk?.ok === 'boolean'
      ? status.disk.ok
      : Number.parseFloat(status.disk?.free_gb || '0') >= 25;
    const ready = graphicsReady && engineReady && modelsReady && storageReady;
    control?.classList.toggle('needs-attention', !ready);
    if (summary) summary.textContent = ready ? 'System ready' : 'Setup needs attention';
    const summaryDetail = summary?.parentElement?.querySelector('small');
    if (summaryDetail) summaryDetail.textContent = ready ? 'Everything is ready to create' : 'Open for simple fixes';
    if (gpu) gpu.textContent = `Graphics · ${graphicsReady ? 'Ready' : 'Check driver'}`;
    if (engine) engine.textContent = `Generation engine · ${engineReady ? 'Ready' : 'Start in Settings'}`;
    if (models) models.textContent = `AI models · ${modelsReady ? 'Ready' : 'Finish setup'}`;
    if (storage) storage.textContent = `Storage · ${storageReady ? `${status.disk.free_gb} GB free` : 'Free up space'}`;
  }

  function setProjectComposer(open) {
    const toggle = document.getElementById('projectCreateToggle');
    const panel = document.getElementById('projectCreatePanel');
    if (!toggle || !panel) return;
    toggleDisclosure(toggle, panel, open);
    if (open) document.getElementById('projectNameInput')?.focus();
  }

  function refreshProjectState() {
    const select = document.getElementById('projectSelect');
    const state = document.getElementById('homeProjectState');
    const name = document.getElementById('homeProjectName');
    const hint = document.getElementById('homeProjectHint');
    if (!select || !state || !name || !hint) return;
    const hasProject = !!select.value;
    state.classList.toggle('has-project', hasProject);
    name.textContent = hasProject ? (select.selectedOptions[0]?.textContent || 'Current project') : 'Start a new project';
    hint.textContent = hasProject ? 'Your work is saved inside this project.' : 'Give your game or character a name when you are ready.';
  }

  function initProjectControls() {
    const toggle = document.getElementById('projectCreateToggle');
    const cancel = document.getElementById('cancelProjectCreateBtn');
    const create = document.getElementById('createProjectBtn');
    const select = document.getElementById('projectSelect');
    if (toggle && !toggle.dataset.bound) {
      toggle.dataset.bound = '1';
      toggle.addEventListener('click', () => setProjectComposer(toggle.getAttribute('aria-expanded') !== 'true'));
    }
    cancel?.addEventListener('click', () => setProjectComposer(false));
    create?.addEventListener('click', () => {
      const observer = new MutationObserver(() => {
        if (!select?.value) return;
        observer.disconnect();
        setProjectComposer(false);
        refreshProjectState();
      });
      if (select) observer.observe(select, { childList: true, subtree: true });
    });
    select?.addEventListener('change', refreshProjectState);
    if (select) new MutationObserver(refreshProjectState).observe(select, { childList: true, subtree: true });
    refreshProjectState();
  }

  function runWorkflow(workflow) {
    if (workflow === 'pack') {
      window.showView?.('aaa_studio');
      return;
    }
    if (workflow === 'convert') {
      window.showView?.('convert');
      return;
    }
    window.openWizard?.('single');
  }

  function initHomeActions() {
    document.querySelectorAll('[data-workflow]').forEach(button => {
      if (button.dataset.consumerBound) return;
      button.dataset.consumerBound = '1';
      button.addEventListener('click', () => runWorkflow(button.dataset.workflow));
    });
    document.querySelectorAll('[data-home-action="learn"]').forEach(button => {
      if (button.dataset.consumerBound) return;
      button.dataset.consumerBound = '1';
      button.addEventListener('click', () => window.openWizard?.('single'));
    });
    document.querySelectorAll('[data-jump]').forEach(button => {
      if (button.dataset.consumerJumpBound) return;
      button.dataset.consumerJumpBound = '1';
      button.addEventListener('click', () => window.showView?.(button.dataset.jump));
    });
  }

  function refreshRecentCreations(outputs) {
    const root = document.getElementById('guidedGallery');
    if (!root) return;
    const items = Array.isArray(outputs) ? outputs.slice(0, 4) : [];
    root.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'home-empty-state';
      empty.innerHTML = '<span aria-hidden="true">✦</span><div><b>Your creations will appear here</b><small>Start with a character above. You can return and continue at any time.</small></div>';
      root.appendChild(empty);
      return;
    }
    items.forEach(item => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'guided-result';
      button.dataset.path = item.path || '';
      if (item.preview_url || item.sheet_url) {
        const image = document.createElement('img');
        image.src = item.preview_url || item.sheet_url;
        image.alt = '';
        button.appendChild(image);
      }
      const copy = document.createElement('span');
      const title = document.createElement('b');
      title.textContent = item.name || 'Character';
      const detail = document.createElement('small');
      detail.textContent = `${item.frame_count || 0} frames · Continue editing`;
      copy.append(title, detail);
      button.appendChild(copy);
      button.addEventListener('click', () => {
        if (item.path) window.openResultPreview?.(item.path);
        else window.showView?.('quality');
      });
      root.appendChild(button);
    });
  }

  function syncProfessionalToggle() {
    const toggle = document.getElementById('proToolsToggle');
    if (!toggle) return;
    const professional = document.body.classList.contains('mode-expert');
    toggle.setAttribute('aria-pressed', professional ? 'true' : 'false');
    const state = toggle.querySelector('small');
    if (state) state.textContent = professional ? 'Shown' : 'Hidden';
  }

  function initProfessionalToggle() {
    const toggle = document.getElementById('proToolsToggle');
    if (!toggle || toggle.dataset.bound) return;
    toggle.dataset.bound = '1';
    toggle.addEventListener('click', () => {
      const show = toggle.getAttribute('aria-pressed') !== 'true';
      window.setUiMode?.(show ? 'expert' : 'simple');
      syncProfessionalToggle();
      decorateNavigation();
    });
    new MutationObserver(syncProfessionalToggle).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    syncProfessionalToggle();
  }

  function enhanceWizard() {
    const modal = document.getElementById('wizardModal');
    if (!modal || modal.dataset.consumerEnhanced) return;
    modal.dataset.consumerEnhanced = '1';
    const title = modal.querySelector('#wizardTitle');
    if (title) title.textContent = 'Create something new';
    const subtitle = modal.querySelector('.wizard-header-title p');
    if (subtitle) subtitle.textContent = 'Four friendly steps. You can change anything later.';
    const labels = ['Choose', 'Character', 'Moves', 'Ready'];
    modal.querySelectorAll('.indicator-label').forEach((label, index) => {
      if (labels[index]) label.textContent = labels[index];
    });
    modal.querySelectorAll('.wizard-step-indicator').forEach((indicator, index) => {
      indicator.setAttribute('aria-label', `Step ${index + 1}: ${labels[index]}`);
    });
    const friendlyGoals = {
      wizCardGoalSingle: ['✦', 'Create a character', 'Make one polished animation to begin.'],
      wizCardGoalPack: ['▦', 'Complete character set', 'Create a ready-to-use set of movements.'],
      wizCardGoalConvert: ['▶', 'Video to sprites', 'Turn a clip into clean animation frames.']
    };
    Object.entries(friendlyGoals).forEach(([id, copy]) => {
      const card = modal.querySelector(`#${id}`);
      if (!card) return;
      const icon = card.querySelector('.choice-icon');
      const title = card.querySelector('b');
      const detail = card.querySelector('small');
      if (icon) icon.textContent = copy[0];
      if (title) title.textContent = copy[1];
      if (detail) detail.textContent = copy[2];
    });
    const close = modal.querySelector('#wizardCloseBtn');
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'wizard-consumer-toggle';
    toggle.textContent = 'Customize';
    toggle.setAttribute('aria-pressed', 'false');
    toggle.addEventListener('click', () => {
      const expanded = modal.classList.toggle('consumer-show-advanced');
      toggle.setAttribute('aria-pressed', expanded ? 'true' : 'false');
      toggle.textContent = expanded ? 'Use simple choices' : 'Customize';
    });
    close?.before(toggle);
  }

  function initWizardObserver() {
    enhanceWizard();
    const container = document.getElementById('wizardContainer');
    if (container) new MutationObserver(enhanceWizard).observe(container, { childList: true, subtree: true });
  }

  function init() {
    if (initialized) {
      decorateNavigation();
      return;
    }
    initialized = true;
    decorateNavigation();
    initHealthSummary();
    initProjectControls();
    initHomeActions();
    initProfessionalToggle();
    initWizardObserver();
    updateViewAccessibility(document.body.dataset.activeView || location.hash.replace('#', '') || 'guide');
  }

  window.ConsumerExperience = {
    init,
    onViewChange: updateViewAccessibility,
    refreshFromStatus: refreshHealthSummary,
    refreshFromOutputs: refreshRecentCreations,
    primaryViews: CONSUMER_PRIMARY_VIEWS,
    labels: CONSUMER_VIEW_LABELS
  };
})();
