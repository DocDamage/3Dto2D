let promptBuilderOptionsCache = null;

function promptBuilderSelect(name, options, labels) {
  const select = document.createElement('select');
  select.id = `promptBuilder${name}`;
  options.forEach(value => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = labels?.[value] ? value.replace(/_/g, ' ') : value.replace(/_/g, ' ');
    select.appendChild(opt);
  });
  return select;
}

function promptBuilderField(labelText, input) {
  const label = document.createElement('label');
  label.textContent = labelText;
  label.appendChild(input);
  return label;
}

async function promptBuilderOptions() {
  if (!promptBuilderOptionsCache) {
    promptBuilderOptionsCache = await api('/api/prompt_builder/options');
  }
  return promptBuilderOptionsCache;
}

async function promptBuilderApply() {
  const form = $('#generateForm');
  if (!form) return;
  const body = {
    character_type: $('#promptBuilderCharacter')?.value,
    body_style: $('#promptBuilderBody')?.value,
    outfit: $('#promptBuilderOutfit')?.value,
    action: $('#promptBuilderAction')?.value,
    direction: $('#promptBuilderDirection')?.value,
    camera: $('#promptBuilderCamera')?.value,
    art_style: $('#promptBuilderArt')?.value,
    extra: $('#promptBuilderExtra')?.value,
    negative_extra: $('#promptBuilderNegative')?.value,
    reference: !!form.elements.reference_image?.value,
  };
  const res = await api('/api/prompt_builder/build', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const prompt = res.prompt || {};
  if (form.elements.character) form.elements.character.value = prompt.generated_character || body.character_type || '';
  if (form.elements.style) form.elements.style.value = prompt.generated_style || body.art_style || '';
  if (form.elements.prompt) form.elements.prompt.value = prompt.positive || '';
  if (form.elements.negative) form.elements.negative.value = prompt.negative || '';
  if (form.elements.sprite_action) form.elements.sprite_action.value = prompt.action || body.action || 'idle';
  if (form.elements.direction) form.elements.direction.value = prompt.direction || body.direction || 'right';
  if (form.elements.fps && prompt.recommended_fps) form.elements.fps.value = prompt.recommended_fps;
  toast('Prompt wizard applied to Generate Sprite.');
}

async function promptBuilderInstall() {
  const form = $('#generateForm');
  if (!form || $('#promptBuilderCard')) return;
  const opts = await promptBuilderOptions();
  const card = document.createElement('section');
  card.id = 'promptBuilderCard';
  card.className = 'prompt-builder';
  card.innerHTML = '<p class="eyebrow">AI Prompt Wizard</p><div class="prompt-builder-grid"></div>';
  const grid = $('.prompt-builder-grid', card);

  const character = document.createElement('input');
  character.id = 'promptBuilderCharacter';
  character.value = 'original game hero';
  grid.appendChild(promptBuilderField('Character type', character));
  grid.appendChild(promptBuilderField('Body style', promptBuilderSelect('Body', Object.keys(opts.body_styles || {}), opts.body_styles)));

  const outfit = document.createElement('input');
  outfit.id = 'promptBuilderOutfit';
  outfit.value = 'distinctive adventure outfit';
  grid.appendChild(promptBuilderField('Outfit', outfit));
  grid.appendChild(promptBuilderField('Action', promptBuilderSelect('Action', opts.actions || ['idle'])));
  grid.appendChild(promptBuilderField('Direction', promptBuilderSelect('Direction', opts.directions || ['right'])));
  grid.appendChild(promptBuilderField('Camera', promptBuilderSelect('Camera', Object.keys(opts.camera_styles || {}), opts.camera_styles)));
  grid.appendChild(promptBuilderField('Art style', promptBuilderSelect('Art', Object.keys(opts.art_styles || {}), opts.art_styles)));

  const extra = document.createElement('textarea');
  extra.id = 'promptBuilderExtra';
  extra.rows = 2;
  extra.placeholder = 'Optional action, mood, material, or silhouette notes';
  grid.appendChild(promptBuilderField('Extra notes', extra));

  const negative = document.createElement('input');
  negative.id = 'promptBuilderNegative';
  negative.placeholder = 'Optional extra negative tokens';
  grid.appendChild(promptBuilderField('Avoid', negative));

  const apply = document.createElement('button');
  apply.type = 'button';
  apply.className = 'mini primary';
  apply.textContent = 'Build Prompt';
  apply.addEventListener('click', promptBuilderApply);
  card.appendChild(apply);

  const anchor = form.querySelector('.preset-builder-card');
  if (anchor) anchor.insertAdjacentElement('afterend', card);
  else form.prepend(card);
}

promptBuilderInstall().catch(err => console.warn(err));
