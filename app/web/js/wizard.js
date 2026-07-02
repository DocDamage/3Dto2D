(function () {
  'use strict';

  const WIZARD_TEMPLATES = {
    platformer: {
      style: 'polished 2D platformer sprite, professional character design, readable side-view silhouette, crisp pixel-friendly edges, locked camera',
      actions: ['idle', 'walk', 'run', 'jump', 'fall', 'land', 'attack_light', 'hurt', 'death'],
      directions: ['right'],
      perspective: 'side_view'
    },
    topdown: {
      style: 'polished top-down RPG sprite, professional character design, readable small-scale silhouette, consistent outfit, locked orthographic camera',
      actions: ['idle', 'walk', 'run', 'attack_light', 'cast', 'hurt', 'death'],
      directions: ['front', 'back', 'left', 'right'],
      perspective: 'isometric'
    },
    fighter: {
      style: 'polished fighting game sprite animation, professional character design, strong pose clarity, clean silhouette, consistent costume, locked camera',
      actions: ['idle', 'walk', 'run', 'attack_light', 'attack_heavy', 'block', 'dodge', 'hurt', 'death'],
      directions: ['right'],
      perspective: 'side_view'
    },
    enemy: {
      style: 'polished game enemy sprite, bold readable silhouette, strong shape language, clean animation poses, locked camera',
      actions: ['idle', 'walk', 'run', 'attack_light', 'hurt', 'death'],
      directions: ['right'],
      perspective: 'three_quarter'
    },
    object: {
      style: 'polished game object sprite animation, centered object, clean outline, cohesive palette, locked camera, transparent-ready background',
      actions: ['idle', 'use', 'interact'],
      directions: ['front'],
      perspective: 'orthographic'
    }
  };

  const PERSPECTIVE_PROMPTS = {
    side_view: 'side-view camera, horizontal profile, locked 2D view',
    front_view: 'front-facing camera, centered character, locked 2D view',
    back_view: 'back-facing camera, centered character, locked 2D view',
    three_quarter: 'three-quarter camera, readable depth, locked camera',
    top_down: 'top-down camera, map-ready silhouette, locked overhead view',
    isometric: 'isometric camera projection, game-ready diagonal view, locked camera',
    orthographic: 'orthographic camera, no perspective distortion, locked view',
    low_angle: 'low-angle heroic camera, consistent sprite framing, locked camera',
    high_angle: 'high-angle camera, readable top surfaces, locked camera',
    overhead: 'direct overhead camera, tactical readable silhouette, locked camera'
  };

  let currentStep = 1;
  const STORAGE_KEY = 'spriteforge_wizard_state';

  // Modal elements
  let modal, form, closeBtn, backBtn, nextBtn, launchBtn, skipBtn;
  let stepperIndicators = [];
  let stepPanels = [];

  function initWizard() {
    modal = document.getElementById('wizardModal');
    form = document.getElementById('wizardForm');
    closeBtn = document.getElementById('wizardCloseBtn');
    backBtn = document.getElementById('wizardBackBtn');
    nextBtn = document.getElementById('wizardNextBtn');
    launchBtn = document.getElementById('wizardLaunchBtn');
    skipBtn = document.getElementById('wizardSkipBtn');

    if (!modal || !form) return;

    stepperIndicators = Array.from(modal.querySelectorAll('.wizard-step-indicator'));
    stepPanels = Array.from(modal.querySelectorAll('.wizard-step-panel'));

    // Bind event listeners
    closeBtn.addEventListener('click', closeWizard);
    backBtn.addEventListener('click', () => setStep(currentStep - 1));
    nextBtn.addEventListener('click', handleNextStep);
    launchBtn.addEventListener('click', submitWizard);
    skipBtn.addEventListener('click', skipToAdvanced);

    // Clickable indicators
    stepperIndicators.forEach(indicator => {
      indicator.addEventListener('click', () => {
        const targetStep = parseInt(indicator.dataset.wizStep);
        if (targetStep < currentStep) {
          setStep(targetStep);
        } else if (targetStep > currentStep) {
          // Attempt to validate current step before letting them click forward
          if (validateStep(currentStep)) {
            setStep(targetStep);
          }
        }
      });
    });

    // Step 1: Radio Card selection behavior
    const goalCards = modal.querySelectorAll('.wizard-choice-card');
    goalCards.forEach(card => {
      card.addEventListener('click', () => {
        goalCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        const radio = card.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          // Trigger change event manually
          const event = new Event('change', { bubbles: true });
          radio.dispatchEvent(event);
        }
      });
    });

    // Step 2 Preview Builder
    const nameInput = form.querySelector('[name="wiz_name"]');
    const descTextarea = form.querySelector('[name="wiz_character"]');
    const templateSelect = form.querySelector('[name="wiz_template"]');

    [nameInput, descTextarea, templateSelect].forEach(el => {
      if (el) el.addEventListener('input', updatePromptPreview);
      if (el) el.addEventListener('change', updatePromptPreview);
    });

    // Template change defaults
    if (templateSelect) {
      templateSelect.addEventListener('change', (e) => {
        applyTemplateDefaults(e.target.value);
      });
    }

    // Step 3 Action Checkboxes styling & Visualizer binding
    const actionCheckboxes = modal.querySelectorAll('.wizard-action-checkbox');
    actionCheckboxes.forEach(label => {
      label.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return; // let default happen
        const input = label.querySelector('input[type="checkbox"]');
        if (input) {
          e.preventDefault();
          input.checked = !input.checked;
          const event = new Event('change', { bubbles: true });
          input.dispatchEvent(event);
        }
      });

      const input = label.querySelector('input[type="checkbox"]');
      if (input) {
        input.addEventListener('change', () => {
          label.classList.toggle('selected', input.checked);
          updateVisualizerGrid();
        });
      }
    });

    const directionSelect = document.getElementById('wizDirectionSelect');
    if (directionSelect) {
      directionSelect.addEventListener('change', () => setSelectedDirections([directionSelect.value]));
    }

    const presetButtons = modal.querySelectorAll('.wiz-action-preset');
    presetButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const actions = (btn.dataset.wizActions || '').split(',').map(a => a.trim()).filter(Boolean);
        setSelectedActions(actions);
      });
    });

    const directionCheckboxes = modal.querySelectorAll('.wizard-direction-checkbox:not(.wizard-perspective-checkbox)');
    directionCheckboxes.forEach(label => {
      label.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        const input = label.querySelector('input[type="checkbox"]');
        if (input) {
          e.preventDefault();
          input.checked = !input.checked;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });

      const input = label.querySelector('input[type="checkbox"]');
      if (input) {
        input.addEventListener('change', () => {
          if (!input.checked && getSelectedDirections().length === 0) {
            input.checked = true;
            toast('Select at least one direction.');
          }
          label.classList.toggle('selected', input.checked);
          const firstDirection = getSelectedDirections()[0];
          if (directionSelect && firstDirection) directionSelect.value = firstDirection;
          updateVisualizerGrid();
        });
      }
    });

    const perspectiveSelect = document.getElementById('wizPerspectiveSelect');
    if (perspectiveSelect) {
      perspectiveSelect.addEventListener('change', () => setSelectedPerspective(perspectiveSelect.value));
    }

    const perspectiveRadios = modal.querySelectorAll('.wizard-perspective-checkbox');
    perspectiveRadios.forEach(label => {
      label.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        const input = label.querySelector('input[type="radio"]');
        if (input) {
          e.preventDefault();
          input.checked = true;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });

      const input = label.querySelector('input[type="radio"]');
      if (input) {
        input.addEventListener('change', () => setSelectedPerspective(input.value));
      }
    });

    // Step 1 goal changes show/hide inputs
    const goals = form.querySelectorAll('[name="wiz_goal"]');
    goals.forEach(radio => {
      radio.addEventListener('change', () => {
        const isConvert = getSelectedGoal() === 'convert';
        const videoPathLabel = document.getElementById('wizVideoPathLabel');
        if (videoPathLabel) {
          videoPathLabel.style.display = isConvert ? 'flex' : 'none';
        }
        updateVisualizerGrid();
      });
    });

    // Load persisted state if exists
    loadWizardState();
    updatePromptPreview();
    updateVisualizerGrid();
  }

  function getSelectedGoal() {
    const checked = form.querySelector('[name="wiz_goal"]:checked');
    return checked ? checked.value : 'single';
  }

  function getSelectedActions() {
    return Array.from(modal.querySelectorAll('.wizard-action-checkbox input[type="checkbox"]:checked')).map(i => i.value);
  }

  function getSelectedDirections() {
    const checked = Array.from(modal.querySelectorAll('.wizard-direction-checkbox:not(.wizard-perspective-checkbox) input[type="checkbox"]:checked')).map(i => i.value);
    const fallback = document.getElementById('wizDirectionSelect')?.value || 'right';
    return checked.length ? checked : [fallback];
  }

  function getSelectedPerspective() {
    return document.getElementById('wizPerspectiveSelect')?.value || 'side_view';
  }

  function setSelectedActions(actions) {
    const selected = new Set(actions);
    modal.querySelectorAll('.wizard-action-checkbox').forEach(label => {
      const input = label.querySelector('input[type="checkbox"]');
      if (!input) return;
      input.checked = selected.has(input.value);
      label.classList.toggle('selected', input.checked);
    });
    updateVisualizerGrid();
  }

  function setSelectedDirections(directions) {
    const selected = new Set(directions);
    modal.querySelectorAll('.wizard-direction-checkbox:not(.wizard-perspective-checkbox)').forEach(label => {
      const input = label.querySelector('input[type="checkbox"]');
      if (!input) return;
      input.checked = selected.has(input.value);
      label.classList.toggle('selected', input.checked);
    });
    const select = document.getElementById('wizDirectionSelect');
    if (select && directions[0]) select.value = directions[0];
    updateVisualizerGrid();
  }

  function setSelectedPerspective(perspective) {
    const select = document.getElementById('wizPerspectiveSelect');
    if (select) select.value = perspective;
    modal.querySelectorAll('.wizard-perspective-checkbox').forEach(label => {
      const input = label.querySelector('input[type="radio"]');
      if (!input) return;
      input.checked = input.value === perspective;
      label.classList.toggle('selected', input.checked);
    });
    updatePromptPreview();
    updateVisualizerGrid();
  }

  function setStep(step) {
    currentStep = Math.max(1, Math.min(4, step));

    // Update panels
    stepPanels.forEach(panel => {
      panel.classList.toggle('active', parseInt(panel.dataset.wizPanel) === currentStep);
    });

    // Update indicators
    stepperIndicators.forEach(ind => {
      const stepNum = parseInt(ind.dataset.wizStep);
      ind.classList.toggle('active', stepNum === currentStep);
      ind.classList.toggle('completed', stepNum < currentStep);
    });

    // Footer buttons
    backBtn.disabled = currentStep === 1;
    if (currentStep === 4) {
      nextBtn.style.display = 'none';
      launchBtn.style.display = 'inline-block';
      buildSummaryPage();
      runPreflightCheck();
    } else {
      nextBtn.style.display = 'inline-block';
      launchBtn.style.display = 'none';
    }

    saveWizardState();
  }

  function handleNextStep() {
    if (validateStep(currentStep)) {
      setStep(currentStep + 1);
    }
  }

  function validateStep(step) {
    if (step === 1) {
      return true; // Goal is radio, always has a default checked
    }
    if (step === 2) {
      const name = form.querySelector('[name="wiz_name"]').value.trim();
      const desc = form.querySelector('[name="wiz_character"]').value.trim();

      if (!name) {
        toast('Character name is required.');
        form.querySelector('[name="wiz_name"]').focus();
        return false;
      }
      if (desc.length < 5) {
        toast('Character description must be at least 5 characters long.');
        form.querySelector('[name="wiz_character"]').focus();
        return false;
      }
      return true;
    }
    if (step === 3) {
      const goal = getSelectedGoal();
      if (goal === 'convert') {
        const video = form.querySelector('[name="wiz_video_path"]').value.trim();
        if (!video) {
          toast('Please specify a video file path to convert.');
          form.querySelector('[name="wiz_video_path"]').focus();
          return false;
        }
      } else {
        const actions = getSelectedActions();
        if (actions.length === 0) {
          toast('Please select at least one animation.');
          return false;
        }
      }
      return true;
    }
    return true;
  }

  function applyTemplateDefaults(templateName) {
    const template = WIZARD_TEMPLATES[templateName];
    if (!template) return;

    setSelectedActions(template.actions);
    setSelectedDirections(template.directions || ['right']);
    setSelectedPerspective(template.perspective || 'side_view');

    updatePromptPreview();
    updateVisualizerGrid();
  }

  function updatePromptPreview() {
    const preview = document.getElementById('wizPromptPreview');
    if (!preview) return;

    const name = form.querySelector('[name="wiz_name"]').value.trim();
    const desc = form.querySelector('[name="wiz_character"]').value.trim();
    const templateName = form.querySelector('[name="wiz_template"]').value;
    const template = WIZARD_TEMPLATES[templateName] || WIZARD_TEMPLATES.platformer;

    const style = template.style;
    const direction = getSelectedDirections()[0] || 'right';
    const perspective = getSelectedPerspective();
    const perspectivePrompt = PERSPECTIVE_PROMPTS[perspective] || PERSPECTIVE_PROMPTS.side_view;

    let previewText = `Character Name: ${name || 'hero'}\n`;
    previewText += `Description: ${desc || '...'}\n`;
    previewText += `Style Inject: ${style}, ${perspectivePrompt}\n`;
    previewText += `Primary Direction: ${direction}\n`;
    previewText += `Camera Perspective: ${perspective.replace(/_/g, ' ')}`;

    preview.textContent = previewText;
  }

  function updateVisualizerGrid() {
    const grid = document.getElementById('wizGridVisualizer');
    if (!grid) return;

    grid.innerHTML = '';
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const goal = getSelectedGoal();
    const actionCount = actions.length;
    const directionCount = directions.length;
    const jobCount = goal === 'single' ? Math.min(actionCount, 1) : actionCount * directionCount;
    const frameEstimate = Math.max(actionCount, 1) * Math.max(directionCount, 1) * 8;

    const animationCount = document.getElementById('wizAnimationCount');
    const directionCountEl = document.getElementById('wizDirectionCount');
    const jobCountEl = document.getElementById('wizJobCount');
    const frameEstimateEl = document.getElementById('wizFrameEstimate');
    if (animationCount) animationCount.textContent = String(actionCount);
    if (directionCountEl) directionCountEl.textContent = String(directionCount);
    if (jobCountEl) jobCountEl.textContent = String(jobCount);
    if (frameEstimateEl) frameEstimateEl.textContent = String(frameEstimate);

    if (goal === 'convert') {
      // Just mock a simple video conversion visualizer
      for (let i = 1; i <= 8; i++) {
        const cell = document.createElement('div');
        cell.className = 'wiz-grid-cell active';
        cell.textContent = `V-${i}`;
        grid.appendChild(cell);
      }
      return;
    }

    if (actions.length === 0) {
      grid.innerHTML = '<div style="color: var(--muted); font-size: 11px; padding: 12px; grid-column: 1/-1; text-align: center;">No animations selected</div>';
      return;
    }

    const previewLimit = 96;
    let cellCount = 0;
    actions.forEach(action => {
      directions.forEach(direction => {
        for (let i = 1; i <= 8; i++) {
          cellCount++;
          if (cellCount > previewLimit) return;
          const cell = document.createElement('div');
          cell.className = 'wiz-grid-cell active';
          cell.textContent = `${action.substring(0, 2)} ${direction.substring(0, 2)} ${i}`;
          grid.appendChild(cell);
        }
      });
    });

    if (frameEstimate > previewLimit) {
      const more = document.createElement('div');
      more.className = 'wiz-grid-cell wiz-grid-more';
      more.textContent = `+${frameEstimate - previewLimit}`;
      grid.appendChild(more);
    } else {
      const totalSlots = Math.ceil(cellCount / 8) * 8;
      for (let i = cellCount + 1; i <= totalSlots; i++) {
        const cell = document.createElement('div');
        cell.className = 'wiz-grid-cell';
        cell.textContent = '-';
        grid.appendChild(cell);
      }
    }
  }

  function buildSummaryPage() {
    const goal = getSelectedGoal();
    const name = form.querySelector('[name="wiz_name"]').value.trim();
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const perspective = getSelectedPerspective();

    const goalLabels = {
      single: 'Single Sprite',
      pack: 'Character Pack',
      convert: 'Convert Video',
      release: 'Prepare Release'
    };

    document.getElementById('wizSummaryGoal').textContent = goalLabels[goal] || goal;
    document.getElementById('wizSummaryName').textContent = name;
    document.getElementById('wizSummaryAnimations').textContent = goal === 'convert' ? 'N/A' : (actions.join(', ') || 'None');
    document.getElementById('wizSummaryDirection').textContent = directions.join(', ');
    const perspectiveSummary = document.getElementById('wizSummaryPerspective');
    if (perspectiveSummary) perspectiveSummary.textContent = perspective.replace(/_/g, ' ');
  }

  async function runPreflightCheck() {
    const list = document.getElementById('wizPreflightList');
    const errBox = document.getElementById('wizPreflightError');
    if (!list) return;

    // Set checking state
    list.querySelectorAll('li').forEach(li => {
      li.querySelector('span').textContent = '⏳';
    });
    if (errBox) errBox.style.display = 'none';

    try {
      // Reuse the global status check endpoint or general status data
      let statusData = window._latestStatus;
      if (!statusData && typeof refreshAll === 'function') {
        await refreshAll();
        statusData = window._latestStatus;
      }

      if (statusData) {
        const comfyLi = document.getElementById('wiz-check-comfy');
        const modelsLi = document.getElementById('wiz-check-models');
        const diskLi = document.getElementById('wiz-check-disk');
        const jobLi = document.getElementById('wiz-check-job');

        const comfyOk = !!statusData.comfy_running;
        const modelsOk = !!(statusData.models && statusData.models.ok);
        const freeGb = statusData.disk ? parseFloat(statusData.disk.free_gb) : 0;
        const diskOk = freeGb >= 5;
        const jobOk = !(statusData.job && statusData.job.running);

        if (comfyLi) comfyLi.querySelector('span').textContent = comfyOk ? '✅' : '❌';
        if (modelsLi) modelsLi.querySelector('span').textContent = modelsOk ? '✅' : '❌';
        if (diskLi) diskLi.querySelector('span').textContent = diskOk ? '✅' : '❌';
        if (jobLi) jobLi.querySelector('span').textContent = jobOk ? '✅' : '❌';

        if (!comfyOk || !modelsOk || !diskOk || !jobOk) {
          const reasons = [];
          if (!comfyOk) reasons.push('ComfyUI is offline.');
          if (!modelsOk) reasons.push('Models are not downloaded.');
          if (!diskOk) reasons.push('Free space is below 5 GB.');
          if (!jobOk) reasons.push('Another task is already running.');

          if (errBox) {
            errBox.textContent = 'Warning: Preflight check failed! ' + reasons.join(' ');
            errBox.style.display = 'block';
          }
        }
      } else {
        list.querySelectorAll('li').forEach(li => {
          li.querySelector('span').textContent = '❓';
        });
      }
    } catch (e) {
      console.error(e);
      list.querySelectorAll('li').forEach(li => {
        li.querySelector('span').textContent = '❌';
      });
      if (errBox) {
        errBox.textContent = 'Preflight failed: ' + e.message;
        errBox.style.display = 'block';
      }
    }
  }

  async function submitWizard() {
    const goal = getSelectedGoal();
    const name = form.querySelector('[name="wiz_name"]').value.trim();
    const desc = form.querySelector('[name="wiz_character"]').value.trim();
    const templateName = form.querySelector('[name="wiz_template"]').value;
    const template = WIZARD_TEMPLATES[templateName] || WIZARD_TEMPLATES.platformer;
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const direction = directions[0] || 'right';
    const perspective = getSelectedPerspective();
    const perspectivePrompt = PERSPECTIVE_PROMPTS[perspective] || PERSPECTIVE_PROMPTS.side_view;
    const quality = document.getElementById('wizQualitySelect').value;

    // Pre-calculate advisor recommend profiles
    let rec = { tier: 'wan21_safe', profile: 'auto' };
    try {
      const recRes = await api(`/api/advisor?quality=${encodeURIComponent(quality || 'balanced')}`);
      if (recRes && recRes.tier) rec = recRes;
    } catch (e) {
      if (quality === 'quality') rec = { tier: 'wan22_5b', profile: 'wan22_5b_local' };
      else if (quality === 'fast') rec = { tier: 'wan21_safe', profile: 'debug' };
    }

    const payload = {
      name: name || 'hero',
      character: desc,
      description: desc,
      style: `${template.style}, ${perspectivePrompt}`,
      sprite_action: actions[0] || 'idle',
      actions: actions.join(','),
      direction: direction,
      directions: directions.join(','),
      perspective: perspective,
      tier: rec.tier || 'wan21_safe',
      profile: rec.profile || 'auto',
      start_comfy: true,
      quality_check: true
    };

    closeWizard();
    toast('Wizard configured! Launching sprite generation...');

    if (goal === 'single') {
      if (typeof runAction === 'function') {
        await runAction('generate_sprite', payload);
        if (typeof showView === 'function') showView('logs');
      }
    } else if (goal === 'pack') {
      if (typeof runAction === 'function') {
        await runAction('queue_create', payload);
        if (typeof showView === 'function') showView('queues');
      }
    } else if (goal === 'convert') {
      const video = form.querySelector('[name="wiz_video_path"]').value.trim();
      if (typeof runAction === 'function') {
        await runAction('convert_video', {
          input: video,
          fps: 12,
          cell_size: '512x512',
          key_color: 'auto',
          drop_loop_duplicate: true,
          preview_gif: true,
          report: true
        });
        if (typeof showView === 'function') showView('logs');
      }
    } else if (goal === 'release') {
      const sprites = selectedSpriteDir || '';
      if (typeof runAction === 'function') {
        await runAction('release_package', { name: `${name}_sprite_pack`, sprites });
        if (typeof showView === 'function') showView('logs');
      }
    }

    // Reset wizard
    localStorage.removeItem(STORAGE_KEY);
    currentStep = 1;
    setStep(1);
  }

  function skipToAdvanced() {
    closeWizard();
    if (typeof showView === 'function') {
      const goal = getSelectedGoal();
      if (goal === 'convert') showView('convert');
      else if (goal === 'release') showView('release');
      else if (goal === 'pack') showView('queue');
      else showView('generate');
    }
  }

  function openWizard(initialGoal) {
    if (!modal) {
      loadWizardHtml().then(() => openWizard(initialGoal)).catch(e => console.error('Error opening wizard:', e));
      return;
    }
    modal.classList.remove('hidden');

    if (initialGoal) {
      const radio = form.querySelector(`input[name="wiz_goal"][value="${initialGoal}"]`);
      if (radio) {
        radio.checked = true;
        const card = document.getElementById(`wizCardGoal${initialGoal.charAt(0).toUpperCase() + initialGoal.slice(1)}`);
        if (card) {
          modal.querySelectorAll('.wizard-choice-card').forEach(c => c.classList.remove('selected'));
          card.classList.add('selected');
        }
        // Dispatch event
        radio.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }

    // Trigger pre-filled templates preview
    updatePromptPreview();
    updateVisualizerGrid();
  }

  function closeWizard() {
    if (!modal) return;
    modal.classList.add('hidden');
  }

  function saveWizardState() {
    const name = form.querySelector('[name="wiz_name"]').value;
    const desc = form.querySelector('[name="wiz_character"]').value;
    const template = form.querySelector('[name="wiz_template"]').value;
    const goal = getSelectedGoal();
    const video = form.querySelector('[name="wiz_video_path"]').value;
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const perspective = getSelectedPerspective();

    const state = {
      currentStep,
      goal,
      name,
      desc,
      template,
      video,
      actions,
      directions,
      perspective
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function loadWizardState() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      const state = JSON.parse(saved);

      if (state.currentStep) currentStep = state.currentStep;

      // Restore Goal
      if (state.goal) {
        const radio = form.querySelector(`input[name="wiz_goal"][value="${state.goal}"]`);
        if (radio) {
          radio.checked = true;
          const cardId = `wizCardGoal${state.goal.charAt(0).toUpperCase() + state.goal.slice(1)}`;
          const card = document.getElementById(cardId);
          if (card) {
            modal.querySelectorAll('.wizard-choice-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
          }
          // trigger change event
          radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }

      // Restore fields
      if (state.name) form.querySelector('[name="wiz_name"]').value = state.name;
      if (state.desc) form.querySelector('[name="wiz_character"]').value = state.desc;
      if (state.template) form.querySelector('[name="wiz_template"]').value = state.template;
      if (state.video) form.querySelector('[name="wiz_video_path"]').value = state.video;
      if (Array.isArray(state.actions)) setSelectedActions(state.actions);
      if (Array.isArray(state.directions)) setSelectedDirections(state.directions);
      if (state.perspective) setSelectedPerspective(state.perspective);

      setStep(currentStep);
    } catch (e) {
      console.error('Error loading wizard state:', e);
    }
  }

  async function loadWizardHtml() {
    const container = document.getElementById('wizardContainer');
    if (!container) return;
    try {
      const res = await fetch('/web/components/wizard.html');
      if (res.ok) {
        container.innerHTML = await res.text();
        initWizard();
        exposeWizardGlobals();
      }
    } catch (e) {
      console.error('Error loading wizard component:', e);
    }
  }

  // Document Ready bindings
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadWizardHtml);
  } else {
    loadWizardHtml();
  }

  function exposeWizardGlobals() {
    if (typeof window.openWizard === 'function') {
      window.openWizard.impl = openWizard;
      if (Array.isArray(window.openWizard.pendingArgs)) {
        const args = window.openWizard.pendingArgs;
        window.openWizard.pendingArgs = null;
        openWizard.apply(null, args);
      }
    } else {
      window.openWizard = openWizard;
    }

    if (typeof window.closeWizard === 'function') {
      window.closeWizard.impl = closeWizard;
    } else {
      window.closeWizard = closeWizard;
    }
  }

  // Expose global methods
  exposeWizardGlobals();

})();
