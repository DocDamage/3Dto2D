(function () {
  'use strict';

  window.SpriteForgeWizardStateConfig = {
    storageKey: 'spriteforge_wizard_state',
    initialStep: 1
  };

  function saveWizardStateSnapshot(state) {
    localStorage.setItem(window.SpriteForgeWizardStateConfig.storageKey, JSON.stringify(state || {}));
  }

  function loadWizardStateSnapshot() {
    try {
      const saved = localStorage.getItem(window.SpriteForgeWizardStateConfig.storageKey);
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      console.error('Error loading wizard state:', e);
      return null;
    }
  }

  function clearWizardStateSnapshot() {
    localStorage.removeItem(window.SpriteForgeWizardStateConfig.storageKey);
  }

  function getSelectedActions(modal) {
    return Array.from(modal.querySelectorAll('.wizard-action-checkbox input[type="checkbox"]:checked')).map(i => i.value);
  }

  function getSelectedDirections(modal) {
    const checked = Array.from(modal.querySelectorAll('.wizard-direction-checkbox:not(.wizard-perspective-checkbox) input[type="checkbox"]:checked')).map(i => i.value);
    const fallback = document.getElementById('wizDirectionSelect')?.value || 'right';
    return checked.length ? checked : [fallback];
  }

  function getSelectedPerspective() {
    return document.getElementById('wizPerspectiveSelect')?.value || 'side_view';
  }

  function setSelectedActions(modal, actions, onChange) {
    const selected = new Set(actions);
    modal.querySelectorAll('.wizard-action-checkbox').forEach(label => {
      const input = label.querySelector('input[type="checkbox"]');
      if (!input) return;
      input.checked = selected.has(input.value);
      label.classList.toggle('selected', input.checked);
    });
    if (typeof onChange === 'function') onChange();
  }

  function setSelectedDirections(modal, directions, onChange) {
    const selected = new Set(directions);
    modal.querySelectorAll('.wizard-direction-checkbox:not(.wizard-perspective-checkbox)').forEach(label => {
      const input = label.querySelector('input[type="checkbox"]');
      if (!input) return;
      input.checked = selected.has(input.value);
      label.classList.toggle('selected', input.checked);
    });
    const select = document.getElementById('wizDirectionSelect');
    if (select && directions[0]) select.value = directions[0];
    if (typeof onChange === 'function') onChange();
  }

  function setSelectedPerspective(modal, perspective, onChange) {
    const select = document.getElementById('wizPerspectiveSelect');
    if (select) select.value = perspective;
    modal.querySelectorAll('.wizard-perspective-checkbox').forEach(label => {
      const input = label.querySelector('input[type="radio"]');
      if (!input) return;
      input.checked = input.value === perspective;
      label.classList.toggle('selected', input.checked);
    });
    if (typeof onChange === 'function') onChange();
  }

  window.SpriteForgeWizardState = {
    saveWizardStateSnapshot,
    loadWizardStateSnapshot,
    clearWizardStateSnapshot,
    getSelectedActions,
    getSelectedDirections,
    getSelectedPerspective,
    setSelectedActions,
    setSelectedDirections,
    setSelectedPerspective
  };
})();
