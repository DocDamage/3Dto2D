(function () {
  'use strict';

  const PREFS = Object.freeze({
    sound: 'spriteforgeUiSound',
    haptics: 'spriteforgeUiHaptics',
    controller: 'spriteforgeControllerNavigation',
    assistant: 'spriteforgeLocalGuide'
  });
  const SAFE_VIEWS = new Set([
    'guide', 'dashboard', 'generate', 'aaa_studio', 'quality', 'release',
    'setup', 'tasks', 'play_workbench', 'animation_player'
  ]);
  const CREATE_STYLES = Object.freeze({
    bright: 'bright friendly adventure sprite, bold readable shapes, clean silhouette, cheerful original palette',
    pixel: 'crisp original pixel art, limited harmonious palette, readable clusters, no anti-aliasing',
    storybook: 'warm storybook game sprite, rounded readable forms, soft painted shading, original character design',
    arcade: 'energetic arcade sprite, graphic color blocking, strong pose, punchy readable silhouette'
  });
  const WORKSHOP_STAGES = Object.freeze([
    ['Sketching', 'Preparing the idea'],
    ['Animating', 'Bringing it to life'],
    ['Polishing', 'Cleaning every frame'],
    ['Packing', 'Getting it game-ready']
  ]);
  const runtime = {
    audioContext: null,
    lastJobRunning: false,
    lastJobId: null,
    status: null,
    controllerFrame: null,
    gamepadLatch: Object.create(null),
    gamepadPressed: Object.create(null),
    assistantOpen: false,
    initialized: false
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function isSimpleMode() {
    return document.body.classList.contains('mode-simple');
  }

  function reduceMotion() {
    return document.body.classList.contains('pref-reduce-motion') ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function preference(key, fallback) {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value;
  }

  function setPreference(key, value) {
    localStorage.setItem(key, String(value));
  }

  function tone(frequency, duration, delay, gainValue, type) {
    const sound = preference(PREFS.sound, 'off');
    if (sound === 'off') return;
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return;
    if (!runtime.audioContext) runtime.audioContext = new AudioCtor();
    const context = runtime.audioContext;
    const start = context.currentTime + (delay || 0);
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = type || 'sine';
    oscillator.frequency.setValueAtTime(frequency, start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(gainValue || 0.035, start + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
  }

  function cue(name) {
    const sound = preference(PREFS.sound, 'off');
    if (sound === 'off') return;
    if (name === 'success') {
      tone(392, 0.16, 0, 0.035, 'triangle');
      tone(523.25, 0.2, 0.09, 0.04, 'triangle');
      if (sound === 'full') tone(659.25, 0.28, 0.18, 0.035, 'sine');
      return;
    }
    if (name === 'error') {
      tone(196, 0.16, 0, 0.032, 'triangle');
      if (sound === 'full') tone(155.56, 0.22, 0.11, 0.028, 'triangle');
      return;
    }
    if (name === 'step') {
      tone(440, 0.08, 0, 0.024, 'sine');
      if (sound === 'full') tone(554.37, 0.1, 0.055, 0.02, 'sine');
      return;
    }
    tone(330, 0.055, 0, sound === 'full' ? 0.024 : 0.014, 'triangle');
  }

  function haptic(pattern) {
    if (preference(PREFS.haptics, 'false') !== 'true') return;
    if (typeof navigator.vibrate === 'function') navigator.vibrate(pattern || 12);
  }

  function setMascotMood(mood, message) {
    const dock = byId('forgeGuideDock');
    if (dock) dock.dataset.mood = mood || 'ready';
    const bubble = byId('forgeGuideBubble');
    if (bubble && message) bubble.textContent = message;
  }

  function celebrate(message) {
    if (reduceMotion()) {
      setMascotMood('happy', message || 'Your sprite is ready!');
      return;
    }
    const layer = document.createElement('div');
    layer.className = 'forge-celebration';
    layer.setAttribute('aria-hidden', 'true');
    const colors = ['#5cb8ff', '#66d6ad', '#ffd76a', '#ff7c91', '#826ee8'];
    for (let index = 0; index < 24; index += 1) {
      const particle = document.createElement('i');
      particle.style.setProperty('--x', `${8 + Math.random() * 84}vw`);
      particle.style.setProperty('--delay', `${Math.random() * 0.22}s`);
      particle.style.setProperty('--spin', `${Math.round(Math.random() * 540 - 270)}deg`);
      particle.style.setProperty('--color', colors[index % colors.length]);
      layer.appendChild(particle);
    }
    document.body.appendChild(layer);
    window.setTimeout(() => layer.remove(), 1800);
    setMascotMood('happy', message || 'Your sprite is ready!');
    cue('success');
    haptic([18, 28, 22]);
  }

  function companionMark() {
    return '<span class="forge-companion-mark" aria-hidden="true"><span class="forge-companion-spark"></span><span class="forge-companion-eye eye-left"></span><span class="forge-companion-eye eye-right"></span><span class="forge-companion-mouth"></span></span>';
  }

  function buildCompanion() {
    if (byId('forgeGuideDock')) return;
    const dock = document.createElement('aside');
    dock.id = 'forgeGuideDock';
    dock.className = 'forge-guide-dock';
    dock.dataset.mood = 'ready';
    dock.innerHTML = `
      <div class="forge-guide-bubble" id="forgeGuideBubble" role="status">I’m Forge. I can help with the next step.</div>
      <button class="forge-guide-toggle" id="forgeGuideToggle" type="button" aria-expanded="false" aria-controls="forgeGuidePanel" aria-label="Ask Forge for help">
        ${companionMark()}<span>Ask Forge</span>
      </button>
      <section class="forge-guide-panel" id="forgeGuidePanel" hidden aria-labelledby="forgeGuideTitle">
        <header><div>${companionMark()}<span><b id="forgeGuideTitle">Forge Guide</b><small>Local, project-aware help</small></span></div><button type="button" id="forgeGuideClose" aria-label="Close guide">×</button></header>
        <div class="forge-guide-answer" id="forgeGuideAnswer" aria-live="polite">
          <p>Ask about setup, creating a character, fixing an animation, or exporting to your engine.</p>
        </div>
        <div class="forge-guide-quick" data-spatial-nav>
          <button type="button" data-forge-question="What should I do next?">What’s next?</button>
          <button type="button" data-forge-question="Help me make my first character">First character</button>
          <button type="button" data-forge-question="Explain the current setup warning">Setup help</button>
        </div>
        <form id="forgeGuideForm">
          <label for="forgeGuideQuestion">Ask a question</label>
          <div><input id="forgeGuideQuestion" autocomplete="off" placeholder="How do I make a smooth walk cycle?" /><button type="submit">Ask</button></div>
        </form>
        <footer><span class="forge-local-dot"></span><span id="forgeGuideMode">Local retrieval</span><button type="button" data-forge-view="setup">Guide settings</button></footer>
      </section>`;
    document.body.appendChild(dock);

    const toggle = byId('forgeGuideToggle');
    const panel = byId('forgeGuidePanel');
    const close = byId('forgeGuideClose');
    const setOpen = open => {
      runtime.assistantOpen = open;
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      dock.classList.toggle('open', open);
      if (open) byId('forgeGuideQuestion')?.focus();
    };
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    close.addEventListener('click', () => {
      setOpen(false);
      toggle.focus();
    });
    dock.addEventListener('click', event => {
      const question = event.target.closest('[data-forge-question]')?.dataset.forgeQuestion;
      if (question) askForge(question);
      const view = event.target.closest('[data-forge-view]')?.dataset.forgeView;
      if (view && SAFE_VIEWS.has(view)) {
        setOpen(false);
        window.showView?.(view);
      }
    });
    byId('forgeGuideForm').addEventListener('submit', event => {
      event.preventDefault();
      const input = byId('forgeGuideQuestion');
      const question = input.value.trim();
      if (!question) return;
      askForge(question);
      input.value = '';
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && runtime.assistantOpen) {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  function renderForgeAnswer(data) {
    const root = byId('forgeGuideAnswer');
    if (!root) return;
    root.replaceChildren();
    const answer = document.createElement('p');
    answer.textContent = data.answer || 'I could not find a helpful answer yet.';
    root.appendChild(answer);
    const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
    if (suggestions.length) {
      const actions = document.createElement('div');
      actions.className = 'forge-guide-suggestions';
      actions.dataset.spatialNav = '';
      suggestions.slice(0, 3).forEach(suggestion => {
        if (!SAFE_VIEWS.has(suggestion.view)) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = suggestion.label || 'Open';
        button.dataset.forgeView = suggestion.view;
        actions.appendChild(button);
      });
      if (actions.childElementCount) root.appendChild(actions);
    }
    const sources = Array.isArray(data.sources) ? data.sources : [];
    if (sources.length) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = `${sources.length} local source${sources.length === 1 ? '' : 's'}`;
      const list = document.createElement('ul');
      sources.slice(0, 5).forEach(source => {
        const item = document.createElement('li');
        item.textContent = source.title || source.path || 'SpriteForge documentation';
        list.appendChild(item);
      });
      details.append(summary, list);
      root.appendChild(details);
    }
    const mode = byId('forgeGuideMode');
    if (mode) mode.textContent = data.mode === 'local-llm' ? 'Local model + retrieval' : 'Local retrieval';
  }

  async function askForge(question) {
    const root = byId('forgeGuideAnswer');
    if (!root) return;
    if (preference(PREFS.assistant, 'true') !== 'true') {
      renderForgeAnswer({
        answer: 'The local guide is turned off. You can enable it in Settings.',
        suggestions: [{ label: 'Open Settings', view: 'setup' }],
        sources: [],
        mode: 'disabled'
      });
      return;
    }
    root.innerHTML = '<p class="forge-thinking"><span></span><span></span><span></span> Looking through local SpriteForge knowledge…</p>';
    setMascotMood('thinking', 'Let me look through your local project knowledge.');
    try {
      const status = runtime.status || window._latestStatus || {};
      const projectSelect = byId('projectSelect');
      const data = await window.api('/api/assistant/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          project: projectSelect?.value || '',
          view: document.body.dataset.activeView || localStorage.getItem('activeView') || 'guide',
          context: {
            job_running: !!status.job?.running,
            job_stage: status.job?.stage_label || '',
            generation_ready: !!status.comfy_running && !!status.models?.ok,
            output_count: Array.isArray(status.outputs) ? status.outputs.length : 0
          }
        })
      });
      renderForgeAnswer(data || {});
      setMascotMood('ready', 'I found a useful next step.');
      cue('step');
    } catch (error) {
      renderForgeAnswer({
        answer: 'My local knowledge service is not available yet. Core SpriteForge tools still work normally.',
        suggestions: [{ label: 'Open Settings', view: 'setup' }],
        sources: [],
        mode: 'offline'
      });
      setMascotMood('concerned', 'The guide is offline, but your tools still work.');
    }
  }

  function buildHomeEnhancements() {
    const home = document.querySelector('.consumer-home');
    if (!home || home.dataset.playfulEnhanced) return;
    home.dataset.playfulEnhanced = '1';
    const mark = home.querySelector('.home-hero-mark');
    if (mark) {
      mark.classList.add('forge-home-companion');
      if (!mark.querySelector('.forge-home-mascot-art')) {
        const image = document.createElement('img');
        image.className = 'forge-home-mascot-art';
        image.src = 'assets/forge_companion.png';
        image.alt = '';
        mark.prepend(image);
      }
      const caption = document.createElement('div');
      caption.className = 'forge-home-caption';
      caption.innerHTML = '<b>Forge is ready</b><span>Your friendly workshop companion</span>';
      mark.appendChild(caption);
    }
    const projectState = byId('homeProjectState');
    if (projectState && !byId('forgeContinueButton')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = 'forgeContinueButton';
      button.className = 'forge-continue-button';
      button.hidden = true;
      button.innerHTML = '<span>Continue creating</span><b>Open your latest character</b><i aria-hidden="true">→</i>';
      button.addEventListener('click', () => window.showView?.('quality'));
      projectState.after(button);
    }
    const help = home.querySelector('.home-help-panel');
    if (help && !help.querySelector('[data-home-action="demo"]')) {
      const demo = document.createElement('button');
      demo.className = 'forge-demo-button';
      demo.type = 'button';
      demo.dataset.homeAction = 'demo';
      demo.innerHTML = '<span aria-hidden="true">▶</span><span><b>Try the demo sprite</b><small>Play before setting anything up</small></span>';
      demo.addEventListener('click', () => {
        if (SAFE_VIEWS.has('play_workbench') && byId('view-play_workbench')) window.showView?.('play_workbench');
        else window.showView?.('animation_player');
      });
      help.insertBefore(demo, help.querySelector('.secondary'));
    }
  }

  function updateJourney(status) {
    const steps = Array.from(document.querySelectorAll('.home-journey li'));
    if (!steps.length) return;
    const projectSelect = byId('projectSelect');
    const hasProject = !!projectSelect?.value || !!status?.project_workspace?.project;
    const outputs = Array.isArray(status?.outputs) ? status.outputs : [];
    const hasOutput = outputs.length > 0;
    const latest = outputs[0] || {};
    const hasQa = latest.qa_score !== undefined || latest.qa_status || latest.report_url;
    const hasRelease = Array.isArray(status?.releases) && status.releases.length > 0;
    const complete = [hasProject, hasOutput, hasQa, hasRelease];
    let activeIndex = complete.findIndex(value => !value);
    if (activeIndex < 0) activeIndex = 3;
    steps.forEach((step, index) => {
      step.classList.toggle('complete', complete[index]);
      step.classList.toggle('active', index === activeIndex);
      const number = step.querySelector('span');
      if (number) number.textContent = complete[index] ? '✓' : String(index + 1);
    });
    const continueButton = byId('forgeContinueButton');
    if (continueButton) {
      continueButton.hidden = !hasOutput;
      const title = continueButton.querySelector('b');
      if (title) title.textContent = latest.name ? `Continue ${latest.name}` : 'Open your latest character';
    }
  }

  function buildCreateFlow() {
    const form = byId('generateForm');
    if (!form || form.querySelector('.consumer-create-flow')) return;
    const flow = document.createElement('section');
    flow.className = 'consumer-create-flow';
    flow.setAttribute('aria-labelledby', 'consumerCreateTitle');
    flow.innerHTML = `
      <header class="forge-flow-header">
        ${companionMark()}
        <span><p>Character workshop</p><h3 id="consumerCreateTitle">Who are we bringing to life?</h3><small>Four friendly choices. SpriteForge handles the technical setup.</small></span>
      </header>
      <div class="forge-create-section">
        <div class="forge-step-number">1</div>
        <div><label for="simpleCharacterDescription">Describe your character</label><textarea id="simpleCharacterDescription" rows="4" placeholder="A cheerful forest courier with a yellow scarf and a sturdy satchel"></textarea><small>Focus on personality, outfit, and one memorable shape.</small></div>
      </div>
      <div class="forge-create-section">
        <div class="forge-step-number">2</div>
        <fieldset><legend>Choose a visual direction</legend><div class="forge-style-grid" data-spatial-nav>
          <button type="button" data-simple-style="bright" aria-pressed="true"><i class="style-swatch bright"></i><b>Bright adventure</b><small>Bold, friendly shapes</small></button>
          <button type="button" data-simple-style="pixel" aria-pressed="false"><i class="style-swatch pixel"></i><b>Crisp pixel</b><small>Clean limited palette</small></button>
          <button type="button" data-simple-style="storybook" aria-pressed="false"><i class="style-swatch storybook"></i><b>Storybook</b><small>Warm painted charm</small></button>
          <button type="button" data-simple-style="arcade" aria-pressed="false"><i class="style-swatch arcade"></i><b>Arcade</b><small>Punchy action poses</small></button>
        </div></fieldset>
      </div>
      <div class="forge-create-section">
        <div class="forge-step-number">3</div>
        <fieldset><legend>Pick the first moves</legend><div class="forge-move-grid" data-spatial-nav>
          <button type="button" data-simple-action="idle" aria-pressed="false"><i>◌</i><span>Idle</span></button>
          <button type="button" data-simple-action="walk" aria-pressed="true"><i>→</i><span>Walk</span></button>
          <button type="button" data-simple-action="run" aria-pressed="false"><i>»</i><span>Run</span></button>
          <button type="button" data-simple-action="attack_light" aria-pressed="false"><i>✦</i><span>Attack</span></button>
          <button type="button" data-simple-action="jump" aria-pressed="false"><i>↑</i><span>Jump</span></button>
          <button type="button" data-simple-action="cast" aria-pressed="false"><i>◇</i><span>Magic</span></button>
        </div><label class="forge-direction-field">Facing direction<select id="simpleDirection"><option value="right">Right</option><option value="left">Left</option><option value="front">Front</option><option value="back">Back</option><option value="all">All directions</option></select></label></fieldset>
      </div>
      <div class="forge-create-section">
        <div class="forge-step-number">4</div>
        <fieldset><legend>How polished should this first pass be?</legend><div class="forge-quality-grid" data-spatial-nav>
          <button type="button" data-simple-quality="fast" aria-pressed="false"><b>Quick sketch</b><small>Fastest preview</small></button>
          <button type="button" data-simple-quality="balanced" aria-pressed="true"><b>Balanced</b><small>Best starting point</small></button>
          <button type="button" data-simple-quality="quality" aria-pressed="false"><b>Extra polish</b><small>More time, finer result</small></button>
        </div></fieldset>
      </div>
      <div class="forge-create-actions"><button class="forge-primary-action" id="simpleCreateButton" type="button"><span>Bring my character to life</span><small>We’ll show each workshop stage</small></button><div><button type="button" id="simpleOpenWizard">Use guided setup</button><button type="button" id="simpleOpenPro">Professional tools</button></div><p id="simpleCreateStatus" role="status"></p></div>`;
    form.prepend(flow);

    const character = form.querySelector('[name="character"]');
    const simpleCharacter = byId('simpleCharacterDescription');
    if (character && simpleCharacter) {
      simpleCharacter.value = character.value;
      simpleCharacter.addEventListener('input', () => {
        character.value = simpleCharacter.value;
        character.dispatchEvent(new Event('input', { bubbles: true }));
      });
    }
    const styleField = form.querySelector('[name="style"]');
    const initialStyle = Object.entries(CREATE_STYLES).find(([, value]) => value === styleField?.value)?.[0] || 'bright';
    flow.querySelectorAll('[data-simple-style]').forEach(button => {
      button.setAttribute('aria-pressed', button.dataset.simpleStyle === initialStyle ? 'true' : 'false');
    });
    if (styleField) {
      styleField.value = CREATE_STYLES[initialStyle];
      styleField.dispatchEvent(new Event('input', { bubbles: true }));
    }
    flow.querySelectorAll('[data-simple-style]').forEach(button => {
      button.addEventListener('click', () => {
        flow.querySelectorAll('[data-simple-style]').forEach(item => item.setAttribute('aria-pressed', item === button ? 'true' : 'false'));
        if (styleField) {
          styleField.value = CREATE_STYLES[button.dataset.simpleStyle] || CREATE_STYLES.bright;
          styleField.dispatchEvent(new Event('input', { bubbles: true }));
        }
        cue('step');
      });
    });
    flow.querySelectorAll('[data-simple-action]').forEach(button => {
      button.addEventListener('click', () => {
        const action = button.dataset.simpleAction;
        const source = form.querySelector(`[data-generate-action][value="${action}"]`);
        const next = button.getAttribute('aria-pressed') !== 'true';
        const selectedCount = flow.querySelectorAll('[data-simple-action][aria-pressed="true"]').length;
        if (!next && selectedCount <= 1) {
          byId('simpleCreateStatus').textContent = 'Keep at least one move selected.';
          cue('error');
          return;
        }
        button.setAttribute('aria-pressed', next ? 'true' : 'false');
        if (source) {
          source.checked = next;
          source.dispatchEvent(new Event('change', { bubbles: true }));
        }
        cue('click');
      });
    });
    byId('simpleDirection')?.addEventListener('change', event => {
      const value = event.target.value;
      const all = form.querySelector('[data-generate-direction-all]');
      form.querySelectorAll('[data-generate-direction]').forEach(input => {
        input.checked = value !== 'all' && input.value === value;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
      if (all) {
        all.checked = value === 'all';
        all.dispatchEvent(new Event('change', { bubbles: true }));
      }
      cue('step');
    });
    flow.querySelectorAll('[data-simple-quality]').forEach(button => {
      button.addEventListener('click', () => {
        flow.querySelectorAll('[data-simple-quality]').forEach(item => item.setAttribute('aria-pressed', item === button ? 'true' : 'false'));
        const advisor = byId('advisorQuality');
        if (advisor) advisor.value = button.dataset.simpleQuality;
        byId('getAdvisorBtn')?.click();
        cue('step');
      });
    });
    byId('simpleCreateButton')?.addEventListener('click', () => {
      const status = byId('simpleCreateStatus');
      if (!simpleCharacter?.value.trim() || simpleCharacter.value.trim().length < 5) {
        status.textContent = 'Tell us a little more about your character first.';
        simpleCharacter?.focus();
        cue('error');
        return;
      }
      status.textContent = 'Opening the workshop…';
      setMascotMood('thinking', 'Great idea. I’ll help bring it to life.');
      cue('success');
      byId('btnSubmitGenerate')?.click();
    });
    byId('simpleOpenWizard')?.addEventListener('click', () => window.openWizard?.('single'));
    byId('simpleOpenPro')?.addEventListener('click', () => byId('proToolsToggle')?.click());
  }

  function reviewVerdict(value, goodThreshold, lowerIsBetter) {
    const number = Number.parseFloat(String(value || '').replace(/[^0-9.-]/g, ''));
    if (!Number.isFinite(number)) return { state: 'waiting', label: 'Not checked yet' };
    const good = lowerIsBetter ? number <= goodThreshold : number >= goodThreshold;
    return { state: good ? 'good' : 'attention', label: good ? 'Looks good' : 'Could use polish' };
  }

  function buildReviewFlow() {
    const view = byId('view-quality');
    const workbench = view?.querySelector('.quality-workbench');
    if (!view || !workbench || view.querySelector('.consumer-review-flow')) return;
    const section = document.createElement('section');
    section.className = 'consumer-review-flow';
    section.innerHTML = `
      <header class="forge-flow-header">${companionMark()}<span><p>Playtest report</p><h3>How does your character feel?</h3><small>Three clear checks, with deeper tools available in Professional mode.</small></span></header>
      <div class="forge-verdict-grid">
        <article data-review-verdict="motion"><span class="verdict-icon">↝</span><div><b>Motion</b><strong>Not checked yet</strong><small>Feet and body stay steady</small></div></article>
        <article data-review-verdict="loop"><span class="verdict-icon">↻</span><div><b>Loop</b><strong>Not checked yet</strong><small>First and last frames connect</small></div></article>
        <article data-review-verdict="silhouette"><span class="verdict-icon">◆</span><div><b>Silhouette</b><strong>Not checked yet</strong><small>The pose reads at game size</small></div></article>
      </div>
      <div class="forge-review-actions" data-spatial-nav><button class="forge-primary-action" type="button" data-simple-review="qa">Run a friendly check</button><button type="button" data-simple-review="fix">Polish it for me</button><button type="button" data-simple-review="play">Playtest character</button></div>`;
    workbench.before(section);
    section.addEventListener('click', event => {
      const action = event.target.closest('[data-simple-review]')?.dataset.simpleReview;
      if (action === 'qa') view.querySelector('[data-quality="qa"]')?.click();
      if (action === 'fix') view.querySelector('[data-quality="fix"]')?.click();
      if (action === 'play') {
        if (byId('view-play_workbench')) window.showView?.('play_workbench');
        else window.showView?.('animation_player');
      }
      if (action) cue('step');
    });
    const metrics = [byId('obj-metric-loop'), byId('obj-metric-drift'), byId('inspect-issues')].filter(Boolean);
    if (metrics.length) {
      const observer = new MutationObserver(refreshReviewVerdicts);
      metrics.forEach(metric => observer.observe(metric, { childList: true, subtree: true, characterData: true }));
    }
    refreshReviewVerdicts();
  }

  function refreshReviewVerdicts() {
    const loop = reviewVerdict(byId('obj-metric-loop')?.textContent, 15, true);
    const motion = reviewVerdict(byId('obj-metric-drift')?.textContent, 2, true);
    const issues = byId('inspect-issues');
    let silhouette = { state: 'waiting', label: 'Not checked yet' };
    if (issues && issues.textContent.trim() && !/no issues|none|select/i.test(issues.textContent)) silhouette = { state: 'attention', label: 'Review suggested' };
    else if (issues && /no issues|passed|clear/i.test(issues.textContent)) silhouette = { state: 'good', label: 'Looks good' };
    [['motion', motion], ['loop', loop], ['silhouette', silhouette]].forEach(([name, verdict]) => {
      const card = document.querySelector(`[data-review-verdict="${name}"]`);
      if (!card) return;
      card.dataset.state = verdict.state;
      const label = card.querySelector('strong');
      if (label) label.textContent = verdict.label;
    });
  }

  function buildExportFlow() {
    const view = byId('view-release');
    const grid = view?.querySelector('.grid-2');
    const form = byId('releaseForm');
    if (!view || !grid || !form || view.querySelector('.consumer-export-flow')) return;
    const section = document.createElement('section');
    section.className = 'consumer-export-flow';
    section.innerHTML = `
      <header class="forge-flow-header">${companionMark()}<span><p>Ready for your game</p><h3>Where is this character going?</h3><small>Choose a destination. SpriteForge will pack the useful files and notes.</small></span></header>
      <div class="forge-export-targets" data-spatial-nav>
        <button type="button" data-export-target="godot" aria-pressed="true"><i>G</i><b>Godot</b><small>Import guide + metadata</small></button>
        <button type="button" data-export-target="unity" aria-pressed="false"><i>U</i><b>Unity</b><small>Sprites + import notes</small></button>
        <button type="button" data-export-target="unreal" aria-pressed="false"><i>UE</i><b>Unreal</b><small>Paper2D-ready notes</small></button>
        <button type="button" data-export-target="png" aria-pressed="false"><i>PNG</i><b>Images</b><small>Sheet + preview</small></button>
        <button type="button" data-export-target="web" aria-pressed="false"><i>WEB</i><b>Web</b><small>Animated formats</small></button>
      </div>
      <div class="forge-package-card"><span class="package-art" aria-hidden="true">✦</span><div><p>Selected creation</p><h4 id="simpleExportSource">Choose or create a character first</h4><small id="simpleExportDetail">Your latest reviewed sprite will be used automatically.</small></div><button type="button" data-simple-export="review">Choose in Review</button></div>
      <div class="forge-export-actions"><button class="forge-primary-action" id="simpleBuildRelease" type="button"><span>Pack it for my game</span><small>Includes previews, metadata, and a helpful README</small></button><p id="simpleExportStatus" role="status"></p></div>`;
    grid.before(section);
    const hiddenTarget = document.createElement('input');
    hiddenTarget.type = 'hidden';
    hiddenTarget.name = 'consumer_target';
    hiddenTarget.value = 'godot';
    form.appendChild(hiddenTarget);
    section.querySelectorAll('[data-export-target]').forEach(button => {
      button.addEventListener('click', () => {
        section.querySelectorAll('[data-export-target]').forEach(item => item.setAttribute('aria-pressed', item === button ? 'true' : 'false'));
        hiddenTarget.value = button.dataset.exportTarget;
        cue('step');
      });
    });
    section.querySelector('[data-simple-export="review"]')?.addEventListener('click', () => window.showView?.('quality'));
    byId('simpleBuildRelease')?.addEventListener('click', () => {
      const sprites = byId('releaseSprites');
      const status = byId('simpleExportStatus');
      if (!sprites?.value.trim()) {
        status.textContent = 'Choose a reviewed character first.';
        cue('error');
        return;
      }
      const project = byId('projectSelect')?.selectedOptions?.[0]?.textContent || 'spriteforge';
      const name = form.querySelector('[name="name"]');
      if (name && (!name.value || name.value === 'hero_sprite_pack')) name.value = `${project.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '').toLowerCase() || 'spriteforge'}_character_pack`;
      status.textContent = 'Packing your character…';
      form.querySelector('button[type="submit"]')?.click();
      cue('success');
    });
  }

  function refreshExport(status) {
    const outputs = Array.isArray(status?.outputs) ? status.outputs : [];
    const latest = outputs[0];
    const source = byId('simpleExportSource');
    const detail = byId('simpleExportDetail');
    const sprites = byId('releaseSprites');
    if (!latest) return;
    if (source) source.textContent = latest.name || 'Latest character';
    if (detail) detail.textContent = `${latest.frame_count || 0} frames · ${latest.qa_status || (latest.qa_score !== undefined ? `quality ${latest.qa_score}` : 'ready to review')}`;
    if (sprites && !sprites.value.trim() && latest.path) sprites.value = latest.path;
  }

  function enhanceStudio() {
    const view = byId('view-aaa_studio');
    if (!view || view.dataset.playfulEnhanced) return;
    view.dataset.playfulEnhanced = '1';
    const toolLabels = { brush: 'Brush', eraser: 'Eraser', anchor: 'Anchor', hitbox: 'Hitbox' };
    view.querySelectorAll('[data-aaa-tool]').forEach(button => {
      button.dataset.playfulLabel = toolLabels[button.dataset.aaaTool] || button.textContent.trim();
    });
    const play = byId('aaaPlayBtn');
    if (play) play.classList.add('forge-studio-play');
    const timeline = byId('aaaTimeline');
    if (timeline) timeline.dataset.spatialNav = '';
  }

  function buildWorkshopTrail() {
    const progress = byId('globalTaskProgress');
    if (!progress || byId('forgeWorkshopTrail')) return;
    const trail = document.createElement('ol');
    trail.id = 'forgeWorkshopTrail';
    trail.className = 'forge-workshop-trail';
    trail.setAttribute('aria-label', 'Sprite workshop stages');
    WORKSHOP_STAGES.forEach(([title, detail], index) => {
      const item = document.createElement('li');
      item.dataset.stage = String(index);
      item.innerHTML = `<span>${index + 1}</span><b>${title}</b><small>${detail}</small>`;
      trail.appendChild(item);
    });
    progress.appendChild(trail);
  }

  function stageFromJob(job) {
    const text = `${job?.stage_label || ''} ${job?.stage_detail || ''} ${job?.title || ''}`.toLowerCase();
    if (/pack|sheet|atlas|export|release|manifest/.test(text)) return 3;
    if (/polish|clean|extract|alpha|stabili|quality|qa|repair|matting/.test(text)) return 2;
    if (/animat|generat|sampl|diffusion|frame|video/.test(text)) return 1;
    const progress = Number(job?.progress || 0);
    if (progress >= 82) return 3;
    if (progress >= 58) return 2;
    if (progress >= 22) return 1;
    return 0;
  }

  function updateWorkshop(job) {
    const trail = byId('forgeWorkshopTrail');
    if (!trail) return;
    const running = !!job?.running;
    const done = !running && job?.exit_code === 0 && !!job?.id;
    const failed = !running && job?.exit_code !== undefined && job?.exit_code !== null && job?.exit_code !== 0;
    const active = done ? 3 : stageFromJob(job);
    trail.querySelectorAll('li').forEach((item, index) => {
      item.classList.toggle('active', running && index === active);
      item.classList.toggle('complete', done || index < active);
      item.classList.toggle('failed', failed && index === active);
      const marker = item.querySelector('span');
      if (marker) marker.textContent = done || index < active ? '✓' : String(index + 1);
    });
    if (running) setMascotMood('working', WORKSHOP_STAGES[active][1]);
    if (failed) {
      setMascotMood('concerned', 'Something snagged. I can help explain it.');
      if (runtime.lastJobRunning) cue('error');
    }
    if (done && runtime.lastJobRunning) celebrate('Your sprite is ready to play!');
    runtime.lastJobRunning = running;
    runtime.lastJobId = job?.id || runtime.lastJobId;
  }

  function buildSettings() {
    const card = document.querySelector('#view-setup .preferences-card');
    if (!card || card.querySelector('.forge-preferences')) return;
    const section = document.createElement('section');
    section.className = 'forge-preferences';
    section.innerHTML = `
      <h4>Playful workshop</h4>
      <div class="forge-preference-grid">
        <label>UI sounds<select id="prefUiSound"><option value="off">Off</option><option value="subtle">Subtle</option><option value="full">Full</option></select><small>Original interface cues only; never affects sprite audio.</small></label>
        <label class="switch"><input type="checkbox" id="prefUiHaptics" /><span></span>Gentle haptics</label>
        <label class="switch"><input type="checkbox" id="prefControllerNav" /><span></span>Controller navigation</label>
        <label class="switch"><input type="checkbox" id="prefLocalGuide" /><span></span>Local Forge guide</label>
      </div>
      <div class="forge-model-settings">
        <button class="forge-model-toggle" type="button" id="forgeModelToggle" aria-expanded="false" aria-controls="forgeModelPanel">Optional embedded language model</button>
        <div id="forgeModelPanel" class="forge-model-panel" hidden>
          <p>Retrieval works without a model. Enable this only when you have a small model running locally through Ollama or another loopback OpenAI-compatible server.</p>
          <div class="forge-model-grid">
            <label class="switch"><input type="checkbox" id="forgeModelEnabled" /><span></span>Use local model for richer answers</label>
            <label>Provider<select id="forgeModelProvider"><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible local server</option></select></label>
            <label>Loopback endpoint<input id="forgeModelEndpoint" value="http://127.0.0.1:11434" spellcheck="false" /></label>
            <label>Local model name<input id="forgeModelName" list="forgeModelChoices" placeholder="qwen3:1.7b" spellcheck="false" /><datalist id="forgeModelChoices"><option value="qwen3:1.7b"></option><option value="gemma3:1b"></option><option value="phi4-mini"></option></datalist><small>Balanced: qwen3:1.7b · Lightest: gemma3:1b · Stronger: phi4-mini</small></label>
          </div>
          <div class="forge-model-actions"><button type="button" id="forgeSaveModelSettings">Save local model settings</button><span id="forgeModelStatus" role="status">Checking local guide…</span></div>
        </div>
      </div>
      <p><b>Privacy:</b> retrieval uses approved local SpriteForge documentation and project context. Model endpoints are restricted to this computer, and suggested actions are navigation-only.</p>`;
    card.appendChild(section);
    const sound = byId('prefUiSound');
    const haptics = byId('prefUiHaptics');
    const controller = byId('prefControllerNav');
    const assistant = byId('prefLocalGuide');
    const modelToggle = byId('forgeModelToggle');
    const modelPanel = byId('forgeModelPanel');
    sound.value = preference(PREFS.sound, 'off');
    haptics.checked = preference(PREFS.haptics, 'false') === 'true';
    controller.checked = preference(PREFS.controller, 'false') === 'true';
    assistant.checked = preference(PREFS.assistant, 'true') === 'true';
    modelToggle?.addEventListener('click', () => {
      const willOpen = modelPanel.hidden;
      modelPanel.hidden = !willOpen;
      modelToggle.setAttribute('aria-expanded', String(willOpen));
      cue('tap');
    });
    sound.addEventListener('change', () => {
      setPreference(PREFS.sound, sound.value);
      if (sound.value !== 'off') cue('success');
    });
    haptics.addEventListener('change', () => {
      setPreference(PREFS.haptics, haptics.checked);
      if (haptics.checked) haptic(18);
    });
    controller.addEventListener('change', () => {
      setPreference(PREFS.controller, controller.checked);
      syncControllerLoop();
    });
    assistant.addEventListener('change', () => {
      setPreference(PREFS.assistant, assistant.checked);
      document.body.classList.toggle('forge-guide-disabled', !assistant.checked);
    });
    const refreshModelStatus = async () => {
      const output = byId('forgeModelStatus');
      try {
        const status = await window.api('/api/assistant/status');
        const llm = status.llm || {};
        byId('forgeModelEnabled').checked = !!llm.enabled;
        if (llm.provider && llm.provider !== 'invalid') byId('forgeModelProvider').value = llm.provider;
        if (llm.endpoint) byId('forgeModelEndpoint').value = llm.endpoint;
        if (llm.model) byId('forgeModelName').value = llm.model;
        output.textContent = status.mode === 'local-llm'
          ? `Local model ready: ${llm.model}`
          : 'Deterministic local retrieval is ready; model is optional.';
      } catch (error) {
        output.textContent = 'Local guide status is unavailable.';
      }
    };
    byId('forgeSaveModelSettings')?.addEventListener('click', async () => {
      const output = byId('forgeModelStatus');
      output.textContent = 'Saving local-only settings…';
      try {
        const saved = await window.api('/api/assistant/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            enabled: byId('forgeModelEnabled').checked,
            provider: byId('forgeModelProvider').value,
            endpoint: byId('forgeModelEndpoint').value.trim(),
            model: byId('forgeModelName').value.trim()
          })
        });
        output.textContent = saved.llm?.configured
          ? `Local model ready: ${saved.settings?.model || byId('forgeModelName').value.trim()}`
          : (saved.message || 'Saved. Deterministic local retrieval remains active.');
        cue('success');
      } catch (error) {
        output.textContent = error.message || 'Could not save local model settings.';
        cue('error');
      }
    });
    refreshModelStatus();
  }

  function visibleSpatialItems(container) {
    return Array.from(container.querySelectorAll('button:not([disabled]), [tabindex="0"]'))
      .filter(item => item.offsetParent !== null && item.getAttribute('aria-hidden') !== 'true');
  }

  function spatialMove(direction) {
    const active = document.activeElement;
    const container = active?.closest?.('[data-spatial-nav]');
    if (!container) return false;
    const items = visibleSpatialItems(container);
    if (items.length < 2) return false;
    const current = active.getBoundingClientRect();
    const cx = current.left + current.width / 2;
    const cy = current.top + current.height / 2;
    const candidates = items.filter(item => item !== active).map(item => {
      const rect = item.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const dx = x - cx;
      const dy = y - cy;
      const valid = direction === 'left' ? dx < -2 : direction === 'right' ? dx > 2 : direction === 'up' ? dy < -2 : dy > 2;
      const primary = direction === 'left' || direction === 'right' ? Math.abs(dx) : Math.abs(dy);
      const secondary = direction === 'left' || direction === 'right' ? Math.abs(dy) : Math.abs(dx);
      return { item, valid, score: primary + secondary * 2.25 };
    }).filter(candidate => candidate.valid).sort((a, b) => a.score - b.score);
    if (!candidates.length) return false;
    candidates[0].item.focus();
    cue('click');
    return true;
  }

  function dispatchDirection(key) {
    const direction = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' }[key];
    return direction ? spatialMove(direction) : false;
  }

  function pollController() {
    runtime.controllerFrame = null;
    if (preference(PREFS.controller, 'false') !== 'true' || typeof navigator.getGamepads !== 'function') return;
    const pad = Array.from(navigator.getGamepads()).find(Boolean);
    if (pad) {
      const now = Date.now();
      const pressed = {
        left: !!pad.buttons[14]?.pressed || pad.axes[0] < -0.65,
        right: !!pad.buttons[15]?.pressed || pad.axes[0] > 0.65,
        up: !!pad.buttons[12]?.pressed || pad.axes[1] < -0.65,
        down: !!pad.buttons[13]?.pressed || pad.axes[1] > 0.65,
        accept: !!pad.buttons[0]?.pressed,
        back: !!pad.buttons[1]?.pressed
      };
      Object.entries(pressed).forEach(([name, active]) => {
        const wasActive = !!runtime.gamepadPressed[name];
        const latch = runtime.gamepadLatch[name] || 0;
        const repeatable = ['left', 'right', 'up', 'down'].includes(name);
        if (active && (!wasActive || (repeatable && now - latch > 260))) {
          runtime.gamepadLatch[name] = now;
          if (repeatable) spatialMove(name);
          if (name === 'accept' && document.activeElement instanceof HTMLElement && document.activeElement.getClientRects().length) {
            document.activeElement.click();
          }
          if (name === 'back') runtime.assistantOpen ? byId('forgeGuideClose')?.click() : window.showView?.('guide');
        }
        runtime.gamepadPressed[name] = active;
      });
    } else {
      runtime.gamepadPressed = Object.create(null);
      runtime.gamepadLatch = Object.create(null);
    }
    runtime.controllerFrame = window.requestAnimationFrame(pollController);
  }

  function syncControllerLoop() {
    if (runtime.controllerFrame) window.cancelAnimationFrame(runtime.controllerFrame);
    runtime.controllerFrame = null;
    runtime.gamepadPressed = Object.create(null);
    runtime.gamepadLatch = Object.create(null);
    if (preference(PREFS.controller, 'false') === 'true') runtime.controllerFrame = window.requestAnimationFrame(pollController);
  }

  function bindGlobalFeedback() {
    document.addEventListener('pointerdown', event => {
      const button = event.target.closest('button');
      if (!button || button.disabled) return;
      button.classList.add('forge-pressed');
      haptic(8);
    });
    document.addEventListener('pointerup', event => event.target.closest('button')?.classList.remove('forge-pressed'));
    document.addEventListener('pointercancel', event => event.target.closest('button')?.classList.remove('forge-pressed'));
    document.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (button && !button.disabled && !button.closest('.forge-guide-toggle')) cue('click');
    });
    document.addEventListener('keydown', event => {
      if (!isSimpleMode() || event.altKey || event.ctrlKey || event.metaKey) return;
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      if (event.target.matches('input, textarea, select, [contenteditable="true"]')) return;
      if (dispatchDirection(event.key)) event.preventDefault();
    });
  }

  function enhanceAll() {
    buildCompanion();
    buildHomeEnhancements();
    buildCreateFlow();
    buildReviewFlow();
    buildExportFlow();
    enhanceStudio();
    buildWorkshopTrail();
    buildSettings();
  }

  function refreshFromStatus(status) {
    runtime.status = status || runtime.status;
    enhanceAll();
    updateJourney(status || {});
    refreshExport(status || {});
    updateWorkshop(status?.job || {});
    const dock = byId('forgeGuideDock');
    if (dock) dock.hidden = preference(PREFS.assistant, 'true') !== 'true' && !isSimpleMode();
  }

  function init() {
    if (runtime.initialized) {
      enhanceAll();
      return;
    }
    runtime.initialized = true;
    enhanceAll();
    bindGlobalFeedback();
    syncControllerLoop();
    const observer = new MutationObserver(enhanceAll);
    observer.observe(document.querySelector('.shell') || document.body, { childList: true, subtree: true });
    document.body.classList.toggle('forge-guide-disabled', preference(PREFS.assistant, 'true') !== 'true');
    if (window._latestStatus) refreshFromStatus(window._latestStatus);
  }

  window.PlayfulConsole = {
    init,
    refreshFromStatus,
    updateJob: updateWorkshop,
    cue,
    celebrate,
    ask: askForge,
    enhance: enhanceAll
  };

  if (window.onSpriteForgeReady) window.onSpriteForgeReady(init);
  else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
