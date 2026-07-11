(function () {
  const namespace = window.SpriteForge = window.SpriteForge || {};
  const hooks = new Map();
  const scriptPromises = new Map();

  function register(view, handlers = {}) {
    const current = hooks.get(view) || { activate: [], deactivate: [] };
    if (typeof handlers.activate === 'function') current.activate.push(handlers.activate);
    if (typeof handlers.deactivate === 'function') current.deactivate.push(handlers.deactivate);
    hooks.set(view, current);
  }

  function loadScript(src) {
    if (scriptPromises.has(src)) return scriptPromises.get(src);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.addEventListener('load', resolve, { once: true });
      script.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true });
      document.body.appendChild(script);
    });
    scriptPromises.set(src, promise);
    return promise;
  }

  function registerLazyScript(view, src) {
    register(view, {
      activate: () => loadScript(src).catch(error => console.error(error)),
    });
  }

  async function transition(nextView, previousView) {
    if (previousView && previousView !== nextView) {
      const previousHooks = hooks.get(previousView);
      for (const handler of previousHooks?.deactivate || []) await handler({ view: previousView, nextView });
    }
    const nextHooks = hooks.get(nextView);
    for (const handler of nextHooks?.activate || []) await handler({ view: nextView, previousView });
  }

  namespace.views = { register, registerLazyScript, transition, loadScript };
  registerLazyScript('pixel_studio', 'js/pixel_studio.js');
})();
