function parseStateMachineStates(text) {
  return String(text || '').split(/\r?\n/).map(line => {
    const parts = line.split('|').map(part => part.trim());
    return { name: parts[0], sprite_path: parts[1], loop: parts[2] !== 'once' };
  }).filter(row => row.name && row.sprite_path);
}

function parseStateMachineTransitions(text) {
  return String(text || '').split(/\r?\n/).map(line => {
    const parts = line.split('->');
    if (parts.length < 2) return null;
    const from = parts[0].trim();
    const rest = parts[1].split(':');
    return { from, to: (rest[0] || '').trim(), condition: (rest[1] || 'trigger').trim() };
  }).filter(Boolean);
}

function stateMachineRecentStateRows() {
  return (window.currentOutputs || []).slice(0, 5).map(item => {
    const name = (item.name || item.path || 'state').replace(/_sprite$/, '');
    return `${name}|${item.path}|loop`;
  }).join('\n');
}

async function buildStateMachine() {
  const payload = {
    active_project: window.activeProjectPath || '',
    name: $('#stateMachineName')?.value || 'hero_controller',
    initial_state: $('#stateMachineInitial')?.value || '',
    states: parseStateMachineStates($('#stateMachineStates')?.value || ''),
    transitions: parseStateMachineTransitions($('#stateMachineTransitions')?.value || ''),
  };
  const result = $('#stateMachineResult');
  if (result) result.textContent = 'Building...';
  try {
    const data = await api('/api/state_machine/build', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (result) {
      result.innerHTML = `
        <span>State machine exported.</span>
        <code>${escapeHtml(data.manifest_path)}</code>
        <code>${escapeHtml(data.godot_script)}</code>
        <code>${escapeHtml(data.unity_script)}</code>
      `;
    }
    toast('State machine exported.');
  } catch (err) {
    if (result) result.textContent = 'State machine export failed.';
    toast(err.message || 'State machine export failed.');
  }
}

function installStateMachinePanel() {
  const atlasForm = $('#atlasForm');
  if (!atlasForm || $('#stateMachineCard')) return;
  const card = document.createElement('section');
  card.id = 'stateMachineCard';
  card.className = 'card form state-machine-card';
  card.innerHTML = `
    <div class="card-head">
      <h3>State Machine</h3>
      <button class="mini" id="fillStateMachineStates" type="button">Use recent</button>
    </div>
    <label>Name<input id="stateMachineName" value="hero_controller" /></label>
    <label>Initial state<input id="stateMachineInitial" value="idle" /></label>
    <label>States<textarea id="stateMachineStates" rows="4" placeholder="idle|output\\hero_idle_sprite|loop&#10;walk|output\\hero_walk_sprite|loop"></textarea></label>
    <label>Transitions<textarea id="stateMachineTransitions" rows="4" placeholder="idle -> walk: move&#10;walk -> idle: stop"></textarea></label>
    <button class="primary" id="buildStateMachineBtn" type="button">Export State Machine</button>
    <div id="stateMachineResult" class="state-machine-result">No state machine exported yet.</div>
  `;
  atlasForm.insertAdjacentElement('afterend', card);
  $('#buildStateMachineBtn')?.addEventListener('click', buildStateMachine);
  $('#fillStateMachineStates')?.addEventListener('click', () => {
    const rows = stateMachineRecentStateRows();
    if (rows) $('#stateMachineStates').value = rows;
  });
}

installStateMachinePanel();
