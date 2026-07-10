(function () {
  window.onSpriteForgeReady = (callback) => {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  };

  const componentVersions = {
    dashboard: '?v=dashboard-fit-no-window-resize',
    generate: '?v=prompt-autofix',
    quality: '?v=quality-lab-compact',
    training: '?v=sakpix-training-polish',
  };

  const views = [
    'guide', 'dashboard', 'production', 'aaa_studio', 'tasks', 'launchpad', 'generate', 'convert', 'quality',
    'packs', 'animation_player', 'play_workbench', 'compare_player', 'lighting_preview', 'cloud_hub',
    'frame_editor', 'queue', 'release', 'setup', 'cleanup', 'logs', 'history',
    'queues', 'ab_runs', 'library', 'qa_dashboard', 'training', 'lpc', 'pixel_studio',
  ];

  async function loadViewComponent(name) {
    const el = document.getElementById('view-' + name);
    if (!el) return;
    try {
      const res = await fetch('components/' + name + '.html' + (componentVersions[name] || ''));
      if (!res.ok) return;
      const html = await res.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const newEl = doc.querySelector('section.view');
      if (newEl) {
        el.innerHTML = newEl.innerHTML;
      }
    } catch (error) {
      console.error('Error loading view component ' + name, error);
    }
  }

  window.viewComponentsLoaded = new Promise((resolve) => {
    window.onSpriteForgeReady(async () => {
      if (window.location.protocol === 'file:') {
        document.documentElement.classList.add('file-mode');
        resolve();
        return;
      }
      await Promise.all(views.map(loadViewComponent));
      resolve();
    });
  });
})();
