(function () {
  'use strict';

  const WIZARD_TEMPLATES = window.SpriteForgeWizardTemplates?.templates || {};
  const PERSPECTIVE_PROMPTS = window.SpriteForgeWizardTemplates?.perspectivePrompts || {};
  const CHARACTER_PRESETS = {
    hero: 'single full body original game hero, professional appealing character design, heroic adult proportions, distinctive outfit, clean readable silhouette, consistent outfit',
    knight: 'single full body armored knight fighter, heroic adult proportions, readable weapon silhouette, distinctive armor plates, clean silhouette, consistent outfit',
    mage: 'single full body fantasy mage caster, robe and staff, readable magical silhouette, distinctive accessories, clean silhouette, consistent outfit',
    rogue: 'single full body agile rogue ranger, hooded adventure outfit, light armor, readable weapon silhouette, clean silhouette, consistent outfit',
    monster: 'single full body enemy monster creature, bold readable shape language, game-ready proportions, clean silhouette, consistent anatomy',
    npc: 'single full body town NPC character, friendly readable design, distinctive outfit, clean silhouette, consistent outfit',
    robot: 'single full body robot mech character, readable mechanical silhouette, bold armor shapes, clean silhouette, consistent materials',
  };
  let currentStep = window.SpriteForgeWizardStateConfig?.initialStep || 1;
  let wizardPreviousFocus = null;
  const STORAGE_KEY = window.SpriteForgeWizardStateConfig?.storageKey || 'spriteforge_wizard_state';

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

    modal.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeWizard();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = Array.from(modal.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
        .filter(item => item.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

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
    const presetSelect = form.querySelector('[name="wiz_character_preset"]');
    const templateSelect = form.querySelector('[name="wiz_template"]');
    const referenceInput = form.querySelector('[name="wiz_reference_image"]');
    const styleInput = form.querySelector('[name="wiz_style_image"]');

    [nameInput, descTextarea, presetSelect, templateSelect, referenceInput, styleInput].forEach(el => {
      if (el) el.addEventListener('input', updatePromptPreview);
      if (el) el.addEventListener('change', updatePromptPreview);
    });

    if (presetSelect) {
      presetSelect.addEventListener('change', () => {
        const preset = CHARACTER_PRESETS[presetSelect.value];
        if (preset && descTextarea) {
          descTextarea.value = preset;
          updatePromptPreview();
        }
      });
    }

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
    return window.SpriteForgeWizardState.getSelectedActions(modal);
  }

  function getSelectedDirections() {
    return window.SpriteForgeWizardState.getSelectedDirections(modal);
  }

  function getSelectedPerspective() {
    return window.SpriteForgeWizardState.getSelectedPerspective();
  }

  function setSelectedActions(actions) {
    window.SpriteForgeWizardState.setSelectedActions(modal, actions, updateVisualizerGrid);
  }

  function setSelectedDirections(directions) {
    window.SpriteForgeWizardState.setSelectedDirections(modal, directions, updateVisualizerGrid);
  }

  function setSelectedPerspective(perspective) {
    window.SpriteForgeWizardState.setSelectedPerspective(modal, perspective, () => {
      updatePromptPreview();
      updateVisualizerGrid();
    });
  }

  function setStep(step) {
    currentStep = window.SpriteForgeWizardUi.renderWizardStep({
      step,
      stepPanels,
      stepperIndicators,
      backBtn,
      nextBtn,
      launchBtn,
      onSummary: buildSummaryPage,
      onPreflight: runPreflightCheck
    });

    saveWizardState();
  }

  function handleNextStep() {
    if (validateStep(currentStep)) {
      setStep(currentStep + 1);
    }
  }

  function validateStep(step) {
    const result = window.SpriteForgeWizardSubmit.validateWizardStep(step, {
      name: form.querySelector('[name="wiz_name"]').value.trim(),
      desc: form.querySelector('[name="wiz_character"]').value.trim(),
      goal: getSelectedGoal(),
      video: form.querySelector('[name="wiz_video_path"]').value.trim(),
      actions: getSelectedActions()
    });
    if (!result.ok) {
      toast(result.message);
      if (result.focus) form.querySelector(`[name="${result.focus}"]`)?.focus();
    }
    return result.ok;
  }

  function applyTemplateDefaults(templateName) {
    window.SpriteForgeWizardTemplates.applyTemplateDefaults(templateName, {
      setSelectedActions,
      setSelectedDirections,
      setSelectedPerspective,
      onApplied: () => {
        updatePromptPreview();
        updateVisualizerGrid();
      }
    });
  }

  function updatePromptPreview() {
    const preview = document.getElementById('wizPromptPreview');
    if (!preview) return;

    const name = form.querySelector('[name="wiz_name"]').value.trim();
    const desc = form.querySelector('[name="wiz_character"]').value.trim();
    const templateName = form.querySelector('[name="wiz_template"]').value;
    const referenceImage = form.querySelector('[name="wiz_reference_image"]').value.trim();
    const styleImage = form.querySelector('[name="wiz_style_image"]').value.trim();
    const direction = getSelectedDirections()[0] || 'right';
    const perspective = getSelectedPerspective();
    preview.textContent = window.SpriteForgeWizardTemplates.buildPromptPreviewText({
      name,
      desc,
      templateName,
      referenceImage,
      styleImage,
      direction,
      perspective
    });
  }

  function updateVisualizerGrid() {
    const grid = document.getElementById('wizGridVisualizer');
    if (!grid) return;

    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const goal = getSelectedGoal();
    window.SpriteForgeWizardUi.renderVisualizerGrid({
      grid,
      actions,
      directions,
      goal,
      animationCount: document.getElementById('wizAnimationCount'),
      directionCountEl: document.getElementById('wizDirectionCount'),
      jobCountEl: document.getElementById('wizJobCount'),
      frameEstimateEl: document.getElementById('wizFrameEstimate')
    });
  }

  function buildSummaryPage() {
    const goal = getSelectedGoal();
    const name = form.querySelector('[name="wiz_name"]').value.trim();
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const perspective = getSelectedPerspective();
    const referenceImage = form.querySelector('[name="wiz_reference_image"]').value.trim();
    const styleImage = form.querySelector('[name="wiz_style_image"]').value.trim();
    window.SpriteForgeWizardUi.renderSummaryPage({
      goal,
      name,
      actions,
      directions,
      perspective,
      referenceImage,
      styleImage
    });
  }

  async function runPreflightCheck(options = {}) {
    const list = document.getElementById('wizPreflightList');
    const errBox = document.getElementById('wizPreflightError');
    if (!list) return;

    window.SpriteForgeWizardUi.renderPreflightChecking(list, errBox);

    try {
      let statusData = window._latestStatus;
      if (options.refresh && typeof api === 'function') {
        const query = typeof projectQuery === 'function' ? projectQuery() : '';
        statusData = await api(`/api/status${query}`);
        window._latestStatus = statusData;
      } else if (!statusData && typeof refreshAll === 'function') {
        await refreshAll();
        statusData = window._latestStatus;
      }

      const goal = getSelectedGoal();
      const result = window.SpriteForgeWizardSubmit.evaluateWizardPreflight(statusData, goal);
      window.SpriteForgeWizardUi.renderPreflightResult(result, errBox);
    } catch (e) {
      console.error(e);
      window.SpriteForgeWizardUi.renderPreflightError(list, errBox, e);
    }
  }

  async function submitWizard() {
    const goal = getSelectedGoal();
    const name = form.querySelector('[name="wiz_name"]').value.trim();
    const desc = form.querySelector('[name="wiz_character"]').value.trim();
    const templateName = form.querySelector('[name="wiz_template"]').value;
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const direction = directions[0] || 'right';
    const perspective = getSelectedPerspective();
    const quality = document.getElementById('wizQualitySelect').value;
    const referenceImage = form.querySelector('[name="wiz_reference_image"]').value.trim();
    const styleImage = form.querySelector('[name="wiz_style_image"]').value.trim();
    const video = form.querySelector('[name="wiz_video_path"]').value.trim();
    const plan = await window.SpriteForgeWizardSubmit.buildWizardGenerationPlan({
      goal,
      name,
      desc,
      templateName,
      actions,
      directions,
      direction,
      perspective,
      quality,
      referenceImage,
      styleImage,
      video,
      selectedSpriteDir
    });

    closeWizard();
    toast('Wizard configured! Launching sprite generation...');

    if (typeof runAction === 'function') {
      await runAction(plan.action, plan.payload);
      if (typeof showView === 'function') showView(plan.view);
    }

    // Reset wizard
    window.SpriteForgeWizardState?.clearWizardStateSnapshot?.();
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
    wizardPreviousFocus = document.activeElement;
    modal.classList.remove('hidden');
    const main = document.getElementById('mainContent');
    const rail = document.querySelector('.rail');
    if (main && 'inert' in main) main.inert = true;
    if (rail && 'inert' in rail) rail.inert = true;

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
    if (currentStep === 4) {
      buildSummaryPage();
      runPreflightCheck({ refresh: true });
    }
    const title = document.getElementById('wizardTitle');
    if (title) {
      title.setAttribute('tabindex', '-1');
      requestAnimationFrame(() => title.focus());
    }
  }

  function closeWizard() {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('consumer-show-advanced');
    const main = document.getElementById('mainContent');
    const rail = document.querySelector('.rail');
    if (main && 'inert' in main) main.inert = false;
    if (rail && 'inert' in rail) rail.inert = window.matchMedia('(max-width: 760px)').matches && !document.body.classList.contains('mobile-rail-open');
    if (wizardPreviousFocus && typeof wizardPreviousFocus.focus === 'function') wizardPreviousFocus.focus();
    wizardPreviousFocus = null;
  }

  function saveWizardState() {
    const name = form.querySelector('[name="wiz_name"]').value;
    const desc = form.querySelector('[name="wiz_character"]').value;
    const characterPreset = form.querySelector('[name="wiz_character_preset"]')?.value || '';
    const template = form.querySelector('[name="wiz_template"]').value;
    const goal = getSelectedGoal();
    const video = form.querySelector('[name="wiz_video_path"]').value;
    const referenceImage = form.querySelector('[name="wiz_reference_image"]').value;
    const styleImage = form.querySelector('[name="wiz_style_image"]').value;
    const actions = getSelectedActions();
    const directions = getSelectedDirections();
    const perspective = getSelectedPerspective();

    const state = {
      currentStep,
      goal,
      name,
      desc,
      characterPreset,
      template,
      video,
      referenceImage,
      styleImage,
      actions,
      directions,
      perspective
    };
    window.SpriteForgeWizardState.saveWizardStateSnapshot(state);
  }

  function loadWizardState() {
    const state = window.SpriteForgeWizardState.loadWizardStateSnapshot();
    if (!state) return;

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
    if (state.characterPreset && form.querySelector('[name="wiz_character_preset"]')) form.querySelector('[name="wiz_character_preset"]').value = state.characterPreset;
    if (state.desc) form.querySelector('[name="wiz_character"]').value = state.desc;
    if (state.template) form.querySelector('[name="wiz_template"]').value = state.template;
    if (state.video) form.querySelector('[name="wiz_video_path"]').value = state.video;
    if (state.referenceImage) form.querySelector('[name="wiz_reference_image"]').value = state.referenceImage;
    if (state.styleImage) form.querySelector('[name="wiz_style_image"]').value = state.styleImage;
    if (Array.isArray(state.actions)) setSelectedActions(state.actions);
    if (Array.isArray(state.directions)) setSelectedDirections(state.directions);
    if (state.perspective) setSelectedPerspective(state.perspective);

    setStep(currentStep);
  }

  async function loadWizardHtml() {
    const container = document.getElementById('wizardContainer');
    if (!container) return;
    try {
      const res = await fetch('components/wizard.html?v=wizard-product-ready-v12');
      if (res.ok) {
        container.innerHTML = await res.text();
        initWizard();
        window.installWizardDrops?.();
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
