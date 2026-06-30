const GUIDE_TEMPLATES = {
  platformer: {
    style: 'polished 2D platformer sprite, professional character design, readable side-view silhouette, crisp pixel-friendly edges, locked camera',
    actions: ['idle', 'walk', 'run', 'jump', 'attack_light', 'hurt'],
    direction: 'right',
  },
  topdown: {
    style: 'polished top-down RPG sprite, professional character design, readable small-scale silhouette, consistent outfit, locked orthographic camera',
    actions: ['idle', 'walk', 'attack_light', 'hurt'],
    direction: 'front',
  },
  fighter: {
    style: 'polished fighting game sprite animation, professional character design, strong pose clarity, clean silhouette, consistent costume, locked camera',
    actions: ['idle', 'walk', 'attack_light', 'attack_heavy', 'hurt'],
    direction: 'right',
  },
  enemy: {
    style: 'polished game enemy sprite, bold readable silhouette, strong shape language, clean animation poses, locked camera',
    actions: ['idle', 'walk', 'attack_light', 'hurt', 'death'],
    direction: 'right',
  },
  object: {
    style: 'polished game object sprite animation, centered object, clean outline, cohesive palette, locked camera, transparent-ready background',
    actions: ['idle'],
    direction: 'front',
  },
};
let guidedStep = 1;

function setGuideStep(step){
  guidedStep = Math.max(1, Math.min(4, Number(step) || 1));
  $$('.guide-step').forEach(btn => btn.classList.toggle('active', Number(btn.dataset.guideStep) === guidedStep));
  $$('.guide-panel').forEach(panel => panel.classList.toggle('active', Number(panel.dataset.guidePanel) === guidedStep));
  if($('#guidedBack')) $('#guidedBack').disabled = guidedStep === 1;
  if($('#guidedNext')) $('#guidedNext').classList.toggle('hidden', guidedStep === 4);
  if($('#guidedRun')) $('#guidedRun').classList.toggle('ready', guidedStep === 4);
}

function guidedActions(){
  const checked = $$('#guidedActionPick input[type="checkbox"]:checked').map(i => i.value);
  return checked.length ? checked : ['idle'];
}

function applyGuideTemplate(name){
  const template = GUIDE_TEMPLATES[name] || GUIDE_TEMPLATES.platformer;
  const form = $('#guidedForm');
  if(!form) return;
  const direction = form.querySelector('[name="direction"]');
  if(direction) direction.value = template.direction;
  $$('#guidedActionPick input[type="checkbox"]').forEach(input => {
    input.checked = template.actions.includes(input.value);
  });
}

async function guideRecommendation(quality){
  try{
    return await api(`/api/advisor?quality=${encodeURIComponent(quality || 'balanced')}`);
  }catch(e){
    if(quality === 'quality') return {tier:'wan22_5b', profile:'wan22_5b_3060_best'};
    if(quality === 'fast') return {tier:'wan21_safe', profile:'debug'};
    return {tier:'wan22_5b', profile:'wan22_5b_local'};
  }
}

function guideBasePayload(form, rec){
  const data = formData(form);
  const template = GUIDE_TEMPLATES[data.template] || GUIDE_TEMPLATES.platformer;
  const actions = guidedActions();
  return {
    name: data.name || 'hero',
    character: data.character || 'single full body original game hero, professional appealing character design, heroic adult proportions, distinctive outfit, clean silhouette',
    description: data.character || 'single full body original game hero, professional appealing character design, heroic adult proportions, distinctive outfit, clean silhouette',
    style: template.style,
    sprite_action: actions[0],
    actions: actions.join(','),
    direction: data.direction || template.direction,
    directions: data.direction || template.direction,
    tier: rec.tier || 'wan21_safe',
    profile: rec.profile || 'auto',
    start_comfy: data.start_comfy !== false,
    quality_check: data.quality_check !== false,
  };
}

async function runGuidedJob(e){
  e.preventDefault();
  const form = e.currentTarget;
  const data = formData(form);
  const rec = await guideRecommendation(data.quality || 'balanced');
  const payload = guideBasePayload(form, rec);
  const goal = data.goal || 'single';
  if(goal === 'single'){
    await runAction('generate_sprite', payload);
    showView('logs');
    return;
  }
  if(goal === 'pack'){
    await runAction('queue_create', payload);
    showView('queues');
    return;
  }
  if(goal === 'convert'){
    const video = String(data.video_path || '').trim();
    if(!video){ toast('Add a video path or use Convert Video to drop a file.'); setGuideStep(3); return; }
    await runAction('convert_video', {
      input: video,
      fps: rec.fps || 12,
      cell_size: rec.cell_size || '512x512',
      key_color: 'auto',
      drop_loop_duplicate: true,
      preview_gif: true,
      report: true,
    });
    showView('logs');
    return;
  }
  if(goal === 'release'){
    const sprites = selectedSpriteDir || currentOutputs.slice(0, 6).map(o => o.path).join('\n');
    if(!sprites){ toast('No finished sprites found yet. Make or convert a sprite first.'); return; }
    await runAction('release_package', {name: `${payload.name}_sprite_pack`, sprites});
    showView('logs');
  }
}

function renderGuidedGallery(outputs){
  const list = $('#guidedGallery');
  if(!list) return;
  clearNode(list);
  if(!outputs || !outputs.length){
    appendText(list, 'div', 'No finished sprites yet.', 'empty compact');
    return;
  }
  outputs.slice(0, 4).forEach(o => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'guided-result';
    btn.dataset.path = o.path || '';
    btn.dataset.previewPath = o.path || '';
    const imgUrl = o.preview_url || o.sheet_url || '';
    if(imgUrl){
      const img = document.createElement('img');
      img.src = `${imgUrl}?t=${Date.now()}`;
      img.alt = o.name || '';
      btn.appendChild(img);
    }
    const text = document.createElement('span');
    appendText(text, 'b', o.name || 'Sprite');
    appendText(text, 'small', `${o.frame_count} frames · ${o.fps} fps`);
    btn.appendChild(text);
    list.appendChild(btn);
  });
}

// Initial Guided Mode setup
document.addEventListener('DOMContentLoaded', () => {
  if($('#guidedForm')) $('#guidedForm').addEventListener('submit', runGuidedJob);
  if($('#guidedBack')) $('#guidedBack').addEventListener('click',()=>setGuideStep(guidedStep - 1));
  if($('#guidedNext')) $('#guidedNext').addEventListener('click',()=>setGuideStep(guidedStep + 1));
  $$('.guide-step').forEach(btn=>btn.addEventListener('click',()=>setGuideStep(btn.dataset.guideStep)));
  if($('#guidedForm')) {
    const tmplSelect = $('#guidedForm').querySelector('[name="template"]');
    if (tmplSelect) tmplSelect.addEventListener('change', e=>applyGuideTemplate(e.currentTarget.value));
  }
  if($('#guidedGallery')) $('#guidedGallery').addEventListener('click', e => {
    const item = e.target.closest('[data-path]');
    if(!item) return;
    openResultPreview(item.dataset.previewPath || item.dataset.path || '');
  });
});
