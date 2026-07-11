(function () {
  'use strict';

  function renderWizardStep(options) {
    const step = Math.max(1, Math.min(4, Number(options.step) || 1));
    options.stepPanels.forEach(panel => {
      const active = parseInt(panel.dataset.wizPanel) === step;
      panel.classList.toggle('active', active);
      panel.setAttribute('aria-hidden', active ? 'false' : 'true');
      if ('inert' in panel) panel.inert = !active;
    });
    options.stepperIndicators.forEach(ind => {
      const stepNum = parseInt(ind.dataset.wizStep);
      ind.classList.toggle('active', stepNum === step);
      ind.classList.toggle('completed', stepNum < step);
      if (stepNum === step) ind.setAttribute('aria-current', 'step');
      else ind.removeAttribute('aria-current');
    });
    options.backBtn.disabled = step === 1;
    if (step === 4) {
      options.nextBtn.style.display = 'none';
      options.launchBtn.style.display = 'inline-block';
      if (typeof options.onSummary === 'function') options.onSummary();
      if (typeof options.onPreflight === 'function') options.onPreflight();
    } else {
      options.nextBtn.style.display = 'inline-block';
      options.launchBtn.style.display = 'none';
    }
    return step;
  }

  function renderVisualizerGrid(options) {
    const grid = options.grid;
    if (!grid) return;
    const actions = options.actions || [];
    const directions = options.directions || [];
    const goal = options.goal || 'single';
    const actionCount = actions.length;
    const directionCount = directions.length;
    const jobCount = goal === 'single' ? Math.min(actionCount, 1) : actionCount * directionCount;
    const frameEstimate = Math.max(actionCount, 1) * Math.max(directionCount, 1) * 8;

    grid.innerHTML = '';
    if (options.animationCount) options.animationCount.textContent = String(actionCount);
    if (options.directionCountEl) options.directionCountEl.textContent = String(directionCount);
    if (options.jobCountEl) options.jobCountEl.textContent = String(jobCount);
    if (options.frameEstimateEl) options.frameEstimateEl.textContent = String(frameEstimate);

    if (goal === 'convert') {
      for (let i = 1; i <= 8; i += 1) {
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
        for (let i = 1; i <= 8; i += 1) {
          cellCount += 1;
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
      for (let i = cellCount + 1; i <= totalSlots; i += 1) {
        const cell = document.createElement('div');
        cell.className = 'wiz-grid-cell';
        cell.textContent = '-';
        grid.appendChild(cell);
      }
    }
  }

  function renderSummaryPage(options) {
    const goalLabels = {
      single: 'Single Sprite',
      pack: 'Character Pack',
      convert: 'Convert Video',
      release: 'Prepare Release'
    };
    document.getElementById('wizSummaryGoal').textContent = goalLabels[options.goal] || options.goal;
    document.getElementById('wizSummaryName').textContent = options.name;
    document.getElementById('wizSummaryAnimations').textContent = options.goal === 'convert' ? 'N/A' : (options.actions.join(', ') || 'None');
    document.getElementById('wizSummaryDirection').textContent = options.directions.join(', ');
    const perspectiveSummary = document.getElementById('wizSummaryPerspective');
    if (perspectiveSummary) perspectiveSummary.textContent = String(options.perspective || 'side_view').replace(/_/g, ' ');
    const referencesSummary = document.getElementById('wizSummaryReferences');
    if (referencesSummary) {
      const refs = [];
      if (options.referenceImage) refs.push('Character');
      if (options.styleImage) refs.push('Style');
      referencesSummary.textContent = refs.length ? refs.join(' + ') : 'None';
    }
  }

  function renderPreflightChecking(list, errBox) {
    if (!list) return;
    const launch = document.getElementById('wizardLaunchBtn');
    if (launch) launch.disabled = true;
    list.querySelectorAll('li').forEach(li => {
      li.querySelector('span').textContent = '⏳';
    });
    if (errBox) {
      errBox.replaceChildren();
      errBox.style.display = 'none';
    }
  }

  function renderPreflightRepair(errBox, message) {
    if (!errBox) return;
    errBox.style.color = 'var(--danger)';
    const copy = document.createElement('span');
    copy.textContent = message;
    const repair = document.createElement('button');
    repair.type = 'button';
    repair.className = 'mini wizard-preflight-repair';
    repair.textContent = 'Fix setup';
    repair.addEventListener('click', () => {
      window.closeWizard?.();
      window.showView?.('setup');
    });
    errBox.replaceChildren(copy, repair);
    errBox.style.display = 'flex';
  }

  function renderPreflightNotice(errBox, message) {
    if (!errBox) return;
    const copy = document.createElement('span');
    copy.textContent = message;
    errBox.replaceChildren(copy);
    errBox.style.color = 'var(--yellow)';
    errBox.style.display = 'flex';
  }

  function renderPreflightResult(result, errBox) {
    const launch = document.getElementById('wizardLaunchBtn');
    if (result.unknown) {
      document.querySelectorAll('#wizPreflightList li').forEach(li => {
        li.querySelector('span').textContent = '❓';
      });
      if (launch) launch.disabled = true;
      renderPreflightRepair(errBox, 'SpriteForge is still checking the workshop. Open Settings if this takes more than a moment.');
      return;
    }
    const map = {
      comfy: document.getElementById('wiz-check-comfy'),
      models: document.getElementById('wiz-check-models'),
      disk: document.getElementById('wiz-check-disk'),
      job: document.getElementById('wiz-check-job')
    };
    Object.entries(map).forEach(([key, item]) => {
      if (!item) return;
      const isApplicable = result.applicable?.[key] !== false;
      const isOptionalNotice = isApplicable && result.required?.[key] === false && !result.checks[key];
      const icon = !isApplicable ? '➖' : (isOptionalNotice ? '⚠️' : (result.checks[key] ? '✅' : '❌'));
      item.querySelector('span').textContent = icon;
      item.dataset.preflightState = !isApplicable ? 'not-applicable' : (isOptionalNotice ? 'notice' : (result.checks[key] ? 'ready' : 'blocked'));
    });
    if (launch) launch.disabled = !result.ok;
    if (!result.ok && errBox) {
      const details = [...result.reasons, ...(result.notices || [])].join(' ');
      renderPreflightRepair(errBox, details);
    } else if (result.notices?.length && errBox) {
      renderPreflightNotice(errBox, result.notices.join(' '));
    } else if (errBox) {
      errBox.replaceChildren();
      errBox.style.display = 'none';
    }
  }

  function renderPreflightError(list, errBox, error) {
    const launch = document.getElementById('wizardLaunchBtn');
    if (launch) launch.disabled = true;
    if (list) {
      list.querySelectorAll('li').forEach(li => {
        li.querySelector('span').textContent = '❌';
      });
    }
    if (errBox) {
      renderPreflightRepair(errBox, `SpriteForge could not finish the ready check: ${error.message}`);
    }
  }

  window.SpriteForgeWizardUi = {
    renderWizardStep,
    renderVisualizerGrid,
    renderSummaryPage,
    renderPreflightChecking,
    renderPreflightResult,
    renderPreflightError
  };
})();
