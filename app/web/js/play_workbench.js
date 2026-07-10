(function () {
  'use strict';

  const DEMO_PATH = 'output/demo_sprite_no_gpu';
  const WORKBENCH_KEYS = new Set([
    'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
    'KeyA', 'KeyD', 'KeyW', 'KeyS', 'KeyJ', 'KeyK', 'KeyR', 'Space',
  ]);
  const CLIP_ALIASES = {
    idle: ['idle', 'rest', 'stand', 'breathe'],
    walk: ['walk', 'run', 'move', 'travel'],
    attack: ['attack', 'slash', 'strike', 'hit', 'shoot', 'thrust', 'cast'],
  };

  const state = {
    bound: false,
    outputs: [],
    path: '',
    bundle: null,
    meta: null,
    sheet: null,
    loadToken: 0,
    usingFallback: true,
    clips: { idle: [0], walk: [0], attack: [0] },
    clip: 'idle',
    clipCursor: 0,
    frameElapsed: 0,
    manualClip: '',
    manualClipUntil: 0,
    attacking: false,
    keys: new Set(),
    x: 400,
    y: 342,
    facing: 1,
    gamepadIndex: null,
    gamepadAttackDown: false,
    raf: 0,
    lastTick: 0,
    sceneryTime: 0,
  };

  function element(id) {
    return document.getElementById(id);
  }

  function safeNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function workbenchActive() {
    const view = element('view-play_workbench');
    return !!view && view.classList.contains('active') && !view.hidden;
  }

  function setStatus(message, tone) {
    const status = element('playWorkbenchStatus');
    if (!status) return;
    status.textContent = message;
    status.dataset.tone = tone || '';
  }

  function setGamepadStatus(message, connected) {
    const status = element('playWorkbenchGamepadStatus');
    if (!status) return;
    status.textContent = message;
    status.dataset.connected = connected ? 'true' : 'false';
  }

  function editableTarget(target) {
    return !!target?.closest?.('input, select, textarea, button, [contenteditable="true"]');
  }

  function pathUrl(path, filename) {
    const normalized = String(path || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    return '/file/' + normalized + '/' + filename;
  }

  async function getJson(path) {
    if (typeof api === 'function') {
      return api(path, { requestKey: 'play-workbench:' + path });
    }
    const response = await fetch(path);
    if (!response.ok) throw new Error(response.statusText || `Request failed (${response.status})`);
    return response.json();
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      if (!url) {
        reject(new Error('Sprite sheet URL is missing.'));
        return;
      }
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Sprite sheet could not be loaded.'));
      image.src = url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
    });
  }

  function indicesFromClip(candidate, count) {
    if (Array.isArray(candidate)) {
      const direct = candidate
        .map(value => typeof value === 'object' ? value.index : value)
        .map(value => Math.floor(safeNumber(value, -1)))
        .filter(value => value >= 0 && value < count);
      if (direct.length) return direct;
    }
    if (!candidate || typeof candidate !== 'object') return [];
    if (Array.isArray(candidate.frames)) return indicesFromClip(candidate.frames, count);
    const start = Math.floor(safeNumber(candidate.start ?? candidate.from ?? candidate.first, -1));
    const end = Math.floor(safeNumber(candidate.end ?? candidate.to ?? candidate.last, -1));
    if (start < 0 || end < start) return [];
    return Array.from({ length: Math.min(count - 1, end) - start + 1 }, (_, index) => start + index);
  }

  function namedClip(meta, clipName, count) {
    const aliases = CLIP_ALIASES[clipName];
    const containers = [meta.clips, meta.animations, meta.tags, meta.frame_tags, meta.extra?.clips];
    for (const container of containers) {
      if (Array.isArray(container)) {
        const match = container.find(item => {
          const name = String(item?.name || item?.id || '').toLowerCase();
          return aliases.some(alias => name.includes(alias));
        });
        const indices = indicesFromClip(match, count);
        if (indices.length) return indices;
      } else if (container && typeof container === 'object') {
        const key = Object.keys(container).find(name => aliases.some(alias => name.toLowerCase().includes(alias)));
        const indices = indicesFromClip(key ? container[key] : null, count);
        if (indices.length) return indices;
      }
    }

    const matchingFrames = (Array.isArray(meta.frames) ? meta.frames : [])
      .map((frame, index) => ({
        index,
        name: String(frame?.name || frame?.source_name || frame?.label || '').toLowerCase(),
      }))
      .filter(frame => aliases.some(alias => frame.name.includes(alias)))
      .map(frame => frame.index);
    return matchingFrames;
  }

  function buildClipMap(meta) {
    const count = Math.max(1, Math.floor(safeNumber(meta?.frame_count, meta?.frames?.length || 1)));
    const all = Array.from({ length: count }, (_, index) => index);
    const idleEnd = Math.max(1, Math.min(count, Math.ceil(count / 4)));
    const attackStart = Math.max(0, Math.floor(count * .62));
    const fallback = {
      idle: all.slice(0, idleEnd),
      walk: all,
      attack: all.slice(attackStart),
    };
    if (!fallback.attack.length) fallback.attack = all.slice(-1);

    Object.keys(fallback).forEach(name => {
      const found = namedClip(meta || {}, name, count);
      if (found.length) fallback[name] = found;
    });

    const declared = String(meta?.animation || '').toLowerCase();
    Object.entries(CLIP_ALIASES).forEach(([name, aliases]) => {
      if (aliases.some(alias => declared.includes(alias))) fallback[name] = all;
    });
    return fallback;
  }

  function outputRowsFromRuntime() {
    const candidates = [];
    if (typeof currentOutputs !== 'undefined' && Array.isArray(currentOutputs)) candidates.push(...currentOutputs);
    if (Array.isArray(window._latestStatus?.outputs)) candidates.push(...window._latestStatus.outputs);
    if (Array.isArray(window.currentOutputs)) candidates.push(...window.currentOutputs);
    const seen = new Set();
    return candidates.filter(item => {
      const path = String(item?.path || '');
      if (!path || seen.has(path)) return false;
      seen.add(path);
      return true;
    });
  }

  async function refreshAssets(options) {
    const settings = options || {};
    const select = element('playWorkbenchSpriteSelect');
    if (!select) return;
    setStatus('Looking for your newest playable sprite…');

    let outputs = outputRowsFromRuntime();
    try {
      const query = typeof projectQuery === 'function' ? projectQuery() : '';
      const data = await getJson('/api/outputs' + query);
      if (Array.isArray(data?.outputs)) outputs = data.outputs;
    } catch (error) {
      // Runtime output state and the bundled demo remain valid offline fallbacks.
    }

    if (!outputs.some(item => item.path === DEMO_PATH)) {
      outputs.push({
        name: 'Built-in demo adventurer',
        path: DEMO_PATH,
        frame_count: 16,
        fps: 12,
        is_demo: true,
      });
    }
    state.outputs = outputs;

    const previous = settings.keepSelection ? (state.path || select.value) : '';
    const saved = settings.keepSelection ? (localStorage.getItem('spriteforgePlayWorkbenchAsset') || '') : '';
    select.replaceChildren();
    outputs.forEach((item, index) => {
      const option = document.createElement('option');
      option.value = item.path || '';
      const isDemo = item.path === DEMO_PATH;
      const prefix = index === 0 && !isDemo ? 'Newest · ' : (isDemo ? 'Demo · ' : '');
      option.textContent = prefix + (item.name || item.path || 'Sprite');
      select.appendChild(option);
    });

    const available = new Set(outputs.map(item => item.path));
    const firstCreation = outputs.find(item => item.path !== DEMO_PATH)?.path || DEMO_PATH;
    const requested = [previous, saved, firstCreation, DEMO_PATH].find(path => path && available.has(path));
    select.value = requested || DEMO_PATH;
    await loadAsset(select.value, { allowDemoFallback: true });
  }

  function updateAssetMeta(bundle, meta, fallback) {
    const source = element('playWorkbenchSource');
    const frames = element('playWorkbenchFrames');
    const cell = element('playWorkbenchCell');
    if (source) source.textContent = fallback ? 'Built-in hero' : (bundle?.name || 'Creation');
    if (frames) frames.textContent = String(meta?.frame_count || meta?.frames?.length || 1);
    if (cell) {
      const width = meta?.frame_width || meta?.cell_width;
      const height = meta?.frame_height || meta?.cell_height;
      cell.textContent = width && height ? `${width}×${height}` : '—';
    }
  }

  function resetHero() {
    state.x = 400;
    state.y = 342;
    state.facing = 1;
  }

  function useSafeFallback(message) {
    state.bundle = null;
    state.meta = { frame_count: 1, fps: 4, frame_width: 24, frame_height: 32 };
    state.sheet = null;
    state.usingFallback = true;
    state.clips = buildClipMap(state.meta);
    activateClip('idle', true);
    updateAssetMeta(null, state.meta, true);
    setStatus(message || 'Using the built-in workbench hero. You can still move and attack.', 'fallback');
    drawScene(performance.now());
  }

  async function loadAsset(path, options) {
    if (!path) {
      useSafeFallback('No sprite was selected, so the built-in workbench hero is ready.');
      return;
    }
    const token = ++state.loadToken;
    const settings = options || {};
    state.path = path;
    state.sheet = null;
    setStatus('Loading sprite sheet and animation metadata…');

    try {
      const listed = state.outputs.find(item => item.path === path) || {};
      let bundle = listed;
      try {
        bundle = { ...listed, ...await getJson('/api/sprite/preview?path=' + encodeURIComponent(path)) };
      } catch (error) {
        bundle = {
          ...listed,
          name: listed.name || path.split(/[\\/]/).pop(),
          path,
          json_url: listed.json_url || pathUrl(path, 'sheet.json'),
          sheet_url: listed.sheet_url || pathUrl(path, 'sheet.png'),
        };
      }
      const meta = await getJson(bundle.json_url || pathUrl(path, 'sheet.json'));
      let sheet = null;
      let imageError = null;
      try {
        sheet = await loadImage(bundle.sheet_url || pathUrl(path, String(meta.image || 'sheet.png')));
      } catch (error) {
        imageError = error;
      }
      if (token !== state.loadToken) return;

      state.bundle = bundle;
      state.meta = meta;
      state.sheet = sheet;
      state.usingFallback = !sheet;
      state.clips = buildClipMap(meta);
      state.frameElapsed = 0;
      state.clipCursor = 0;
      state.attacking = false;
      resetHero();
      activateClip('idle', true);
      updateAssetMeta(bundle, meta, !sheet);
      localStorage.setItem('spriteforgePlayWorkbenchAsset', path);
      const select = element('playWorkbenchSpriteSelect');
      if (select && Array.from(select.options).some(option => option.value === path)) select.value = path;

      if (imageError) {
        setStatus('Metadata loaded, but the sheet image is missing. The built-in hero is standing in safely.', 'fallback');
      } else {
        const source = path === DEMO_PATH ? 'Demo ready' : 'Creation ready';
        setStatus(`${source} · Move with WASD or the arrow keys.`, 'ready');
      }
      drawScene(performance.now());
    } catch (error) {
      if (token !== state.loadToken) return;
      if (settings.allowDemoFallback && path !== DEMO_PATH) {
        const select = element('playWorkbenchSpriteSelect');
        if (select) select.value = DEMO_PATH;
        setStatus('That creation was unavailable. Loading the bundled demo instead…', 'fallback');
        await loadAsset(DEMO_PATH, { allowDemoFallback: false });
        return;
      }
      useSafeFallback('No sprite assets were available, so the built-in workbench hero is ready.');
    }
  }

  function frameRect(index) {
    const meta = state.meta || {};
    const frame = Array.isArray(meta.frames) ? (meta.frames[index] || {}) : {};
    const width = Math.max(1, safeNumber(meta.frame_width ?? meta.cell_width ?? frame.w, 1));
    const height = Math.max(1, safeNumber(meta.frame_height ?? meta.cell_height ?? frame.h, 1));
    const margin = Math.max(0, safeNumber(meta.margin, 0));
    const spacing = Math.max(0, safeNumber(meta.spacing, 0));
    const inferredColumns = state.sheet ? Math.max(1, Math.floor((state.sheet.width - margin * 2 + spacing) / (width + spacing))) : 1;
    const columns = Math.max(1, Math.floor(safeNumber(meta.columns, inferredColumns)));
    return {
      x: safeNumber(frame.x, margin + (index % columns) * (width + spacing)),
      y: safeNumber(frame.y, margin + Math.floor(index / columns) * (height + spacing)),
      width: Math.max(1, safeNumber(frame.w, width)),
      height: Math.max(1, safeNumber(frame.h, height)),
      duration: Math.max(32, safeNumber(frame.duration_ms, 1000 / Math.max(1, safeNumber(meta.fps, 12)))),
    };
  }

  function currentFrame() {
    const frames = state.clips[state.clip] || [0];
    return frames[state.clipCursor % frames.length] ?? 0;
  }

  function updateClipButtons() {
    document.querySelectorAll('[data-workbench-clip]').forEach(button => {
      const active = button.dataset.workbenchClip === state.clip;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    const label = element('playWorkbenchClipLabel');
    if (label) label.textContent = state.clip.charAt(0).toUpperCase() + state.clip.slice(1);
  }

  function activateClip(name, restart) {
    const next = state.clips[name]?.length ? name : 'idle';
    if (next !== state.clip || restart) {
      state.clip = next;
      state.clipCursor = 0;
      state.frameElapsed = 0;
      updateClipButtons();
    }
  }

  function previewClip(name) {
    if (name === 'attack') {
      startAttack();
      return;
    }
    state.attacking = false;
    state.manualClip = name;
    state.manualClipUntil = name === 'walk' ? performance.now() + 1800 : performance.now() + 900;
    activateClip(name, true);
    startLoop();
  }

  function startAttack() {
    if (state.attacking) return;
    state.attacking = true;
    state.manualClip = '';
    state.manualClipUntil = 0;
    activateClip('attack', true);
    startLoop();
  }

  function advanceAnimation(deltaMs) {
    const frames = state.clips[state.clip] || [0];
    if (!frames.length) return;
    state.frameElapsed += deltaMs;
    let duration = frameRect(currentFrame()).duration;
    while (state.frameElapsed >= duration) {
      state.frameElapsed -= duration;
      const next = state.clipCursor + 1;
      if (state.clip === 'attack' && next >= frames.length) {
        state.attacking = false;
        activateClip('idle', true);
        break;
      }
      state.clipCursor = next % frames.length;
      duration = frameRect(currentFrame()).duration;
    }
  }

  function activeGamepad() {
    if (!element('playWorkbenchGamepadToggle')?.checked || typeof navigator.getGamepads !== 'function') return null;
    const pads = Array.from(navigator.getGamepads() || []).filter(Boolean);
    let pad = pads.find(item => item.index === state.gamepadIndex) || pads[0] || null;
    if (pad) state.gamepadIndex = pad.index;
    return pad;
  }

  function movementInput() {
    let horizontal = (state.keys.has('ArrowRight') || state.keys.has('KeyD') ? 1 : 0)
      - (state.keys.has('ArrowLeft') || state.keys.has('KeyA') ? 1 : 0);
    let vertical = (state.keys.has('ArrowDown') || state.keys.has('KeyS') ? 1 : 0)
      - (state.keys.has('ArrowUp') || state.keys.has('KeyW') ? 1 : 0);
    const pad = activeGamepad();
    if (pad) {
      const axisX = Math.abs(pad.axes?.[0] || 0) > .22 ? pad.axes[0] : 0;
      const axisY = Math.abs(pad.axes?.[1] || 0) > .22 ? pad.axes[1] : 0;
      horizontal += axisX + (pad.buttons?.[15]?.pressed ? 1 : 0) - (pad.buttons?.[14]?.pressed ? 1 : 0);
      vertical += axisY + (pad.buttons?.[13]?.pressed ? 1 : 0) - (pad.buttons?.[12]?.pressed ? 1 : 0);
      const attackDown = !!(pad.buttons?.[0]?.pressed || pad.buttons?.[2]?.pressed);
      if (attackDown && !state.gamepadAttackDown) startAttack();
      state.gamepadAttackDown = attackDown;
      setGamepadStatus(`Connected · ${pad.id || 'Gamepad'}`, true);
    } else {
      state.gamepadAttackDown = false;
    }
    const magnitude = Math.hypot(horizontal, vertical);
    if (magnitude > 1) {
      horizontal /= magnitude;
      vertical /= magnitude;
    }
    return { horizontal, vertical };
  }

  function updateHero(deltaSeconds, now) {
    const input = movementInput();
    const moving = Math.abs(input.horizontal) > .05 || Math.abs(input.vertical) > .05;
    if (!state.attacking && moving) {
      state.x = clamp(state.x + input.horizontal * 185 * deltaSeconds, 58, 742);
      state.y = clamp(state.y + input.vertical * 112 * deltaSeconds, 286, 374);
      if (Math.abs(input.horizontal) > .05) state.facing = input.horizontal < 0 ? -1 : 1;
    }

    if (!state.attacking) {
      if (state.manualClip && now < state.manualClipUntil) activateClip(state.manualClip, false);
      else {
        state.manualClip = '';
        activateClip(moving ? 'walk' : 'idle', false);
      }
    }
  }

  function roundedRect(context, x, y, width, height, radius, fill) {
    context.beginPath();
    context.roundRect(x, y, width, height, radius);
    context.fillStyle = fill;
    context.fill();
  }

  function drawTree(context, x, y, scale) {
    context.fillStyle = '#76513b';
    context.fillRect(x - 7 * scale, y - 52 * scale, 14 * scale, 58 * scale);
    context.fillStyle = '#276f62';
    context.beginPath();
    context.arc(x, y - 64 * scale, 30 * scale, 0, Math.PI * 2);
    context.arc(x - 21 * scale, y - 48 * scale, 23 * scale, 0, Math.PI * 2);
    context.arc(x + 22 * scale, y - 48 * scale, 24 * scale, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = '#51a76f';
    context.beginPath();
    context.arc(x - 9 * scale, y - 73 * scale, 14 * scale, 0, Math.PI * 2);
    context.fill();
  }

  function drawDiorama(context, now) {
    const reduced = document.body.classList.contains('pref-reduce-motion') || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const drift = reduced ? 0 : (now / 80) % 900;
    const sky = context.createLinearGradient(0, 0, 0, 300);
    sky.addColorStop(0, '#65cce5');
    sky.addColorStop(1, '#dcf3d2');
    context.fillStyle = sky;
    context.fillRect(0, 0, 800, 450);

    context.fillStyle = '#fff4bd';
    context.beginPath();
    context.arc(680, 80, 37, 0, Math.PI * 2);
    context.fill();

    context.fillStyle = 'rgba(255,255,255,.72)';
    [-120, 245, 690].forEach((base, index) => {
      const x = (base + drift * (.12 + index * .02)) % 940 - 70;
      context.beginPath();
      context.arc(x, 76 + index * 24, 22, 0, Math.PI * 2);
      context.arc(x + 25, 66 + index * 24, 29, 0, Math.PI * 2);
      context.arc(x + 56, 77 + index * 24, 21, 0, Math.PI * 2);
      context.fill();
    });

    context.fillStyle = '#72b887';
    context.beginPath();
    context.moveTo(0, 253);
    context.quadraticCurveTo(132, 126, 282, 249);
    context.quadraticCurveTo(405, 119, 560, 245);
    context.quadraticCurveTo(676, 152, 800, 238);
    context.lineTo(800, 330);
    context.lineTo(0, 330);
    context.closePath();
    context.fill();

    context.fillStyle = '#3f8d6d';
    context.beginPath();
    context.moveTo(0, 267);
    context.quadraticCurveTo(120, 194, 270, 274);
    context.quadraticCurveTo(440, 177, 605, 275);
    context.quadraticCurveTo(705, 212, 800, 268);
    context.lineTo(800, 345);
    context.lineTo(0, 345);
    context.closePath();
    context.fill();

    drawTree(context, 105, 306, 1.2);
    drawTree(context, 726, 298, .95);

    context.fillStyle = '#a5d574';
    context.fillRect(0, 277, 800, 173);
    context.fillStyle = '#75b957';
    for (let y = 290; y < 450; y += 24) {
      for (let x = (y % 48); x < 800; x += 48) context.fillRect(x, y, 22, 5);
    }

    context.fillStyle = '#dec486';
    context.beginPath();
    context.ellipse(400, 376, 268, 54, 0, 0, Math.PI * 2);
    context.fill();
    context.strokeStyle = '#c2a76c';
    context.lineWidth = 3;
    context.stroke();

    // A tiny original forge hut gives the scene its own SpriteForge identity.
    roundedRect(context, 590, 211, 91, 72, 8, '#8d6045');
    context.fillStyle = '#d85d55';
    context.beginPath();
    context.moveTo(578, 220);
    context.lineTo(635, 172);
    context.lineTo(694, 220);
    context.closePath();
    context.fill();
    roundedRect(context, 623, 242, 27, 41, 4, '#493c38');
    context.fillStyle = '#ffd978';
    context.fillRect(598, 232, 16, 15);
    context.fillStyle = '#734a3d';
    context.fillRect(666, 179, 12, 38);

    // Foreground flowers and stepping stones.
    context.fillStyle = '#f7e1b6';
    [[205, 366, 33, 11], [296, 391, 43, 13], [507, 365, 35, 11]].forEach(stone => {
      context.beginPath();
      context.ellipse(stone[0], stone[1], stone[2], stone[3], 0, 0, Math.PI * 2);
      context.fill();
    });
    [[55, 345, '#ff776e'], [156, 402, '#fff079'], [687, 388, '#ff8aa8'], [755, 345, '#fff079']].forEach(flower => {
      context.fillStyle = flower[2];
      context.fillRect(flower[0] - 3, flower[1] - 3, 7, 7);
      context.fillStyle = '#347c51';
      context.fillRect(flower[0], flower[1] + 4, 2, 9);
    });
  }

  function drawFallbackSprite(context, x, y, scale, facing, attacking) {
    context.save();
    context.translate(x, y);
    context.scale(facing * scale, scale);
    const pixel = (px, py, width, height, color) => {
      context.fillStyle = color;
      context.fillRect(px, py, width, height);
    };
    pixel(-8, -28, 16, 7, '#3f3555');
    pixel(-11, -25, 22, 6, '#5d4d78');
    pixel(-8, -20, 16, 11, '#ffd0a3');
    pixel(2, -17, 3, 3, '#26384a');
    pixel(-9, -9, 18, 15, '#36a6a0');
    pixel(-12, -5, 5, 13, '#ffd0a3');
    pixel(7, -5, 5, 13, '#ffd0a3');
    pixel(-8, 6, 7, 11, '#355178');
    pixel(2, 6, 7, 11, '#355178');
    pixel(-10, 17, 9, 4, '#493d4d');
    pixel(2, 17, 9, 4, '#493d4d');
    pixel(-5, -6, 10, 3, '#ffd978');
    if (attacking) {
      pixel(10, -8, 15, 3, '#eff9ff');
      pixel(22, -11, 3, 8, '#eff9ff');
      pixel(8, -9, 4, 6, '#8b5b42');
    }
    context.restore();
  }

  function drawHero(context) {
    const depthScale = .86 + ((state.y - 286) / 88) * .18;
    context.save();
    context.fillStyle = 'rgba(35, 55, 42, .24)';
    context.beginPath();
    context.ellipse(state.x, state.y + 4, 34 * depthScale, 10 * depthScale, 0, 0, Math.PI * 2);
    context.fill();
    context.restore();

    let spriteDrawn = false;
    if (state.sheet && state.meta) {
      const rect = frameRect(currentFrame());
      const sourceX = clamp(rect.x, 0, state.sheet.width);
      const sourceY = clamp(rect.y, 0, state.sheet.height);
      const sourceWidth = Math.min(rect.width, state.sheet.width - sourceX);
      const sourceHeight = Math.min(rect.height, state.sheet.height - sourceY);
      if (sourceWidth > 0 && sourceHeight > 0) {
        const targetHeight = 128 * depthScale;
        const targetWidth = targetHeight * (sourceWidth / sourceHeight);
        context.save();
        context.translate(state.x, state.y);
        context.scale(state.facing, 1);
        context.imageSmoothingEnabled = false;
        try {
          context.drawImage(
            state.sheet,
            sourceX, sourceY, sourceWidth, sourceHeight,
            -targetWidth / 2, -targetHeight, targetWidth, targetHeight,
          );
          spriteDrawn = true;
        } catch (error) {
          spriteDrawn = false;
        }
        context.restore();
      }
    }
    if (!spriteDrawn) {
      drawFallbackSprite(context, state.x, state.y, 4 * depthScale, state.facing, state.clip === 'attack');
    }

    if (state.clip === 'attack' && state.attacking) {
      const frames = state.clips.attack || [0];
      const progress = frames.length > 1 ? state.clipCursor / (frames.length - 1) : .5;
      context.save();
      context.strokeStyle = `rgba(255, 245, 170, ${.45 + Math.sin(progress * Math.PI) * .5})`;
      context.lineWidth = 7;
      context.lineCap = 'round';
      context.beginPath();
      if (state.facing > 0) context.arc(state.x + 5, state.y - 59, 45, -1.05, .85);
      else context.arc(state.x - 5, state.y - 59, 45, Math.PI - .85, Math.PI + 1.05);
      context.stroke();
      context.restore();
    }
  }

  function drawScene(now) {
    const canvas = element('playWorkbenchCanvas');
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    drawDiorama(context, now || 0);
    drawHero(context);
  }

  function frameLoop(now) {
    state.raf = 0;
    if (!workbenchActive()) return;
    const deltaMs = state.lastTick ? clamp(now - state.lastTick, 0, 50) : 16;
    state.lastTick = now;
    state.sceneryTime += deltaMs;
    updateHero(deltaMs / 1000, now);
    advanceAnimation(deltaMs);
    drawScene(now);
    state.raf = requestAnimationFrame(frameLoop);
  }

  function startLoop() {
    if (state.raf || !workbenchActive()) return;
    state.lastTick = 0;
    state.raf = requestAnimationFrame(frameLoop);
  }

  function stopLoop() {
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    state.lastTick = 0;
    state.keys.clear();
  }

  function handleKeyDown(event) {
    if (!workbenchActive() || editableTarget(event.target) || !WORKBENCH_KEYS.has(event.code)) return;
    event.preventDefault();
    if (event.code === 'KeyR') {
      resetHero();
      drawScene(performance.now());
      return;
    }
    if ((event.code === 'Space' || event.code === 'KeyJ' || event.code === 'KeyK') && !event.repeat) {
      startAttack();
    }
    state.keys.add(event.code);
    startLoop();
  }

  function handleKeyUp(event) {
    state.keys.delete(event.code);
  }

  function bindWorkbench() {
    if (state.bound || !element('playWorkbenchCanvas')) return;
    state.bound = true;
    const select = element('playWorkbenchSpriteSelect');
    const canvas = element('playWorkbenchCanvas');
    const gamepadToggle = element('playWorkbenchGamepadToggle');

    select?.addEventListener('change', event => loadAsset(event.target.value, { allowDemoFallback: true }));
    element('playWorkbenchRefreshBtn')?.addEventListener('click', () => refreshAssets({ keepSelection: false }));
    document.querySelectorAll('[data-workbench-clip]').forEach(button => {
      button.addEventListener('click', () => previewClip(button.dataset.workbenchClip));
    });
    canvas?.addEventListener('pointerdown', () => {
      canvas.focus({ preventScroll: true });
      startLoop();
    });
    canvas?.addEventListener('dblclick', resetHero);
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    const gamepadSaved = localStorage.getItem('spriteforgePlayWorkbenchGamepad');
    if (gamepadToggle) gamepadToggle.checked = gamepadSaved !== 'false';
    gamepadToggle?.addEventListener('change', () => {
      localStorage.setItem('spriteforgePlayWorkbenchGamepad', gamepadToggle.checked ? 'true' : 'false');
      if (!gamepadToggle.checked) setGamepadStatus('Gamepad input off', false);
      else setGamepadStatus('Gamepad ready to connect', false);
    });
    window.addEventListener('gamepadconnected', event => {
      state.gamepadIndex = event.gamepad.index;
      if (gamepadToggle?.checked) setGamepadStatus(`Connected · ${event.gamepad.id || 'Gamepad'}`, true);
      startLoop();
    });
    window.addEventListener('gamepaddisconnected', event => {
      if (state.gamepadIndex === event.gamepad.index) state.gamepadIndex = null;
      setGamepadStatus('Gamepad ready to connect', false);
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stopLoop();
      else if (workbenchActive()) startLoop();
    });

    window.SpriteForge?.views?.register('play_workbench', {
      activate: () => {
        if (!state.path) refreshAssets({ keepSelection: true });
        startLoop();
      },
      deactivate: stopLoop,
    });

    useSafeFallback('Preparing your newest creation…');
    refreshAssets({ keepSelection: true });
    if (workbenchActive()) startLoop();
  }

  window.refreshPlayWorkbenchSprites = () => refreshAssets({ keepSelection: true });
  window.viewComponentsLoaded?.then(bindWorkbench);
})();
